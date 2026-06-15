"""
Phase 3 — Scenario Prioritization (PRIORITY).

Presents consolidated scenarios to all stakeholders. Each stakeholder votes
(assigns priority scores). Uses :class:`VoteExtractor` with
:class:`PriorityVoteModel` to extract votes, then aggregates into weighted
priority scores.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..models import PriorityVoteModel, Scenario
from .base_phase import ATAMPhaseBase


class ScenarioPrioritizationPhase(ATAMPhaseBase):
    """ATAM Phase 3: Scenario prioritization via stakeholder voting."""

    def prepare_stimulus(self, scenarios: List[Scenario] = None, **kwargs: Any) -> str:
        """Return a stimulus listing scenarios and instructing stakeholders to vote.

        Args:
            scenarios: The consolidated scenarios to present for voting.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioPrioritizationPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 3, **kwargs: Any) -> List[Scenario]:
        """Broadcast scenarios, extract votes, aggregate, return sorted scenarios.

        Returns:
            Scenarios sorted by aggregated priority score (descending).

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioPrioritizationPhase.execute is not yet implemented."
        )

    def extract_results(self) -> Any:
        """Extract vote results via :class:`VoteExtractor`.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioPrioritizationPhase.extract_results is not yet implemented."
        )

    def _aggregate_votes(self, votes: List[PriorityVoteModel]) -> Dict[str, float]:
        """Normalize and average vote scores across stakeholders.

        Each stakeholder's scores are normalized to 0.0–1.0 using
        ``PRIORITIZATION_VOTE_RANGE`` from config, then averaged per scenario.

        Args:
            votes: A list of :class:`PriorityVoteModel`, one per stakeholder.

        Returns:
            A mapping ``{scenario_name: average_normalized_score}``.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioPrioritizationPhase._aggregate_votes is not yet implemented."
        )