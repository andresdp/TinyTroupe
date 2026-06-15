"""
Unit tests for the domain models in :mod:`atamsim.models`.

These are pure unit tests — no LLM calls, no TinyTroupe simulation state.
They validate enum parsing, dataclass construction, Pydantic model
validation, and the conversion helper functions.
"""

from __future__ import annotations

import pytest

from atamsim.models import (
    ATAMPhase,
    ATAMReport,
    ArchitecturalApproach,
    Concern,
    ConcernItemModel,
    ConcernType,
    PriorityVoteModel,
    QualityAttribute,
    Scenario,
    ScenarioItemModel,
    ScenariosExtractionModel,
    StakeholderRoleTemplate,
    approach_item_to_dataclass,
    concern_item_to_dataclass,
    parse_concern_type,
    parse_quality_attribute,
    scenario_item_to_dataclass,
)


# ####################################################################
# Enum tests
# ####################################################################


class TestQualityAttributeEnum:
    """Tests for the QualityAttribute enum."""

    def test_enum_values(self):
        assert QualityAttribute.AVAILABILITY.value == "availability"
        assert QualityAttribute.PERFORMANCE.value == "performance"
        assert QualityAttribute.SECURITY.value == "security"

    def test_enum_count(self):
        assert len(list(QualityAttribute)) == 10

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("availability", QualityAttribute.AVAILABILITY),
            ("Availability", QualityAttribute.AVAILABILITY),
            ("AVAILABILITY", QualityAttribute.AVAILABILITY),
            ("performance", QualityAttribute.PERFORMANCE),
            ("security", QualityAttribute.SECURITY),
            ("  performance  ", QualityAttribute.PERFORMANCE),
        ],
    )
    def test_parse_quality_attribute(self, input_str, expected):
        assert parse_quality_attribute(input_str) == expected

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("latency", QualityAttribute.PERFORMANCE),
            ("throughput", QualityAttribute.PERFORMANCE),
            ("maintainability", QualityAttribute.MODIFIABILITY),
            ("safety", QualityAttribute.RELIABILITY),
            ("robustness", QualityAttribute.RELIABILITY),
            ("flexibility", QualityAttribute.MODIFIABILITY),
            ("cost-effectiveness", QualityAttribute.COST),
            ("budget", QualityAttribute.COST),
        ],
    )
    def test_parse_quality_attribute_aliases(self, alias, expected):
        assert parse_quality_attribute(alias) == expected

    def test_parse_quality_attribute_none(self):
        assert parse_quality_attribute(None) == QualityAttribute.PERFORMANCE

    def test_parse_quality_attribute_unrecognized_defaults(self):
        assert (
            parse_quality_attribute("totally_made_up")
            == QualityAttribute.PERFORMANCE
        )


class TestConcernTypeEnum:
    """Tests for the ConcernType enum."""

    def test_enum_values(self):
        assert ConcernType.RISK.value == "risk"
        assert ConcernType.NON_RISK.value == "non_risk"
        assert ConcernType.SENSITIVITY_POINT.value == "sensitivity_point"
        assert ConcernType.TRADEOFF.value == "tradeoff"

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("risk", ConcernType.RISK),
            ("RISK", ConcernType.RISK),
            ("non_risk", ConcernType.NON_RISK),
            ("non-risk", ConcernType.NON_RISK),
            ("sensitivity_point", ConcernType.SENSITIVITY_POINT),
            ("sensitivity", ConcernType.SENSITIVITY_POINT),
            ("tradeoff", ConcernType.TRADEOFF),
            ("trade_off", ConcernType.TRADEOFF),
            ("trade-off", ConcernType.TRADEOFF),
        ],
    )
    def test_parse_concern_type(self, input_str, expected):
        assert parse_concern_type(input_str) == expected

    def test_parse_concern_type_none(self):
        assert parse_concern_type(None) == ConcernType.RISK

    def test_parse_concern_type_unrecognized_defaults(self):
        assert parse_concern_type("nonsense") == ConcernType.RISK


class TestATAMPhaseEnum:
    """Tests for the ATAMPhase enum."""

    def test_enum_values(self):
        assert ATAMPhase.PRESENTATION.value == "presentation"
        assert ATAMPhase.SCENARIO_GENERATION.value == "scenario_generation"
        assert (
            ATAMPhase.SCENARIO_PRIORITIZATION.value
            == "scenario_prioritization"
        )

    def test_enum_count(self):
        assert len(list(ATAMPhase)) == 7


# ####################################################################
# Dataclass tests
# ####################################################################


