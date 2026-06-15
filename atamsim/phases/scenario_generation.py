"""
Phase 2 — Scenario Generation (PRIORITY).

Asks each stakeholder to propose quality-attribute scenarios based on their
role priorities and the architecture. Uses :class:`ScenarioExtractor` to
extract structured scenarios from each agent's interactions.
"""

from __future__ import annotations

from typing import Any, List

from ..models import Scenario
from .base_phase import ATAMPhaseBase


class ScenarioGenerationPhase(ATAMPhaseBase):
    """ATAM Phase 2: Scenario generation — stakeholders propose scenarios."""

    def prepare_stimulus(self, **kwargs: Any) -> str:
        """Return a stimulus instructing stakeholders to propose scenarios.

        The prompt references the scenario generation template and
        incorporates each stakeholder's role priorities.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioGenerationPhase.prepare_stimulus is not yet implemented."
        )

    def execute(self, n_steps: int = 5, **kwargs: Any) -> List[Scenario]:
        """Broadcast stimulus, run simulation, extract scenarios per agent.

        Returns:
            A consolidated list of :class:`Scenario` instances from all agents.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioGenerationPhase.execute is not yet implemented."
        )

    def extract_results(self) -> List[Scenario]:
        """Delegate to :class:`ScenarioExtractor.extract_results_from_agents`.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioGenerationPhase.extract_results is not yet implemented."
        )