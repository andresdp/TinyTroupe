"""
Web Browser Mental Faculty
============================

Provides :class:`TinyWebBrowserFaculty`, a :class:`TinyMentalFaculty` subclass
that gives TinyTroupe agents the ability to interact with **real** web
pages through a Playwright-driven browser.

The faculty supports two levels of interaction:

* **High-level (``BROWSE``)** — the agent issues a natural-language
  instruction (e.g., *"fill in the contact form with my details"*) and the
  faculty auto-decomposes it into low-level Playwright steps via a sub-LLM
  call.
* **Low-level (``BROWSE_ACTION``)** — the agent directly specifies an atomic
  browser operation such as ``click``, ``fill``, ``goto``, etc.
* **Help request (``BROWSE_REQUEST_USER_HELP``)** — the agent explicitly
  asks the human operator for assistance (e.g., CAPTCHAs, complex logins).

After every browser action the faculty automatically feeds back **both** a
screenshot (via ``agent.see()``) and the page content (via a
``BROWSER_OBSERVATION`` stimulus), giving the agent maximum flexibility to
reason from either modality.

User-facing methods (``user_browse``, ``user_action``, ``user_goto``, …)
bypass the agent's cognitive loop entirely, allowing the human operator to
manipulate the browser directly — the agent observes the updated state on
its next browser action.  This interaction model works particularly well in
Jupyter notebook workflows.

Requires the optional ``playwright`` dependency::

    pip install tinytroupe[browser]
    playwright install msedge
"""

import logging
import os
import re
import textwrap

from tinytroupe.agent import logger
from tinytroupe.agent.mental_faculty import TinyMentalFaculty
from tinytroupe.utils import JsonSerializableRegistry

logger = logging.getLogger("tinytroupe")


