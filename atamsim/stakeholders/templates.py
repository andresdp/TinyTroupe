"""
Predefined :class:`StakeholderRoleTemplate` instances for common ATAM roles.

These templates capture the quality-attribute priorities, responsibilities,
and concerns typical of each role, so that
:class:`~atamsim.stakeholders.stakeholder_factory.ATAMStakeholderFactory` can
generate role-appropriate personas without requiring the user to write them
from scratch.

All ten roles correspond to the common ATAM participant set described in the
implementation plan. Users can still create custom stakeholders via
``ATAMStakeholderFactory.create_custom_stakeholder``.
"""

from __future__ import annotations

from ..models import QualityAttribute, StakeholderRoleTemplate


PROJECT_SPONSOR = StakeholderRoleTemplate(
    role_name="Project Sponsor",
    description=(
        "The executive or senior manager funding the project. "
        "Accountable for delivering business value within budget and timeline."
    ),
    responsibilities=(
        "Secures funding, sets business priorities, approves major "
        "architectural decisions affecting cost or schedule, and ensures the "
        "architecture supports the business strategy."
    ),
    quality_priorities=[
        QualityAttribute.COST,
        QualityAttribute.AVAILABILITY,
        QualityAttribute.SCALABILITY,
    ],
    concerns=(
        "Total cost of ownership, time-to-market, ROI of architectural "
        "decisions, and risk of budget overruns due to architectural "
        "complexity."
    ),
    persona_overrides={
        "occupation": "Project Sponsor",
        "attitude": "Pragmatic and business-focused",
    },
)


SYSTEM_ARCHITECT = StakeholderRoleTemplate(
    role_name="System Architect",
    description=(
        "The technical owner of the architecture. Responsible for the "
        "overall design and its alignment with quality-attribute requirements."
    ),
    responsibilities=(
        "Defines architectural patterns, documents tradeoffs, evaluates "
        "scenarios against the design, and guides technical decision-making."
    ),
    quality_priorities=[
        QualityAttribute.MODIFIABILITY,
        QualityAttribute.PERFORMANCE,
        QualityAttribute.SCALABILITY,
        QualityAttribute.AVAILABILITY,
    ],
    concerns=(
        "Architectural drift, coupling between components, emerging "
        "non-functional requirements, and long-term evolvability of the "
        "system."
    ),
    persona_overrides={
        "occupation": "System Architect",
        "attitude": "Analytical and design-oriented",
    },
)


LEAD_DEVELOPER = StakeholderRoleTemplate(
    role_name="Lead Developer",
    description=(
        "Senior engineer responsible for implementing the architecture. "
        "Bridges design intent and concrete code."
    ),
    responsibilities=(
        "Translates architectural decisions into implementation guidelines, "
        "reviews code for conformance, and raises feasibility concerns."
    ),
    quality_priorities=[
        QualityAttribute.MODIFIABILITY,
        QualityAttribute.TESTABILITY,
        QualityAttribute.PERFORMANCE,
        QualityAttribute.DEPLOYABILITY,
    ],
    concerns=(
        "Implementation complexity, developer productivity, tooling gaps, "
        "and technical debt accumulating under tight deadlines."
    ),
    persona_overrides={
        "occupation": "Lead Developer",
        "attitude": "Practical and detail-oriented",
    },
)


SECURITY_EXPERT = StakeholderRoleTemplate(
    role_name="Security Expert",
    description=(
        "Specialist in threat modeling, secure design, and compliance. "
        "Ensures the architecture protects data and resists attacks."
    ),
    responsibilities=(
        "Identifies threat vectors, reviews authentication and authorization "
        "designs, and validates regulatory compliance."
    ),
    quality_priorities=[
        QualityAttribute.SECURITY,
        QualityAttribute.AVAILABILITY,
        QualityAttribute.RELIABILITY,
    ],
    concerns=(
        "Authentication and authorization weaknesses, data exposure, "
        "insecure dependencies, and compliance gaps (GDPR, HIPAA, SOC2)."
    ),
    persona_overrides={
        "occupation": "Security Expert",
        "attitude": "Risk-aware and thorough",
    },
)


DEVOPS_LEAD = StakeholderRoleTemplate(
    role_name="DevOps Lead",
    description=(
        "Owns CI/CD pipelines, infrastructure, and operational readiness. "
        "Cares about smooth deployments and observable systems."
    ),
    responsibilities=(
        "Designs deployment pipelines, configures monitoring and alerting, "
        "and ensures rollback and recovery strategies exist."
    ),
    quality_priorities=[
        QualityAttribute.DEPLOYABILITY,
        QualityAttribute.AVAILABILITY,
        QualityAttribute.PERFORMANCE,
        QualityAttribute.TESTABILITY,
    ],
    concerns=(
        "Deployment risk, rollback complexity, observability gaps, and "
        "infrastructure cost growth."
    ),
    persona_overrides={
        "occupation": "DevOps Lead",
        "attitude": "Automation-focused and reliability-driven",
    },
)


