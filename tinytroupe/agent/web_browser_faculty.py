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


# ======================================================================
# Module-level LLM-based content filter
# ======================================================================

import tinytroupe.utils as utils


@utils.llm(enable_json_output_format=False, enable_justification_step=False)
def _generate_page_guide(
    page_content: str,
    guide_instructions: str,
    screenshot_description: str = "",
) -> str:
    """
    You are a **page-orientation assistant** for a web-browsing agent.

    You will receive:
      1. The **raw structured text** of a web page (accessibility tree, cleaned HTML, or visible text).
      2. **Guide instructions** describing the scenario and what interactive elements the agent cares about.
      3. An optional **screenshot description** of the current page state.

    Your job is to produce a **natural-language guide** that helps the agent
    *quickly orient itself* on the page and take the right next action. The guide must:

      - **Describe the page layout** in 2-3 sentences: what sections are visible, what the page is about.
      - **List each key interactive element** mentioned in the guide instructions. For each, provide:
        - A short label (e.g., "Query input textbox")
        - Its current state (visible / off-screen / empty / filled / selected / disabled)
        - A **CSS selector or accessibility name** the agent can use in a `BROWSE_ACTION click` or `BROWSE fill` command
          (e.g., `input[placeholder="Enter your query..."]`, `text=Send`, `role=radio[name="Left is better"]`).
      - **Flag off-screen elements**: if an element from the guide instructions is NOT found in the visible page
        content, note that the agent needs to **scroll down** to reveal it.
      - **Identify scrollable containers**: if the page has sidebars, panels, or list containers that can scroll
        independently of the main page (e.g., a sidebar with its own scrollbar), note their CSS selector so the
        agent can use `scroll_element <selector> down` to scroll them. This is critical for panels like
        "Query set" sidebars where items extend below the visible area.
      - **Include verbatim content** when the guide instructions explicitly ask for specific page content
        (e.g., response text, article bodies, data tables). Reproduce that content **in full** — do not
        summarize or truncate it. The agent may need the complete text to make informed decisions.
      - Use **bullet points** for clarity. Be terse on layout/navigation details — every token counts —
        but reproduce requested content sections in full.
      - Do NOT wrap in code fences.
      - Do NOT make up selectors — only use identifiers you can see in the actual page content.

    Output ONLY the guide text, no preamble.
    """
    parts = [f"## Guide instructions\n\n{guide_instructions}"]
    if screenshot_description:
        parts.append(f"\n## Screenshot description\n\n{screenshot_description}")
    parts.append(f"\n## Raw page content\n\n{page_content}")
    return "\n".join(parts)


