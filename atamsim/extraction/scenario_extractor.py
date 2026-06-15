"""
:class:`ScenarioExtractor` — extract structured scenarios from agent interactions.

Wraps :class:`tinytroupe.extraction.ResultsExtractor` with a scenario-specific
prompt template and :class:`ScenariosExtractionModel` parsing. Converts the
LLM output to :class:`Scenario` dataclass instances.
"""

from __future__ import annotations

from typing import List, Optional

from tinytroupe.agent import TinyPerson

from ..models import Scenario


class ScenarioExtractor:
    """Extract structured ATAM scenarios from agent interaction histories."""

    def __init__(self, prompt_template_path: Optional[str] = None) -> None:
        """Initialize the extractor.

        Args:
            prompt_template_path: Optional path to a Mustache template for the
                extraction prompt. Defaults to the bundled
                ``prompts/scenario_generation.mustache``.
        """
        self.prompt_template_path = prompt_template_path

    def extract_from_agent(self, agent: TinyPerson) -> List[Scenario]:
        """Extract scenarios from a single agent's interaction history.

        Args:
            agent: The stakeholder agent to extract scenarios from.

        Returns:
            A list of :class:`Scenario` instances.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioExtractor.extract_from_agent is not yet implemented."
        )

    def extract_from_agents(self, agents: List[TinyPerson]) -> List[Scenario]:
        """Extract scenarios from multiple agents, tagging each with ``generated_by``.

        Args:
            agents: List of stakeholder agents.

        Returns:
            A consolidated list of :class:`Scenario` instances.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ScenarioExtractor.extract_from_agents is not yet implemented."
        )