class TestScenarioDataclass:
    """Tests for the Scenario dataclass."""

    def _make_scenario(self, **overrides):
        defaults = dict(
            id="s1",
            name="Peak Load Checkout",
            description="Checkout under peak load",
            stimulus_source="external user",
            stimulus="user initiates checkout",
            environment="peak load (Black Friday)",
            artifact="order service",
            response="processes order",
            response_measure="latency < 500ms p95",
            quality_attribute=QualityAttribute.PERFORMANCE,
        )
        defaults.update(overrides)
        return Scenario(**defaults)

    def test_construction_required_fields(self):
        s = self._make_scenario()
        assert s.name == "Peak Load Checkout"
        assert s.quality_attribute == QualityAttribute.PERFORMANCE

    def test_default_optional_fields(self):
        s = self._make_scenario()
        assert s.generated_by is None
        assert s.priority_score is None
        assert s.votes == {}

    def test_default_dict_factory_isolation(self):
        """Each instance should get its own ``votes`` dict."""
        s1 = self._make_scenario(id="s1")
        s2 = self._make_scenario(id="s2")
        s1.votes["alice"] = 5
        assert "alice" not in s2.votes


class TestConcernDataclass:
    """Tests for the Concern dataclass."""

    def test_construction(self):
        c = Concern(
            id="c1",
            type=ConcernType.RISK,
            description="Single point of failure in payment service",
        )
        assert c.type == ConcernType.RISK
        assert c.related_scenarios == []
        assert c.related_attributes == []
        assert c.severity is None
        assert c.mitigation is None

    def test_construction_with_optional_fields(self):
        c = Concern(
            id="c2",
            type=ConcernType.TRADEOFF,
            description="Caching improves read perf but risks stale data",
            severity="high",
            architectural_element="product service",
            related_scenarios=["s1", "s2"],
            related_attributes=[QualityAttribute.PERFORMANCE, QualityAttribute.AVAILABILITY],
        )
        assert c.severity == "high"
        assert len(c.related_scenarios) == 2


class TestArchitecturalApproachDataclass:
    """Tests for the ArchitecturalApproach dataclass."""

    def test_construction(self):
        a = ArchitecturalApproach(
            name="API Gateway",
            description="Centralized entry point for all requests",
        )
        assert a.name == "API Gateway"
        assert a.patterns == []
        assert a.attributes_addressed == []

    def test_construction_with_lists(self):
        a = ArchitecturalApproach(
            name="CQRS",
            description="Separate read and write models",
            patterns=["CQRS", "Eventual Consistency"],
            attributes_addressed=[QualityAttribute.PERFORMANCE, QualityAttribute.SCALABILITY],
        )
        assert len(a.patterns) == 2
        assert len(a.attributes_addressed) == 2


class TestATAMReportDataclass:
    """Tests for the ATAMReport dataclass."""

    def test_construction(self):
        r = ATAMReport(
            project_name="ShopFlow",
            evaluation_date="2025-01-01",
            business_drivers="Expand to 3 regions",
            architecture_summary="Microservices on Kubernetes",
        )
        assert r.project_name == "ShopFlow"
        assert r.scenarios == []
        assert r.prioritized_scenarios == []
        assert r.concerns == []
        assert r.approaches == []
        assert r.phase_summaries == {}
        assert r.stakeholders == []


class TestStakeholderRoleTemplateDataclass:
    """Tests for the StakeholderRoleTemplate dataclass."""

    def test_construction(self):
        t = StakeholderRoleTemplate(
            role_name="System Architect",
            description="Owns the architecture",
            responsibilities="Makes architectural decisions",
            quality_priorities=[QualityAttribute.MODIFIABILITY, QualityAttribute.PERFORMANCE],
            concerns="Coupling between services",
        )
        assert t.role_name == "System Architect"
        assert len(t.quality_priorities) == 2
        assert t.persona_overrides == {}


# ####################################################################
# Pydantic model tests
# ####################################################################


class TestScenarioItemModel:
    """Tests for the ScenarioItemModel Pydantic model."""

    def _valid_data(self):
        return dict(
            name="Peak Load Checkout",
            description="Checkout under peak load",
            stimulus_source="external user",
            stimulus="user initiates checkout",
            environment="peak load",
            artifact="order service",
            response="processes order",
            response_measure="latency < 500ms",
            quality_attribute="performance",
        )

    def test_valid_construction(self):
        m = ScenarioItemModel(**self._valid_data())
        assert m.name == "Peak Load Checkout"
        assert m.quality_attribute == "performance"

    def test_missing_required_field_raises(self):
        data = self._valid_data()
        del data["name"]
        with pytest.raises(Exception):
            ScenarioItemModel(**data)


