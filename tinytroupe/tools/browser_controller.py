"""
Browser Controller — Playwright wrapper for TinyTroupe
========================================================

Encapsulates all Playwright browser-automation logic in a class that is
completely independent of TinyTroupe's agent system.  It can be used
stand-alone or driven by ``TinyWebBrowserFaculty``.

Key capabilities:

* **Browser selection** — defaults to Microsoft Edge (``msedge`` channel),
  falls back to Chromium.  Configurable via constructor or ``[Browser]``
  config section.
* **Headed by default** — the browser window is visible so the user can
  watch and, if needed, intervene manually.
* **Content extraction** — pluggable strategies: accessibility tree
  (default), cleaned HTML, or visible text only.
* **Multi-tab support** — ``new_tab()``, ``switch_tab()``, ``close_tab()``.
* **Authentication** — persistent user profile, manual-login pause,
  programmatic credential injection, and cookie/storage-state persistence.
* **Safety** — destructive-action detection with user confirmation via
  the ``UserInteraction`` protocol.
* **NL command execution** — decomposes a natural-language instruction
  into low-level Playwright steps using an LLM sub-call.
* **Action logging** — every browser action is recorded with timestamp,
  parameters, and outcome.

Requires the ``playwright`` package (optional dependency, install with
``pip install tinytroupe[browser]``).
"""

import asyncio
import concurrent.futures
import functools
import html as html_module
import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger("tinytroupe")


