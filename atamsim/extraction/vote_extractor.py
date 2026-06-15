"""
:class:`VoteExtractor` — extract priority votes from agent interactions.

Uses :class:`PriorityVoteModel` as the ``response_format`` for an LLM call to
extract a structured vote from each stakeholder's interactions during the
scenario prioritization phase.
"""

from __future__ import annotations

from tinytroupe.agent import TinyPerson

from ..models import PriorityVoteModel


class VoteExtractor:
    """Extract a structured priority vote from a stakeholder's interactions."""

    def extract_vote(self, agent: TinyPerson) -> PriorityVoteModel:
        """Extract a priority vote from an agent's interaction history.

        Args:
            agent: The stakeholder agent who voted.

        Returns:
            A :class:`PriorityVoteModel` containing the agent's votes and
            justification.

        Raises:
            NotImplementedError: Stub awaiting implementation.
        """
        raise NotImplementedError(
            "VoteExtractor.extract_vote is not yet implemented."
        )