class TinyWebBrowserFaculty(TinyMentalFaculty):
    """
    Mental faculty that equips a TinyTroupe agent with a real web browser.

    The browser session persists across simulation steps so that the user
    can watch, intervene, and resume without losing state.

    Args:
        name: Display name of this faculty.
        browser_channel: Playwright channel (``"msedge"``, ``"chrome"``),
            or ``None`` for Playwright's bundled Chromium.  When omitted,
            defaults to ``"msedge"`` or the value in the ``[Browser]``
            config section.  Pass ``None`` explicitly to use bundled
            Chromium (avoids Edge's single-instance lock conflicts).
        headless: ``True`` for invisible browser.  Defaults to ``False``.
        content_strategy: ``"accessibility_tree"``, ``"cleaned_html"``,
            or ``"visible_text"``.
        user_data_dir: Path to a persistent browser profile (for auth).
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        user_interaction: A :class:`UserInteraction` instance.  Defaults to
            :class:`ConsoleUserInteraction`.
        confirm_destructive: Whether to ask the user before destructive
            actions (form submissions, purchases, …).
        wait_strategy: Playwright wait strategy — ``"domcontentloaded"``
            (fast, default), ``"load"``, or ``"networkidle"`` (slow on
            ad-heavy pages).
        action_delay_ms: Milliseconds between consecutive low-level actions.
        max_content_length: Truncate extracted page content to this length.
        use_vision: When ``True`` (default), every browser observation
            includes an LLM vision call to describe the screenshot.
            When ``False``, the agent still receives the accessibility-tree
            page content but skips the expensive vision call — roughly
            halving the time per browsing step.
        requires_faculties: Other faculties this one depends on.
    """

    # Prompt templates are loaded once and cached at class level.
    _actions_template: str | None = None
    _constraints_template: str | None = None

    # Sentinel indicating "no explicit value provided" — lets us distinguish
    # between ``browser_channel=None`` (caller explicitly wants bundled
    # Chromium, i.e. no channel) and the parameter being omitted entirely
    # (fall back to config / default "msedge").
    _CHANNEL_UNSET = object()

    def __init__(
        self,
        name: str = "WebBrowser",
        browser_channel: str | None | object = _CHANNEL_UNSET,
        headless: bool | None = None,
        content_strategy: str | None = None,
        wait_strategy: str | None = None,
        user_data_dir: str | None = None,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        user_interaction=None,
        confirm_destructive: bool = True,
        action_delay_ms: int = 0,
        max_content_length: int | None = None,
        use_vision: bool = True,
        cdp_url: str | None = None,
        real_world_side_effect_delay: float = 5.0,
        requires_faculties: list | None = None,
    ):
        super().__init__(name, requires_faculties,
                         real_world_side_effect_delay=real_world_side_effect_delay)

        # ------- resolve defaults from config -------
        import tinytroupe.utils as utils

        cfg = utils.read_config_file()

        def _cfg_get(key: str, default):
            """Read from [Browser] config section with fallback."""
            try:
                return cfg.get("Browser", key)
            except Exception:
                return default

        # If the caller explicitly passed browser_channel (even None), use
        # that value.  None → Playwright's bundled Chromium (no channel).
        # If omitted (_CHANNEL_UNSET), fall back to config / "msedge".
        if browser_channel is self._CHANNEL_UNSET:
            self._browser_channel = _cfg_get("CHANNEL", "msedge")
        else:
            self._browser_channel = browser_channel
        self._headless = headless if headless is not None else _cfg_get("HEADLESS", "false").lower() == "true"
        self._content_strategy = content_strategy or _cfg_get("CONTENT_STRATEGY", "accessibility_tree")
        self._wait_strategy = wait_strategy or _cfg_get("WAIT_STRATEGY", "domcontentloaded")
        self._user_data_dir = user_data_dir or _cfg_get("USER_DATA_DIR", "") or None
        self._viewport_width = viewport_width or int(_cfg_get("VIEWPORT_WIDTH", "1280"))
        self._viewport_height = viewport_height or int(_cfg_get("VIEWPORT_HEIGHT", "720"))
        self._confirm_destructive = confirm_destructive
        self._action_delay_ms = action_delay_ms
        self._max_content_length = max_content_length
        self._use_vision = use_vision
        self._cdp_url = cdp_url

        # ------- user interaction backend -------
        if user_interaction is None:
            from tinytroupe.ui.user_interaction import ConsoleUserInteraction
            user_interaction = ConsoleUserInteraction()
        self._user_interaction = user_interaction

        # ------- browser controller (lazy-created) -------
        self._browser_controller = None  # created on first use

        # Dirty flag: set to True when the browser state changes via a
        # user_* method (user_goto, user_browse, etc.) so that
        # process_observations() knows to feed the updated state to the
        # agent before the next act() call.
        self._browser_state_dirty = False

    # ------------------------------------------------------------------
    # Browser controller lifecycle
    # ------------------------------------------------------------------

    def _get_browser_controller(self):
        """Return the :class:`BrowserController`, creating it on first use."""
        if self._browser_controller is None:
            from tinytroupe.tools.browser_controller import BrowserController

            self._browser_controller = BrowserController(
                channel=self._browser_channel,
                headless=self._headless,
                viewport_width=self._viewport_width,
                viewport_height=self._viewport_height,
                content_strategy=self._content_strategy,
                wait_strategy=self._wait_strategy,
                user_data_dir=self._user_data_dir,
                user_interaction=self._user_interaction,
                confirm_destructive=self._confirm_destructive,
                action_delay_ms=self._action_delay_ms,
                max_content_length=self._max_content_length,
                cdp_url=self._cdp_url,
            )
        return self._browser_controller

    def ensure_browser(self):
        """Launch the browser if it is not already running."""
        self._get_browser_controller().ensure_launched()
        return self

    def close_browser(self):
        """Close the browser and release resources."""
        if self._browser_controller is not None:
            self._browser_controller.close()

    def is_browser_open(self) -> bool:
        """Return ``True`` if the browser is currently running."""
        return self._browser_controller is not None and self._browser_controller.is_alive()

    # ------------------------------------------------------------------
    # Prompt generation (TinyMentalFaculty interface)
    # ------------------------------------------------------------------

    def actions_definitions_prompt(self) -> str:
        """Return the prompt fragment that describes available browser actions."""
        if TinyWebBrowserFaculty._actions_template is None:
            TinyWebBrowserFaculty._actions_template = self._load_template(
                "web_browser_faculty.actions.mustache"
            )
        return TinyWebBrowserFaculty._actions_template

    def actions_constraints_prompt(self) -> str:
        """Return the prompt fragment describing behavioural constraints."""
        if TinyWebBrowserFaculty._constraints_template is None:
            TinyWebBrowserFaculty._constraints_template = self._load_template(
                "web_browser_faculty.constraints.mustache"
            )
        return TinyWebBrowserFaculty._constraints_template

    @staticmethod
    def _load_template(filename: str) -> str:
        """Load a Mustache template from the ``prompts/`` directory."""
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        path = os.path.join(prompts_dir, filename)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    # ------------------------------------------------------------------
    # Observation delivery (TinyMentalFaculty lifecycle hook)
    # ------------------------------------------------------------------

    def process_observations(self, agent) -> None:
        """Deliver pending browser state to the agent before the next act().

        When the user (experimenter) manipulates the browser externally via
        ``user_goto()``, ``user_browse()``, ``user_action()``, etc., the
        faculty sets an internal dirty flag.  This method checks the flag
        and, if set, snapshots the current browser state and feeds it to
        the agent via ``_feed_observation()``, so the agent sees the
        updated page in its next LLM turn.

        This hook is called automatically by ``TinyPerson.act()`` before
        each turn — no manual ``_feed_observation()`` calls are needed.
        """
        if not self._browser_state_dirty:
            return

        ctrl = self._get_browser_controller()
        if not ctrl.is_alive():
            self._browser_state_dirty = False
            return

        try:
            self._feed_observation(
                agent,
                "Browser state updated (user navigation)",
                {
                    "screenshot": ctrl.screenshot(),
                    "page_content": ctrl.get_page_content(),
                    "metadata": ctrl.get_page_metadata(),
                },
            )
        except Exception as exc:
            logger.warning(f"Could not deliver browser observation: {exc}")
        finally:
            self._browser_state_dirty = False

    # ------------------------------------------------------------------
    # Action processing (TinyMentalFaculty interface)
    # ------------------------------------------------------------------

    def process_action(self, agent, action: dict) -> bool:
        """
        Process an agent action.

        Handled action types:

        * ``BROWSE`` — high-level NL instruction → sub-LLM decomposition.
        * ``BROWSE_ACTION`` — low-level atomic browser command.
        * ``BROWSE_REQUEST_USER_HELP`` — pause for human help.

        Returns ``True`` if the action was handled, ``False`` otherwise.
        """
        action_type = action.get("type", "")

        if action_type == "BROWSE":
            return self._handle_browse(agent, action)
        elif action_type == "BROWSE_ACTION":
            return self._handle_browse_action(agent, action)
        elif action_type == "BROWSE_REQUEST_USER_HELP":
            return self._handle_request_user_help(agent, action)
        else:
            return False

    # ----- BROWSE (high-level NL) -----

    def _handle_browse(self, agent, action: dict) -> bool:
        """Handle a high-level ``BROWSE`` action."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()

        content = action.get("content", "")
        target_url = action.get("target", "")

        # If a target URL is specified, navigate there first.
        if target_url:
            ctrl.goto(target_url)

        result = ctrl.execute_nl_command(content)
        self._feed_observation(agent, f"BROWSE: {content}", result)
        return True

    # ----- BROWSE_ACTION (low-level) -----

    def _handle_browse_action(self, agent, action: dict) -> bool:
        """Handle a low-level ``BROWSE_ACTION`` action."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()

        raw = (action.get("content", "") or "").strip()
        result = self._dispatch_low_level(ctrl, raw)
        self._feed_observation(agent, f"BROWSE_ACTION: {raw}", result)
        return True

    def _dispatch_low_level(self, ctrl, raw: str) -> dict:
        """
        Parse a ``BROWSE_ACTION`` content string and dispatch to the
        appropriate :class:`BrowserController` method.

        Returns a result dict.
        """
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "goto":
            return ctrl.goto(arg)
        elif cmd == "click":
            return ctrl.click(arg)
        elif cmd == "fill":
            # format: fill <selector> <text>
            m = re.match(r"(\S+)\s+(.*)", arg)
            if m:
                return ctrl.fill(m.group(1), m.group(2))
            return {"success": False, "error": "fill requires <selector> <text>"}
        elif cmd == "select":
            m = re.match(r"(\S+)\s+(.*)", arg)
            if m:
                return ctrl.select_option(m.group(1), m.group(2))
            return {"success": False, "error": "select requires <selector> <value>"}
        elif cmd == "press":
            return ctrl.press(arg)
        elif cmd == "scroll":
            scroll_parts = arg.split()
            direction = scroll_parts[0] if scroll_parts else "down"
            amount = int(scroll_parts[1]) if len(scroll_parts) > 1 else 300
            return ctrl.scroll(direction, amount)
        elif cmd == "hover":
            return ctrl.hover(arg)
        elif cmd == "screenshot":
            path = ctrl.screenshot()
            return {"success": path is not None, "screenshot": path}
        elif cmd == "get_content":
            content = ctrl.get_page_content()
            return {"success": True, "page_content": content}
        elif cmd == "new_tab":
            return ctrl.new_tab(arg if arg else None)
        elif cmd == "switch_tab":
            return ctrl.switch_tab(int(arg))
        elif cmd == "close_tab":
            return ctrl.close_tab(int(arg) if arg else None)
        elif cmd == "back":
            return ctrl.go_back()
        elif cmd == "forward":
            return ctrl.go_forward()
        elif cmd == "reload":
            return ctrl.reload()
        elif cmd == "wait_for":
            return ctrl.wait_for(arg)
        elif cmd == "wait_for_stable":
            return ctrl.wait_for_page_stable()
        elif cmd == "upload_file":
            m = re.match(r"(\S+)\s+(.*)", arg)
            if m:
                return ctrl.upload_file(m.group(1), m.group(2))
            return {"success": False, "error": "upload_file requires <selector> <path>"}
        else:
            return {"success": False, "error": f"Unknown BROWSE_ACTION command: {cmd}"}

    # ----- BROWSE_REQUEST_USER_HELP -----

    def _handle_request_user_help(self, agent, action: dict) -> bool:
        """Handle a ``BROWSE_REQUEST_USER_HELP`` action — pause for the user."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()

        message = action.get("content", "The agent needs your help with the browser.")
        self._user_interaction.pause_for_action(message)

        # After the user finishes, capture the new state and feed it back.
        result = {
            "success": True,
            "screenshot": ctrl.screenshot(),
            "page_content": ctrl.get_page_content(),
            "metadata": ctrl.get_page_metadata(),
        }
        self._feed_observation(agent, "User completed manual browser action", result)
        return True

    # ------------------------------------------------------------------
    # Observation feedback
    # ------------------------------------------------------------------

    def _feed_observation(self, agent, action_summary: str, result: dict) -> None:
        """
        Feed the browser state back to the agent after an action:

        1. Screenshot → ``agent.see(images=..., description=...)``
        2. Page content + metadata → ``BROWSER_OBSERVATION`` stimulus via
           ``agent._observe()``.
        """
        ctrl = self._get_browser_controller()

        # --- screenshot ---
        screenshot_path = result.get("screenshot")
        if not screenshot_path:
            screenshot_path = ctrl.screenshot()

        if screenshot_path:
            if self._use_vision:
                # Full vision path: LLM describes the screenshot image.
                # Produces high-quality visual observations but costs an
                # extra LLM call (~5-15 s) per action.
                agent.see(
                    images=[screenshot_path],
                    description=f"Current browser state after: {action_summary}",
                )
            else:
                # Fast path: skip the LLM vision call.  The agent still
                # receives the accessibility-tree page content below,
                # which is sufficient for most browsing tasks.
                agent.see(
                    description=f"Current browser state after: {action_summary}",
                )

        # --- page content + metadata ---
        page_content = result.get("page_content")
        if not page_content:
            try:
                page_content = ctrl.get_page_content()
            except Exception:
                page_content = "(could not extract page content)"

        metadata = result.get("metadata")
        if not metadata:
            try:
                metadata = ctrl.get_page_metadata()
            except Exception:
                metadata = {}

        tabs = ctrl.list_tabs() if ctrl.is_alive() else []

        # Include error info if the action failed, so the agent can adapt
        error_info = ""
        if not result.get("success", True):
            error_msg = result.get("error", "unknown error")
            error_info = f"\n**Action failed:** {error_msg}\n"

        observation_text = (
            f"**Browser observation** after: {action_summary}\n"
            f"{error_info}\n"
            f"**URL:** {metadata.get('url', 'N/A')}\n"
            f"**Title:** {metadata.get('title', 'N/A')}\n"
            f"**Open tabs ({len(tabs)}):** "
            + ", ".join(f"[{t['index']}] {t['title']}" for t in tabs)
            + "\n\n"
            f"**Page content:**\n```\n{page_content}\n```"
        )

        agent._observe(
            stimulus={
                "type": "BROWSER_OBSERVATION",
                "content": observation_text,
                "source": "",
            }
        )

    # ------------------------------------------------------------------
    # User-facing methods (bypass agent cognition)
    # ------------------------------------------------------------------

    def user_browse(self, command: str) -> dict:
        """
        Execute a natural-language browsing command directly.

        This bypasses the agent's cognitive loop — the agent will observe
        the resulting state on its next ``BROWSE`` / ``BROWSE_ACTION``.

        Args:
            command: Natural-language instruction.

        Returns:
            Observation dict with ``screenshot``, ``page_content``, etc.
        """
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        result = ctrl.execute_nl_command(command)
        self._browser_state_dirty = True
        return result

    def user_action(self, action_str: str) -> dict:
        """
        Execute a low-level action string directly.

        The format is the same as ``BROWSE_ACTION`` content, e.g.
        ``"click #submit-btn"`` or ``"goto https://example.com"``.

        Args:
            action_str: Low-level action string.

        Returns:
            Result dict.
        """
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        result = self._dispatch_low_level(ctrl, action_str)
        self._browser_state_dirty = True
        return result

    def user_goto(self, url: str) -> dict:
        """Navigate the browser to ``url``."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        result = ctrl.goto(url)
        self._browser_state_dirty = True
        return result

    def user_screenshot(self) -> str | None:
        """Take a screenshot and return the file path."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        return ctrl.screenshot()

    def user_get_page_content(self) -> str:
        """Return the current page content using the configured strategy."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        return ctrl.get_page_content()

    def user_pause_for_login(self, url: str, message: str = None) -> dict:
        """
        Navigate to ``url`` and pause so the user can log in manually.

        Args:
            url: Login page URL.
            message: Custom instructions.
        """
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        result = ctrl.pause_for_login(url, message)
        self._browser_state_dirty = True
        return result

    def user_inject_credentials(
        self,
        url: str,
        username: str,
        password: str,
        username_selector: str = "input[type=email], input[type=text], input[name=username]",
        password_selector: str = "input[type=password]",
        submit_selector: str = None,
    ) -> dict:
        """
        Navigate to ``url``, fill in credentials, and submit.

        Args:
            url: Login page URL.
            username: Username / email.
            password: Password.
            username_selector: CSS selector for the username field.
            password_selector: CSS selector for the password field.
            submit_selector: CSS selector for the submit button.
        """
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        result = ctrl.inject_credentials(
            url, username, password,
            username_selector=username_selector,
            password_selector=password_selector,
            submit_selector=submit_selector,
        )
        self._browser_state_dirty = True
        return result

    def user_save_session(self, path: str) -> dict:
        """Save cookies and localStorage for later reuse."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        return ctrl.save_storage_state(path)

    def user_load_session(self, path: str) -> dict:
        """Load cookies and localStorage from a file."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()
        return ctrl.load_storage_state(path)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        """
        Serialize the faculty's *configuration* (not the browser state).

        The browser itself cannot be serialized — on deserialization a new
        browser must be launched.
        """
        return {
            "class": self.__class__.__name__,
            "name": self.name,
            "browser_channel": self._browser_channel,
            "headless": self._headless,
            "content_strategy": self._content_strategy,
            "user_data_dir": self._user_data_dir,
            "viewport_width": self._viewport_width,
            "viewport_height": self._viewport_height,
            "confirm_destructive": self._confirm_destructive,
            "action_delay_ms": self._action_delay_ms,
            "max_content_length": self._max_content_length,
        }

    @classmethod
    def from_json(cls, json_dict: dict) -> "TinyWebBrowserFaculty":
        """
        Deserialize from a JSON dict.

        A fresh :class:`ConsoleUserInteraction` is used since the original
        interaction backend is not serializable.  The browser is **not**
        launched — call ``ensure_browser()`` after restoring.
        """
        return cls(
            name=json_dict.get("name", "WebBrowser"),
            browser_channel=json_dict.get("browser_channel"),
            headless=json_dict.get("headless"),
            content_strategy=json_dict.get("content_strategy"),
            user_data_dir=json_dict.get("user_data_dir"),
            viewport_width=json_dict.get("viewport_width"),
            viewport_height=json_dict.get("viewport_height"),
            confirm_destructive=json_dict.get("confirm_destructive", True),
            action_delay_ms=json_dict.get("action_delay_ms", 0),
            max_content_length=json_dict.get("max_content_length"),
        )