def _require_playwright():
    """Import playwright at call time and raise a helpful error if missing."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise ImportError(
            "The 'playwright' package is required for browser automation. "
            "Install it with:  pip install tinytroupe[browser]  "
            "Then run:  playwright install msedge"
        )


# ---------------------------------------------------------------------------
# Patterns that hint at destructive / side-effecting interactions
# ---------------------------------------------------------------------------
_DESTRUCTIVE_PATTERNS = re.compile(
    r"\b(submit|delete|remove|purchase|buy|pay|send|confirm|checkout|place.order)\b",
    re.IGNORECASE,
)


class BrowserController:
    """
    Low-level Playwright wrapper.

    Args:
        channel: Playwright browser channel (``"msedge"``, ``"chrome"``,
            ``"chromium"``, …).  Defaults to ``"msedge"``.
        headless: Run the browser without a visible window.  Defaults to
            ``False`` (headed).
        viewport_width: Browser viewport width in pixels.
        viewport_height: Browser viewport height in pixels.
        content_strategy: How to extract page content — one of
            ``"accessibility_tree"``, ``"cleaned_html"``, ``"visible_text"``.
        wait_strategy: Playwright load-state to wait for after each
            navigation or action — ``"networkidle"``, ``"domcontentloaded"``,
            or ``"load"``.
        user_data_dir: Path to a persistent browser profile directory.
            When set, ``launch_persistent_context()`` is used so that
            cookies, sessions, and other profile data are preserved.
        user_interaction: A ``UserInteraction`` instance for confirmations
            and prompts.  Defaults to ``ConsoleUserInteraction`` if ``None``.
        confirm_destructive: Ask the user before executing actions that
            match destructive patterns (form submissions, purchases, etc.).
        action_delay_ms: Milliseconds to wait between consecutive low-level
            actions.  Helps avoid anti-bot detection.  ``0`` by default.
        max_content_length: Maximum character length for page-content
            extraction.  ``None`` means unlimited.
    """

    # Public methods that perform Playwright operations and must run on
    # the dedicated Playwright thread when inside an asyncio event loop
    # (e.g. Jupyter).  ``launch()`` and ``close()`` handle their own
    # dispatch and are NOT in this set.
    _PW_THREAD_METHODS = frozenset({
        "goto", "go_back", "go_forward", "reload",
        "click", "fill", "select_option", "press", "type_text",
        "scroll", "hover", "wait_for_page_stable",
        "upload_file", "wait_for",
        "new_tab", "switch_tab", "close_tab", "list_tabs",
        "switch_to_frame", "switch_to_main_frame",
        "get_page_content", "get_accessibility_tree", "get_cleaned_html",
        "get_visible_text", "get_page_metadata",
        "screenshot", "_quick_snapshot",
        "pause_for_login", "inject_credentials",
        "save_storage_state", "load_storage_state",
        "execute_nl_command",
    })

    def __getattribute__(self, name):
        """
        Transparent thread dispatch for Playwright operations.

        When ``BrowserController`` is launched inside an asyncio event loop
        (e.g. a Jupyter notebook), Playwright's sync API cannot run on the
        event-loop thread.  ``launch()`` detects this and creates a single-
        thread ``ThreadPoolExecutor``.  This ``__getattribute__`` override
        transparently dispatches every public Playwright method to that
        dedicated thread, while allowing reentrant (internal) calls —
        methods that are *already* on the Playwright thread call through
        directly, avoiding deadlocks.
        """
        attr = super().__getattribute__(name)
        if name in BrowserController._PW_THREAD_METHODS and callable(attr):
            try:
                executor = super().__getattribute__('_pw_executor')
                pw_thread = super().__getattribute__('_pw_thread')
            except AttributeError:
                return attr
            if executor is not None and threading.current_thread() is not pw_thread:
                @functools.wraps(attr)
                def _dispatch(*args, **kwargs):
                    return executor.submit(attr, *args, **kwargs).result()
                return _dispatch
        return attr

    def __init__(
        self,
        channel: str = "msedge",
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        content_strategy: str = "accessibility_tree",
        wait_strategy: str = "domcontentloaded",
        user_data_dir: Optional[str] = None,
        user_interaction=None,
        confirm_destructive: bool = True,
        action_delay_ms: int = 0,
        max_content_length: Optional[int] = None,
        cdp_url: Optional[str] = None,
    ):
        self._channel = channel
        self._headless = headless
        self._cdp_url = cdp_url
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._content_strategy = content_strategy
        self._wait_strategy = wait_strategy
        self._user_data_dir = user_data_dir
        self._confirm_destructive = confirm_destructive
        self._action_delay_ms = action_delay_ms
        self._max_content_length = max_content_length

        # User interaction backend
        if user_interaction is None:
            from tinytroupe.ui.user_interaction import ConsoleUserInteraction
            user_interaction = ConsoleUserInteraction()
        self._user_interaction = user_interaction

        # Playwright objects — populated by launch()
        self._playwright = None
        self._browser = None
        self._context = None
        self._pages: list = []          # managed page list
        self._active_page_index: int = 0

        # Action log
        self._action_log: list[dict[str, Any]] = []

        # Thread-dispatch for Jupyter / asyncio compatibility.
        # When ``launch()`` detects a running asyncio event loop, it creates
        # a single-thread executor so that all Playwright calls happen on
        # one dedicated (non-asyncio) thread.  In normal (non-Jupyter) use
        # these remain ``None`` and every call runs on the caller's thread.
        self._pw_executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._pw_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def launch(self) -> "BrowserController":
        """
        Launch the browser.  Uses ``launch_persistent_context()`` when
        ``user_data_dir`` is set, otherwise ``launch()`` + a new context.

        When called from inside an asyncio event loop (e.g. a Jupyter
        notebook kernel), Playwright's sync API cannot start on the
        event-loop thread.  In that case a single-thread
        ``ThreadPoolExecutor`` is created and the launch (and all
        subsequent Playwright operations — see ``__getattribute__``)
        is dispatched to that dedicated thread.

        Returns:
            ``self``, for method chaining.
        """
        if self.is_alive():
            logger.debug("Browser already alive — skipping launch.")
            return self

        # Detect whether we are inside a running asyncio event loop
        # (e.g. Jupyter) and, if so, create a dedicated thread for
        # Playwright so that its sync API does not conflict.
        if self._pw_executor is None:
            try:
                asyncio.get_running_loop()
                # We're in an asyncio loop — spin up a dedicated thread.
                self._pw_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="playwright",
                )
                logger.info(
                    "Detected running asyncio event loop (Jupyter?) — "
                    "Playwright will use a dedicated background thread."
                )
            except RuntimeError:
                pass  # No running loop — normal (non-Jupyter) mode.

        if self._pw_executor is not None:
            return self._pw_executor.submit(self._launch_impl).result()
        return self._launch_impl()

    def _launch_impl(self) -> "BrowserController":
        """Internal: perform the actual Playwright launch on the current thread."""
        # Record which thread owns Playwright so that __getattribute__
        # can detect reentrant (internal) calls and avoid deadlocks.
        self._pw_thread = threading.current_thread()

        # On Windows, Jupyter's ipykernel sets WindowsSelectorEventLoopPolicy
        # globally.  SelectorEventLoop does not support subprocess creation,
        # which Playwright needs to spawn its browser-server process.  We
        # switch to ProactorEventLoop on this dedicated thread so that
        # ``sync_playwright().start()`` gets a capable event loop.
        import sys
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        sync_playwright = _require_playwright()
        self._playwright = sync_playwright().start()

        viewport = {"width": self._viewport_width, "height": self._viewport_height}

        if self._cdp_url:
            # Connect to an already-running browser via Chrome DevTools
            # Protocol over TCP.  This is used when the browser must be
            # launched externally (e.g. Edge launched via subprocess to
            # bypass Jupyter's event-loop pipe issues, or to preserve
            # installed extensions and conditional-access compliance).
            self._browser = self._playwright.chromium.connect_over_cdp(
                self._cdp_url,
                timeout=60_000,  # 60s — generous for slow Edge+SSO startups
            )
            self._context = self._browser.contexts[0]
            self._apply_stealth()
            self._pages = list(self._context.pages) or [self._context.new_page()]
            # Make the Playwright-controlled page the visually focused tab
            # so the user sees the same page Playwright is operating on.
            if self._pages:
                try:
                    self._pages[self._active_page_index].bring_to_front()
                except Exception:
                    pass  # best-effort — may fail if the page is not ready
        elif self._user_data_dir:
            # Persistent context inherits cookies, sessions, extensions, etc.
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self._user_data_dir,
                channel=self._channel,
                headless=self._headless,
                viewport=viewport,
            )
            self._apply_stealth()
            # A persistent context always has at least one page.
            self._pages = list(self._context.pages) or [self._context.new_page()]
        else:
            try:
                self._browser = self._playwright.chromium.launch(
                    channel=self._channel,
                    headless=self._headless,
                )
            except Exception as exc:
                # If the requested channel (e.g. msedge) is not installed, fall
                # back to plain Chromium.
                logger.warning(
                    f"Could not launch browser with channel '{self._channel}': {exc}. "
                    "Falling back to plain Chromium."
                )
                self._browser = self._playwright.chromium.launch(
                    headless=self._headless,
                )

            self._context = self._browser.new_context(viewport=viewport)
            self._apply_stealth()
            page = self._context.new_page()
            self._pages = [page]

        self._active_page_index = 0
        self._log_action("launch", {}, True)
        return self

    def ensure_launched(self) -> "BrowserController":
        """Launch the browser if it is not already running."""
        if not self.is_alive():
            self.launch()
        return self

    def _apply_stealth(self) -> None:
        """Remove common automation-detection signals from the browser.

        Modern websites — especially search engines — check
        ``navigator.webdriver`` to detect automated browsers and may
        respond with CAPTCHAs or outright blocks.  Overriding this
        property makes the browser appear more like a regular user
        session, which is essential for agents that need to browse
        real websites autonomously.

        Note: ``add_init_script`` is not supported on contexts obtained
        via ``connect_over_cdp()``.  In that case we silently skip
        stealth setup — CDP-connected browsers are real user browsers
        and don't have the ``navigator.webdriver`` flag anyway.
        """
        if self._context is not None:
            try:
                self._context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', "
                    "{get: () => undefined})"
                )
            except Exception:
                # CDP-connected contexts don't support add_init_script.
                # This is fine — real browsers don't set navigator.webdriver.
                pass

    def close(self) -> None:
        """Close the browser and release all Playwright resources.

        If a dedicated Playwright thread was created (Jupyter mode),
        the close operations are dispatched to that thread and then
        the thread pool is shut down.
        """
        if self._pw_executor is not None:
            try:
                self._pw_executor.submit(self._close_impl).result()
            finally:
                self._pw_executor.shutdown(wait=True)
                self._pw_executor = None
                self._pw_thread = None
        else:
            self._close_impl()

    def _close_impl(self) -> None:
        """Internal: perform the actual Playwright teardown."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.debug(f"Error during browser close: {exc}")
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._pages = []
            self._active_page_index = 0
            self._log_action("close", {}, True)

    def is_alive(self) -> bool:
        """Return ``True`` if the browser is running and usable."""
        return self._context is not None and len(self._pages) > 0

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _page(self):
        """The currently active page (tab)."""
        if not self._pages:
            raise RuntimeError("No browser page available. Call launch() first.")
        return self._pages[self._active_page_index]

    def _wait_for_stable(self, timeout: int = 2_000) -> None:
        """Wait until the page reaches the configured load state.

        The timeout is intentionally short (2 s default) so that
        ad-heavy pages (which may never reach ``networkidle``) do not
        cause unnecessary delays.  The page DOM is almost always ready
        well before this timeout fires.
        """
        try:
            if self._page.is_closed():
                logger.debug("Page is closed — skipping wait.")
                return
            self._page.wait_for_load_state(self._wait_strategy, timeout=timeout)
        except Exception:
            # Timeout is not fatal — we still continue with whatever state we have.
            logger.debug(f"Wait for '{self._wait_strategy}' timed out — continuing.")

    def _delay(self) -> None:
        if self._action_delay_ms > 0:
            time.sleep(self._action_delay_ms / 1000.0)

    def _log_action(self, action: str, params: dict, success: bool, error: str = None) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "params": params,
            "success": success,
        }
        if error:
            entry["error"] = error
        self._action_log.append(entry)

    def _truncate(self, text: str) -> str:
        """Truncate ``text`` to ``max_content_length`` if configured."""
        if self._max_content_length and len(text) > self._max_content_length:
            return text[: self._max_content_length] + "\n\n... [content truncated]"
        return text

    def _check_destructive(self, description: str) -> bool:
        """
        If ``confirm_destructive`` is enabled and the action description
        matches a destructive pattern, ask the user for confirmation.

        Returns ``True`` if the action should proceed, ``False`` to abort.
        """
        if not self._confirm_destructive:
            return True
        if _DESTRUCTIVE_PATTERNS.search(description):
            return self._user_interaction.confirm(
                f"Potentially destructive action detected: {description}. Proceed?"
            )
        return True

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def goto(self, url: str) -> dict:
        """Navigate the active tab to ``url``."""
        self.ensure_launched()
        try:
            try:
                self._page.goto(url, wait_until=self._wait_strategy, timeout=10_000)
            except Exception:
                if self._wait_strategy in ("networkidle",):
                    # Busy pages (search engines, social media, ad-heavy
                    # sites) continuously make background requests for
                    # analytics, ads, etc. and may never reach
                    # ``networkidle``.  By this point the page has
                    # already navigated — the DOM and ``load`` event
                    # have almost certainly fired, so we simply
                    # proceed.  Calling ``wait_for_load_state`` as a
                    # fallback is intentionally avoided because it can
                    # hang if the underlying browser page was
                    # disconnected (a known Playwright edge-case).
                    logger.info(
                        f"Wait strategy '{self._wait_strategy}' timed "
                        f"out for {url}; proceeding (page likely loaded)."
                    )
                else:
                    raise
            self._wait_for_stable()
            self._delay()
            self._log_action("goto", {"url": url}, True)
            return {"success": True, "url": self._page.url, "title": self._page.title()}
        except Exception as exc:
            self._log_action("goto", {"url": url}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def go_back(self) -> dict:
        """Navigate back in history."""
        self.ensure_launched()
        try:
            self._page.go_back(wait_until=self._wait_strategy, timeout=5_000)
            self._wait_for_stable()
            self._delay()
            self._log_action("go_back", {}, True)
            return {"success": True, "url": self._page.url}
        except Exception as exc:
            self._log_action("go_back", {}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def go_forward(self) -> dict:
        """Navigate forward in history."""
        self.ensure_launched()
        try:
            self._page.go_forward(wait_until=self._wait_strategy, timeout=15_000)
            self._wait_for_stable()
            self._delay()
            self._log_action("go_forward", {}, True)
            return {"success": True, "url": self._page.url}
        except Exception as exc:
            self._log_action("go_forward", {}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def reload(self) -> dict:
        """Reload the current page."""
        self.ensure_launched()
        try:
            self._page.reload(wait_until=self._wait_strategy, timeout=15_000)
            self._wait_for_stable()
            self._delay()
            self._log_action("reload", {}, True)
            return {"success": True, "url": self._page.url}
        except Exception as exc:
            self._log_action("reload", {}, False, str(exc))
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_selector(selector: str) -> list[str]:
        """
        Return a list of candidate selectors to try, starting with the
        original and including common LLM-generated variations.

        LLMs frequently produce invalid or overly specific selectors.
        This helper generates sensible fallbacks so clicks succeed on
        the first attempt more often.
        """
        import re as _re

        candidates = [selector]

        # link:has-text('…') → a:has-text('…')
        if selector.startswith("link:") or selector.startswith("link["):
            candidates.append("a:" + selector[5:] if ":" in selector[4:] else "a" + selector[4:])

        # Extract quoted text for generic text-match fallback
        m = _re.search(r"""has-text\(\s*['"](.+?)['"]\s*\)""", selector)
        if m:
            text = m.group(1)
            candidates.append(f"a:has-text('{text}')")
            candidates.append(f"text='{text}'")
            candidates.append(f"text={text}")

            # Strip leading number prefixes like "8. " or "12. " that
            # the LLM often copies from the visual list numbering but
            # which may not be part of the element's accessible text.
            stripped = _re.sub(r"^\d+\.\s*", "", text)
            if stripped != text:
                tag_prefix = selector.split(":has-text(")[0] if ":has-text(" in selector else ""
                if tag_prefix:
                    candidates.append(f"{tag_prefix}:has-text('{stripped}')")
                candidates.append(f"text='{stripped}'")
                candidates.append(f"text={stripped}")

        # nth-of-type / nth-child are fragile — if the selector also
        # contains a tag name, try a generic :nth-child variant and
        # also try without the positional pseudo-class.
        if ":nth-of-type(" in selector or ":nth-child(" in selector:
            base = _re.sub(r":nth-(of-type|child)\(\d+\)", "", selector).strip()
            if base:
                candidates.append(base)  # try without positional

        # If the selector is a bare tag:nth-of-type (e.g. listitem:nth-of-type(6)),
        # try the Playwright :nth-match pseudo-class and text= approaches.
        m_nth = _re.match(r"(\w+):nth-(?:of-type|child)\((\d+)\)", selector)
        if m_nth:
            tag, idx = m_nth.group(1), m_nth.group(2)
            candidates.append(f":nth-match({tag}, {idx})")

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    def click(self, selector: str) -> dict:
        """
        Click an element matching ``selector``.

        If the literal selector fails, the method tries normalized
        alternatives (see :meth:`_normalize_selector`) before giving up.
        This compensates for common LLM-generated selector mistakes such
        as ``link:has-text(...)`` instead of ``a:has-text(...)``.
        """
        self.ensure_launched()
        if not self._check_destructive(f"click {selector}"):
            self._log_action("click", {"selector": selector}, False, "User declined")
            return {"success": False, "error": "Action declined by user."}

        candidates = self._normalize_selector(selector)
        last_error = ""
        for candidate in candidates:
            try:
                self._page.click(candidate, timeout=10_000)
                self._wait_for_stable()
                self._delay()
                if candidate != selector:
                    logger.info(
                        f"click: original selector '{selector}' failed; "
                        f"succeeded with '{candidate}'"
                    )
                self._log_action("click", {"selector": candidate}, True)
                return {"success": True}
            except Exception as exc:
                last_error = str(exc)
                logger.debug(f"click: selector '{candidate}' failed: {last_error}")

        self._log_action("click", {"selector": selector}, False, last_error)
        return {"success": False, "error": last_error}

    def fill(self, selector: str, text: str) -> dict:
        """Clear and fill an input element with ``text``.

        Uses keyboard typing as the **primary** strategy: click to focus,
        Ctrl+A to select existing content, then ``keyboard.type()`` which
        fires real ``keydown``/``keypress``/``input``/``keyup`` events.
        This is critical for React/SPA controlled inputs — Playwright's
        native ``page.fill()`` sets the DOM value directly, but React
        immediately overwrites it from its internal state on the next
        render cycle, so the value silently disappears.  Keyboard events,
        on the other hand, travel through React's synthetic event system
        and correctly update the component state.

        Falls back to ``page.fill()`` only if the keyboard approach fails
        (e.g. because the selector doesn't match a clickable element).
        """
        self.ensure_launched()

        # ── Primary: keyboard approach (React-compatible) ────────────
        try:
            logger.debug(f"fill: keyboard approach — clicking '{selector}'")
            self._page.click(selector, timeout=5_000)
            time.sleep(0.3)  # let React process focus events / re-render
            self._page.keyboard.press("Control+a")
            time.sleep(0.1)
            logger.debug(f"fill: typing {len(text)} chars into '{selector}'")
            self._page.keyboard.type(text, delay=15)
            self._delay()
            self._log_action("fill", {"selector": selector, "text": text}, True)
            return {"success": True}
        except Exception as kbd_exc:
            logger.debug(
                f"fill: keyboard approach failed for '{selector}': {kbd_exc}. "
                "Trying page.fill() fallback."
            )

        # ── Fallback: Playwright native fill ─────────────────────────
        try:
            self._page.fill(selector, text, timeout=10_000)
            self._delay()
            self._log_action("fill", {"selector": selector, "text": text}, True,
                             "used page.fill() fallback")
            return {"success": True}
        except Exception as exc:
            self._log_action("fill", {"selector": selector, "text": text}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def select_option(self, selector: str, value: str) -> dict:
        """Select a ``<select>`` option by value."""
        self.ensure_launched()
        try:
            self._page.select_option(selector, value, timeout=10_000)
            self._delay()
            self._log_action("select_option", {"selector": selector, "value": value}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("select_option", {"selector": selector, "value": value}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def press(self, key: str) -> dict:
        """Press a keyboard key (e.g. ``"Enter"``, ``"Tab"``, ``"Escape"``)."""
        self.ensure_launched()
        try:
            self._page.keyboard.press(key)
            self._wait_for_stable()
            self._delay()
            self._log_action("press", {"key": key}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("press", {"key": key}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def type_text(self, text: str, delay: int = 50) -> dict:
        """Type text character-by-character via the keyboard.

        Unlike :meth:`fill`, this works on ``contenteditable`` elements,
        rich-text editors, and chat inputs that don't expose a standard
        ``<input>`` or ``<textarea>`` interface.  It simulates real
        keystroke events (``keydown`` → ``keypress`` → ``keyup``).

        Args:
            text: The text to type.
            delay: Milliseconds between keystrokes (default 50).
        """
        self.ensure_launched()
        try:
            self._page.keyboard.type(text, delay=delay)
            self._delay()
            self._log_action("type_text", {"text": text[:100]}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("type_text", {"text": text[:100]}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def scroll(self, direction: str = "down", amount: int = 300) -> dict:
        """
        Scroll the page.

        Args:
            direction: ``"up"`` or ``"down"``.
            amount: Pixels to scroll.
        """
        self.ensure_launched()
        delta = amount if direction == "down" else -amount
        try:
            self._page.mouse.wheel(0, delta)
            self._wait_for_stable(timeout=3_000)
            self._delay()
            self._log_action("scroll", {"direction": direction, "amount": amount}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("scroll", {"direction": direction, "amount": amount}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def wait_for_page_stable(
        self,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        initial_timeout: float = 8.0,
        minimum_settle_time: float = 4.0,
        stable_checks: int = 2,
        on_poll=None,
    ) -> dict:
        """Wait until the page content stops changing, with adaptive timeout.

        Uses an **adaptive timeout** strategy instead of a fixed budget:

        * Waits at least ``minimum_settle_time`` seconds before declaring
          the page stable, giving async operations time to start their
          DOM updates.
        * Requires ``stable_checks`` consecutive identical snapshots
          (default 2) before declaring stable.
        * If the page **changed** since the last poll, the soft deadline
          is extended by ``2 × poll_interval`` — the page is clearly
          still loading, so we keep waiting.
        * Never exceeds the hard ``timeout`` cap.

        This means a sidebar click that settles in ~1 s finishes after
        the minimum settle time + 2 stable polls (~8 s).  A "Send" that
        triggers a 60 s API call extends automatically and finishes as
        soon as the response stabilises.

        Args:
            timeout: Hard upper-bound in seconds (never exceeded).
            poll_interval: Seconds between text-snapshot polls.
            initial_timeout: Starting soft-deadline budget in seconds.
                Extended automatically while the page is actively
                changing.
            minimum_settle_time: Seconds to wait before the page can be
                declared stable.  Prevents premature "settled" when an
                async API call hasn't started updating the DOM yet.
            stable_checks: Number of consecutive identical snapshots
                required to declare the page stable (default 2).
            on_poll: Optional callback ``f(elapsed, changed, snapshot_len)``
                called after each poll for progress reporting.

        Returns:
            Result dict with ``success``, ``elapsed``, and
            ``content_length``.
        """
        self.ensure_launched()

        # Suppress noisy greenlet threading errors from Playwright's sync
        # API callbacks in Jupyter.  These are non-fatal (stale callbacks
        # firing on the wrong thread) but clutter the output.
        import logging as _logging
        _asyncio_logger = _logging.getLogger("asyncio")
        _prev_level = _asyncio_logger.level
        _asyncio_logger.setLevel(_logging.CRITICAL)

        start = time.time()
        hard_deadline = start + timeout
        soft_deadline = start + initial_timeout
        min_settle_deadline = start + minimum_settle_time

        prev_snapshot = self._quick_snapshot()
        prev_len = len(prev_snapshot)
        consecutive_stable = 0

        while True:
            time.sleep(poll_interval)
            now = time.time()
            elapsed = round(now - start, 1)

            curr_snapshot = self._quick_snapshot()
            curr_len = len(curr_snapshot)
            page_changed = (curr_snapshot != prev_snapshot)

            # Report progress if a callback is provided.
            if on_poll:
                try:
                    on_poll(elapsed, page_changed, curr_len)
                except Exception:
                    pass

            if not page_changed and prev_len > 0:
                consecutive_stable += 1
                # Only declare stable if we've passed the minimum settle
                # time AND seen enough consecutive identical snapshots.
                if (consecutive_stable >= stable_checks
                        and now >= min_settle_deadline):
                    self._log_action(
                        "wait_for_page_stable",
                        {"elapsed": elapsed, "content_length": curr_len,
                         "adaptive": True},
                        True,
                    )
                    _asyncio_logger.setLevel(_prev_level)
                    return {
                        "success": True,
                        "elapsed": elapsed,
                        "content_length": curr_len,
                    }
            else:
                consecutive_stable = 0

            # Page is still changing — extend the soft deadline
            # (but never past the hard cap).
            if page_changed:
                soft_deadline = min(
                    now + poll_interval * 2, hard_deadline
                )

            prev_snapshot = curr_snapshot
            prev_len = curr_len

            # Check deadlines.
            if now >= hard_deadline or now >= soft_deadline:
                self._log_action(
                    "wait_for_page_stable",
                    {"elapsed": elapsed, "content_length": curr_len,
                     "adaptive": True},
                    False,
                    "adaptive timeout",
                )
                _asyncio_logger.setLevel(_prev_level)
                return {
                    "success": False,
                    "elapsed": elapsed,
                    "content_length": curr_len,
                    "error": f"Page did not stabilize within {elapsed}s",
                }

    def _quick_snapshot(self) -> str:
        """Return a fast text fingerprint of the current page state.

        Uses ``document.body.innerText`` (visible text only) rather than
        the full accessibility tree or cleaned HTML, for speed (~5 ms
        vs ~200 ms).  This makes polling cheap enough for 2 s intervals.

        Suppresses greenlet threading errors that can occur in Jupyter
        when Playwright's sync API callbacks fire on the wrong thread.
        """
        try:
            if self._page.is_closed():
                return ""
            return self._page.evaluate("() => document.body.innerText") or ""
        except Exception:
            return ""

    def hover(self, selector: str) -> dict:
        """Hover over an element."""
        self.ensure_launched()
        try:
            self._page.hover(selector, timeout=10_000)
            self._delay()
            self._log_action("hover", {"selector": selector}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("hover", {"selector": selector}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def upload_file(self, selector: str, path: str) -> dict:
        """Upload a file to a file-input element."""
        self.ensure_launched()
        try:
            self._page.set_input_files(selector, path, timeout=10_000)
            self._delay()
            self._log_action("upload_file", {"selector": selector, "path": path}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("upload_file", {"selector": selector, "path": path}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def wait_for(self, selector: str, timeout: int = 10_000) -> dict:
        """Wait for an element to appear on the page."""
        self.ensure_launched()
        try:
            self._page.wait_for_selector(selector, timeout=timeout)
            self._log_action("wait_for", {"selector": selector}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("wait_for", {"selector": selector}, False, str(exc))
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def new_tab(self, url: str = None) -> dict:
        """Open a new tab, optionally navigating to ``url``."""
        self.ensure_launched()
        try:
            page = self._context.new_page()
            self._pages.append(page)
            self._active_page_index = len(self._pages) - 1
            if url:
                page.goto(url, wait_until=self._wait_strategy, timeout=30_000)
                self._wait_for_stable()
            self._delay()
            self._log_action("new_tab", {"url": url}, True)
            return {"success": True, "tab_index": self._active_page_index}
        except Exception as exc:
            self._log_action("new_tab", {"url": url}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def switch_tab(self, index: int) -> dict:
        """Switch to tab at ``index``."""
        if 0 <= index < len(self._pages):
            self._active_page_index = index
            self._pages[index].bring_to_front()
            self._log_action("switch_tab", {"index": index}, True)
            return {"success": True, "tab_index": index}
        self._log_action("switch_tab", {"index": index}, False, "Index out of range")
        return {"success": False, "error": f"Tab index {index} out of range (have {len(self._pages)} tabs)."}

    def close_tab(self, index: int = None) -> dict:
        """
        Close a tab.  Defaults to the active tab.  If it is the last tab,
        a fresh blank tab is opened automatically.
        """
        self.ensure_launched()
        if index is None:
            index = self._active_page_index
        if not (0 <= index < len(self._pages)):
            return {"success": False, "error": f"Tab index {index} out of range."}
        try:
            self._pages[index].close()
            self._pages.pop(index)
            if not self._pages:
                # Keep at least one tab alive.
                page = self._context.new_page()
                self._pages.append(page)
            self._active_page_index = min(self._active_page_index, len(self._pages) - 1)
            self._log_action("close_tab", {"index": index}, True)
            return {"success": True, "active_tab": self._active_page_index}
        except Exception as exc:
            self._log_action("close_tab", {"index": index}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def list_tabs(self) -> list[dict]:
        """Return metadata for every open tab."""
        tabs = []
        for i, page in enumerate(self._pages):
            tabs.append({
                "index": i,
                "title": page.title() if page and not page.is_closed() else "(closed)",
                "url": page.url if page and not page.is_closed() else "",
                "active": i == self._active_page_index,
            })
        return tabs

    # ------------------------------------------------------------------
    # Frame management (for iframes)
    # ------------------------------------------------------------------

    def switch_to_frame(self, selector: str) -> dict:
        """Focus a child frame identified by ``selector``."""
        self.ensure_launched()
        try:
            frame = self._page.frame_locator(selector)
            # Store a reference so callers can interact with the frame
            self._active_frame = frame
            self._log_action("switch_to_frame", {"selector": selector}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("switch_to_frame", {"selector": selector}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def switch_to_main_frame(self) -> dict:
        """Return focus to the top-level frame."""
        self._active_frame = None
        self._log_action("switch_to_main_frame", {}, True)
        return {"success": True}

    # ------------------------------------------------------------------
    # Content extraction
    # ------------------------------------------------------------------

    def get_page_content(self, strategy: str = None) -> str:
        """
        Extract page content using the specified (or default) strategy.

        Args:
            strategy: ``"accessibility_tree"``, ``"cleaned_html"``, or
                ``"visible_text"``.

        Returns:
            The extracted content as a string.
        """
        self.ensure_launched()
        strategy = strategy or self._content_strategy

        if strategy == "accessibility_tree":
            return self.get_accessibility_tree()
        elif strategy == "cleaned_html":
            return self.get_cleaned_html()
        elif strategy == "visible_text":
            return self.get_visible_text()
        else:
            logger.warning(f"Unknown content strategy '{strategy}', falling back to visible_text.")
            return self.get_visible_text()

    def get_accessibility_tree(self) -> str:
        """
        Build a compact textual representation of the accessibility tree.

        The accessibility tree captures the semantic structure of the page —
        headings, links, buttons, form fields, etc. — in a format that is
        far more compact than raw HTML yet preserves the information an
        agent needs to decide what to interact with.  This approach is
        inspired by the *WebArena* and *BrowserGym* benchmarks for web
        agents (Zhou et al., 2024).

        Each interactive element is annotated with an index ``[N]`` that
        can be used as a selector shorthand in subsequent actions.
        """
        self.ensure_launched()
        try:
            snapshot = self._page.accessibility.snapshot()
            if not snapshot:
                return self._truncate(f"[Page: {self._page.title()}]\n(empty accessibility tree)")
            lines = []
            self._walk_a11y_node(snapshot, lines, depth=0, counter=[0])
            return self._truncate("\n".join(lines))
        except Exception as exc:
            logger.debug(f"Accessibility tree extraction failed: {exc}")
            return self.get_visible_text()

    def _walk_a11y_node(self, node: dict, lines: list, depth: int, counter: list) -> None:
        """Recursively walk an accessibility snapshot node."""
        role = node.get("role", "")
        name = node.get("name", "")
        value = node.get("value", "")

        interactive_roles = {
            "link", "button", "textbox", "combobox", "checkbox",
            "radio", "menuitem", "tab", "option", "searchbox",
            "spinbutton", "slider", "switch",
        }

        indent = "  " * depth
        parts = [role]
        if name:
            parts.append(f'"{name}"')
        if value:
            parts.append(f'value="{value}"')

        if role in interactive_roles:
            idx = counter[0]
            counter[0] += 1
            label = f"{indent}[{idx}] {' '.join(parts)}"
        else:
            label = f"{indent}{' '.join(parts)}"

        lines.append(label)

        for child in node.get("children", []):
            self._walk_a11y_node(child, lines, depth + 1, counter)

    def get_cleaned_html(self) -> str:
        """
        Return the page's HTML with ``<script>``, ``<style>``, comments,
        and inline styles removed.
        """
        self.ensure_launched()
        try:
            raw = self._page.content()
            # Strip <script> and <style> blocks
            cleaned = re.sub(r"<script[\s\S]*?</script>", "", raw, flags=re.IGNORECASE)
            cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
            # Strip HTML comments
            cleaned = re.sub(r"<!--[\s\S]*?-->", "", cleaned)
            # Strip inline style attributes
            cleaned = re.sub(r'\s+style="[^"]*"', "", cleaned)
            cleaned = re.sub(r"\s+style='[^']*'", "", cleaned)
            # Collapse whitespace
            cleaned = re.sub(r"\n\s*\n", "\n", cleaned)
            return self._truncate(cleaned.strip())
        except Exception as exc:
            logger.debug(f"Cleaned HTML extraction failed: {exc}")
            return f"(error extracting HTML: {exc})"

    def get_visible_text(self) -> str:
        """Return the visible text of the page body."""
        self.ensure_launched()
        try:
            text = self._page.inner_text("body")
            return self._truncate(text.strip())
        except Exception as exc:
            logger.debug(f"Visible text extraction failed: {exc}")
            return f"(error extracting text: {exc})"

    def get_page_metadata(self) -> dict:
        """Return metadata for the current page."""
        self.ensure_launched()
        return {
            "url": self._page.url,
            "title": self._page.title(),
            "viewport": {"width": self._viewport_width, "height": self._viewport_height},
            "tab_count": len(self._pages),
            "active_tab": self._active_page_index,
        }

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def screenshot(self, full_page: bool = False) -> str:
        """
        Take a screenshot of the current page.

        Args:
            full_page: Capture the entire scrollable page, not just the viewport.

        Returns:
            Absolute path to the saved PNG file.
        """
        self.ensure_launched()
        path = os.path.join(tempfile.gettempdir(), f"tinytroupe_browser_{int(time.time() * 1000)}.png")
        try:
            self._page.screenshot(path=path, full_page=full_page)
            self._log_action("screenshot", {"full_page": full_page, "path": path}, True)
            return path
        except Exception as exc:
            self._log_action("screenshot", {"full_page": full_page}, False, str(exc))
            return None

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def pause_for_login(self, url: str, message: str = None) -> dict:
        """
        Navigate to ``url`` and pause so the user can log in manually.

        Args:
            url: The login page URL.
            message: Custom instructions.  If ``None``, a generic message
                is displayed.

        Returns:
            Result dict with current URL after login.
        """
        self.ensure_launched()
        self.goto(url)
        msg = message or f"Please log in at {url}, then signal to continue."
        self._user_interaction.pause_for_action(msg)
        self._wait_for_stable()
        self._log_action("pause_for_login", {"url": url}, True)
        return {"success": True, "url": self._page.url, "title": self._page.title()}

    def inject_credentials(
        self,
        url: str,
        username: str,
        password: str,
        username_selector: str = "input[type=email], input[type=text], input[name=username]",
        password_selector: str = "input[type=password]",
        submit_selector: str = None,
    ) -> dict:
        """
        Navigate to ``url``, fill in credentials, and optionally submit.

        Args:
            url: Login page URL.
            username: Username / email.
            password: Password.
            username_selector: CSS selector for the username field.
            password_selector: CSS selector for the password field.
            submit_selector: CSS selector for the submit button.  If
                ``None``, presses Enter after filling the password field.

        Returns:
            Result dict.
        """
        self.ensure_launched()
        nav = self.goto(url)
        if not nav.get("success"):
            return nav

        try:
            self._page.fill(username_selector, username, timeout=10_000)
            self._page.fill(password_selector, password, timeout=10_000)

            if submit_selector:
                self._page.click(submit_selector, timeout=10_000)
            else:
                self._page.keyboard.press("Enter")

            self._wait_for_stable()
            self._delay()
            self._log_action("inject_credentials", {"url": url, "username": username}, True)
            return {"success": True, "url": self._page.url, "title": self._page.title()}
        except Exception as exc:
            self._log_action("inject_credentials", {"url": url}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def save_storage_state(self, path: str) -> dict:
        """Save cookies and localStorage to a JSON file for later reuse."""
        self.ensure_launched()
        try:
            self._context.storage_state(path=path)
            self._log_action("save_storage_state", {"path": path}, True)
            return {"success": True, "path": path}
        except Exception as exc:
            self._log_action("save_storage_state", {"path": path}, False, str(exc))
            return {"success": False, "error": str(exc)}

    def load_storage_state(self, path: str) -> dict:
        """
        Load cookies and localStorage from a JSON file.

        .. note:: Storage state can only be applied when creating a new
           context.  This method closes the current context and opens a
           fresh one with the saved state.
        """
        self.ensure_launched()
        try:
            # Close current context and create a new one with stored state.
            old_url = self._page.url
            self._context.close()
            viewport = {"width": self._viewport_width, "height": self._viewport_height}
            self._context = self._browser.new_context(viewport=viewport, storage_state=path)
            self._apply_stealth()
            page = self._context.new_page()
            self._pages = [page]
            self._active_page_index = 0
            if old_url and old_url != "about:blank":
                page.goto(old_url, wait_until=self._wait_strategy, timeout=30_000)
                self._wait_for_stable()
            self._log_action("load_storage_state", {"path": path}, True)
            return {"success": True}
        except Exception as exc:
            self._log_action("load_storage_state", {"path": path}, False, str(exc))
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # NL command execution (sub-LLM decomposition)
    # ------------------------------------------------------------------

    def execute_nl_command(self, command: str) -> dict:
        """
        Execute a natural-language browsing instruction by decomposing it
        into low-level Playwright actions via an LLM sub-call.

        The current page's accessibility tree (or configured content
        strategy) is included in the prompt so the LLM knows what elements
        are available on the page.

        Args:
            command: Natural-language instruction such as "Find the search
                box and search for 'TinyTroupe'".

        Returns:
            A dict with ``"success"``, ``"actions_executed"`` (list of
            action dicts with outcomes), ``"screenshot"`` (path), and
            ``"page_content"`` (str).
        """
        self.ensure_launched()

        page_content = self.get_page_content()
        metadata = self.get_page_metadata()

        # Take a screenshot so the sub-LLM can see the page visually.
        # This helps it identify the correct elements, especially when
        # the accessibility tree is ambiguous or truncated.
        screenshot_path = self.screenshot()

        # Build the prompt for the sub-LLM
        prompt = self._build_nl_decomposition_prompt(command, page_content, metadata)

        # Call the LLM — use multimodal content if we have a screenshot
        from tinytroupe.clients import client as get_client

        if screenshot_path:
            from tinytroupe.utils.media import build_multimodal_content_array
            user_content = build_multimodal_content_array(
                text=prompt["user"],
                image_refs=[screenshot_path],
                detail="auto",
            )
        else:
            user_content = prompt["user"]

        messages = [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user_content},
        ]

        try:
            response = get_client().send_message(messages)
        except Exception as exc:
            logger.error(f"LLM call for NL command decomposition failed: {exc}")
            return {"success": False, "error": f"LLM call failed: {exc}"}

        # Parse the response into a list of actions
        actions = self._parse_nl_response(response)
        if not actions:
            return {
                "success": False,
                "error": "Could not parse LLM response into executable actions.",
                "raw_response": response,
            }

        # Execute each action sequentially
        results = []
        from rich.console import Console
        _console = Console()
        _console.print(
            f"  :globe_with_meridians: [bold bright_cyan]NL decomposition[/] → "
            f"[bright_cyan]{len(actions)} action(s)[/]"
        )
        for idx, a in enumerate(actions):
            action_name = a.get('action', '?')
            selector = a.get('selector', a.get('url', a.get('key', '')))
            text_val = a.get('text', '')
            detail = f" [dim]{selector}[/]" if selector else ""
            if text_val:
                detail += f" [dim italic]'{text_val[:60]}{'…' if len(text_val) > 60 else ''}'[/]"
            _console.print(
                f"    [bright_cyan][{idx+1}/{len(actions)}][/] "
                f"[bold]{action_name}[/]{detail}"
            )
        for i, action in enumerate(actions):
            action_name = action.get('action', '?')
            _console.print(
                f"  :arrow_forward: [bold]Executing[/] [{i+1}/{len(actions)}] "
                f"[bold bright_cyan]{action_name}[/] …"
            )
            result = self._execute_parsed_action(action)
            results.append({"action": action, "result": result})
            if not result.get("success", False):
                action_name_lower = action.get("action", "").lower()
                # wait_for / wait_for_stable failures are non-blocking:
                # the element might already exist or the page might
                # already be stable.  Continue with the next action.
                if action_name_lower in ("wait_for", "wait_for_stable"):
                    _console.print(
                        f"    [dim yellow]:hourglass: wait timed out (non-blocking), continuing[/]"
                    )
                    continue
                # All other failures stop the sequence.
                error_msg = result.get('error', '(no error)')
                _console.print(
                    f"    [bold red]:cross_mark: FAILED:[/] [red]{error_msg}[/]"
                )
                break
            else:
                _console.print(
                    f"    [green]:white_check_mark: success[/]"
                )
            # Brief pause between sub-actions for React microtask flush.
            # The real waiting happens in _auto_settle after the full
            # NL command completes.
            if i < len(actions) - 1:
                time.sleep(0.5)

        # Final observation
        screenshot_path = self.screenshot()
        final_content = self.get_page_content()
        final_meta = self.get_page_metadata()

        self._log_action("execute_nl_command", {"command": command}, True)

        return {
            "success": True,
            "actions_executed": results,
            "screenshot": screenshot_path,
            "page_content": final_content,
            "metadata": final_meta,
        }

    def _build_nl_decomposition_prompt(self, command: str, page_content: str, metadata: dict) -> dict:
        """Build the system+user prompt for NL→actions decomposition."""
        system = (
            "You are a browser automation assistant. Given a natural-language "
            "instruction, a screenshot of the current page, and a structured "
            "accessibility tree of the page content, produce a JSON array of "
            "low-level browser actions to accomplish the instruction.\n\n"
            "You receive BOTH an image of the page (so you can see the visual "
            "layout, colors, and positions) AND the accessibility tree text "
            "(so you can identify the correct CSS selectors for elements). "
            "Use them together: the image clarifies WHAT the user wants, "
            "the accessibility tree tells you HOW to target it.\n\n"
            "## Available actions\n"
            "Each action is a JSON object with an `action` field and relevant parameters:\n"
            '- `{"action": "goto", "url": "..."}` — navigate to a URL\n'
            '- `{"action": "click", "selector": "..."}` — click an element\n'
            '- `{"action": "fill", "selector": "...", "text": "..."}` — fill an input\n'
            '- `{"action": "select_option", "selector": "...", "value": "..."}` — select a dropdown option\n'
            '- `{"action": "press", "key": "..."}` — press a key (Enter, Tab, Escape, etc.)\n'
            '- `{"action": "scroll", "direction": "up|down", "amount": 300}` — scroll\n'
            '- `{"action": "hover", "selector": "..."}` — hover over an element\n'
            '- `{"action": "wait_for", "selector": "..."}` — wait for an element to appear\n'
            '- `{"action": "wait_for_stable"}` — wait for the page to stop changing (use after triggering async loads)\n\n'
            "## Rules\n"
            "- Output ONLY a JSON array of action objects, no other text.\n"
            "- For click actions, ALWAYS prefer `text=` selectors (e.g. `text=Send`, "
            "`text=<unset query>`) or `has-text()` selectors (e.g. `listitem:has-text('<unset query>')`) "
            "over positional selectors like nth-of-type or nth-child, which are fragile.\n"
            "- When using `has-text()`, do NOT include list-item number prefixes like '8. ' — "
            "use only the actual text content (e.g. `has-text('<unset query>')` not `has-text('8. <unset query>')`).\n"
            "- For fill actions, prefer `role=` selectors (e.g. `role=textbox[name=\"...\"]`) "
            "because they reliably match accessibility tree names, including placeholder text.\n"
            "- NEVER use positional selectors like `:nth-of-type()` or `:nth-child()` — "
            "they break when the page layout changes. Use text content to identify elements.\n"
            "- Do NOT add `wait_for` actions unless the instruction explicitly asks to wait.\n"
            "- Keep the action list as short as possible.\n"
            "- Do NOT duplicate or retry actions. Produce each action exactly once.\n"
            "- If the instruction cannot be accomplished with the current page state, "
            'return `[{"action": "error", "message": "..."}]`.\n'
        )

        user = (
            f"## Current page\n"
            f"- URL: {metadata.get('url', 'N/A')}\n"
            f"- Title: {metadata.get('title', 'N/A')}\n\n"
            f"## Page content (accessibility tree / content)\n"
            f"```\n{page_content}\n```\n\n"
            f"## Instruction\n"
            f"{command}\n\n"
            f"Produce the JSON array of actions:"
        )

        return {"system": system, "user": user}

    def _parse_nl_response(self, response) -> list[dict]:
        """Parse the LLM response (string or dict) into a list of action dicts."""
        if response is None:
            return []

        # response from client().send_message() is typically a dict with 'content'
        text = response
        if isinstance(response, dict):
            text = response.get("content", "")
        if not isinstance(text, str):
            text = str(text)

        # Try to extract JSON array from the response
        # Handle markdown code blocks
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            # Try to find a JSON array in the text
            match = re.search(r"\[[\s\S]*\]", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        logger.warning(f"Could not parse NL response as JSON: {text[:200]}")
        return []

    def _execute_parsed_action(self, action_dict: dict) -> dict:
        """Execute a single parsed action dict."""
        action_name = action_dict.get("action", "").lower()

        dispatch = {
            "goto": lambda: self.goto(action_dict.get("url", "")),
            "click": lambda: self.click(action_dict.get("selector", "")),
            "fill": lambda: self.fill(action_dict.get("selector", ""), action_dict.get("text", "")),
            "select_option": lambda: self.select_option(action_dict.get("selector", ""), action_dict.get("value", "")),
            "press": lambda: self.press(action_dict.get("key", "")),
            "scroll": lambda: self.scroll(action_dict.get("direction", "down"), action_dict.get("amount", 300)),
            "hover": lambda: self.hover(action_dict.get("selector", "")),
            "wait_for_stable": lambda: self.wait_for_page_stable(),
            "wait_for": lambda: self.wait_for(action_dict.get("selector", "")),
            "upload_file": lambda: self.upload_file(action_dict.get("selector", ""), action_dict.get("path", "")),
            "error": lambda: {"success": False, "error": action_dict.get("message", "Unknown error from LLM")},
        }

        handler = dispatch.get(action_name)
        if handler:
            return handler()
        else:
            return {"success": False, "error": f"Unknown action: {action_name}"}

    # ------------------------------------------------------------------
    # Action log
    # ------------------------------------------------------------------

    def get_action_log(self) -> list[dict]:
        """Return a copy of the complete action log."""
        return list(self._action_log)

    def clear_action_log(self) -> None:
        """Clear the action log."""
        self._action_log.clear()


# ======================================================================
# Standalone utilities
# ======================================================================

def launch_edge_with_cdp(
    url: str = "about:blank",
    port: int = 9222,
    user_data_dir: Optional[str] = None,
    kill_existing: bool = True,
    timeout: int = 30,
) -> tuple:
    """Launch Microsoft Edge with a remote debugging port for CDP connection.

    This utility solves three intertwined problems that arise when using
    Playwright with a real Edge profile from Jupyter:

    1. **Single-instance enforcement** — Edge uses named pipes derived from
       the profile directory hash; a running Edge instance (even in the
       background) causes new ``msedge.exe`` processes to delegate and exit.
    2. **Jupyter event-loop conflict** — Playwright's ``--remote-debugging-pipe``
       (used by ``launch_persistent_context``) fails from inside Jupyter's
       asyncio event loop.
    3. **Conditional access / extensions** — Enterprise environments often
       require the real Edge browser with compliance extensions installed,
       which Playwright's bundled Chromium cannot provide.

    The solution: kill Edge, remove stale lock files, and relaunch Edge
    externally with ``--remote-debugging-port``.  Playwright then connects
    via ``connect_over_cdp()`` over TCP, which works from Jupyter.

    Args:
        url: Initial URL to open in Edge (default: ``"about:blank"``).
        port: TCP port for Chrome DevTools Protocol (default: 9222).
        user_data_dir: Path to the Edge user data directory.  If ``None``,
            auto-detects the default Edge profile on Windows.
        kill_existing: If ``True`` (default), kill all running Edge
            processes and remove singleton lock files before launching.
        timeout: Seconds to wait for the CDP endpoint to become ready.

    Returns:
        A ``(cdp_url, edge_process)`` tuple where:
        - ``cdp_url`` (``str``) — the CDP endpoint URL, e.g.
          ``"http://localhost:9222"``, ready to pass to
          ``TinyWebBrowserFaculty(cdp_url=...)`` or
          ``BrowserController(cdp_url=...)``.
        - ``edge_process`` (``subprocess.Popen``) — the Edge subprocess
          handle.  Call ``edge_process.terminate()`` when done.

    Raises:
        FileNotFoundError: If Edge or the profile directory cannot be found.
        TimeoutError: If the CDP endpoint does not become ready in time.

    Example::

        from tinytroupe.tools.browser_controller import launch_edge_with_cdp
        from tinytroupe.agent.web_browser_faculty import TinyWebBrowserFaculty

        cdp_url, edge_proc = launch_edge_with_cdp(
            url="https://www.office.com",
        )

        faculty = TinyWebBrowserFaculty(cdp_url=cdp_url)
        # ... use the faculty ...

        faculty.close_browser()
        edge_proc.terminate()
    """
    import subprocess
    import time
    import urllib.request

    # ── 1. Locate Edge executable ────────────────────────────────────
    edge_exe = None
    for candidate in [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Microsoft", "Edge", "Application", "msedge.exe"),
    ]:
        if os.path.isfile(candidate):
            edge_exe = candidate
            break

    if not edge_exe:
        raise FileNotFoundError(
            "Microsoft Edge not found.  Install Edge or pass the "
            "executable path manually."
        )

    # ── 2. Resolve Edge profile directory ────────────────────────────
    if user_data_dir is None:
        user_data_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Microsoft", "Edge", "User Data",
        )
    if not os.path.isdir(user_data_dir):
        raise FileNotFoundError(
            f"Edge profile not found at: {user_data_dir}"
        )

    # ── 3. Kill existing Edge processes ──────────────────────────────
    if kill_existing:
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe"],
            capture_output=True,
        )
        time.sleep(2)

        # Retry in case Startup Boost respawned Edge
        for _ in range(3):
            check = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/NH"],
                capture_output=True, text=True,
            )
            if "msedge.exe" not in check.stdout:
                break
            subprocess.run(
                ["taskkill", "/F", "/IM", "msedge.exe"],
                capture_output=True,
            )
            time.sleep(2)

        # Remove stale singleton lock files left by force-kill
        for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = os.path.join(user_data_dir, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except OSError:
                    pass

    # ── 4. Launch Edge with --remote-debugging-port ──────────────────
    edge_process = subprocess.Popen([
        edge_exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ])

    # ── 5. Wait for CDP endpoint ─────────────────────────────────────
    cdp_url = f"http://localhost:{port}"
    for _ in range(timeout):
        try:
            urllib.request.urlopen(f"{cdp_url}/json/version", timeout=1)
            return cdp_url, edge_process
        except Exception:
            time.sleep(1)

    # If we get here, Edge launched but CDP never responded.
    edge_process.terminate()
    raise TimeoutError(
        f"Edge CDP endpoint did not become ready at {cdp_url} "
        f"within {timeout}s."
    )