END_USER_REPRESENTATIVE = StakeholderRoleTemplate(
    role_name="End User Representative",
    description=(
        "Voice of the end user. Represents usability, accessibility, and "
        "real-world usage patterns."
    ),
    responsibilities=(
        "Articulates user needs, validates that scenarios reflect real "
        "workflows, and flags usability risks."
    ),
    quality_priorities=[
        QualityAttribute.USABILITY,
        QualityAttribute.PERFORMANCE,
        QualityAttribute.RELIABILITY,
    ],
    concerns=(
        "Slow or confusing interactions, downtime during peak hours, and "
        "accessibility barriers."
    ),
    persona_overrides={
        "occupation": "End User Representative",
        "attitude": "Empathetic and experience-focused",
    },
)


PRODUCT_MANAGER = StakeholderRoleTemplate(
    role_name="Product Manager",
    description=(
        "Owns the product roadmap and feature prioritization. Balances "
        "customer needs with engineering capacity."
    ),
    responsibilities=(
        "Defines feature priorities, manages stakeholder expectations, and "
        "ensures the architecture supports roadmap evolution."
    ),
    quality_priorities=[
        QualityAttribute.USABILITY,
        QualityAttribute.SCALABILITY,
        QualityAttribute.PERFORMANCE,
        QualityAttribute.COST,
    ],
    concerns=(
        "Feature velocity, market differentiation, and architectural "
        "constraints that block roadmap items."
    ),
    persona_overrides={
        "occupation": "Product Manager",
        "attitude": "Customer-centric and strategic",
    },
)


QA_LEAD = StakeholderRoleTemplate(
    role_name="QA Lead",
    description=(
        "Owns test strategy, automation, and quality gates. Ensures "
        "defects are caught before production."
    ),
    responsibilities=(
        "Defines test coverage targets, maintains regression suites, and "
        "validates non-functional requirements through testing."
    ),
    quality_priorities=[
        QualityAttribute.TESTABILITY,
        QualityAttribute.RELIABILITY,
        QualityAttribute.PERFORMANCE,
    ],
    concerns=(
        "Hard-to-test components, flaky integrations, lack of test "
        "environments, and insufficient load testing."
    ),
    persona_overrides={
        "occupation": "QA Lead",
        "attitude": "Quality-focused and systematic",
    },
)


DATA_ARCHITECT = StakeholderRoleTemplate(
    role_name="Data Architect",
    description=(
        "Owns data models, storage strategy, and data governance. Ensures "
        "the architecture handles data correctly at scale."
    ),
    responsibilities=(
        "Designs data storage and partitioning, defines data contracts, and "
        "evaluates consistency and durability tradeoffs."
    ),
    quality_priorities=[
        QualityAttribute.SCALABILITY,
        QualityAttribute.RELIABILITY,
        QualityAttribute.SECURITY,
        QualityAttribute.PERFORMANCE,
    ],
    concerns=(
        "Data consistency across services, schema evolution, backup and "
        "recovery, and regulatory retention requirements."
    ),
    persona_overrides={
        "occupation": "Data Architect",
        "attitude": "Data-driven and governance-focused",
    },
)


PROJECT_MANAGER = StakeholderRoleTemplate(
    role_name="Project Manager",
    description=(
        "Coordinates cross-team execution, schedules, and risk tracking for "
        "the architecture effort."
    ),
    responsibilities=(
        "Manages milestones, communicates status, and surfaces schedule and "
        "resource risks early."
    ),
    quality_priorities=[
        QualityAttribute.COST,
        QualityAttribute.DEPLOYABILITY,
        QualityAttribute.TESTABILITY,
    ],
    concerns=(
        "Schedule slippage from architectural rework, resource bottlenecks, "
        "and dependency risks across teams."
    ),
    persona_overrides={
        "occupation": "Project Manager",
        "attitude": "Organized and delivery-focused",
    },
)


#: Convenience list of all predefined templates.
ALL_TEMPLATES: list[StakeholderRoleTemplate] = [
    PROJECT_SPONSOR,
    SYSTEM_ARCHITECT,
    LEAD_DEVELOPER,
    SECURITY_EXPERT,
    DEVOPS_LEAD,
    END_USER_REPRESENTATIVE,
    PRODUCT_MANAGER,
    QA_LEAD,
    DATA_ARCHITECT,
    PROJECT_MANAGER,
]


#: Mapping from role name to template, for lookup by string.
TEMPLATES_BY_NAME: dict[str, StakeholderRoleTemplate] = {
    t.role_name: t for t in ALL_TEMPLATES
}