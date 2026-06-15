# Implementation Plan

[High-Level Overview]

## What We Are Building

`atam_sim` is a standalone Python package that extends TinyTroupe to simulate stakeholder-driven software architecture evaluations using the Architecture Tradeoff Analysis Method (ATAM). Instead of gathering human stakeholders in a room, ATAM sessions are run as multi-agent simulations: each stakeholder is an AI agent with a role-specific persona, and the evaluation phases (scenario generation, prioritization, risk identification, etc.) are orchestrated as simulation steps.

## Architecture Diagram

The diagram below shows how `atam_sim` maps ATAM concepts onto TinyTroupe's existing abstractions and how the layers interact.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER / NOTEBOOK                                   │
│  (create stakeholders, load architecture docs, run evaluation, report)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ imports
┌────────────────────────────────────▼────────────────────────────────────┐
│                         atam_sim (NEW PACKAGE)                           │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │                     ATAMSession                                  │     │
│  │                  (extends TinyWorld)                             │     │
│  │  • run_phase(phase)   • consolidate_scenarios()                 │     │
│  │  • run_full_evaluation()  • prioritize_scenarios()              │     │
│  │  • generate_report()   • accumulators: scenarios, concerns...   │     │
│  └──┬──────────┬───────────────────────────────────┬──────────────┘     │
│     │          │                                   │                     │
│     │  ┌───────▼────────┐   ┌─────────────────┐   ▼                     │
│     │  │   Phases        │   │  Extraction     │   │ Report              │
│     │  │  (orchestrate   │   │ (ScenarioExtr.  │   │ Generator           │
│     │  │   sim + extract)│   │  ConcernExtr.   │   │ (JSON/MD)           │
│     │  │                 │   │  VoteExtractor) │   │                     │
│     │  │ • Scenario Gen  │   └────────┬────────┘   │                     │
│     │  │ • Scenario Prio │            │            │                     │
│     │  │ • Approach Anlys│            │            │                     │
│     │  │ • Brainstorming │            │            │                     │
│     │  └───────┬─────────┘            │            │                     │
│     │          │                      │            │                     │
│  ┌──▼──────────▼──────────────────────▼────────────▼──────────────┐      │
│  │            ATAMStakeholderFactory (extends TinyPersonFactory)   │      │
│  │  • create_from_template()  • create_panel()                     │      │
│  │  • Predefined templates: Sponsor, Architect, Developer,         │      │
│  │    Security Expert, DevOps, Product Manager, QA Lead, etc.      │      │
│  └──────────────────────────┬─────────────────────────────────────┘      │
│                             │ creates                                     │
│  ┌──────────────────────────▼─────────────────────────────────────┐      │
│  │                    Domain Models (models.py)                    │      │
│  │  Enums: QualityAttribute, ConcernType, ATAMPhase                │      │
│  │  Dataclasses: Scenario, Concern, ATAMReport, ...                │      │
│  │  Pydantic: ScenariosExtractionModel, ConcernsExtractionModel... │      │
│  └──────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ depends on (public API only)
┌────────────────────────────────────▼────────────────────────────────────┐
│                       tinytroupe (EXISTING, UNCHANGED)                   │
│  TinyPerson  TinyWorld  TinyPersonFactory  ResultsExtractor              │
│  Proposition  FilesAndWebGroundingFaculty  client()  config_manager      │
└─────────────────────────────────────────────────────────────────────────┘
```

## ATAM Phase Flow

The diagram below shows how the ATAM phases flow through the simulation. Priority phases (bold) are implemented first; remaining phases follow the same pattern.

```
                    ┌──────────────────┐
                    │  Phase 0:        │
                    │  Presentation    │  (architecture + business drivers)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Phase 1:        │
                    │  Approach ID     │  (identify architectural patterns)
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Phase 2: SCENARIO GEN ★    │  (stakeholders propose scenarios)
              │  (PRIORITY — implement 1st) │
              └──────────────┬──────────────┘
                             │ consolidate + deduplicate
              ┌──────────────▼──────────────┐
              │  Phase 3: SCENARIO PRIO ★   │  (stakeholders vote, scores)
              │  (PRIORITY — implement 2nd) │
              └──────────────┬──────────────┘
                             │ sorted scenarios
                    ┌────────▼─────────┐
                    │  Phase 4:        │
                    │  Approach Analysis│  (architecture vs top scenarios)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Phase 5:        │
                    │  Concern ID      │  (risks, tradeoffs, sensitivity pts)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Phase 6:        │
                    │  Brainstorming   │  (mitigation strategies)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │     Report       │  (ATAMReport: JSON + Markdown)
                    └──────────────────┘