class TestScenariosExtractionModel:
    """Tests for the ScenariosExtractionModel Pydantic model."""

    def test_empty_default(self):
        m = ScenariosExtractionModel()
        assert m.scenarios == []

    def test_with_items(self):
        m = ScenariosExtractionModel(
            scenarios=[
                ScenarioItemModel(
                    name="S1",
                    description="d1",
                    stimulus_source="user",
                    stimulus="click",
                    environment="normal",
                    artifact="api",
                    response="ok",
                    response_measure="200ms",
                    quality_attribute="performance",
                ),
            ]
        )
        assert len(m.scenarios) == 1


class TestPriorityVoteModel:
    """Tests for the PriorityVoteModel Pydantic model."""

    def test_empty_default(self):
        m = PriorityVoteModel()
        assert m.votes == []
        assert m.justification == ""

    def test_with_votes(self):
        m = PriorityVoteModel(
            votes=[
                {"scenario_name": "S1", "score": 8},
                {"scenario_name": "S2", "score": 5},
            ],
            justification="S1 is critical for peak season",
        )
        assert len(m.votes) == 2
        assert m.votes[0]["score"] == 8


class TestConcernItemModel:
    """Tests for the ConcernItemModel Pydantic model."""

    def test_valid_construction(self):
        m = ConcernItemModel(
            type="risk",
            description="Single point of failure",
            severity="high",
        )
        assert m.type == "risk"
        assert m.severity == "high"
        assert m.related_scenarios == []

    def test_optional_fields_default(self):
        m = ConcernItemModel(
            type="tradeoff",
            description="Caching vs freshness",
            severity="medium",
        )
        assert m.architectural_element is None
        assert m.mitigation is None


# ####################################################################
# Conversion helper tests
# ####################################################################


class TestScenarioItemToDataclass:
    """Tests for scenario_item_to_dataclass()."""

    def test_conversion_basic(self):
        item = ScenarioItemModel(
            name="Peak Checkout",
            description="Checkout during peak",
            stimulus_source="external user",
            stimulus="checkout request",
            environment="peak load",
            artifact="order service",
            response="process order",
            response_measure="< 500ms p95",
            quality_attribute="performance",
        )
        s = scenario_item_to_dataclass(item)
        assert s.name == "Peak Checkout"
        assert s.quality_attribute == QualityAttribute.PERFORMANCE
        assert s.generated_by is None
        assert s.id.startswith("scenario")

    def test_conversion_with_generated_by(self):
        item = ScenarioItemModel(
            name="S1",
            description="d",
            stimulus_source="src",
            stimulus="stim",
            environment="env",
            artifact="art",
            response="resp",
            response_measure="meas",
            quality_attribute="security",
        )
        s = scenario_item_to_dataclass(item, generated_by="Alice")
        assert s.generated_by == "Alice"

    def test_conversion_invalid_quality_attribute_defaults(self):
        item = ScenarioItemModel(
            name="S1",
            description="d",
            stimulus_source="src",
            stimulus="stim",
            environment="env",
            artifact="art",
            response="resp",
            response_measure="meas",
            quality_attribute="nonsense",
        )
        s = scenario_item_to_dataclass(item)
        assert s.quality_attribute == QualityAttribute.PERFORMANCE


class TestConcernItemToDataclass:
    """Tests for concern_item_to_dataclass()."""

    def test_conversion_basic(self):
        item = ConcernItemModel(
            type="risk",
            description="SPOF in payment",
            severity="HIGH",
            related_attributes=["availability", "security"],
        )
        c = concern_item_to_dataclass(item)
        assert c.type == ConcernType.RISK
        assert c.severity == "high"  # lowercased
        assert c.related_attributes == [
            QualityAttribute.AVAILABILITY,
            QualityAttribute.SECURITY,
        ]
        assert c.id.startswith("concern")

    def test_conversion_with_identified_by(self):
        item = ConcernItemModel(
            type="tradeoff",
            description="cache vs freshness",
            severity="medium",
        )
        c = concern_item_to_dataclass(item, identified_by="Bob")
        assert c.identified_by == "Bob"


class TestApproachItemToDataclass:
    """Tests for approach_item_to_dataclass()."""

    def test_conversion(self):
        from atamsim.models import ApproachItemModel

        item = ApproachItemModel(
            name="CQRS",
            description="Separate read/write models",
            patterns=["CQRS"],
            attributes_addressed=["performance", "scalability"],
        )
        a = approach_item_to_dataclass(item)
        assert a.name == "CQRS"
        assert a.patterns == ["CQRS"]
        assert a.attributes_addressed == [
            QualityAttribute.PERFORMANCE,
            QualityAttribute.SCALABILITY,
        ]