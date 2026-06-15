"""
:class:`ATAMStakeholderFactory` — template-driven stakeholder generation.

This class extends :class:`tinytroupe.factory.TinyPersonFactory` to add:

* **Template-based generation** — create stakeholders from any of the
  predefined :class:`StakeholderRoleTemplate` instances in
  :mod:`atamsim.stakeholders.templates`.
* **Grounding faculty attachment** — automatically attach
  :class:`tinytroupe.agent.mental_faculty.FilesAndWebGroundingFaculty` so
  stakeholders can ``LIST_DOCUMENTS`` and ``CONSULT`` architecture
  artifacts during the simulation.
* **Recall faculty attachment** — gives stakeholders semantic memory recall.

The actual persona generation (name, demographics, personality) is delegated
to ``TinyPersonFactory.generate_person``, which uses an LLM call. This stub
defines the complete signature and docstrings; the method bodies are
intentionally left as ``NotImplementedError`` for incremental implementation.
"""

from __future__ import annotations

from typing import List, Optional

from tinytroupe.agent import TinyPerson
from tinytroupe.factory import TinyPersonFactory

from ..config import config
from ..models import QualityAttribute, StakeholderRoleTemplate


class ATAMStakeholderFactory(TinyPersonFactory):
    """Factory for generating ATAM stakeholder agents from templates.

    Extends :class:`TinyPersonFactory` to add template-driven generation and
    automatic grounding/recall faculty attachment.
    """

    def __init__(
        self,
        project_context: str,
        architecture_docs_path: Optional[str] = None,
    ) -> None:
        """Initialize the factory.

        Args:
            project_context: A description of the project being evaluated.
                This is merged into each stakeholder's persona context.
            architecture_docs_path: Optional path to a folder containing
                architecture documents. When provided (and when
                ``ENABLE_GROUNDING_DOCUMENTS`` is true in config), each
                generated agent receives a
                :class:`FilesAndWebGroundingFaculty` pointing here.
        """
        self.project_context = project_context
        self.architecture_docs_path = architecture_docs_path
        self._created_roles: List[str] = []

        # Build a combined context string for the parent factory.
        full_context = self._build_factory_context(project_context)
        super().__init__(context=full_context)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_from_template(
        self,
        template: StakeholderRoleTemplate,
        name: Optional[str] = None,
    ) -> TinyPerson:
        """Create a single stakeholder agent from a predefined template.

        Args:
            template: The role template to use.
            name: Optional explicit name for the agent. If ``None``, the
                factory generates a context-appropriate name.

        Returns:
            A :class:`TinyPerson` with the template's persona fragment,
            grounding faculty (if configured), and recall faculty attached.

        Raises:
            NotImplementedError: This method is a stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMStakeholderFactory.create_from_template is not yet implemented. "
            "This is part of the Phase 4 scaffolding plan (stakeholder generation)."
        )

    def create_panel(
        self,
        templates: List[StakeholderRoleTemplate],
        names: Optional[List[str]] = None,
    ) -> List[TinyPerson]:
        """Create a panel of stakeholders from multiple templates.

        Args:
            templates: List of role templates, one per desired stakeholder.
            names: Optional list of explicit names, aligned with *templates*.

        Returns:
            A list of :class:`TinyPerson` agents.

        Raises:
            NotImplementedError: This method is a stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMStakeholderFactory.create_panel is not yet implemented. "
            "This is part of the Phase 4 scaffolding plan (stakeholder generation)."
        )

    def create_custom_stakeholder(
        self,
        role_name: str,
        description: str,
        quality_priorities: List[QualityAttribute],
        concerns: str,
    ) -> TinyPerson:
        """Create a stakeholder with custom parameters (no template).

        Args:
            role_name: The role title (e.g., "Accessibility Specialist").
            description: A brief description of the role.
            quality_priorities: Which quality attributes this role prioritizes.
            concerns: Role-specific concerns to embed in the persona.

        Returns:
            A :class:`TinyPerson` with the custom persona.

        Raises:
            NotImplementedError: This method is a stub awaiting implementation.
        """
        raise NotImplementedError(
            "ATAMStakeholderFactory.create_custom_stakeholder is not yet implemented. "
            "This is part of the Phase 4 scaffolding plan (stakeholder generation)."
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_factory_context(self, project_context: str) -> str:
        """Build the context string passed to the parent ``TinyPersonFactory``."""
        grounding_note = ""
        if self.architecture_docs_path and config.get_bool(
            "ENABLE_GROUNDING_DOCUMENTS", True
        ):
            grounding_note = (
                f"\n\nArchitecture documents are available at: "
                f"{self.architecture_docs_path}. Stakeholders can consult "
                f"these documents during the evaluation."
            )
        return (
            f"An ATAM (Architecture Tradeoff Analysis Method) evaluation session.\n"
            f"Project context: {project_context}{grounding_note}"
        )

    def _build_persona_context(self, template: StakeholderRoleTemplate) -> str:
        """Merge template fields into a context string for persona generation.

        Args:
            template: The role template.

        Returns:
            A formatted string combining role name, responsibilities,
            quality priorities, and concerns.
        """
        priorities_str = ", ".join(qa.value for qa in template.quality_priorities)
        return (
            f"Role: {template.role_name}\n"
            f"Description: {template.description}\n"
            f"Responsibilities: {template.responsibilities}\n"
            f"Quality attribute priorities: {priorities_str}\n"
            f"Specific concerns: {template.concerns}\n"
            f"Project context: {self.project_context}"
        )