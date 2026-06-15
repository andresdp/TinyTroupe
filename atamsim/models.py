"""
Domain models for ATAM simulations.

This module is the foundational data layer of the package. It defines:

* **Enums** — :class:`QualityAttribute`, :class:`ConcernType`, :class:`ATAMPhase`.
* **Dataclasses** — :class:`Scenario`, :class:`Concern`,
  :class:`ArchitecturalApproach`, :class:`ATAMReport`,
  :class:`StakeholderRoleTemplate`.
* **Pydantic models** — used as ``response_format`` in structured LLM calls
  for extraction (scenarios, concerns, votes, approaches).
* **Conversion helpers** — turn Pydantic instances into dataclass instances
  and safely parse enum values from free-form strings.

The module has no dependencies on TinyTroupe at import time except for
:func:`tinytroupe.utils.fresh_id`, which is imported lazily so that the
pure-data portions (enums, dataclasses, Pydantic) can be unit-tested in
isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ####################################################################
# Enums
# ####################################################################


class QualityAttribute(Enum):
    """ISO 25010 + common ATAM quality attributes."""

    AVAILABILITY = "availability"
    MODIFIABILITY = "modifiability"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TESTABILITY = "testability"
    USABILITY = "usability"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"
    DEPLOYABILITY = "deployability"
    COST = "cost"


class ConcernType(Enum):
    """ATAM concern classification."""

    RISK = "risk"
    NON_RISK = "non_risk"
    SENSITIVITY_POINT = "sensitivity_point"
    TRADEOFF = "tradeoff"


class ATAMPhase(Enum):
    """Enumeration of ATAM phases."""

    PRESENTATION = "presentation"  # Phase 0
    APPROACH_IDENTIFICATION = "approach_identification"  # Phase 1
    SCENARIO_GENERATION = "scenario_generation"  # Phase 2
    SCENARIO_PRIORITIZATION = "scenario_prioritization"  # Phase 3
    APPROACH_ANALYSIS = "approach_analysis"  # Phase 4
    CONCERN_IDENTIFICATION = "concern_identification"  # Phase 5
    BRAINSTORMING = "brainstorming"  # Phase 6


# ####################################################################
# Domain dataclasses
# ####################################################################


@dataclass
class Scenario:
    """An ATAM scenario — the central evaluation artifact.

    Follows the SAAMS-style scenario structure:
    stimulus → environment → artifact → response → measure.
    """

    id: str
    name: str
    description: str
    stimulus_source: str
    stimulus: str
    environment: str
    artifact: str
    response: str
    response_measure: str
    quality_attribute: QualityAttribute
    generated_by: Optional[str] = None
    priority_score: Optional[float] = None
    votes: Dict[str, int] = field(default_factory=dict)


@dataclass
class Concern:
    """An ATAM finding: risk, non-risk, sensitivity point, or tradeoff."""

    id: str
    type: ConcernType
    description: str
    related_scenarios: List[str] = field(default_factory=list)
    related_attributes: List[QualityAttribute] = field(default_factory=list)
    architectural_element: Optional[str] = None
    severity: Optional[str] = None
    mitigation: Optional[str] = None
    identified_by: Optional[str] = None


@dataclass
class ArchitecturalApproach:
    """An architectural strategy or pattern identified in the architecture."""

    name: str
    description: str
    patterns: List[str] = field(default_factory=list)
    attributes_addressed: List[QualityAttribute] = field(default_factory=list)


@dataclass
class ATAMReport:
    """The final aggregated ATAM evaluation report."""

    project_name: str
    evaluation_date: str
    business_drivers: str
    architecture_summary: str
    stakeholders: List[str] = field(default_factory=list)
    scenarios: List[Scenario] = field(default_factory=list)
    prioritized_scenarios: List[Scenario] = field(default_factory=list)
    approaches: List[ArchitecturalApproach] = field(default_factory=list)
    concerns: List[Concern] = field(default_factory=list)
    phase_summaries: Dict[str, str] = field(default_factory=dict)


@dataclass
class StakeholderRoleTemplate:
    """A predefined template for generating an ATAM stakeholder agent."""

    role_name: str
    description: str
    responsibilities: str
    quality_priorities: List[QualityAttribute]
    concerns: str
    persona_overrides: dict = field(default_factory=dict)


# ####################################################################
# Pydantic models for structured LLM output
# ####################################################################


class ScenarioItemModel(BaseModel):
    """Single scenario extracted from agent interactions."""

    name: str
    description: str
    stimulus_source: str
    stimulus: str
    environment: str
    artifact: str
    response: str
    response_measure: str
    quality_attribute: str  # matches a QualityAttribute enum value


class ScenariosExtractionModel(BaseModel):
    """Multiple scenarios extracted from a single agent's interactions."""

    scenarios: List[ScenarioItemModel] = Field(default_factory=list)


class ConsolidatedScenariosModel(BaseModel):
    """Deduplicated and consolidated scenarios from multiple agents."""

    scenarios: List[ScenarioItemModel] = Field(default_factory=list)
    consolidation_notes: Optional[str] = None


class PriorityVoteModel(BaseModel):
    """A single stakeholder's priority vote for scenarios."""

    votes: List[Dict[str, Any]] = Field(default_factory=list)
    justification: str = ""

    # votes entries: {"scenario_name": str, "score": int}


