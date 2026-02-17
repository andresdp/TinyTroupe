"""
Scenario tests for the web browsing mental faculty.

These tests demonstrate end-to-end workflows where TinyTroupe agents
equipped with ``TinyWebBrowserFaculty`` autonomously browse real websites,
extract information, and report findings — just as they would autonomously
decide to ``WRITE_DOCUMENT`` when given a ``TinyToolUse`` faculty.

**Multi-turn browsing:**  Unlike tool-use faculties (where the agent
generates the output itself and a single ``listen_and_act`` suffices), web
browsing is inherently *reactive* — the agent must observe what the browser
shows, decide on the next step, observe again, and so on.  A single
``listen_and_act`` call produces only one LLM inference, so all actions
(BROWSE, THINK, TALK, DONE) are generated before the agent can see the
browser's response.  We use a ``TinyWorld`` with ``world.run(steps)`` to
drive the multi-turn perception–action loop idiomatically.

Uses ``AutoUserInteraction`` to avoid blocking on prompts, and runs
headless for CI compatibility.  Marked ``@pytest.mark.slow`` because they
launch a real browser and make LLM calls.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.examples import create_oscar_the_architect, create_lisa_the_data_scientist
from tinytroupe.environment import TinyWorld
from tinytroupe.agent.web_browser_faculty import TinyWebBrowserFaculty
from tinytroupe.ui.user_interaction import AutoUserInteraction

from testing_utils import *
import conftest

logger = logging.getLogger("tinytroupe")

# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _collect_all_of_type(actions: list, action_type: str) -> list:
    """Return all actions of the given type."""
    return [a for a in actions if a["action"]["type"] == action_type]


def _count_browse_actions(actions: list) -> int:
    """Count how many BROWSE or BROWSE_ACTION actions are in the list."""
    return sum(
        1 for a in actions
        if a["action"]["type"] in ("BROWSE", "BROWSE_ACTION")
    )


def _join_talk_content(actions: list) -> str:
    """Concatenate the content of all TALK actions."""
    talks = _collect_all_of_type(actions, "TALK")
    return " ".join(a["action"]["content"] for a in talks)


def _flatten_world_actions(actions_over_time: list, agent_name: str) -> list:
    """
    Flatten the ``TinyWorld.run(return_actions=True)`` result into a
    single list of action dicts for the given agent.

    ``world.run()`` returns a list of step dicts, each mapping agent names
    to their per-step action lists.
    """
    flat = []
    for step_dict in actions_over_time:
        agent_actions = step_dict.get(agent_name, [])
        flat.extend(agent_actions)
    return flat


class TestWebBrowsingScenarios:
    """
    Scenario tests for the web browsing faculty.

    These require a real browser (Chromium, headless) and real LLM calls
    (cached when ``--use_cache`` is used).
    """

    @pytest.mark.slow
    def test_hungry_agent_searches_gazpacho_recipes(self, setup):
        """
        Oscar — very hungry — browses AllRecipes to find a gazpacho
        recipe, reads it, and shares his opinion.

        Following the notebook pattern, the **user** handles the
        mechanical navigation steps (going to AllRecipes, submitting
        the search query) and the **agent** handles the cognitive
        steps (choosing a recipe, clicking, reading, forming an
        opinion).  This mirrors the realistic Jupyter workflow:
        set up the starting point, then let the agent explore.

        We also feed the current browser state to the agent via
        ``_feed_observation()`` before autonomous steps so the agent
        can see where it already is.

        ``use_vision=False`` skips the expensive LLM screenshot
        description call (~10 s saved per step) — the agent still
        receives the accessibility tree which is sufficient for
        reading and navigating.
        """
        import time

        oscar = create_oscar_the_architect()

        oscar.change_context([
            "You are very hungry right now and craving a cold Spanish "
            "gazpacho.  You want to find a good traditional recipe "
            "online.",
        ])

        auto_ui = AutoUserInteraction()
        faculty = TinyWebBrowserFaculty(
            headless=conftest.headless,
            user_interaction=auto_ui,
            # use_vision=False: skip LLM vision call per step for speed;
            # the agent still receives the accessibility tree.
            use_vision=False,
            # max_content_length: 5000 chars includes recipe-level detail
            # (ingredients, steps) while staying safely under the embedding
            # model's 8192-token limit during memory consolidation.
            max_content_length=5000,
        )
        oscar.add_mental_faculty(faculty)

        try:
            # ── User interventions (mechanical navigation) ────────────
            # The user handles the "mechanical" steps: navigating to
            # AllRecipes and submitting the search query.  The agent
            # handles the cognitive parts: choosing, clicking, reading.
            recipe_url = "https://www.allrecipes.com/search?q=gazpacho"
            result = faculty.user_goto(recipe_url)
            assert result["success"] is True, (
                f"Failed to navigate to AllRecipes: {result.get('error', '?')}"
            )
            time.sleep(3)  # let the page fully load

            # Feed the current browser state so the agent can see the
            # search results immediately without re-navigating.
            ctrl = faculty._get_browser_controller()
            faculty._feed_observation(
                oscar,
                "Page already loaded: AllRecipes gazpacho search results",
                {
                    "screenshot": ctrl.screenshot(),
                    "page_content": ctrl.get_page_content(),
                    "metadata": ctrl.get_page_metadata(),
                },
            )

            world = TinyWorld("Gazpacho Recipe Search", [oscar])

            # ----------------------------------------------------------
            # Phase 1 — Autonomous browsing (6 steps)
            # The agent scrolls, picks a recipe, clicks, and reads it.
            # Uses BROWSE_ACTION commands for reliable interaction.
            # ----------------------------------------------------------
            world.broadcast(
                "Your browser is ALREADY showing AllRecipes.com search "
                "results for 'gazpacho'. You can see the recipe links "
                "in your last browser observation — do NOT navigate to "
                "any new URL.\n"
                "Your task:\n"
                "1. Use BROWSE_ACTION scroll down 500 to see more results.\n"
                "2. Look at the recipe links in your browser observation "
                "and pick one that catches your eye — do NOT always pick "
                "the first one; choose whichever looks most interesting.\n"
                "3. Use BROWSE_ACTION click to click that recipe's link.\n"
                "4. Once on the recipe page, use BROWSE_ACTION scroll "
                "down 500 to see the full recipe — ingredients, quantities, "
                "preparation steps, tips.\n"
                "5. Do NOT talk yet — just focus on browsing, clicking, "
                "and reading.\n"
                "IMPORTANT: Use BROWSE_ACTION commands (scroll, click) to "
                "interact with the page. Do NOT use BROWSE with long "
                "instructions."
            )

            phase1_actions = world.run(
                6, return_actions=True, parallelize=False,
            ) or []

            # ----------------------------------------------------------
            # Phase 2 — Report findings (3 steps)
            # Now instruct the agent to share what it found.
            # ----------------------------------------------------------
            world.broadcast(
                "You have finished reading the gazpacho recipe page.  "
                "Now TALK and share your opinion:\n"
                "- What specific ingredients did the recipe call for?\n"
                "- How is the dish prepared (key steps)?\n"
                "- Would you cook this tonight?  Why or why not?\n"
                "Base your answer ONLY on what you actually read in the "
                "browser.  Be specific — mention actual quantities and "
                "techniques."
            )

            phase2_actions = world.run(
                3, return_actions=True, parallelize=False,
            ) or []

            all_actions = (
                _flatten_world_actions(phase1_actions, oscar.name)
                + _flatten_world_actions(phase2_actions, oscar.name)
            )

            logger.info("=== ALL ACTIONS ===")
            for a in all_actions:
                act = a["action"]
                logger.info(
                    f"  [{act['type']}] {act.get('content', '')[:200]}"
                )
            logger.info(oscar.pp_current_interactions())

            # ----------------------------------------------------------
            # Assertion 1: The agent used the browser multiple times
            # (search + read results/click + read recipe).
            # ----------------------------------------------------------
            browse_count = _count_browse_actions(all_actions)
            assert browse_count >= 3, (
                f"Expected at least 3 browse actions (search, results, "
                f"recipe) but got {browse_count}."
            )

            # ----------------------------------------------------------
            # Assertion 2: The agent produced substantial talk.
            # ----------------------------------------------------------
            talk_content = _join_talk_content(all_actions)
            logger.info(f"Full talk content: {talk_content}")

            assert len(talk_content) > 50, (
                f"Expected substantial recipe discussion, got: "
                f"{talk_content[:100]}"
            )

            # ----------------------------------------------------------
            # Assertion 3: Concrete recipe details from the web.
            # ----------------------------------------------------------
            assert proposition_holds(
                f"The following text describes a gazpacho recipe found "
                f"on the web, mentioning specific details such as "
                f"ingredients (e.g. tomatoes, peppers, cucumbers, "
                f"bread, olive oil, garlic, or vinegar), preparation "
                f"steps, or a personal opinion about the recipe.  "
                f"A text that only states intent to search or gives "
                f"generic statements without concrete recipe details "
                f"does NOT qualify: '{talk_content}'"
            ), (
                f"Expected concrete recipe details but Oscar said: "
                f"{talk_content}"
            )

        finally:
            faculty.close_browser()

    @pytest.mark.slow
    def test_user_intervention_via_faculty(self, setup):
        """
        The user navigates via ``user_goto()`` and the agent subsequently
        observes the page and reports what it sees.

        This demonstrates the Jupyter-notebook-friendly workflow where the
        user manipulates the browser between agent action cycles.

        Following the notebook pattern:
        - ``use_vision=False`` for speed (accessibility tree is sufficient).
        - ``max_content_length=5000`` to stay under the embedding limit.
        - ``_feed_observation()`` to give the agent the initial page state.

        We verify that:
        1. Direct user navigation works (``user_goto``, screenshots, content).
        2. The agent uses the browser to look at the already-open page.
        3. The agent's report is actually about the page content (example.com),
           not a generic or hallucinated description.
        """
        lisa = create_lisa_the_data_scientist()

        auto_ui = AutoUserInteraction()
        faculty = TinyWebBrowserFaculty(
            headless=conftest.headless,
            user_interaction=auto_ui,
            use_vision=False,
            max_content_length=5000,
        )
        lisa.add_mental_faculty(faculty)

        try:
            # ---- User intervenes directly on the faculty ----
            result = faculty.user_goto("https://example.com")
            assert result["success"] is True, (
                f"Failed to navigate to example.com: {result.get('error', '?')}"
            )

            # User takes a screenshot to verify
            path = faculty.user_screenshot()
            assert path is not None and os.path.isfile(path)

            # User checks the page content
            content = faculty.user_get_page_content()
            assert len(content) > 0

            # ---- Feed the current browser state to the agent ----
            # This mirrors the notebook pattern: give the agent the page
            # state before autonomous steps so it sees where it is.
            ctrl = faculty._get_browser_controller()
            faculty._feed_observation(
                lisa,
                "Page already loaded: example.com",
                {
                    "screenshot": ctrl.screenshot(),
                    "page_content": ctrl.get_page_content(),
                    "metadata": ctrl.get_page_metadata(),
                },
            )

            # ---- Now ask the agent to look at the already-open browser ----
            # Place Lisa in a world and let her run a few steps so she can
            # observe the already-open page and report what she sees.
            world = TinyWorld("Page Review", [lisa])

            world.broadcast(
                "Your browser is ALREADY showing a web page. You can see "
                "the page content in your last browser observation.\n"
                "Your task:\n"
                "1. Use BROWSE_ACTION get_content to read the page text.\n"
                "2. Then TALK and describe what you see — headings, text, "
                "links, and any other visible elements."
            )

            # NOTE: parallelize=False — Playwright requires same-thread access.
            actions_over_time = world.run(5, return_actions=True, parallelize=False) or []
            all_actions = _flatten_world_actions(actions_over_time, lisa.name)

            logger.info(lisa.pp_current_interactions())

            # ----------------------------------------------------------
            # The agent should have interacted with the browser.
            # ----------------------------------------------------------
            has_browse = contains_action_type(all_actions, "BROWSE")
            has_browse_action = contains_action_type(all_actions, "BROWSE_ACTION")
            assert has_browse or has_browse_action, (
                f"{lisa.name} should have used BROWSE or BROWSE_ACTION to "
                f"observe the page."
            )

            # ----------------------------------------------------------
            # The agent should TALK about the page.
            # ----------------------------------------------------------
            assert contains_action_type(all_actions, "TALK"), \
                f"{lisa.name} should TALK about what she sees on the page."

            # ----------------------------------------------------------
            # The TALK should be about example.com (not hallucinated).
            # example.com shows "Example Domain" and a note about IANA.
            # ----------------------------------------------------------
            talk_content = _join_talk_content(all_actions)
            logger.info(f"Lisa said: {talk_content}")

            assert proposition_holds(
                f"The following text describes the content of a web page about "
                f"'Example Domain' or mentions that the page is a placeholder "
                f"or example domain managed by IANA, or references the simple "
                f"content typically found at example.com: '{talk_content}'"
            ), (
                f"Lisa should describe example.com content but said: "
                f"{talk_content}"
            )

        finally:
            faculty.close_browser()

    @pytest.mark.slow
    def test_multi_tab_research(self, setup):
        """
        Oscar is asked to look at two websites and compare them.

        The first page (example.com) is pre-navigated via ``user_goto()``
        for reliability.  The agent must then autonomously navigate to the
        second page (iana.org/domains/reserved), read both, and report a
        comparison.

        Following the notebook pattern:
        - ``use_vision=False`` for speed (accessibility tree is sufficient).
        - ``max_content_length=5000`` to stay under the embedding limit.
        - ``_feed_observation()`` to give the agent the initial page state.

        We verify that the agent's final report mentions content from
        **both** pages, not just one or neither.
        """
        oscar = create_oscar_the_architect()

        auto_ui = AutoUserInteraction()
        faculty = TinyWebBrowserFaculty(
            browser_channel="chromium",
            headless=conftest.headless,
            user_interaction=auto_ui,
            use_vision=False,
            max_content_length=5000,
        )
        oscar.add_mental_faculty(faculty)

        try:
            # Pre-navigate to the first page so the agent starts with
            # something already visible in the browser.
            result = faculty.user_goto("https://example.com")
            assert result["success"] is True

            # Feed the current browser state so the agent can see
            # the page immediately without re-navigating.
            ctrl = faculty._get_browser_controller()
            faculty._feed_observation(
                oscar,
                "Page already loaded: example.com",
                {
                    "screenshot": ctrl.screenshot(),
                    "page_content": ctrl.get_page_content(),
                    "metadata": ctrl.get_page_metadata(),
                },
            )

            world = TinyWorld("Page Comparison", [oscar])

            world.broadcast(
                "Your browser is ALREADY showing example.com. You can see "
                "the page content in your last browser observation.\n"
                "Your task:\n"
                "1. Use BROWSE_ACTION get_content to read the current page.\n"
                "2. Then use BROWSE_ACTION goto https://www.iana.org/domains/reserved "
                "to navigate to the second page.\n"
                "3. Use BROWSE_ACTION get_content to read that page too.\n"
                "4. After reading both pages, TALK and compare them — what is "
                "each one about?\n"
                "IMPORTANT: Use BROWSE_ACTION commands to interact with the "
                "browser. Do NOT use BROWSE with long instructions."
            )

            # NOTE: parallelize=False — Playwright requires same-thread access.
            actions_over_time = world.run(8, return_actions=True, parallelize=False) or []
            all_actions = _flatten_world_actions(actions_over_time, oscar.name)

            logger.info(oscar.pp_current_interactions())

            # ----------------------------------------------------------
            # The agent should have browsed multiple times (at least one
            # visit per page).
            # ----------------------------------------------------------
            browse_count = _count_browse_actions(all_actions)
            assert browse_count >= 2, (
                f"{oscar.name} should have browsed at least twice (once per "
                f"page), but only produced {browse_count} browse action(s)."
            )

            # ----------------------------------------------------------
            # The agent should report a comparison.
            # ----------------------------------------------------------
            assert contains_action_type(all_actions, "TALK"), \
                f"{oscar.name} should TALK about the two pages."

            talk_content = _join_talk_content(all_actions)
            logger.info(f"Oscar said: {talk_content}")

            # The report should mention content from both pages.
            # example.com: "Example Domain", placeholder, IANA.
            # iana.org/domains/reserved: reserved domains, RFC 2606, etc.
            assert proposition_holds(
                f"The following text describes or compares two different web "
                f"pages, mentioning specific content from each. One page is "
                f"about an 'example domain' or placeholder site, and the other "
                f"is about reserved domains, IANA, or domain name standards. "
                f"A text that only mentions one page or neither does NOT "
                f"qualify: '{talk_content}'"
            ), (
                f"Oscar should compare both pages but said: {talk_content}"
            )

        finally:
            faculty.close_browser()
