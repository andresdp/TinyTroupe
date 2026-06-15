"""
atamsim — ATAM multi-agent simulation extension for TinyTroupe.

This package extends :mod:`tinytroupe` to simulate stakeholder-driven software
architecture evaluations using the Architecture Tradeoff Analysis Method
(ATAM). Instead of gathering human stakeholders in a room, ATAM sessions are
run as multi-agent simulations: each stakeholder is an AI agent with a
role-specific persona, and the evaluation phases are orchestrated as
simulation steps.

Public API
----------

::

    from atamsim import (
        # Core session
        ATAMSession,
        # Stakeholder generation
        ATAMStakeholderFactory,
        StakeholderRoleTemplate,
        # Domain models
        Scenario, Concern, ArchitecturalApproach, ATAMReport,
        QualityAttribute, ConcernType, ATAMPhase,
        # Phases
        PresentationPhase, ApproachIdentificationPhase,
        ScenarioGenerationPhase, ScenarioPrioritizationPhase,
        ApproachAnalysisPhase, ConcernIdentificationPhase,
        BrainstormingPhase,
        # Extraction
        ScenarioExtractor, ConcernExtractor, VoteExtractor,
        ATAMReportGenerator,
    )
"""

from __future__ import annotations

from .config import config
from .extraction import (
    ATAMReportGenerator,
    ConcernExtractor,
    ScenarioExtractor,
    VoteExtractor,
)
from .models import (
    ATAMPhase,
    ATAMReport,
    ArchitecturalApproach,
    Concern,
    ConcernType,
    PriorityVoteModel,
    QualityAttribute,
    Scenario,
    StakeholderRoleTemplate,
    concern_item_to_dataclass,
    parse_concern_type,
    parse_quality_attribute,
    scenario_item_to_dataclass,
)
from .phases import (
    ApproachAnalysisPhase,
    ApproachIdentificationPhase,
    ATAMPhaseBase,
    BrainstormingPhase,
    ConcernIdentificationPhase,
    PresentationPhase,
    ScenarioGenerationPhase,
    ScenarioPrioritizationPhase,
)
from .session import ATAMSession
from .stakeholders import (
    ATAMStakeholderFactory,
    ALL_TEMPLATES,
    TEMPLATES_BY_NAME,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Config
    "config",
    # Core session
    "ATAMSession",
    # Stakeholder generation
    "ATAMStakeholderFactory",
    "StakeholderRoleTemplate",
    "ALL_TEMPLATES",
    "TEMPLATES_BY_NAME",
    # Domain models — enums
    "QualityAttribute",
    "ConcernType",
    "ATAMPhase",
    # Domain models — dataclasses
    "Scenario",
    "Concern",
    "ArchitecturalApproach",
    "ATAMReport",
    # Domain models — pydantic
    "PriorityVoteModel",
    # Conversion helpers
    "parse_quality_attribute",
    "parse_concern_type",
    "scenario_item_to_dataclass",
    "concern_item_to_dataclass",
    # Phases
    "ATAMPhaseBase",
    "PresentationPhase",
    "ApproachIdentificationPhase",
    "ScenarioGenerationPhase",
    "ScenarioPrioritizationPhase",
    "ApproachAnalysisPhase",
    "ConcernIdentificationPhase",
    "BrainstormingPhase",
    # Extraction
    "ScenarioExtractor",
    "ConcernExtractor",
    "VoteExtractor",
    "ATAMReportGenerator",
]