class ConcernItemModel(BaseModel):
    """A single concern (risk/tradeoff/sensitivity) extracted from analysis."""

    type: str  # "risk", "non_risk", "sensitivity_point", "tradeoff"
    description: str
    severity: str  # "high", "medium", "low"
    related_scenarios: List[str] = Field(default_factory=list)
    related_attributes: List[str] = Field(default_factory=list)
    architectural_element: Optional[str] = None
    mitigation: Optional[str] = None


class ConcernsExtractionModel(BaseModel):
    """Multiple concerns extracted from approach analysis."""

    concerns: List[ConcernItemModel] = Field(default_factory=list)


class ApproachItemModel(BaseModel):
    """A single architectural approach."""

    name: str
    description: str
    patterns: List[str] = Field(default_factory=list)
    attributes_addressed: List[str] = Field(default_factory=list)


class ApproachesExtractionModel(BaseModel):
    """Multiple approaches identified from the architecture."""

    approaches: List[ApproachItemModel] = Field(default_factory=list)


# ####################################################################
# Conversion helpers
# ####################################################################


def _generate_id(prefix: str = "atam") -> str:
    """Generate a unique id, using TinyTroupe's ``fresh_id`` when available."""
    try:
        from tinytroupe.utils import fresh_id

        # fresh_id returns an int scoped to the given prefix; format as a
        # human-readable string with the prefix.
        return f"{prefix}_{fresh_id(prefix)}"
    except Exception:
        # Fallback for environments where tinytroupe is not importable
        # (e.g., isolated unit tests). Uses a module-level counter.
        import uuid

        return f"{prefix}_{uuid.uuid4().hex[:12]}"


def parse_quality_attribute(value: str) -> QualityAttribute:
    """Safely parse a string into a :class:`QualityAttribute`.

    Defaults to :attr:`QualityAttribute.PERFORMANCE` if the value is not
    recognized.
    """
    if value is None:
        return QualityAttribute.PERFORMANCE

    cleaned = value.strip().lower()

    # Direct value match.
    for attr in QualityAttribute:
        if attr.value == cleaned:
            return attr

    # Common synonyms / aliases.
    aliases = {
        "latency": QualityAttribute.PERFORMANCE,
        "throughput": QualityAttribute.PERFORMANCE,
        "maintainability": QualityAttribute.MODIFIABILITY,
        "safety": QualityAttribute.RELIABILITY,
        "robustness": QualityAttribute.RELIABILITY,
        "flexibility": QualityAttribute.MODIFIABILITY,
        "cost-effectiveness": QualityAttribute.COST,
        "budget": QualityAttribute.COST,
    }
    if cleaned in aliases:
        return aliases[cleaned]

    return QualityAttribute.PERFORMANCE


def parse_concern_type(value: str) -> ConcernType:
    """Safely parse a string into a :class:`ConcernType`.

    Defaults to :attr:`ConcernType.RISK` if the value is not recognized.
    """
    if value is None:
        return ConcernType.RISK

    cleaned = value.strip().lower().replace("-", "_").replace(" ", "_")

    aliases = {
        "sensitivity": ConcernType.SENSITIVITY_POINT,
        "sensitivity_point": ConcernType.SENSITIVITY_POINT,
        "nonrisk": ConcernType.NON_RISK,
        "non_risk": ConcernType.NON_RISK,
        "not_a_risk": ConcernType.NON_RISK,
        "trade_off": ConcernType.TRADEOFF,
        "trade-off": ConcernType.TRADEOFF,
    }
    if cleaned in aliases:
        return aliases[cleaned]

    for ct in ConcernType:
        if ct.value == cleaned:
            return ct

    return ConcernType.RISK


def scenario_item_to_dataclass(
    item: ScenarioItemModel, generated_by: Optional[str] = None
) -> Scenario:
    """Convert a Pydantic :class:`ScenarioItemModel` to a :class:`Scenario`."""
    return Scenario(
        id=_generate_id("scenario"),
        name=item.name,
        description=item.description,
        stimulus_source=item.stimulus_source,
        stimulus=item.stimulus,
        environment=item.environment,
        artifact=item.artifact,
        response=item.response,
        response_measure=item.response_measure,
        quality_attribute=parse_quality_attribute(item.quality_attribute),
        generated_by=generated_by,
    )


def concern_item_to_dataclass(
    item: ConcernItemModel, identified_by: Optional[str] = None
) -> Concern:
    """Convert a Pydantic :class:`ConcernItemModel` to a :class:`Concern`."""
    return Concern(
        id=_generate_id("concern"),
        type=parse_concern_type(item.type),
        description=item.description,
        related_scenarios=list(item.related_scenarios),
        related_attributes=[
            parse_quality_attribute(a) for a in item.related_attributes
        ],
        architectural_element=item.architectural_element,
        severity=item.severity.lower() if item.severity else None,
        mitigation=item.mitigation,
        identified_by=identified_by,
    )


def approach_item_to_dataclass(item: ApproachItemModel) -> ArchitecturalApproach:
    """Convert a Pydantic :class:`ApproachItemModel` to an :class:`ArchitecturalApproach`."""
    return ArchitecturalApproach(
        name=item.name,
        description=item.description,
        patterns=list(item.patterns),
        attributes_addressed=[
            parse_quality_attribute(a) for a in item.attributes_addressed
        ],
    )