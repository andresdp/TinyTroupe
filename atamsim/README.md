# atamsim

**ATAM (Architecture Tradeoff Analysis Method) multi-agent simulation extension for TinyTroupe.**

`atamsim` simulates stakeholder-driven software architecture evaluations using the
Architecture Tradeoff Analysis Method. Instead of gathering human stakeholders in
a room, ATAM sessions are run as multi-agent simulations: each stakeholder is an
AI agent with a role-specific persona, and the evaluation phases (scenario
generation, prioritization, risk identification, etc.) are orchestrated as
simulation steps.

## Status

**Scaffolded** — the package structure, domain models, stakeholder templates,
phase orchestration stubs, extraction stubs, prompt templates, sample data, and
unit tests for the model layer are in place. The core logic of phases and
extractors is stubbed for incremental implementation.

See `docs/atam_implementation_plan.md` for the full design.

## Installation

```bash
# From the repository root
cd atamsim
pip install -e .
```

Requires `tinytroupe` (installed from the parent repo), `pydantic>=2.0`, and
`chevron`.

## Quick Start (once phases are implemented)

```python
from atamsim import ATAMSession, ATAMStakeholderFactory
from atamsim.stakeholders.templates import SYSTEM_ARCHITECT, SECURITY_EXPERT
from atamsim.models import ATAMPhase

# 1. Create stakeholders from predefined templates
factory = ATAMStakeholderFactory(
    project_context="ShopFlow e-commerce platform",
    architecture_docs_path="./atamsim/data/sample_architecture",
)
stakeholders = factory.create_panel([SYSTEM_ARCHITECT, SECURITY_EXPERT])

# 2. Create an ATAM session
session = ATAMSession(
    name="ShopFlow ATAM",
    business_drivers="Expand to 3 regions; 99.99% checkout availability",
    architecture_docs_path="./atamsim/data/sample_architecture",
    stakeholders=stakeholders,
)

# 3. Run evaluation phases
session.run_phase(ATAMPhase.SCENARIO_GENERATION)
session.run_phase(ATAMPhase.SCENARIO_PRIORITIZATION)

# 4. Generate report
report = session.generate_report()
```

## Package Structure

```
atamsim/
├── pyproject.toml              # Package metadata
├── config.ini                  # ATAM-specific config
├── config.py                   # Config loader
├── models.py                   # Enums, dataclasses, Pydantic models, helpers
├── __init__.py                 # Public API exports
├── stakeholders/
│   ├── templates.py            # 10 predefined role templates
│   └── stakeholder_factory.py  # ATAMStakeholderFactory(TinyPersonFactory)
├── session/
│   └── atam_session.py         # ATAMSession(TinyWorld)
├── phases/
│   ├── base_phase.py           # ATAMPhaseBase abstract class
│   ├── presentation_phase.py
│   ├── scenario_generation.py
│   ├── scenario_prioritization.py
│   ├── approach_identification.py
│   ├── approach_analysis.py
│   ├── concern_identification.py
│   └── brainstorming_phase.py
├── extraction/
│   ├── scenario_extractor.py
│   ├── concern_extractor.py
│   ├── vote_extractor.py
│   └── report_generator.py
├── prompts/                    # Mustache templates for LLM prompts
├── data/sample_architecture/   # Sample architecture docs for demos
└── tests/                      # Unit and integration tests
```

## Architecture

The package follows TinyTroupe's architectural conventions:

| ATAM Concept       | TinyTroupe Abstraction               |
|--------------------|--------------------------------------|
| Stakeholder        | `TinyPerson`                         |
| Evaluation session | `TinyWorld` (`ATAMSession`)          |
| Facilitator        | `ATAMSession` methods                |
| Architecture doc   | Grounding document                   |
| Scenario           | `Scenario` dataclass                 |
| Risk/Tradeoff      | `Concern` dataclass                  |
| Prioritization     | `PriorityVoteModel` + aggregation    |
| Report             | `ATAMReport` dataclass               |

The package depends only on TinyTroupe's public API — no changes to the
`tinytroupe/` source tree are required.

## Predefined Stakeholder Templates

| Constant                 | Role                 | Key Quality Priorities                     |
|--------------------------|----------------------|--------------------------------------------|
| `PROJECT_SPONSOR`        | Project Sponsor      | Cost, Availability                         |
| `SYSTEM_ARCHITECT`       | System Architect     | Modifiability, Performance, Scalability    |
| `LEAD_DEVELOPER`         | Lead Developer       | Modifiability, Testability                 |
| `SECURITY_EXPERT`        | Security Expert      | Security, Reliability                      |
| `DEVOPS_LEAD`            | DevOps Lead          | Deployability, Reliability                 |
| `END_USER_REPRESENTATIVE`| End User Rep.        | Usability, Performance                     |
| `PRODUCT_MANAGER`        | Product Manager      | Usability, Scalability                     |
| `QA_LEAD`                | QA Lead              | Testability, Reliability                   |
| `DATA_ARCHITECT`         | Data Architect       | Reliability, Scalability                   |
| `PROJECT_MANAGER`        | Project Manager      | Cost, Modifiability                        |

## Running Tests

```bash
cd atamsim
python -m pytest tests/ -v
```

The model-layer tests are pure unit tests (no LLM calls). Integration tests for
phases and extractors will use TinyTroupe's `CACHE_API_CALLS` mechanism.

## License

MIT