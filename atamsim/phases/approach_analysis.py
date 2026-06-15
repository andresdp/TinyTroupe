"""
Phase 4 — Approach Analysis.

For each top-priority scenario, stakeholders analyze how the architecture
addresses it. Uses :class:`ConcernExtractor` to identify risks, tradeoffs,
and sensitivity points.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..models import Concern, Scenario
from .base_phase import ATAMPhaseBase


class ApproachAnalysisPhase(ATAMPhaseBase):
    """ATAM Phase 4: Analyze architecture against top-priority scenarios."""

    def prepare_stimulus(self, scenario: Scenario = None, **kwargs: Any) -> str:
        """Return a stimulus for analyzing a specific scenario.

        Args:
            scenario: The scenario to analyze against the architecture.
        """
        raise NotImplementedError(
            "ApproachAnalysisPhase.prepare_stimulus is not yet implemented."
        )

    def execute(
        self,
        n_steps: int = 5,
        scenarios: Optional[List[Scenario]] = None,
        **kwargs: Any,
    ) -> List[Concern]:
        """Iterate over top scenarios, broadcast analysis prompts, extract concerns.

        Args:
            n_steps: Steps per scenario analysis.
            scenarios: Explicit list of scenarios to analyze. Defaults to the
                session's prioritized scenarios.

        Returns:
            A list of :class:`Concern` instances.
        """
        raise NotImplementedError(
            "ApproachAnalysisPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        raise NotImplementedError(
            "ApproachAnalysisPhase.extract_results is not yet implemented."
        )