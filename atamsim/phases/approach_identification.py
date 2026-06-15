"""
Phase 1 — Approach Identification.

Identifies architectural approaches/patterns from the architecture documents
using an LLM call with :class:`ApproachesExtractionModel`.
"""

from __future__ import annotations

from typing import Any, List

from ..models import ArchitecturalApproach
from .base_phase import ATAMPhaseBase


class ApproachIdentificationPhase(ATAMPhaseBase):
    """ATAM Phase 1: Identify architectural approaches/patterns."""

    def prepare_stimulus(self, **kwargs: Any) -> str:
        raise NotImplementedError(
            "ApproachIdentificationPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 3, **kwargs: Any) -> List[ArchitecturalApproach]:
        raise NotImplementedError(
            "ApproachIdentificationPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        raise NotImplementedError(
            "ApproachIdentificationPhase.extract_results is not yet implemented."
        )