@utils.llm(enable_json_output_format=False, enable_justification_step=False)
def _filter_page_content(page_content: str, filter_instructions: str) -> str:
    """
    You are a page-content filter for a web-browsing agent.

    You will receive:
      1. The **raw structured text** of a web page (accessibility tree, cleaned HTML, or visible text).
      2. A set of **filter instructions** describing which sections or regions of the page are relevant.

    Your job is to produce a **filtered version** of the page content that:
      - **KEEPS** every section, element, or text fragment that matches the filter instructions — reproduced **verbatim**, preserving the original formatting, indentation, and structure exactly as-is. Do NOT rephrase, summarize, or alter the kept content in any way.
      - **REMOVES** everything else (ads, navigation chrome, boilerplate, irrelevant data panels, etc.).
      - At every point where content was removed, insert the following marker on its own line so the agent knows something was stripped:

            ⚠️ [CONTENT FILTERED — section removed by content filter to reduce size]

      - Preserve the **relative order** of kept sections exactly as they appear in the original.
      - **Do NOT summarize** the kept sections — reproduce them in full.
      - Do NOT wrap the output in markdown code fences or add any preamble — output only the filtered page text.

    If the filter instructions are ambiguous or you are unsure whether a section matches, **keep it** (err on the side of inclusion).
    """
    # The docstring above is the system prompt; the return value below is the user prompt.
    return (
        f"## Filter instructions\n\n{filter_instructions}\n\n"
        f"## Raw page content to filter\n\n{page_content}"
    )


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
        pause_on_user_help: Whether to block the simulation when the agent
            issues a ``BROWSE_REQUEST_USER_HELP`` action.  When ``True``
            (default), the user is prompted to press Enter before the
            simulation resumes.  When ``False``, a non-blocking
            informational notice is shown instead, and the simulation
            continues automatically.  Set to ``False`` for unattended /
            Jupyter runs.
        wait_strategy: Playwright wait strategy — ``"domcontentloaded"``
            (fast, default), ``"load"``, or ``"networkidle"`` (slow on
            ad-heavy pages).
        action_delay_ms: Milliseconds between consecutive low-level actions.
        max_content_length: Truncate extracted page content to this length.
        use_vision: When ``True`` (default), every browser observation
            includes the screenshot image.  When ``False``, the agent only
            receives the accessibility-tree page content.
        vision_mode: Controls *how* the screenshot is delivered when
            ``use_vision`` is ``True``:

            * ``"described"`` (default) — the screenshot is sent to a
              vision LLM for a textual description **and** included as a
              multimodal image reference.  High-quality observations at
              the cost of an extra LLM call per step.
            * ``"raw"`` — the screenshot is included as a multimodal
              image reference **without** a vision LLM call.  The main
              agent LLM sees both the raw image and the accessibility-
              tree text side by side, keeping cost and latency low.

            Ignored when ``use_vision`` is ``False``.
        display_screenshots: When ``True``, display each browser
            screenshot inline in the notebook/terminal output as it is
            captured.  In Jupyter environments the image is rendered
            inline; in plain terminals the file path is printed instead.
            Defaults to ``False``.
        auto_wait_for_stable: When ``True`` (default), the faculty
            automatically calls ``wait_for_page_stable()`` after every
            state-changing browser action (click, fill, BROWSE, etc.)
            before feeding the observation back to the agent.  This
            ensures the agent always sees the **final, settled** page
            state rather than intermediate loading spinners or streaming
            content.  Disable this for pages that never stabilize (e.g.
            live dashboards with continuous updates).
        auto_wait_timeout: Maximum seconds to wait for the page to
            stabilize when ``auto_wait_for_stable`` is ``True``.
            Defaults to ``180.0`` (3 minutes), which accommodates
            slow API responses such as LLM-powered chat endpoints.
            The wait is non-blocking — if the page hasn't stabilized
            by this timeout the agent still receives the latest
            snapshot and moves on.
        nl_retries: Number of automatic retry attempts when an NL-
            decomposed browser action fails (e.g. selector timeout).
            On each retry the page state is re-captured and the sub-LLM
            is re-called with the failure context so it can try a
            different selector strategy.  Defaults to ``3``.
        content_filter_prompt: Optional natural-language instructions
            that describe which **sections** of the page content should
            be **kept** in the observation sent to the agent.  When set,
            an auxiliary LLM call filters the raw page content before it
            reaches the agent, dramatically reducing prompt size on
            complex pages.  For example::

                content_filter_prompt=(
                    "Keep only: the Query Set sidebar, the query "
                    "input area, the Sydney Reply panes (A and B), "
                    "and the Judgment Questionnaire section."
                )

            Set to ``None`` (default) to disable filtering and pass the
            full content (subject to ``max_content_length`` truncation).
        page_guide_prompt: Optional natural-language instructions that
            describe the **scenario context** and the **key interactive
            elements** the agent should look for on the page.  When set,
            an auxiliary LLM call generates a short, structured
            *page guide* (``BROWSER_PAGE_GUIDE`` stimulus) after each
            browser action, listing the relevant UI elements with their
            CSS selectors or accessibility names.

            When a page guide is active, regular ``BROWSER_OBSERVATION``
            stimuli **omit the full accessibility tree** to save context
            tokens.  The agent can still request the full tree on demand
            via ``BROWSE_ACTION get_content`` or ``BROWSE_ACTION observe``.

            Example::

                page_guide_prompt=(
                    "Describe the SBS evaluation tool layout: "
                    "1) The 'Query set' sidebar with queries and "
                    "'<unset query>' slots. "
                    "2) The query input textbox and Send button. "
                    "3) The Sydney Reply panes (Result A, Result B). "
                    "4) The Judgment Questionnaire radio buttons "
                    "and Submit button."
                )

            Set to ``None`` (default) to disable page guide generation.
            Can be used together with ``content_filter_prompt`` — the
            guide always sees the **full unfiltered** page content.
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
        pause_on_user_help: bool = True,
        action_delay_ms: int = 0,
        max_content_length: int | None = None,
        use_vision: bool = True,
        vision_mode: str = "described",
        display_screenshots: bool = False,
        cdp_url: str | None = None,
        auto_wait_for_stable: bool = True,
        auto_wait_timeout: float = 180.0,
        real_world_side_effect_delay: float = 5.0,
        nl_retries: int = 3,
        content_filter_prompt: str | None = None,
        page_guide_prompt: str | None = None,
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
        self._pause_on_user_help = pause_on_user_help
        self._action_delay_ms = action_delay_ms
        self._max_content_length = max_content_length
        self._use_vision = use_vision
        self._vision_mode = vision_mode
        self._display_screenshots = display_screenshots
        self._cdp_url = cdp_url
        self._auto_wait_for_stable = auto_wait_for_stable
        self._auto_wait_timeout = auto_wait_timeout
        self._nl_retries = nl_retries
        self._content_filter_prompt = content_filter_prompt
        self._page_guide_prompt = page_guide_prompt

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

        # Pending-settle flag: set to True when _auto_settle times out
        # (the page was still changing when we gave up).  On the next
        # process_observations() call we re-check: if the page has now
        # stabilized, we feed a fresh observation so the agent sees the
        # final loaded state.
        self._pending_settle = False
        self._pending_settle_snapshot = ""

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
                nl_retries=self._nl_retries,
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

        Handles two cases:

        1. **User-dirty flag** — the user (experimenter) manipulated the
           browser externally and we need to feed the new state.
        2. **Pending-settle flag** — a previous ``_auto_settle`` timed out
           while the page was still loading.  We re-check here: if the
           page has now stabilized (content differs from the timeout
           snapshot), we feed a fresh observation so the agent sees the
           final loaded state.  This is printed with Rich output so the
           user knows the deferred check happened.
        """
        ctrl = self._get_browser_controller()
        if not ctrl.is_alive():
            self._browser_state_dirty = False
            self._pending_settle = False
            return

        # ── Deferred settle re-check ─────────────────────────────────
        if self._pending_settle:
            from rich.console import Console
            _console = Console()

            try:
                # Use get_page_content() instead of _quick_snapshot()
                # because it's thread-dispatched and won't cause
                # greenlet threading errors in Jupyter.
                current_snapshot = ctrl.get_page_content() or ""
            except Exception:
                current_snapshot = ""

            if current_snapshot and current_snapshot != self._pending_settle_snapshot:
                # Page changed since the timeout — it likely finished
                # loading.  Feed the fresh state.
                _console.print(
                    "  :arrows_counterclockwise: "
                    "[bold bright_cyan]Page updated since last timeout "
                    "\u2014 feeding fresh observation to agent[/]"
                )
                try:
                    self._feed_observation(
                        agent,
                        "Page finished loading (deferred settle check)",
                        {
                            "screenshot": ctrl.screenshot(),
                            "page_content": ctrl.get_page_content(),
                            "metadata": ctrl.get_page_metadata(),
                        },
                    )
                except Exception as exc:
                    logger.warning(f"Deferred settle observation failed: {exc}")
                self._pending_settle = False
                self._pending_settle_snapshot = ""
            else:
                _console.print(
                    "  :hourglass_flowing_sand: "
                    "[dim]Page still unchanged since timeout "
                    "\u2014 agent proceeds with latest state[/]"
                )
                self._pending_settle = False
                self._pending_settle_snapshot = ""

        # ── User-dirty flag ──────────────────────────────────────────
        if not self._browser_state_dirty:
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

        # Auto-wait: after a BROWSE action the page may be loading
        # dynamic content (e.g. API responses, streaming chat).  Wait
        # for the page to stabilize so the agent sees the final state,
        # not an intermediate "loading..." spinner.
        if self._auto_wait_for_stable:
            self._auto_settle(ctrl, result)

        self._feed_observation(agent, f"BROWSE: {content}", result)
        return True

    # ----- BROWSE_ACTION (low-level) -----

    # Commands that modify the page state and should trigger auto-wait.
    # Note: "goto" is excluded because navigation already waits for the
    # page load via BrowserController.goto(); adding auto_settle on top
    # would cause long timeouts on SSO redirects and other multi-step
    # navigation flows.
    _STATE_CHANGING_COMMANDS = frozenset({
        "click", "fill", "select", "press", "submit",
    })

    def _handle_browse_action(self, agent, action: dict) -> bool:
        """Handle a low-level ``BROWSE_ACTION`` action."""
        ctrl = self._get_browser_controller()
        ctrl.ensure_launched()

        raw = (action.get("content", "") or "").strip()
        result = self._dispatch_low_level(ctrl, raw)

        # Auto-wait after state-changing commands so the agent sees the
        # settled page, not a loading state.  Skip for read-only commands
        # (screenshot, scroll, get_content) and for wait_for_stable itself.
        cmd = raw.split(maxsplit=1)[0].lower() if raw else ""
        if self._auto_wait_for_stable and cmd in self._STATE_CHANGING_COMMANDS:
            self._auto_settle(ctrl, result)

        # When the agent explicitly requests page content or a fresh
        # snapshot, always include the full accessibility tree even if a
        # page guide is active (opt-in detail).
        force_full = cmd in ("get_content", "observe")
        self._feed_observation(
            agent, f"BROWSE_ACTION: {raw}", result,
            force_full_content=force_full,
        )
        return True

    # Bare element types that are too generic to be useful as selectors.
    # Using these alone (e.g. "click radio") will match the first element
    # on the page, which is almost never the intended target.
    _GENERIC_SELECTORS = frozenset({
        "radio", "button", "input", "textbox", "checkbox", "select",
        "link", "img", "textarea", "option", "a", "div", "span",
        "label", "form", "table", "li", "ul", "ol", "p", "h1", "h2",
        "h3", "h4", "h5", "h6", "section", "article", "header",
        "footer", "nav", "main",
    })

    @classmethod
    def _reject_underspecified_selector(cls, selector: str, cmd: str) -> dict | None:
        """Return an error dict if *selector* is a bare element type
        (e.g., ``"radio"``, ``"button"``, ``"role=radio"``).
        Otherwise return ``None``.

        This catches a common agent mistake: issuing ``click radio``,
        ``click button``, or ``click role=radio`` instead of a qualified
        selector like ``role=radio[name="Left is better"]`` or
        ``text=Submit``.
        """
        if not selector:
            return {
                "success": False,
                "error": (
                    f"'{cmd}' requires a selector but none was provided. "
                    f"Use BROWSE instead for natural-language element descriptions."
                ),
            }
        stripped = selector.strip().lower()

        # Check bare element type: "radio", "button", etc.
        if stripped in cls._GENERIC_SELECTORS:
            return cls._generic_selector_error(selector, cmd)

        # Check bare role selector: "role=radio", "role=button", etc.
        # These match the first element with that ARIA role — still too
        # generic.  A proper role selector needs a qualifier like
        # role=radio[name="Left is better"].
        if stripped.startswith("role="):
            role_type = stripped[5:]  # everything after "role="
            if role_type in cls._GENERIC_SELECTORS and "[" not in stripped:
                return cls._generic_selector_error(selector, cmd)

        return None

    @staticmethod
    def _generic_selector_error(selector: str, cmd: str) -> dict:
        """Build the error dict for an underspecified selector."""
        # Extract the base type for the hint (strip "role=" prefix if present)
        base = selector.strip()
        if base.lower().startswith("role="):
            base = base[5:]
        return {
            "success": False,
            "error": (
                f"Selector '{selector}' is too generic — it matches the FIRST "
                f"'{base}' on the page, which is almost certainly wrong. "
                f"Use a qualified selector like: "
                f"role={base}[name=\"...\"], "
                f"text=<visible label>, "
                f"{base}:has-text('...'), or "
                f"use BROWSE with a natural-language description instead."
            ),
        }

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
            rejected = self._reject_underspecified_selector(arg, cmd)
            if rejected:
                return rejected
            return ctrl.click(arg)
        elif cmd == "fill":
            # format: fill <selector> <text>
            m = re.match(r"(\S+)\s+(.*)", arg)
            if m:
                rejected = self._reject_underspecified_selector(m.group(1), cmd)
                if rejected:
                    return rejected
                return ctrl.fill(m.group(1), m.group(2))
            return {"success": False, "error": "fill requires <selector> <text>"}
        elif cmd == "select":
            m = re.match(r"(\S+)\s+(.*)", arg)
            if m:
                rejected = self._reject_underspecified_selector(m.group(1), cmd)
                if rejected:
                    return rejected
                return ctrl.select_option(m.group(1), m.group(2))
            return {"success": False, "error": "select requires <selector> <value>"}
        elif cmd == "press":
            return ctrl.press(arg)
        elif cmd == "scroll":
            scroll_parts = arg.split()
            direction = scroll_parts[0] if scroll_parts else "down"
            amount = int(scroll_parts[1]) if len(scroll_parts) > 1 else 300
            return ctrl.scroll(direction, amount)
        elif cmd == "scroll_element":
            # format: scroll_element <selector> <up|down> [amount]
            # The selector may contain spaces (e.g., ".sidebar .list"),
            # so we parse direction and optional amount from the RIGHT.
            if not arg.strip():
                return {"success": False, "error": "scroll_element requires <selector> <up|down> [amount]"}
            tokens = arg.rsplit(maxsplit=1)
            # Try to parse the last token as amount
            se_amount = 300
            remainder = arg
            if len(tokens) == 2:
                try:
                    se_amount = int(tokens[-1])
                    remainder = tokens[0]
                except ValueError:
                    pass  # last token isn't a number, treat whole arg as selector+direction
            # Now parse direction from the right of remainder
            tokens2 = remainder.rsplit(maxsplit=1)
            if len(tokens2) < 2:
                return {"success": False, "error": "scroll_element requires <selector> <up|down> [amount]"}
            se_selector = tokens2[0]
            se_direction = tokens2[1].lower()
            if se_direction not in ("up", "down"):
                return {"success": False, "error": f"scroll_element direction must be 'up' or 'down', got '{se_direction}'"}
            return ctrl.scroll_element(se_selector, se_direction, se_amount)
        elif cmd == "hover":
            rejected = self._reject_underspecified_selector(arg, cmd)
            if rejected:
                return rejected
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
        elif cmd == "observe":
            # Take a fresh snapshot of the page (screenshot + content)
            # without performing any action.  Useful for the agent to
            # actively check the current page state after waiting or
            # to recover from stale observations.
            return {
                "success": True,
                "screenshot": ctrl.screenshot(),
                "page_content": ctrl.get_page_content(),
                "metadata": ctrl.get_page_metadata(),
            }
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
        if self._pause_on_user_help:
            self._user_interaction.pause_for_action(message)
        else:
            self._user_interaction.notify(
                f"[dim](pause_on_user_help is disabled — auto-dismissed)[/dim]\n\n{message}"
            )

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
    # Auto-wait for page stability
    # ------------------------------------------------------------------

    def _auto_settle(self, ctrl, result: dict) -> None:
        """Wait for the page to stop changing after a state-changing action.

        Uses the **adaptive timeout** in ``wait_for_page_stable()``: starts
        with a short 8 s budget and automatically extends while the page
        is actively changing (up to ``auto_wait_timeout``).  Simple UI
        clicks settle in one poll cycle (~2 s); heavy API calls extend as
        needed.

        Progress is reported to the simulation trajectory using Rich-
        styled output so the user can see exactly what's happening.

        Inspired by the psychological concept of *perceptual constancy*:
        humans naturally wait for a scene to settle before interpreting it.
        We give the agent the same courtesy.
        """
        from rich.console import Console
        _console = Console()

        _console.print(
            "  :hourglass_flowing_sand: [dim bright_cyan]Waiting for page to settle…[/]"
        )

        last_reported = [0.0]  # mutable for closure

        def _on_poll(elapsed, changed, content_len):
            """Callback from wait_for_page_stable — print progress."""
            # Only print updates when the page is still changing and
            # at least 5 s have passed since the last report (to avoid
            # flooding the output).
            if changed and elapsed - last_reported[0] >= 5.0:
                _console.print(
                    f"    :arrows_counterclockwise: "
                    f"[dim yellow]Page still changing[/] "
                    f"[dim]({elapsed}s elapsed, {content_len:,} chars)[/]"
                )
                last_reported[0] = elapsed

        try:
            settle_result = ctrl.wait_for_page_stable(
                timeout=self._auto_wait_timeout,
                poll_interval=2.0,
                initial_timeout=8.0,
                on_poll=_on_poll,
            )
        except Exception as exc:
            logger.debug(f"auto_settle: wait_for_page_stable failed: {exc}")
            settle_result = {"success": False, "elapsed": 0}

        elapsed = settle_result.get("elapsed", "?")
        if settle_result.get("success"):
            _console.print(
                f"    :white_check_mark: "
                f"[green]Page settled[/] [dim]({elapsed}s)[/]"
            )
            self._pending_settle = False
        else:
            _console.print(
                f"    :warning: "
                f"[yellow]Settle timeout[/] [dim]({elapsed}s \u2014 "
                f"proceeding with current state, will re-check next turn)[/]"
            )
            # Mark for deferred re-check on next process_observations()
            self._pending_settle = True
            try:
                self._pending_settle_snapshot = ctrl.get_page_content() or ""
            except Exception:
                self._pending_settle_snapshot = ""

        # Refresh the result with the settled page state so
        # _feed_observation picks up the final screenshot + content.
        try:
            result["screenshot"] = ctrl.screenshot()
            result["page_content"] = ctrl.get_page_content()
            result["metadata"] = ctrl.get_page_metadata()
        except Exception as exc:
            logger.debug(f"auto_settle: could not refresh result: {exc}")

    # ------------------------------------------------------------------
    # Content filtering
    # ------------------------------------------------------------------

    def _apply_content_filter(self, page_content: str) -> str:
        """
        Apply an LLM-based content filter to ``page_content`` using the
        configured ``content_filter_prompt``.

        The filter removes sections of the page that are irrelevant to
        the agent's current task, replacing them with clear suppression
        markers.  This can reduce prompt size by 50-90% on complex pages
        while preserving the information the agent actually needs.

        Returns the filtered content, or the original content if the
        filter fails.
        """
        from rich.console import Console
        _console = Console()

        original_len = len(page_content)
        _console.print(
            f"  :scissors: [bold bright_cyan]Content filter[/] — "
            f"filtering {original_len:,} chars…"
        )

        try:
            filtered = _filter_page_content(
                page_content, self._content_filter_prompt
            )
        except Exception as exc:
            logger.warning(f"Content filter LLM call failed: {exc}. "
                           "Using unfiltered content.")
            _console.print(
                f"    :warning: [yellow]Filter failed[/] — "
                f"using full content ({original_len:,} chars)"
            )
            return page_content

        if not filtered or not filtered.strip():
            logger.warning("Content filter returned empty result. "
                           "Using unfiltered content.")
            _console.print(
                f"    :warning: [yellow]Filter returned empty[/] — "
                f"using full content ({original_len:,} chars)"
            )
            return page_content

        filtered_len = len(filtered)
        reduction_pct = ((original_len - filtered_len) / original_len * 100
                         if original_len > 0 else 0)
        _console.print(
            f"    :white_check_mark: [green]Filtered[/] "
            f"{original_len:,} → {filtered_len:,} chars "
            f"([bold green]{reduction_pct:.0f}% reduction[/])"
        )

        return filtered

    # ------------------------------------------------------------------
    # Observation feedback
    # ------------------------------------------------------------------

    def _feed_observation(
        self,
        agent,
        action_summary: str,
        result: dict,
        force_full_content: bool = False,
    ) -> None:
        """
        Feed the browser state back to the agent after an action:

        1. Screenshot → ``agent.see(images=..., description=...)``
        2. (Optional) NL page guide → ``BROWSER_PAGE_GUIDE`` stimulus via
           ``agent._observe()`` — only when ``page_guide_prompt`` is set.
        3. Page content + metadata → ``BROWSER_OBSERVATION`` stimulus via
           ``agent._observe()``.

        When a ``page_guide_prompt`` is configured the
        ``BROWSER_OBSERVATION`` stimulus omits the full accessibility
        tree by default, since the page guide already provides an
        actionable summary.  The agent can request the full tree at
        any time via ``BROWSE_ACTION get_content`` or
        ``BROWSE_ACTION observe`` (which set *force_full_content*).
        """
        ctrl = self._get_browser_controller()

        # --- screenshot ---
        screenshot_path = result.get("screenshot")
        if not screenshot_path:
            screenshot_path = ctrl.screenshot()

        if screenshot_path:
            # Optionally display the screenshot inline (Jupyter) or print
            # the file path (terminal) so the operator can follow along.
            if self._display_screenshots:
                self._display_screenshot(screenshot_path)

            if self._use_vision:
                describe = self._vision_mode != "raw"
                # When vision_mode="described": LLM describes the screenshot
                # image (extra LLM call, higher quality observations).
                # When vision_mode="raw": the screenshot is attached as a
                # multimodal image reference without an LLM vision call —
                # the main agent LLM sees the raw image alongside the
                # accessibility-tree text.
                see_result = agent.see(
                    images=[screenshot_path],
                    description=f"Current browser state after: {action_summary}",
                    describe=describe,
                )
                # When vision_mode="described", the LLM generates a textual
                # description that is stored inside the VISUAL stimulus.
                # We don't extract it here — the page guide LLM call
                # works from the full page content, which is richer.
            else:
                # Vision off: skip the screenshot entirely.  The agent
                # still receives the accessibility-tree page content below.
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
            error_info = (
                f"\n**⚠️ Action FAILED:** {error_msg}\n"
                f"The browser action you requested could not be completed "
                f"even after automatic retries. You should try the action "
                f"again, possibly with a different approach (e.g. scroll "
                f"first to reveal elements, use a different description, "
                f"or use BROWSE_ACTION with an explicit selector).\n"
            )

        # ----- Optional NL page guide -----
        # When page_guide_prompt is configured, generate a concise
        # orientation guide as a separate stimulus.  The guide uses the
        # FULL (unfiltered) page content for maximum accuracy.
        guide_active = bool(self._page_guide_prompt)
        if guide_active and page_content:
            guide_text = self._apply_page_guide(page_content)
            if guide_text:
                agent._observe(
                    stimulus={
                        "type": "BROWSER_PAGE_GUIDE",
                        "content": (
                            f"**Page guide** after: {action_summary}\n\n"
                            f"{guide_text}"
                        ),
                        "source": "",
                    }
                )

        # ----- Optional LLM-based content filter -----
        # When a content_filter_prompt is configured, an auxiliary LLM
        # call strips irrelevant sections from the page content before
        # it reaches the agent.  This can save tens of thousands of
        # tokens per turn on complex pages.
        if page_content and self._content_filter_prompt:
            page_content = self._apply_content_filter(page_content)

        # ----- Decide whether to include full page content -----
        # When a page_guide_prompt is active the guide already provides
        # an actionable summary.  Including the full accessibility tree
        # in every observation would waste context tokens and drown out
        # the guide.  We omit the tree unless:
        #   (a) force_full_content is True (get_content / observe), or
        #   (b) no page_guide_prompt is configured (backward compat).
        include_tree = force_full_content or not guide_active

        if include_tree:
            # Truncate the page content for the agent observation.  The
            # full content (up to max_content_length) is available to
            # the NL decomposition sub-call, but the agent-level LLM
            # only needs a summary to decide its next action.
            _MAX_OBSERVATION_CONTENT = 15_000
            if page_content and len(page_content) > _MAX_OBSERVATION_CONTENT:
                obs_page_content = (
                    page_content[:_MAX_OBSERVATION_CONTENT]
                    + "\n\n... [content truncated — scroll down to see more elements]"
                )
            else:
                obs_page_content = page_content

            page_section = f"**Page content:**\n```\n{obs_page_content}\n```"
        else:
            # Guide-only mode: omit the tree, point agent to get_content.
            page_section = (
                "*(Page content omitted — the **Page guide** above "
                "summarizes the key elements. Use `BROWSE_ACTION get_content` "
                "or `BROWSE_ACTION observe` to see the full page structure "
                "if needed.)*"
            )

        observation_text = (
            f"**Browser observation** after: {action_summary}\n"
            f"{error_info}\n"
            f"**URL:** {metadata.get('url', 'N/A')}\n"
            f"**Title:** {metadata.get('title', 'N/A')}\n"
            f"**Open tabs ({len(tabs)}):** "
            + ", ".join(f"[{t['index']}] {t['title']}" for t in tabs)
            + "\n\n"
            + page_section
        )

        agent._observe(
            stimulus={
                "type": "BROWSER_OBSERVATION",
                "content": observation_text,
                "source": "",
            }
        )

    def _apply_page_guide(
        self, page_content: str, screenshot_description: str = ""
    ) -> str:
        """
        Generate a concise NL page guide using an auxiliary LLM call.

        The guide gives the agent a quick orientation of the page layout
        and lists key interactive elements with actionable selectors,
        based on the configured ``page_guide_prompt``.

        Returns the guide text, or an empty string if generation fails.
        """
        from rich.console import Console
        _console = Console()

        _console.print(
            "  :compass: [bold bright_cyan]Page guide[/] — "
            f"generating orientation guide…"
        )

        try:
            guide = _generate_page_guide(
                page_content,
                self._page_guide_prompt,
                screenshot_description=screenshot_description,
            )
        except Exception as exc:
            logger.warning(f"Page guide LLM call failed: {exc}. "
                           "Skipping guide for this turn.")
            _console.print(
                f"    :warning: [yellow]Guide generation failed[/] — "
                f"agent will see page content only"
            )
            return ""

        if not guide or not guide.strip():
            logger.warning("Page guide returned empty result. "
                           "Skipping guide for this turn.")
            return ""

        guide_len = len(guide)
        _console.print(
            f"    :white_check_mark: [green]Guide ready[/] "
            f"({guide_len:,} chars)"
        )

        return guide.strip()

    @staticmethod
    def _display_screenshot(path: str) -> None:
        """Display a screenshot inline in Jupyter, or print the path in a terminal."""
        try:
            from IPython.display import display, Image as IPImage
            display(IPImage(filename=path, width=600))
        except (ImportError, Exception):
            # Not in Jupyter or display failed — print the path instead.
            logger.info(f"\U0001F4F7 Screenshot: {path}")

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
            "pause_on_user_help": self._pause_on_user_help,
            "action_delay_ms": self._action_delay_ms,
            "max_content_length": self._max_content_length,
            "content_filter_prompt": self._content_filter_prompt,
            "page_guide_prompt": self._page_guide_prompt,
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
            pause_on_user_help=json_dict.get("pause_on_user_help", True),
            action_delay_ms=json_dict.get("action_delay_ms", 0),
            max_content_length=json_dict.get("max_content_length"),
            content_filter_prompt=json_dict.get("content_filter_prompt"),
            page_guide_prompt=json_dict.get("page_guide_prompt"),
        )
