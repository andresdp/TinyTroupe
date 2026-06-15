"""
pytest fixtures for atamsim tests.

Provides:
- Mock architecture context (business drivers + architecture docs path).
- Cached TinyTroupe configuration for deterministic, low-cost test runs.
- Sample stakeholder agents for integration tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Path to the sample architecture data bundled with the package.
SAMPLE_ARCH_PATH = Path(__file__).parent.parent / "data" / "sample_architecture"


@pytest.fixture
def sample_architecture_path() -> Path:
    """Path to the bundled sample architecture documents."""
    return SAMPLE_ARCH_PATH


@pytest.fixture
def sample_business_drivers() -> str:
    """Sample business drivers text for testing."""
    return (
        "ShopFlow is expanding to 3 new regions (EU, UK, LATAM) within "
        "12 months. Peak season traffic is expected to reach 500K "
        "concurrent users. Checkout availability must be 99.99%."
    )


@pytest.fixture
def sample_architecture_summary() -> str:
    """Sample architecture summary text for testing."""
    return (
        "Microservices architecture on Kubernetes (EKS) with Istio service "
        "mesh. Core services: API Gateway, Product, Cart, Order, Payment, "
        "User, Notification. Data stores: PostgreSQL, Redis, Elasticsearch, "
        "Kafka. Patterns: API Gateway, CQRS, Event Sourcing, Saga, "
        "Circuit Breaker."
    )


@pytest.fixture
def sample_scenario_data():
    """Valid scenario data for constructing test scenarios."""
    return dict(
        id="test-scn-1",
        name="Peak Load Checkout",
        description="Checkout flow under peak Black Friday load",
        stimulus_source="external user",
        stimulus="user initiates checkout",
        environment="peak load (Black Friday)",
        artifact="order service",
        response="processes order through checkout saga",
        response_measure="latency < 500ms p95",
        quality_attribute="performance",
    )


@pytest.fixture
def sample_concern_data():
    """Valid concern data for constructing test concerns."""
    return dict(
        id="test-concern-1",
        type="risk",
        description="Single point of failure in payment service integration",
        severity="high",
        related_scenarios=["test-scn-1"],
        related_attributes=["availability", "security"],
        architectural_element="payment service",
    )