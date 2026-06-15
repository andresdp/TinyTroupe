"""
Phase 0 — Presentation.

Presents business drivers and the architecture overview to stakeholders.
Agents consult grounding documents and confirm their understanding.
"""

from __future__ import annotations

from typing import Any

from .base_phase import ATAMPhaseBase


class PresentationPhase(ATAMPhaseBase):
    """ATAM Phase 0: Business drivers + architecture presentation."""

    def prepare_stimulus(self, **kwargs: Any) -> str:
        """Return a stimulus summarizing business drivers and architecture.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "PresentationPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 5, **kwargs: Any) -> Any:
        """Broadcast architecture summary, run steps, extract understanding summaries.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "PresentationPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        """Extract a summary of each stakeholder's understanding.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "PresentationPhase.extract_results is not yet implemented."
        )