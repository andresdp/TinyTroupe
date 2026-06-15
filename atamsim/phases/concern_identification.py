"""
Phase 5 — Concern Identification.

Consolidates concerns from approach analysis. Deduplicates and classifies
them. Optionally validates using :class:`Proposition` checks.
"""

from __future__ import annotations

from typing import Any, List

from ..models import Concern
from .base_phase import ATAMPhaseBase


class ConcernIdentificationPhase(ATAMPhaseBase):
    """ATAM Phase 5: Consolidate and classify risks/tradeoffs/sensitivity points."""

    def prepare_stimulus(self, **kwargs: Any) -> str:
        raise NotImplementedError(
            "ConcernIdentificationPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 3, **kwargs: Any) -> List[Concern]:
        raise NotImplementedError(
            "ConcernIdentificationPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        raise NotImplementedError(
            "ConcernIdentificationPhase.extract_results is not yet implemented."
        )