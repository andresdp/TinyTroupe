"""
Phase 6 — Brainstorming.

Stakeholders brainstorm mitigation strategies for identified risks.
Broadcasts risk descriptions, extracts mitigation proposals, and updates
``Concern.mitigation`` fields.
"""

from __future__ import annotations

from typing import Any, List

from ..models import Concern
from .base_phase import ATAMPhaseBase


class BrainstormingPhase(ATAMPhaseBase):
    """ATAM Phase 6: Brainstorm mitigation strategies for identified risks."""

    def prepare_stimulus(self, concerns: List[Concern] = None, **kwargs: Any) -> str:
        """Return a stimulus presenting risks and requesting mitigations.

        Args:
            concerns: The identified concerns (risks/tradeoffs) to mitigate.
        """
        raise NotImplementedError(
            "BrainstormingPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 5, **kwargs: Any) -> List[Concern]:
        """Broadcast risk descriptions, extract mitigations, update concerns.

        Returns:
            The updated concerns with ``mitigation`` fields populated.
        """
        raise NotImplementedError(
            "BrainstormingPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        raise NotImplementedError(
            "BrainstormingPhase.extract_results is not yet implemented."
        )