```

## Key Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Separate package** (`atam_sim/`), not a TinyTroupe subpackage | Keeps TinyTroupe core untouched; `atam_sim` depends only on TinyTroupe's public API. Allows independent versioning and optional use. |
| 2 | **Stakeholders = `TinyPerson` agents** | Reuses TinyTroupe's full agent cognition (episodic/semantic memory, action generation, quality checks). Stakeholders "think" and "talk" like real participants. |
| 3 | **ATAM sessions = `TinyWorld` subclass** | Inherits turn-taking (`run()`), stimulus broadcasting (`broadcast()`), parallel agent actions, display, and serialization — no need to reimplement execution mechanics. |
| 4 | **Phases are plain Python objects**, not simulation entities | Phases orchestrate (broadcast stimulus → run steps → extract results) but are not themselves part of the simulation state. This keeps them lightweight and avoids serialization complexity. |
| 5 | **Extractors use composition over inheritance** | `ScenarioExtractor`, `ConcernExtractor`, etc. wrap `ResultsExtractor` internally because ATAM extraction needs Pydantic structured output models, while `ResultsExtractor` returns free-form JSON dicts. |
| 6 | **Predefined stakeholder templates** | 10 common ATAM roles (Sponsor, Architect, Developer, Security Expert, etc.) with role-specific quality priorities, concerns, and persona fragments. Users can also create custom stakeholders. |
| 7 | **Architecture artifacts as grounding documents** | Uses TinyTroupe's existing `FilesAndWebGroundingFaculty` to give stakeholders access to architecture descriptions, business drivers, and other docs — stakeholders can `LIST_DOCUMENTS` and `CONSULT` them during discussions. |
| 8 | **Pydantic models for structured LLM output** | All extraction LLM calls use Pydantic `response_format` models (e.g., `ScenariosExtractionModel`) to ensure the extracted scenarios, concerns, and votes are well-structured and directly convertible to dataclass instances. |
| 9 | **Scenario prioritization via stakeholder voting** | Each stakeholder independently scores scenarios; the system normalizes and averages scores into a 0.0–1.0 `priority_score`. This mirrors real ATAM's 30-vote allocation method. |
| 10 | **Incremental implementation** | Phases 2 + 3 (scenario generation + prioritization) and stakeholder modeling are the priority deliverables. The remaining phases follow the same architectural pattern and can be added incrementally without restructuring. |

## Concept Mapping: ATAM ↔ TinyTroupe

| ATAM Concept | TinyTroupe Abstraction | Notes |
|---|---|---|
| Stakeholder | `TinyPerson` | Persona includes role, responsibilities, quality priorities |
| Evaluation session | `TinyWorld` (`ATAMSession`) | Manages turn-taking, broadcasting, phase orchestration |
| Facilitator | `ATAMSession` methods | The session itself acts as facilitator (no separate agent) |
| Architecture artifact | Grounding document | Via `FilesAndWebGroundingFaculty` |
| Scenario | `Scenario` dataclass | Extracted from agent interactions via `ScenarioExtractor` |
| Risk / Tradeoff / Sensitivity | `Concern` dataclass | Extracted via `ConcernExtractor`, validated via `Proposition` |
| Prioritization voting | `PriorityVoteModel` | Each agent independently votes, system aggregates |
| Evaluation report | `ATAMReport` dataclass | Generated by `ATAMReportGenerator` |

[Overview]

This plan describes the creation of `atam_sim`, a standalone Python package that extends TinyTroupe to model stakeholder-driven architecture evaluations following the Architecture Tradeoff Analysis Method (ATAM).

ATAM is a structured method for evaluating software architectures against quality-attribute requirements through stakeholder participation. By mapping ATAM concepts onto TinyTroupe's multi-agent simulation framework, we can create AI-driven stakeholder panels that generate, prioritize, and analyze architectural scenarios, identify risks/tradeoffs/sensitivity points, and produce structured evaluation outputs — all without requiring human stakeholder availability for preliminary or exploratory evaluations.

The package depends on `tinytroupe` as its core simulation engine and follows TinyTroupe's architectural conventions: stakeholders are `TinyPerson` agents, ATAM sessions are `TinyWorld` subclasses, quality-attribute reasoning is implemented as mental faculties, scenario generation and concern extraction use the `ResultsExtractor` pattern, and result validation uses the `Proposition` system. The design supports all ATAM phases (0 through 9) but prioritizes implementation of scenario generation, scenario prioritization, and stakeholder modeling, with the remaining phases structured for incremental addition.

The separate-package approach keeps the TinyTroupe core untouched while fully leveraging its public API (`TinyPerson`, `TinyWorld`, `TinyPersonFactory`, `ResultsExtractor`, `Proposition`, `FilesAndWebGroundingFaculty`, `Intervention`). The package includes predefined stakeholder role templates (Project Sponsor, System Architect, Lead Developer, Security Expert, DevOps Lead, End User, Product Manager, QA Lead), grounding-document integration for architecture artifacts, and a report generator that aggregates results into a standard ATAM output.

[Types]

The type system introduces domain-specific data structures for ATAM artifacts, Pydantic models for LLM structured output, and enums for quality attributes and concern categories.

### Enums

```python
# atam_sim/models.py

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
    RISK = "risk"                          # Architectural decision with potential negative consequence
    NON_RISK = "non_risk"                 # Issue raised that is NOT an architectural risk
    SENSITIVITY_POINT = "sensitivity_point" # Property where a change in one parameter affects a quality attribute
    TRADEOFF = "tradeoff"                  # Decision that affects multiple quality attributes in opposing ways

class ATAMPhase(Enum):
    """Enumeration of ATAM phases."""
    PRESENTATION = "presentation"                        # Phase 0: Business drivers + architecture
    APPROACH_IDENTIFICATION = "approach_identification"  # Phase 1: Architectural approaches
    SCENARIO_GENERATION = "scenario_generation"          # Phase 2: Utility tree + scenario brainstorming
    SCENARIO_PRIORITIZATION = "scenario_prioritization"  # Phase 3: Voting and ranking
    APPROACH_ANALYSIS = "approach_analysis"              # Phase 4: Analyze architecture vs scenarios
    CONCERN_IDENTIFICATION = "concern_identification"    # Phase 5: Risks, tradeoffs, sensitivity points
    BRAINSTORMING = "brainstorming"                      # Phase 6: Mitigation strategies
