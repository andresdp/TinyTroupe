"""
:class:`ConcernExtractor` — extract risks/tradeoffs/sensitivity points.

Wraps :class:`tinytroupe.extraction.ResultsExtractor` with a concern-specific
prompt template and :class:`ConcernsExtractionModel` parsing. Converts the
LLM output to :class:`Concern` dataclass instances.
"""

from __future__ import annotations

from typing import List, Optional

from tinytroupe.agent import TinyPerson
from tinytroupe.environment import TinyWorld

from ..models import Concern


class ConcernExtractor:
    """Extract structured ATAM concerns from agent/world interaction histories."""

    def __init__(self, prompt_template_path: Optional[str] = None) -> None:
        """Initialize the extractor.

        Args:
            prompt_template_path: Optional path to a Mustache template for the
                extraction prompt. Defaults to the bundled
                ``prompts/concern_extraction.mustache``.
        """
        self.prompt_template_path = prompt_template_path

    def extract_from_agent(
        self, agent: TinyPerson, scenario_context: Optional[str] = None
    ) -> List[Concern]:
        """Extract concerns from a single agent's interaction history.

        Args:
            agent: The stakeholder agent.
            scenario_context: Optional text describing the scenario under
                analysis, to focus the extraction.

        Returns:
            A list of :class:`Concern` instances.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ConcernExtractor.extract_from_agent is not yet implemented."
        )

    def extract_from_world(
        self, world: TinyWorld, scenario_context: Optional[str] = None
    ) -> List[Concern]:
        """Extract concerns from the full world interaction history.

        Args:
            world: The simulation world.
            scenario_context: Optional text describing the scenario under
                analysis.

        Returns:
            A list of :class:`Concern` instances.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "ConcernExtractor.extract_from_world is not yet implemented."
        )