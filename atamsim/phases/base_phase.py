"""
Abstract base class for ATAM phases.

Phases are plain Python objects (not simulation entities) that orchestrate a
segment of the ATAM evaluation: they prepare a stimulus, broadcast it to
stakeholders, run simulation steps, and extract structured results.

The :meth:`ATAMPhaseBase._broadcast_and_run` helper is the only concrete
method — it delegates to ``session.broadcast()`` and ``session.run()``, both
inherited from :class:`tinytroupe.environment.TinyWorld`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..session.atam_session import ATAMSession


class ATAMPhaseBase(ABC):
    """Abstract base class for all ATAM phases.

    Subclasses must implement :meth:`prepare_stimulus`, :meth:`execute`, and
    :meth:`extract_results`.
    """

    def __init__(self, session: "ATAMSession", name: str = "") -> None:
        """Initialize the phase.

        Args:
            session: The owning :class:`ATAMSession`.
            name: A human-readable name for this phase.
        """
        self.session = session
        self.name = name or self.__class__.__name__

    @abstractmethod
    def prepare_stimulus(self, **kwargs: Any) -> str:
        """Return the stimulus text to broadcast to stakeholders.

        Args:
            **kwargs: Phase-specific parameters (e.g., scenarios to present).

        Returns:
            The stimulus string.
        """
        ...

    @abstractmethod
    def execute(self, n_steps: int = 5, **kwargs: Any) -> Any:
        """Orchestrate the phase: broadcast stimulus, run steps, extract results.

        Args:
            n_steps: Number of simulation steps to run after broadcasting.
            **kwargs: Phase-specific parameters.

        Returns:
            The extracted phase results (type varies by phase).
        """
        ...

    @abstractmethod
    def extract_results(self) -> Any:
        """Extract structured results after the phase simulation has run.

        Returns:
            The extracted results (type varies by phase).
        """
        ...

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------
    def _broadcast_and_run(self, stimulus: str, n_steps: int) -> None:
        """Broadcast *stimulus* to all agents and run *n_steps* steps.

        This is a thin wrapper around the session's inherited
        :meth:`TinyWorld.broadcast` and :meth:`TinyWorld.run` methods.

        Args:
            stimulus: The stimulus text to broadcast.
            n_steps: Number of simulation steps to execute.
        """
        self.session.broadcast(stimulus)
        self.session.run(n_steps)