```

### Domain Data Structures (dataclasses)

```python
@dataclass
class Scenario:
    """An ATAM scenario — the central evaluation artifact.
    
    Follows the SAAMS-style scenario structure: stimulus → environment → artifact → response → measure.
    """
    id: str
    name: str
    description: str
    stimulus_source: str            # Who or what generates the stimulus (e.g., "external user", "internal batch job")
    stimulus: str                   # The condition or event arriving at the system
    environment: str                # Conditions under which the stimulus occurs (e.g., "normal operation", "peak load")
    artifact: str                   # Which part of the system is stimulated (e.g., "authentication service")
    response: str                   # The system's expected activity in response
    response_measure: str           # How the response is measured (e.g., "latency < 200ms", "99.99% uptime")
    quality_attribute: QualityAttribute
    generated_by: Optional[str] = None       # Stakeholder agent name who proposed it
    priority_score: Optional[float] = None   # 0.0–1.0, assigned during prioritization
    votes: Dict[str, int] = field(default_factory=dict)  # {stakeholder_name: vote_weight}

@dataclass
class Concern:
    """An ATAM finding: risk, non-risk, sensitivity point, or tradeoff."""
    id: str
    type: ConcernType
    description: str
    related_scenarios: List[str] = field(default_factory=list)   # Scenario IDs
    related_attributes: List[QualityAttribute] = field(default_factory=list)
    architectural_element: Optional[str] = None                  # Component/connector affected
    severity: Optional[str] = None                               # "high", "medium", "low"
    mitigation: Optional[str] = None                             # Proposed mitigation (from brainstorming phase)
    identified_by: Optional[str] = None                          # Stakeholder agent name

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
```

### Stakeholder Role Template Type

```python
@dataclass
class StakeholderRoleTemplate:
    """A predefined template for generating an ATAM stakeholder agent."""
    role_name: str                              # e.g., "System Architect"
    description: str                            # Brief description of the role
    responsibilities: str                       # What this role is responsible for
    quality_priorities: List[QualityAttribute]  # Which attributes this role cares most about
    concerns: str                               # Role-specific concerns to embed in the persona
    persona_overrides: dict = field(default_factory=dict)  # Optional overrides for TinyPerson persona fields
```

### Pydantic Models for LLM Structured Output

```python
# Used as response_format in client().send_message() calls

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
    quality_attribute: str  # String matching QualityAttribute enum value

class ScenariosExtractionModel(BaseModel):
    """Multiple scenarios extracted from a single agent's interactions."""
    scenarios: List[ScenarioItemModel]

class ConsolidatedScenariosModel(BaseModel):
    """Deduplicated and consolidated scenarios from multiple agents."""
    scenarios: List[ScenarioItemModel]
    consolidation_notes: Optional[str] = None

class PriorityVoteModel(BaseModel):
    """A single stakeholder's priority vote for scenarios."""
    votes: List[dict]  # [{"scenario_name": str, "score": int}]  score 1-10
    justification: str

class ConcernItemModel(BaseModel):
    """A single concern (risk/tradeoff/sensitivity) extracted from analysis."""
    type: str           # "risk", "non_risk", "sensitivity_point", "tradeoff"
    description: str
    severity: str       # "high", "medium", "low"
    related_scenarios: List[str] = []
    related_attributes: List[str] = []
    architectural_element: Optional[str] = None
    mitigation: Optional[str] = None

class ConcernsExtractionModel(BaseModel):
    """Multiple concerns extracted from approach analysis."""
    concerns: List[ConcernItemModel]

class ApproachItemModel(BaseModel):
    """A single architectural approach."""
    name: str
    description: str
    patterns: List[str] = []
    attributes_addressed: List[str] = []

class ApproachesExtractionModel(BaseModel):
    """Multiple approaches identified from the architecture."""
    approaches: List[ApproachItemModel]
