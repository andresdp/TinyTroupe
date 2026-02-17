"""
User Interaction Protocol for TinyTroupe
=========================================

Provides a pluggable protocol for requesting user input during simulations.
The primary use case is the web-browser mental faculty, where the agent may
need to pause the simulation for destructive-action confirmation, manual
login, or other situations that require human judgement.

Classes:

- **UserInteraction** — Abstract base class defining the protocol.
- **ConsoleUserInteraction** — Default implementation using ``rich.prompt``.
  Works identically in terminal and Jupyter notebook environments.
- **AutoUserInteraction** — Auto-responding implementation for automated
  tests and headless runs.

Design rationale
----------------
Python's built-in ``input()`` — and, by extension, ``rich.prompt`` which
wraps it — works in **both** terminal and Jupyter notebook environments.
In Jupyter, ``input()`` renders an inline text-input widget inside the
cell output and blocks the cell until the user responds.  This makes a
single implementation sufficient for both execution contexts, without
any environment-detection logic.

The protocol is intentionally minimal so that users can substitute a
custom implementation (e.g., ``ipywidgets``-based dialogs, a web UI, or
a Slack bot) without touching any faculty code.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger("tinytroupe")


# ---------------------------------------------------------------------------
# Abstract protocol
# ---------------------------------------------------------------------------

class UserInteraction(ABC):
    """
    Abstract base class for user-interaction backends.

    Every method may block the calling thread until the user responds.
    Implementations must be **synchronous** — the simulation loop is
    single-threaded and expects a direct return value.
    """

    @abstractmethod
    def confirm(self, message: str, default: bool = False) -> bool:
        """
        Ask the user a yes/no question.

        Args:
            message: The question to display.
            default: The pre-selected answer when the user presses Enter
                without typing anything.

        Returns:
            ``True`` for *yes*, ``False`` for *no*.
        """
        ...

    @abstractmethod
    def prompt(self, message: str, default: str = "") -> str:
        """
        Ask the user for free-form text input.

        Args:
            message: The prompt message.
            default: Value returned when the user presses Enter without input.

        Returns:
            The user's input string.
        """
        ...

    @abstractmethod
    def notify(self, message: str) -> None:
        """
        Display an informational message that does **not** require a response.

        Args:
            message: The notification text.
        """
        ...

    @abstractmethod
    def pause_for_action(self, message: str) -> None:
        """
        Block until the user explicitly signals to continue (e.g., by pressing
        Enter).  This is used when the user needs to perform a manual action —
        such as logging into a website — before the simulation resumes.

        Args:
            message: Instructions explaining what the user should do.
        """
        ...


# ---------------------------------------------------------------------------
# Console implementation (default)
# ---------------------------------------------------------------------------

class ConsoleUserInteraction(UserInteraction):
    """
    Default implementation that uses ``rich`` for styled console output and
    Python's ``input()`` under the hood.  Works in both terminal and Jupyter
    notebook environments without any special handling.
    """

    def confirm(self, message: str, default: bool = False) -> bool:
        from rich.prompt import Confirm

        logger.debug(f"ConsoleUserInteraction.confirm: {message}")
        return Confirm.ask(f"[bold bright_magenta]🤖 Agent request:[/] {message}", default=default)

    def prompt(self, message: str, default: str = "") -> str:
        from rich.prompt import Prompt

        logger.debug(f"ConsoleUserInteraction.prompt: {message}")
        return Prompt.ask(f"[bold bright_magenta]🤖 Agent request:[/] {message}", default=default or None)

    def notify(self, message: str) -> None:
        from rich import print as rprint
        from rich.panel import Panel

        logger.debug(f"ConsoleUserInteraction.notify: {message}")
        rprint(Panel(message, title="🌐 Browser", border_style="bright_magenta"))

    def pause_for_action(self, message: str) -> None:
        from rich import print as rprint
        from rich.panel import Panel

        logger.debug(f"ConsoleUserInteraction.pause_for_action: {message}")
        rprint(Panel(
            f"{message}\n\n[dim]Press Enter when done…[/]",
            title="⏸️  Action Required",
            border_style="bold yellow",
        ))
        input()


# ---------------------------------------------------------------------------
# Auto-responding implementation (for tests / headless)
# ---------------------------------------------------------------------------

class AutoUserInteraction(UserInteraction):
    """
    Auto-responding implementation for automated tests and headless runs.

    Every method records the interaction in ``self.history`` and returns
    a pre-configured default value without blocking.

    Args:
        auto_confirm: Default answer for ``confirm()`` calls.
        auto_prompt_value: Default answer for ``prompt()`` calls.
        log_interactions: Whether to also emit ``logger.info`` messages.
    """

    def __init__(
        self,
        auto_confirm: bool = True,
        auto_prompt_value: str = "",
        log_interactions: bool = True,
    ):
        self.auto_confirm = auto_confirm
        self.auto_prompt_value = auto_prompt_value
        self.log_interactions = log_interactions
        self.history: list[dict[str, Any]] = []

    def _record(self, kind: str, message: str, response: Any) -> None:
        entry = {
            "kind": kind,
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(entry)
        if self.log_interactions:
            logger.info(f"AutoUserInteraction.{kind}: {message!r} → {response!r}")

    def confirm(self, message: str, default: bool = False) -> bool:
        result = self.auto_confirm
        self._record("confirm", message, result)
        return result

    def prompt(self, message: str, default: str = "") -> str:
        result = self.auto_prompt_value if self.auto_prompt_value else default
        self._record("prompt", message, result)
        return result

    def notify(self, message: str) -> None:
        self._record("notify", message, None)

    def pause_for_action(self, message: str) -> None:
        self._record("pause_for_action", message, None)
