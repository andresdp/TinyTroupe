import pytest
import logging
logger = logging.getLogger("tinytroupe")

import sys
# Insert paths at the beginning of sys.path (position 0)
sys.path.insert(0, '..')
sys.path.insert(0, '../../')
sys.path.insert(0, '../../tinytroupe/')

from tinytroupe.examples import create_lisa_the_data_scientist, create_oscar_the_architect, create_marcos_the_physician
from tinytroupe.environment import TinyWorld
from testing_utils import *

@pytest.mark.core
def test_run(setup, focus_group_world):

    # empty world
    world_1 = TinyWorld("Empty land", [])   
    world_1.run(2)

    # world with agents
    world_2 = focus_group_world
    world_2.broadcast("Discuss ideas for a new AI product you'd love to have.")
    world_2.run(2)

    # check integrity of conversation
    for agent in world_2.agents:
        for msg in agent.episodic_memory.retrieve_all():
            if 'action' in msg['content'] and 'target' in msg['content']['action']:
                assert msg['content']['action']['target'] != agent.name, f"{agent.name} should not have any messages with itself as the target."
            
            # Semantic verification: if it's a TALK action, ensure it relates to AI product discussion
            if 'action' in msg['content'] and msg['content']['action'].get('type') == 'TALK':
                action_content = msg['content']['action'].get('content', '')
                if action_content:  # Only check if there's content
                    assert proposition_holds(action_content + " - The message relates to AI products, technology, or innovation")
            
            # TODO stimulus integrity check?
        

@pytest.mark.core
def test_broadcast(setup, focus_group_world):

    world = focus_group_world
    world.broadcast("""
                Folks, we need to brainstorm ideas for a new baby product. Something moms have been asking for centuries and never got.

                Please start the discussion now.
                """)
    
    for agent in focus_group_world.agents:
        # did the agents receive the message?
        assert "Folks, we need to brainstorm" in agent.episodic_memory.retrieve_first(1)[0]['content']['stimuli'][0]['content'], f"{agent.name} should have received the message."
    
    # Run the world to let agents respond
    world.run(1)
    
    # Semantic verification: check that agent responses relate to baby products or brainstorming
    for agent in focus_group_world.agents:
        recent_actions = agent.episodic_memory.retrieve_first(3)  # Get recent actions
        for msg in recent_actions:
            if 'action' in msg['content'] and msg['content']['action'].get('type') == 'TALK':
                action_content = msg['content']['action'].get('content', '')
                if action_content and len(action_content) > 20:  # Only check substantial responses
                    assert proposition_holds(action_content + " - The message relates to baby products, parenting, or product brainstorming")


@pytest.mark.core
def test_encode_complete_state(setup, focus_group_world):
    world = focus_group_world

    # encode the state
    state = world.encode_complete_state()
    
    assert state is not None, "The state should not be None."
    assert state['name'] == world.name, "The state should have the world name."
    assert state['agents'] is not None, "The state should have the agents."

@pytest.mark.core
def test_decode_complete_state(setup, focus_group_world):
    world = focus_group_world

    name_1 = world.name
    n_agents_1 = len(world.agents)

    # encode the state
    state = world.encode_complete_state()
    
    # screw up the world
    world.name = "New name"
    world.agents = []

    # decode the state back into the world
    world_2 = world.decode_complete_state(state)

    assert world_2 is not None, "The world should not be None."
    assert world_2.name == name_1, "The world should have the same name."
    assert len(world_2.agents) == n_agents_1, "The world should have the same number of agents."


@pytest.mark.core
def test_task_over_early_stop(setup):
    """
    Test that TASK_OVER causes TinyWorld to skip remaining simulation steps.

    Scenario:
      - Create a world with ``allow_early_stop_via_task_over=True``
      - Give an agent a simple, completable task
      - Run with enough steps that the agent should finish and issue TASK_OVER
      - Verify that: (a) the agent issued TASK_OVER, (b) the world stopped early

    Multi-task lifecycle:
      - After the first run, broadcast a NEW task and run again
      - Verify the agent participates normally in the second run (TASK_OVER resets)
    """
    oscar = create_oscar_the_architect()

    world = TinyWorld(
        "Task Over Test",
        [oscar],
        allow_early_stop_via_task_over=True,
    )

    # --- First task ---
    world.broadcast(
        "Think briefly about what your favorite building is and why, "
        "then tell me about it. This is a SIMPLE task. Once you have "
        "answered, the task is fully complete and you should signal that."
    )

    # Give enough steps for the agent to finish
    actions_over_time = world.run(5, return_actions=True, parallelize=False)

    # The world should have stopped early (agent should finish in 1-2 steps)
    assert len(actions_over_time) < 5, (
        f"Expected early stop via TASK_OVER, but the world ran all 5 steps "
        f"({len(actions_over_time)} steps executed)."
    )

    # Check that TASK_OVER was issued
    assert oscar.name in world._task_over_agents, (
        "Oscar should be in _task_over_agents after issuing TASK_OVER."
    )

    # Check that the agent actually produced a TASK_OVER action in its memory
    task_over_found = False
    for msg in oscar.episodic_memory.retrieve_all():
        if (msg.get("role") == "assistant"
                and "action" in msg.get("content", {})
                and msg["content"]["action"].get("type") == "TASK_OVER"):
            task_over_found = True
            break
    assert task_over_found, "Oscar should have a TASK_OVER action in episodic memory."

    # --- Second task (multi-task lifecycle) ---
    world.broadcast(
        "Now think about what your least favorite building is and why, "
        "then tell me about it. Once you have answered, the task is fully "
        "complete and you should signal that."
    )

    actions_over_time_2 = world.run(5, return_actions=True, parallelize=False)

    # The agent should have participated (TASK_OVER resets per run)
    assert len(actions_over_time_2) >= 1, (
        "Oscar should participate in the second run after TASK_OVER reset."
    )

    # And should have issued TASK_OVER again
    assert oscar.name in world._task_over_agents, (
        "Oscar should be in _task_over_agents again after the second task."
    )


@pytest.mark.core
def test_task_over_disabled_by_default(setup):
    """
    When ``allow_early_stop_via_task_over`` is False (default), agents should
    NOT see TASK_OVER in their prompt and the world never stops early.
    """
    oscar = create_oscar_the_architect()
    world = TinyWorld("No Task Over", [oscar])

    # The agent should NOT have _allow_task_over set
    assert not oscar._allow_task_over, (
        "Agent should have _allow_task_over=False when world does not enable it."
    )

    # The flag should be False on the world
    assert not world._allow_early_stop_via_task_over

    # TASK_OVER should NOT appear in the agent's system prompt
    prompt = oscar.generate_agent_system_prompt()
    assert "TASK_OVER" not in prompt, (
        "TASK_OVER should not appear in agent prompt when disabled."
    )


@pytest.mark.core
def test_task_over_in_prompt_when_enabled(setup):
    """
    When ``allow_early_stop_via_task_over`` is True, TASK_OVER should appear
    in the agent's system prompt.
    """
    oscar = create_oscar_the_architect()
    world = TinyWorld("With Task Over", [oscar], allow_early_stop_via_task_over=True)

    assert oscar._allow_task_over, (
        "Agent should have _allow_task_over=True when world enables it."
    )

    prompt = oscar.generate_agent_system_prompt()
    assert "TASK_OVER" in prompt, (
        "TASK_OVER should appear in agent prompt when enabled."
    )