```

[Files]

The package is organized into subpackages mirroring ATAM's conceptual structure, with all new files under a top-level `atam_sim/` directory.

### New Files to Create

#### Package Skeleton & Configuration

- **`atam_sim/pyproject.toml`** — Package metadata with dependency on `tinytroupe`, `pydantic`, `chevron`. Defines `[project]` with `name = "atam_sim"`, `version = "0.1.0"`, `dependencies = ["tinytroupe", "pydantic>=2.0", "chevron"]`.
- **`atam_sim/atam_sim/__init__.py`** — Public API exports: `ATAMSession`, `ATAMStakeholderFactory`, `StakeholderRoleTemplate`, `Scenario`, `Concern`, `QualityAttribute`, `ATAMReport`, and all phase classes. Prints no AI disclaimer (TinyTroupe already does this on import).
- **`atam_sim/atam_sim/config.py`** — Reads ATAM-specific config from a local `config.ini` and falls back to defaults. Keys: `DEFAULT_STEPS_PER_PHASE`, `SCENARIO_MAX_PER_STAKEHOLDER`, `PRIORITIZATION_VOTE_RANGE`, `ENABLE_GROUNDING_DOCUMENTS`.

#### Domain Models

- **`atam_sim/atam_sim/models.py`** — All enums (`QualityAttribute`, `ConcernType`, `ATAMPhase`), dataclasses (`Scenario`, `Concern`, `ArchitecturalApproach`, `ATAMReport`, `StakeholderRoleTemplate`), and Pydantic models (`ScenarioItemModel`, `ScenariosExtractionModel`, `ConsolidatedScenariosModel`, `PriorityVoteModel`, `ConcernItemModel`, `ConcernsExtractionModel`, `ApproachItemModel`, `ApproachesExtractionModel`). Conversion helpers: `scenario_item_to_dataclass()`, `concern_item_to_dataclass()`, `approach_item_to_dataclass()`.

#### Stakeholder Templates & Factory

- **`atam_sim/atam_sim/stakeholders/__init__.py`** — Exports `ATAMStakeholderFactory` and `StakeholderRoleTemplate`.
- **`atam_sim/atam_sim/stakeholders/templates.py`** — Predefined `StakeholderRoleTemplate` instances for 10 common ATAM roles: `PROJECT_SPONSOR`, `SYSTEM_ARCHITECT`, `LEAD_DEVELOPER`, `SECURITY_EXPERT`, `DEVOPS_LEAD`, `END_USER_REPRESENTATIVE`, `PRODUCT_MANAGER`, `QA_LEAD`, `DATA_ARCHITECT`, `PROJECT_MANAGER`. Each template includes role-specific quality priorities, concerns, and persona fragment text.
- **`atam_sim/atam_sim/stakeholders/stakeholder_factory.py`** — `ATAMStakeholderFactory` class extending `TinyPersonFactory`. Methods: `create_from_template()`, `create_panel()`, `create_custom_stakeholder()`. Each created agent gets `FilesAndWebGroundingFaculty` pointing to architecture docs and `RecallFaculty`.

#### ATAM Session (Environment)

- **`atam_sim/atam_sim/session/__init__.py`** — Exports `ATAMSession`.
- **`atam_sim/atam_sim/session/atam_session.py`** — `ATAMSession(TinyWorld)` subclass. Manages the overall evaluation lifecycle: stores `architecture_context` (path to grounding docs), `business_drivers` (text), `scenarios`/`concerns`/`approaches` accumulators, and `phase_results` dict. Core methods: `run_phase(phase)`, `run_full_evaluation()`, `add_scenario()`, `add_concern()`, `consolidate_scenarios()`, `prioritize_scenarios()`, `generate_report()`. Implements facilitator logic (stimulus broadcasting, turn management) without needing a separate facilitator agent.

#### Phases

- **`atam_sim/atam_sim/phases/__init__.py`** — Exports all phase classes.
- **`atam_sim/atam_sim/phases/base_phase.py`** — `ATAMPhaseBase` abstract base class. Holds a reference to the owning `ATAMSession`. Abstract methods: `prepare_stimulus()`, `execute(n_steps)`, `extract_results()`. Concrete helper: `_broadcast_and_run(stimulus, n_steps)` which broadcasts to all agents and calls `self.session.run(n_steps)`.
- **`atam_sim/atam_sim/phases/presentation_phase.py`** — `PresentationPhase(ATAMPhaseBase)`: Presents business drivers and architecture overview. Broadcasts architecture summary as stimulus; stakeholders consult grounding documents and confirm understanding. Extracts a summary of each stakeholder's understanding.
- **`atam_sim/atam_sim/phases/scenario_generation.py`** — `ScenarioGenerationPhase(ATAMPhaseBase)`: Asks each stakeholder to propose quality-attribute scenarios based on their role priorities and the architecture. Broadcasts a scenario-generation prompt. Uses `ScenarioExtractor` to extract structured scenarios from each agent. Returns `List[Scenario]`.
- **`atam_sim/atam_sim/phases/scenario_prioritization.py`** — `ScenarioPrioritizationPhase(ATAMPhaseBase)`: Presents consolidated scenarios to all stakeholders. Each stakeholder votes (assigns priority scores). Uses `ResultsExtractor` with `PriorityVoteModel` to extract votes. Aggregates votes into weighted priority scores. Returns updated `List[Scenario]` sorted by priority.
- **`atam_sim/atam_sim/phases/approach_identification.py`** — `ApproachIdentificationPhase(ATAMPhaseBase)`: Identifies architectural approaches/patterns from the architecture documents. Uses an LLM call with `ApproachesExtractionModel`. Returns `List[ArchitecturalApproach]`.
- **`atam_sim/atam_sim/phases/approach_analysis.py`** — `ApproachAnalysisPhase(ATAMPhaseBase)`: For each top-priority scenario, stakeholders analyze how the architecture addresses it. Broadcasts analysis prompts. Uses `ConcernExtractor` to identify risks, tradeoffs, sensitivity points. Returns `List[Concern]`.
- **`atam_sim/atam_sim/phases/concern_identification.py`** — `ConcernIdentificationPhase(ATAMPhaseBase)`: Consolidates concerns from approach analysis. Deduplicates and classifies. Optionally validates using `Proposition` checks (e.g., "Scenario X is adequately addressed by the architecture"). Returns `List[Concern]`.
- **`atam_sim/atam_sim/phases/brainstorming_phase.py`** — `BrainstormingPhase(ATAMPhaseBase)`: Stakeholders brainstorm mitigation strategies for identified risks. Broadcasts risk descriptions. Uses `ResultsExtractor` to extract mitigation proposals. Updates `Concern.mitigation` fields.

#### Extraction

- **`atam_sim/atam_sim/extraction/__init__.py`** — Exports `ScenarioExtractor`, `ConcernExtractor`, `VoteExtractor`, `ATAMReportGenerator`.
- **`atam_sim/atam_sim/extraction/scenario_extractor.py`** — `ScenarioExtractor`: Wraps `ResultsExtractor` with scenario-specific prompt template and `ScenariosExtractionModel` parsing. Converts LLM output to `List[Scenario]` dataclass instances.
- **`atam_sim/atam_sim/extraction/concern_extractor.py`** — `ConcernExtractor`: Wraps `ResultsExtractor` with concern-specific prompt and `ConcernsExtractionModel` parsing. Converts to `List[Concern]`.
- **`atam_sim/atam_sim/extraction/vote_extractor.py`** — `VoteExtractor`: Extracts `PriorityVoteModel` from each stakeholder's interactions during prioritization.
- **`atam_sim/atam_sim/extraction/report_generator.py`** — `ATAMReportGenerator`: Aggregates all phase outputs into an `ATAMReport` dataclass. Methods: `generate()`, `to_json(path)`, `to_markdown(path)`, `to_dict()`.

#### Prompt Templates

- **`atam_sim/atam_sim/prompts/scenario_generation.mustache`** — Mustache template for scenario generation extraction. Instructs the LLM to identify scenarios in the SAAMS structure from agent interactions.
- **`atam_sim/atam_sim/prompts/scenario_prioritization.mustache`** — Template for extracting priority votes.
- **`atam_sim/atam_sim/prompts/concern_extraction.mustache`** — Template for extracting risks/tradeoffs/sensitivity points.
- **`atam_sim/atam_sim/prompts/approach_analysis.mustache`** — Template for analyzing architecture approaches against scenarios.
- **`atam_sim/atam_sim/prompts/presentation.mustache`** — Template for the presentation phase stimulus.
- **`atam_sim/atam_sim/prompts/brainstorming.mustache`** — Template for mitigation brainstorming.

#### Data & Examples

- **`atam_sim/atam_sim/data/sample_architecture/README.md`** — Sample architecture document for testing/demonstration.
- **`atam_sim/atam_sim/data/sample_architecture/architecture_overview.md`** — A simple e-commerce architecture description for the example.
- **`atam_sim/atam_sim/data/sample_architecture/business_drivers.md`** — Sample business drivers document.

#### Tests

- **`atam_sim/tests/test_models.py`** — Unit tests for enums, dataclasses, Pydantic models, and conversion functions.
- **`atam_sim/tests/test_stakeholder_factory.py`** — Tests for `ATAMStakeholderFactory`: template instantiation, panel creation, grounding faculty attachment.
- **`atam_sim/tests/test_scenario_generation.py`** — Tests for `ScenarioGenerationPhase` and `ScenarioExtractor`.
- **`atam_sim/tests/test_scenario_prioritization.py`** — Tests for `ScenarioPrioritizationPhase` and vote aggregation.
- **`atam_sim/tests/test_atam_session.py`** — Integration tests for `ATAMSession` running multiple phases.
- **`atam_sim/tests/test_report_generator.py`** — Tests for `ATAMReportGenerator` output formats.
- **`atam_sim/tests/conftest.py`** — pytest fixtures: mock architecture context, cached TinyTroupe config, sample stakeholders.

#### Example Notebook

- **`atam_sim/examples/atam_evaluation_example.ipynb`** — End-to-end example: creating stakeholders from templates, loading architecture docs, running scenario generation + prioritization, generating a report.

### Existing Files to Modify

None. The package is entirely separate from the TinyTroupe source tree and depends only on TinyTroupe's public API. No changes to any file under `tinytroupe/` are required.

### Configuration File

- **`atam_sim/atam_sim/config.ini`** — ATAM-specific configuration:
  ```ini
  [ATAM]
  DEFAULT_STEPS_PER_PHASE = 5
  SCENARIO_MAX_PER_STAKEHOLDER = 5
  PRIORITIZATION_VOTE_RANGE = 10
  ENABLE_GROUNDING_DOCUMENTS = true
  CONSOLIDATION_ENABLED = true
  ```

[Functions]

This section details every new function and method. No existing functions are modified.

### New Functions

#### `atam_sim/atam_sim/models.py`

- `scenario_item_to_dataclass(item: ScenarioItemModel, generated_by: str = None) -> Scenario` — Converts a Pydantic `ScenarioItemModel` to a `Scenario` dataclass, generating an ID via `utils.fresh_id()`.
- `concern_item_to_dataclass(item: ConcernItemModel, identified_by: str = None) -> Concern` — Converts a Pydantic `ConcernItemModel` to a `Concern` dataclass.
- `approach_item_to_dataclass(item: ApproachItemModel) -> ArchitecturalApproach` — Converts a Pydantic `ApproachItemModel` to an `ArchitecturalApproach` dataclass.
- `parse_quality_attribute(value: str) -> QualityAttribute` — Safely parses a string into a `QualityAttribute` enum, defaulting to `PERFORMANCE` if unrecognized.
- `parse_concern_type(value: str) -> ConcernType` — Safely parses a string into a `ConcernType` enum.

#### `atam_sim/atam_sim/stakeholders/stakeholder_factory.py`

- `ATAMStakeholderFactory.__init__(self, project_context: str, architecture_docs_path: str = None)` — Stores context and docs path. Calls `super().__init__()` with a generated context description.
- `ATAMStakeholderFactory.create_from_template(self, template: StakeholderRoleTemplate, name: str = None) -> TinyPerson` — Creates a single stakeholder from a predefined template. Merges template persona fragment with project context. Attaches `FilesAndWebGroundingFaculty` and `RecallFaculty`.
- `ATAMStakeholderFactory.create_panel(self, templates: List[StakeholderRoleTemplate], names: List[str] = None) -> List[TinyPerson]` — Creates a panel of stakeholders from multiple templates. Uses parallel generation when enabled in config.
- `ATAMStakeholderFactory.create_custom_stakeholder(self, role_name: str, description: str, quality_priorities: List[QualityAttribute], concerns: str) -> TinyPerson` — Creates a stakeholder with custom parameters (no template).
- `ATAMStakeholderFactory._build_persona_context(self, template: StakeholderRoleTemplate) -> str` — Internal helper that merges template fields into a context string for `TinyPersonFactory.generate_person()`.

#### `atam_sim/atam_sim/session/atam_session.py`

- `ATAMSession.__init__(self, name: str, business_drivers: str, architecture_docs_path: str = None, stakeholders: List[TinyPerson] = None)` — Initializes the world, stores evaluation metadata, creates phase instances lazily.
- `ATAMSession.run_phase(self, phase: ATAMPhase, **kwargs) -> Any` — Dispatches to the appropriate phase class, executes it, stores results in `self.phase_results`, returns the phase output.
- `ATAMSession.run_full_evaluation(self, phases: List[ATAMPhase] = None) -> ATAMReport` — Runs all (or a subset of) phases in sequence. Returns the final `ATAMReport`.
- `ATAMSession.consolidate_scenarios(self, scenarios: List[Scenario]) -> List[Scenario]` — Deduplicates scenarios by name similarity using an LLM call with `ConsolidatedScenariosModel`.
- `ATAMSession.prioritize_scenarios(self, scenarios: List[Scenario]) -> List[Scenario]` — Delegates to `ScenarioPrioritizationPhase`. Returns sorted scenarios.
- `ATAMSession.generate_report(self) -> ATAMReport` — Calls `ATAMReportGenerator.generate()` with all accumulated results.
- `ATAMSession._get_phase_instance(self, phase: ATAMPhase) -> ATAMPhaseBase` — Internal factory method that returns the appropriate phase class instance.

#### `atam_sim/atam_sim/phases/base_phase.py`

- `ATAMPhaseBase.__init__(self, session: ATAMSession)` — Stores session reference.
- `ATAMPhaseBase.prepare_stimulus(self, **kwargs) -> str` — Abstract. Returns the stimulus text to broadcast.
- `ATAMPhaseBase.execute(self, n_steps: int = 5, **kwargs) -> Any` — Abstract. Orchestrates the phase simulation and extraction.
- `ATAMPhaseBase.extract_results(self) -> Any` — Abstract. Extracts structured results after simulation.
- `ATAMPhaseBase._broadcast_and_run(self, stimulus: str, n_steps: int)` — Protected helper. Calls `self.session.broadcast(stimulus)` then `self.session.run(n_steps)`.

#### `atam_sim/atam_sim/phases/scenario_generation.py`

- `ScenarioGenerationPhase.prepare_stimulus(self) -> str` — Returns a stimulus prompt instructing stakeholders to propose scenarios based on their role and the architecture context. References the scenario generation prompt template.
- `ScenarioGenerationPhase.execute(self, n_steps: int = 5) -> List[Scenario]` — Broadcasts stimulus, runs simulation, then calls `ScenarioExtractor` on each stakeholder. Consolidates results.
- `ScenarioGenerationPhase.extract_results(self) -> List[Scenario]` — Delegates to `ScenarioExtractor.extract_results_from_agents()`.

#### `atam_sim/atam_sim/phases/scenario_prioritization.py`

- `ScenarioPrioritizationPhase.prepare_stimulus(self, scenarios: List[Scenario]) -> str` — Returns a stimulus listing all consolidated scenarios and instructing stakeholders to assign priority scores.
- `ScenarioPrioritizationPhase.execute(self, n_steps: int = 3) -> List[Scenario]` — Broadcasts scenarios, runs simulation, extracts votes via `VoteExtractor`, aggregates scores, updates `Scenario.priority_score` fields, returns sorted list.
- `ScenarioPrioritizationPhase._aggregate_votes(self, votes: List[PriorityVoteModel]) -> Dict[str, float]` — Internal method that normalizes and averages vote scores across stakeholders.

#### `atam_sim/atam_sim/phases/approach_analysis.py`

- `ApproachAnalysisPhase.prepare_stimulus(self, scenario: Scenario) -> str` — Returns a stimulus for analyzing a specific scenario against the architecture.
- `ApproachAnalysisPhase.execute(self, n_steps: int = 5, scenarios: List[Scenario] = None) -> List[Concern]` — Iterates over top-priority scenarios, broadcasts analysis prompts, extracts concerns via `ConcernExtractor`.

#### `atam_sim/atam_sim/extraction/scenario_extractor.py`

- `ScenarioExtractor.__init__(self, prompt_template_path: str = None)` — Initializes with path to `scenario_generation.mustache`. Defaults to the bundled template.
- `ScenarioExtractor.extract_from_agent(self, agent: TinyPerson) -> List[Scenario]` — Extracts scenarios from a single agent's interaction history using LLM call with `ScenariosExtractionModel`. Calls `scenario_item_to_dataclass()` for each.
- `ScenarioExtractor.extract_from_agents(self, agents: List[TinyPerson]) -> List[Scenario]` — Iterates over agents, collects all scenarios, tags each with `generated_by`.

#### `atam_sim/atam_sim/extraction/concern_extractor.py`

- `ConcernExtractor.__init__(self, prompt_template_path: str = None)` — Initializes with concern extraction prompt.
- `ConcernExtractor.extract_from_agent(self, agent: TinyPerson, scenario_context: str = None) -> List[Concern]` — Extracts concerns from agent interactions. Calls `concern_item_to_dataclass()`.
- `ConcernExtractor.extract_from_world(self, world: TinyWorld, scenario_context: str = None) -> List[Concern]` — Extracts concerns from the full world interaction history.

#### `atam_sim/atam_sim/extraction/vote_extractor.py`

- `VoteExtractor.extract_vote(self, agent: TinyPerson) -> PriorityVoteModel` — Extracts a priority vote from an agent's interaction history using LLM call with `PriorityVoteModel` as `response_format`.

#### `atam_sim/atam_sim/extraction/report_generator.py`

- `ATAMReportGenerator.__init__(self, session: ATAMSession)` — Stores session reference.
- `ATAMReportGenerator.generate(self) -> ATAMReport` — Assembles `ATAMReport` from session accumulators.
- `ATAMReportGenerator.to_json(self, report: ATAMReport, path: str)` — Serializes report to JSON file.
- `ATAMReportGenerator.to_markdown(self, report: ATAMReport, path: str)` — Serializes report to Markdown file with sections for each ATAM artifact type.
- `ATAMReportGenerator.to_dict(self, report: ATAMReport) -> dict` — Converts report to dictionary for programmatic use.

[Classes]

### New Classes

#### `ATAMSession(TinyWorld)` — `atam_sim/atam_sim/session/atam_session.py`
- **Inheritance**: `TinyWorld` from `tinytroupe.environment`
- **Key Methods**: `run_phase()`, `run_full_evaluation()`, `consolidate_scenarios()`, `prioritize_scenarios()`, `generate_report()`, `add_scenario()`, `add_concern()`, `add_approach()`
- **State**: `architecture_docs_path`, `business_drivers`, `scenarios: List[Scenario]`, `concerns: List[Concern]`, `approaches: List[ArchitecturalApproach]`, `phase_results: Dict[str, Any]`, `phase_instances: Dict[ATAMPhase, ATAMPhaseBase]`
- **Rationale**: Subclassing `TinyWorld` gives automatic access to turn-taking (`run()`), stimulus broadcasting (`broadcast()`), parallel agent actions, display, and serialization. The session overrides no `TinyWorld` internals — it adds ATAM-specific orchestration on top.

#### `ATAMStakeholderFactory(TinyPersonFactory)` — `atam_sim/atam_sim/stakeholders/stakeholder_factory.py`
- **Inheritance**: `TinyPersonFactory` from `tinytroupe.factory`
- **Key Methods**: `create_from_template()`, `create_panel()`, `create_custom_stakeholder()`, `_build_persona_context()`
- **State**: `project_context`, `architecture_docs_path`, `_created_roles: List[str]` (for uniqueness tracking)
- **Rationale**: Extends `TinyPersonFactory` to add template-driven generation and automatic grounding faculty attachment, while reusing the parent's LLM-based persona generation and name uniqueness enforcement.

#### `ATAMPhaseBase` (Abstract) — `atam_sim/atam_sim/phases/base_phase.py`
- **Inheritance**: `object` (no TinyTroupe base needed — phases are orchestration, not simulation entities)
- **Key Methods**: `prepare_stimulus()`, `execute()`, `extract_results()`, `_broadcast_and_run()`
- **State**: `session: ATAMSession`, `name: str`

#### `PresentationPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/presentation_phase.py`
- **Methods**: `prepare_stimulus()`, `execute(n_steps=5)`, `extract_results()`

#### `ScenarioGenerationPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/scenario_generation.py`
- **Methods**: `prepare_stimulus()`, `execute(n_steps=5)`, `extract_results()`

#### `ScenarioPrioritizationPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/scenario_prioritization.py`
- **Methods**: `prepare_stimulus(scenarios)`, `execute(n_steps=3)`, `extract_results()`, `_aggregate_votes()`

#### `ApproachIdentificationPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/approach_identification.py`
- **Methods**: `prepare_stimulus()`, `execute(n_steps=3)`, `extract_results()`

#### `ApproachAnalysisPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/approach_analysis.py`
- **Methods**: `prepare_stimulus(scenario)`, `execute(n_steps=5, scenarios=None)`, `extract_results()`

#### `ConcernIdentificationPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/concern_identification.py`
- **Methods**: `prepare_stimulus()`, `execute(n_steps=3)`, `extract_results()`

#### `BrainstormingPhase(ATAMPhaseBase)` — `atam_sim/atam_sim/phases/brainstorming_phase.py`
- **Methods**: `prepare_stimulus(concerns)`, `execute(n_steps=5)`, `extract_results()`

#### `ScenarioExtractor` — `atam_sim/atam_sim/extraction/scenario_extractor.py`
- **Inheritance**: `object` (wraps `ResultsExtractor` internally rather than subclassing, because ATAM extraction uses Pydantic models while `ResultsExtractor` uses free-form JSON)
- **Methods**: `extract_from_agent()`, `extract_from_agents()`

#### `ConcernExtractor` — `atam_sim/atam_sim/extraction/concern_extractor.py`
- **Methods**: `extract_from_agent()`, `extract_from_world()`

#### `VoteExtractor` — `atam_sim/atam_sim/extraction/vote_extractor.py`
- **Methods**: `extract_vote()`

#### `ATAMReportGenerator` — `atam_sim/atam_sim/extraction/report_generator.py`
- **Methods**: `generate()`, `to_json()`, `to_markdown()`, `to_dict()`

### Modified Classes

None. No existing TinyTroupe classes are modified. All extensibility is achieved through inheritance (`TinyWorld`, `TinyPersonFactory`) and composition (wrapping `ResultsExtractor`, using `TinyPerson` and `FilesAndWebGroundingFaculty` as-is).

### Removed Classes

None.

[Dependencies]

### New Package Dependencies

- `tinytroupe` — The core simulation framework. Installed from the local package or PyPI. Required for `TinyPerson`, `TinyWorld`, `TinyPersonFactory`, `ResultsExtractor`, `Proposition`, mental faculties, and the `client()` LLM abstraction.
- `pydantic >= 2.0` — Already a dependency of TinyTroupe; used for structured LLM output models in `atam_sim`.
- `chevron` — Already a dependency of TinyTroupe; used for Mustache prompt template rendering.

No additional external dependencies are introduced. All other functionality (LLM calls, caching, parallel execution) flows through TinyTroupe's existing client and config layers.

### Version Requirements

- Python >= 3.10 (matching TinyTroupe's requirement)
- `tinytroupe >= 0.1.0` (local development references the repository directly)

### Integration Requirements

- The package imports TinyTrove via `from tinytroupe.agent import TinyPerson` etc. — using only public API.
- TinyTroupe's `config.ini` (at the project root or `examples/`) governs LLM model settings. The `atam_sim` package reads its own `config.ini` for ATAM-specific parameters but does not override TinyTroupe's config.
- API call caching (`CACHE_API_CALLS`) and concurrency limiting (`MAX_CONCURRENT_MODEL_CALLS`) are inherited from TinyTroupe's client layer.

[Testing]

### Test Strategy

Tests use pytest with TinyTroupe's existing caching mechanism (`CACHE_API_CALLS=true`) to avoid repeated LLM costs during development. A `conftest.py` provides fixtures for mock architecture documents, cached configuration, and sample stakeholder panels.

### Test Files

- **`test_models.py`** — Tests enum parsing, dataclass construction, Pydantic model validation, and conversion functions. Pure unit tests, no LLM calls. Validates: `parse_quality_attribute("availability") == QualityAttribute.AVAILABILITY`, `Scenario` dataclass field defaults, `ScenariosExtractionModel` validates correct JSON.
- **`test_stakeholder_factory.py`** — Tests `ATAMStakeholderFactory.create_from_template()` with each predefined template. Validates: agent has correct persona fields, agent has `FilesAndWebGroundingFaculty` attached, agent names are unique across panel. Uses cached LLM calls.
- **`test_scenario_generation.py`** — Tests `ScenarioGenerationPhase.execute()` with a 2-stakeholder panel and cached config. Validates: returns `List[Scenario]`, each scenario has all required fields populated, `quality_attribute` is a valid enum value.
- **`test_scenario_prioritization.py`** — Tests `ScenarioPrioritizationPhase.execute()` with pre-populated scenarios. Validates: `priority_score` is assigned to each scenario, scenarios are returned sorted by priority, vote aggregation logic produces normalized scores.
- **`test_atam_session.py`** — Integration test: creates a session, runs scenario generation + prioritization phases, validates `phase_results` dict contains expected keys and the session accumulators are populated.
- **`test_report_generator.py`** — Tests `ATAMReportGenerator` with a pre-populated session state. Validates: JSON output contains all sections, Markdown output has expected headers, dict output is serializable.

### Validation Strategy

- **Smoke test**: A notebook (`atam_evaluation_example.ipynb`) demonstrates the full workflow with the sample architecture.
- **Cached regression**: LLM responses are cached via TinyTroupe's `CACHE_API_CALLS`. Tests verify the pipeline produces structurally correct output against cached responses.
- **Proposition-based validation**: The `ConcernIdentificationPhase` can optionally validate concerns using `Proposition` checks (e.g., "The architecture adequately addresses scenario X" scored 0–9, with low scores indicating risks).

[Implementation Order]

1. **Create package skeleton**: `pyproject.toml`, `__init__.py` files, directory structure, `config.py`, `config.ini`. Verify `pip install -e .` works and `import atam_sim` succeeds.
2. **Implement domain models**: `models.py` with all enums, dataclasses, Pydantic models, and conversion functions. Write and run `test_models.py`.
3. **Implement stakeholder templates**: `stakeholders/templates.py` with all 10 predefined `StakeholderRoleTemplate` instances.
4. **Implement stakeholder factory**: `stakeholders/stakeholder_factory.py` with `ATAMStakeholderFactory`. Write and run `test_stakeholder_factory.py`.
5. **Create prompt templates**: All `.mustache` files under `prompts/`.
6. **Implement extractors**: `extraction/scenario_extractor.py`, `extraction/concern_extractor.py`, `extraction/vote_extractor.py`.
7. **Implement base phase**: `phases/base_phase.py` with `ATAMPhaseBase`.
8. **Implement scenario generation phase**: `phases/scenario_generation.py`. Write and run `test_scenario_generation.py`.
9. **Implement scenario prioritization phase**: `phases/scenario_prioritization.py`. Write and run `test_scenario_prioritization.py`.
10. **Implement ATAM session**: `session/atam_session.py`. Write and run `test_atam_session.py`.
11. **Implement report generator**: `extraction/report_generator.py`. Write and run `test_report_generator.py`.
12. **Implement remaining phases** (lower priority): `presentation_phase.py`, `approach_identification.py`, `approach_analysis.py`, `concern_identification.py`, `brainstorming_phase.py`.
13. **Create sample data**: `data/sample_architecture/` documents.
14. **Create example notebook**: `examples/atam_evaluation_example.ipynb`.
15. **Write README**: `README.md` with usage instructions and architecture overview.