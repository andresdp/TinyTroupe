"""
Stakeholder generation for ATAM simulations.

This subpackage provides :class:`ATAMStakeholderFactory` for creating
``TinyPerson`` agents from predefined role templates, and the templates
themselves.
"""

from ..models import StakeholderRoleTemplate
from .stakeholder_factory import ATAMStakeholderFactory
from .templates import ALL_TEMPLATES, TEMPLATES_BY_NAME

__all__ = [
    "ATAMStakeholderFactory",
    "StakeholderRoleTemplate",
    "ALL_TEMPLATES",
    "TEMPLATES_BY_NAME",
]