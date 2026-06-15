"""
:class:`ATAMSession` — the ATAM evaluation environment.

This class extends :class:`tinytroupe.environment.TinyWorld` to manage the
overall ATAM evaluation lifecycle. It acts as the facilitator (broadcasting
stimuli, managing turn-taking) and accumulates results across phases.

Subclassing ``TinyWorld`` gives automatic access to:

* ``run(steps)`` — turn-taking simulation.
* ``broadcast(speech)`` — stimulus delivery to all agents.
* Parallel agent actions within a step.
* Display and serialization.

The session adds ATAM-specific orchestration on top: accumulators for
scenarios, concerns, and approaches; phase dispatch; consolidation; and
report generation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

from ..config import config
from ..models import (
    ATAMPhase,
    ATAMReport,
    ArchitecturalApproach,
    Concern,
    Scenario,
)
from ..extraction.report_generator import ATAMReportGenerator
from ..phases.base_phase import ATAMPhaseBase


class ATAMSession(TinyWorld):
    """A :class:`TinyWorld` subclass for running ATAM evaluations.

    Manages the overall evaluation lifecycle: stores architecture context,
    business drivers, and accumulators for scenarios/concerns/approaches.
    Phase execution is delegated to phase classes created lazily via
    :meth:`_get_phase_instance`.
    """

    def __init__(
        self,
        name: str = "ATAM Session",
        business_drivers: str = "",
        architecture_docs_path: Optional[str] = None,
        architecture_summary: str = "",
        stakeholders: Optional[List[TinyPerson]] = None,
        project_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the ATAM session.

        Args:
            name: Name for the world (shown in simulation output).
            business_drivers: Text describing the business drivers for the
                project being evaluated.
            architecture_docs_path: Optional path to a folder containing
                architecture documents for grounding.
            architecture_summary: A text summary of the architecture.
            stakeholders: Optional list of stakeholder agents to add.
            project_name: Optional project name for the report. Defaults to
                *name*.
            **kwargs: Additional keyword arguments forwarded to
                :class:`TinyWorld`.
        """
        super().__init__(name=name, agents=stakeholders or [], **kwargs)

        self.project_name = project_name or name
        self.business_drivers = business_drivers
        self.architecture_docs_path = architecture_docs_path
        self.architecture_summary = architecture_summary
        self.evaluation_date = datetime.now().isoformat()

        # Accumulators for ATAM artifacts.
        self.scenarios: List[Scenario] = []
        self.concerns: List[Concern] = []
        self.approaches: List[ArchitecturalApproach] = []

        # Results from each phase, keyed by ATAMPhase enum value.
        self.phase_results: Dict[str, Any] = {}

        # Lazy cache of phase instances.
        self._phase_instances: Dict[ATAMPhase, ATAMPhaseBase] = {}

    # ------------------------------------------------------------------
    # Accumulator helpers (fully implemented)
    # ------------------------------------------------------------------
    def add_scenario(self, scenario: Scenario) -> None:
        """Add a scenario to the session's accumulator."""
        self.scenarios.append(scenario)

    def add_concern(self, concern: Concern) -> None:
        """Add a concern to the session's accumulator."""
        self.concerns.append(concern)

    def add_approach(self, approach: ArchitecturalApproach) -> None:
        """Add an architectural approach to the session's accumulator."""
        self.approaches.append(approach)

    def add_scenarios(self, scenarios: List[Scenario]) -> None:
        """Add multiple scenarios at once."""
        self.scenarios.extend(scenarios)

    def add_concerns(self, concerns: List[Concern]) -> None:
        """Add multiple concerns at once."""
        self.concerns.extend(concerns)

    def add_approaches(self, approaches: List[ArchitecturalApproach]) -> None:
        """Add multiple approaches at once."""
        self.approaches.extend(approaches)

    # ------------------------------------------------------------------
    # Phase orchestration (stubs)
    # ------------------------------------------------------------------
    def run_phase(self, phase: ATAMPhase, **kwargs: Any) -> Any:
        """Dispatch to the appropriate phase class, execute, store results.

        Args:
            phase: The :class:`ATAMPhase` to run.
            **kwargs: Phase-specific parameters forwarded to ``execute()``.

        Returns:
            The phase output.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMSession.run_phase is not yet implemented."
        )

    def run_full_evaluation(
        self, phases: Optional[List[ATAMPhase]] = None
    ) -> ATAMReport:
        """Run all (or a subset of) phases in sequence.

        Args:
            phases: Optional list of phases to run. Defaults to all phases
                in canonical order.

        Returns:
            The final :class:`ATAMReport`.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMSession.run_full_evaluation is not yet implemented."
        )

    def consolidate_scenarios(
        self, scenarios: Optional[List[Scenario]] = None
    ) -> List[Scenario]:
        """Deduplicate scenarios by name similarity.

        Args:
            scenarios: Scenarios to consolidate. Defaults to the session's
                accumulated scenarios.

        Returns:
            The deduplicated list.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMSession.consolidate_scenarios is not yet implemented."
        )

    def prioritize_scenarios(
        self, scenarios: Optional[List[Scenario]] = None
    ) -> List[Scenario]:
        """Delegate to :class:`ScenarioPrioritizationPhase` for voting.

        Args:
            scenarios: Scenarios to prioritize. Defaults to the session's
                accumulated scenarios.

        Returns:
            Scenarios sorted by priority score.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMSession.prioritize_scenarios is not yet implemented."
        )

    def generate_report(self) -> ATAMReport:
        """Call :class:`ATAMReportGenerator.generate()` with accumulated results.

        Returns:
            The assembled :class:`ATAMReport`.
        """
        return ATAMReportGenerator(self).generate()

    def _get_phase_instance(self, phase: ATAMPhase) -> ATAMPhaseBase:
        """Return the phase class instance for *phase*, creating it lazily.

        Args:
            phase: The :class:`ATAMPhase` enum value.

        Returns:
            An :class:`ATAMPhaseBase` subclass instance.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMSession._get_phase_instance is not yet implemented."
        )