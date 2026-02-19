"""
Extended tests for TinySocialNetwork, TinySocialNetworkFactory,
simulation trace caching, and interactions with the rest of TinyTroupe.
"""
import pytest
import os
import logging

logger = logging.getLogger("tinytroupe")

import sys
sys.path.insert(0, '../../tinytroupe/')
sys.path.insert(0, '../../')
sys.path.insert(0, '..')

from tinytroupe.environment.tiny_social_network import TinySocialNetwork, TinySocialNetworkFactory
from tinytroupe.environment import TinyWorld
from tinytroupe.examples import create_oscar_the_architect, create_lisa_the_data_scientist, create_marcos_the_physician
from tinytroupe.agent import TinyPerson
from tinytroupe.control import Simulation
import tinytroupe.control as control

from testing_utils import *


###########################################################################
# TinySocialNetwork — relation management (new features)
###########################################################################

def test_add_relation_with_attributes(setup):
    """Test adding relations with custom attributes."""
    network = TinySocialNetwork("Attributes Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues", attributes={"weight": 0.9, "department": "R&D"})

    attrs = network.get_relation_attributes(oscar, lisa, "colleagues")
    assert attrs is not None
    assert attrs["weight"] == 0.9
    assert attrs["department"] == "R&D"


def test_remove_relation(setup):
    """Test removing relations between agents."""
    network = TinySocialNetwork("Remove Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "colleagues")
    network.add_relation(oscar, lisa, "friends")
    network.add_relation(oscar, marcos, "colleagues")

    # remove specific relation
    network.remove_relation(oscar, lisa, "friends")
    assert not network.is_in_relation_with(oscar, lisa, "friends")
    assert network.is_in_relation_with(oscar, lisa, "colleagues")

    # remove all relations between oscar and lisa
    network.remove_relation(oscar, lisa)
    assert not network.is_in_relation_with(oscar, lisa)

    # oscar-marcos should be unaffected
    assert network.is_in_relation_with(oscar, marcos, "colleagues")


def test_get_agents_in_relation(setup):
    """Test querying all agents in a named relation."""
    network = TinySocialNetwork("Agents In Relation Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "colleagues")
    network.add_relation(oscar, marcos, "colleagues")

    agents = network.get_agents_in_relation("colleagues")
    assert oscar in agents
    assert lisa in agents
    assert marcos in agents


def test_get_relations_for(setup):
    """Test getting all relations for a specific agent."""
    network = TinySocialNetwork("Relations For Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "colleagues")
    network.add_relation(oscar, marcos, "friends")

    rels = network.get_relations_for(oscar)
    other_agents = [r[0] for r in rels]
    assert lisa in other_agents
    assert marcos in other_agents

    rels_filtered = network.get_relations_for(oscar, relation_name="friends")
    assert len(rels_filtered) == 1
    assert rels_filtered[0][0] is marcos


def test_deduplicate_relations(setup):
    """Test that duplicate relations are prevented."""
    network = TinySocialNetwork("Dedup Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")
    network.add_relation(oscar, lisa, "colleagues")  # duplicate
    network.add_relation(lisa, oscar, "colleagues")  # reversed duplicate

    assert len(network.relations["colleagues"]) == 1


###########################################################################
# Network statistics
###########################################################################

def test_degree(setup):
    """Test degree computation."""
    network = TinySocialNetwork("Degree Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)
    network.add_relation(oscar, lisa, "connected")
    network.add_relation(oscar, marcos, "connected")

    assert network.degree(oscar) == 2
    assert network.degree(lisa) == 1
    assert network.degree(marcos) == 1

    degrees = network.degree()
    assert degrees[oscar] == 2
    assert degrees[lisa] == 1


def test_density(setup):
    """Test network density."""
    network = TinySocialNetwork("Density Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)

    # no edges
    assert network.density() == 0.0

    # fully connected: density == 1.0
    network.add_relation(oscar, lisa, "c")
    network.add_relation(oscar, marcos, "c")
    network.add_relation(lisa, marcos, "c")
    assert abs(network.density() - 1.0) < 1e-9


def test_clustering_coefficient(setup):
    """Test clustering coefficient."""
    network = TinySocialNetwork("Clustering Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    # Triangle: all connected → cc should be 1.0
    network.add_relation(oscar, lisa, "c")
    network.add_relation(oscar, marcos, "c")
    network.add_relation(lisa, marcos, "c")

    assert abs(network.clustering_coefficient(oscar) - 1.0) < 1e-9
    assert abs(network.clustering_coefficient() - 1.0) < 1e-9


def test_connected_components_and_is_connected(setup):
    """Test connected components."""
    network = TinySocialNetwork("Components Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)

    # three isolated nodes → 3 components
    components = network.connected_components()
    assert len(components) == 3
    assert not network.is_connected()

    # connect oscar-lisa
    network.add_relation(oscar, lisa, "c")
    components = network.connected_components()
    assert len(components) == 2
    assert not network.is_connected()

    # connect lisa-marcos → all connected
    network.add_relation(lisa, marcos, "c")
    assert network.is_connected()


def test_shortest_path_and_diameter(setup):
    """Test shortest path and diameter."""
    network = TinySocialNetwork("Path Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    # linear: oscar -- lisa -- marcos
    network.add_relation(oscar, lisa, "c")
    network.add_relation(lisa, marcos, "c")

    path = network.shortest_path(oscar, marcos)
    assert len(path) == 3
    assert path[0] is oscar
    assert path[-1] is marcos

    assert network.diameter() == 2


def test_betweenness_centrality(setup):
    """Test betweenness centrality."""
    network = TinySocialNetwork("BC Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    # linear: oscar -- lisa -- marcos
    network.add_relation(oscar, lisa, "c")
    network.add_relation(lisa, marcos, "c")

    bc = network.betweenness_centrality()
    # Lisa is in the middle so she should have the highest betweenness
    assert bc[lisa] > bc[oscar]
    assert bc[lisa] > bc[marcos]


def test_degree_centrality(setup):
    """Test degree centrality."""
    network = TinySocialNetwork("DC Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "c")
    network.add_relation(oscar, marcos, "c")

    dc = network.degree_centrality()
    # Oscar is connected to both, so highest centrality
    assert dc[oscar] > dc[lisa]
    assert dc[oscar] > dc[marcos]


def test_get_network_summary(setup):
    """Test the comprehensive network summary."""
    network = TinySocialNetwork("Summary Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "c")

    summary = network.get_network_summary()
    assert summary["num_agents"] == 2
    assert summary["num_edges"] == 1
    assert summary["is_connected"] is True
    assert summary["diameter"] == 1
    assert "degrees" in summary
    assert "degree_centrality" in summary
    assert "betweenness_centrality" in summary


def test_adjacency_matrix(setup):
    """Test adjacency matrix generation."""
    network = TinySocialNetwork("Matrix Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "c")

    matrix, agent_list = network.get_adjacency_matrix()
    assert len(matrix) == 2
    assert len(agent_list) == 2

    i_oscar = agent_list.index(oscar)
    i_lisa = agent_list.index(lisa)
    assert matrix[i_oscar][i_lisa] == 1
    assert matrix[i_lisa][i_oscar] == 1
    assert matrix[i_oscar][i_oscar] == 0


###########################################################################
# Message logging
###########################################################################

def test_message_logging(setup):
    """Test that message log records TALK and REACH_OUT actions."""
    network = TinySocialNetwork("Message Log Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    # Simulate a TALK action
    network._handle_talk(oscar, "Hello Lisa", lisa.name)

    assert network.get_message_count() == 1
    assert network.get_message_count(source=oscar) == 1
    assert network.get_message_count(source=marcos) == 0

    log_entries = network.get_message_log(source=oscar)
    assert len(log_entries) == 1
    assert log_entries[0]["action_type"] == "TALK"
    assert log_entries[0]["content"] == "Hello Lisa"

    # Simulate a REACH_OUT action between connected agents
    network._handle_reach_out(oscar, "Reaching out", lisa.name)
    assert network.get_message_count() == 2

    # Clear the log
    network.clear_message_log()
    assert network.get_message_count() == 0


def test_message_log_blocked_actions(setup):
    """Test that blocked actions (no relation) are not logged."""
    network = TinySocialNetwork("Blocked Log Test", broadcast_if_no_target=False)
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)
    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    # oscar tries to talk to marcos (no relation, no broadcast)
    network._handle_talk(oscar, "Hello Marcos", marcos.name)
    assert network.get_message_count() == 0

    # oscar talks to lisa (relation exists)
    network._handle_talk(oscar, "Hello Lisa", lisa.name)
    assert network.get_message_count() == 1


###########################################################################
# TinySocialNetworkFactory
###########################################################################

def test_factory_random_network(setup):
    """Test Erdős–Rényi random network creation."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_random_network("Random Net", agents, p=1.0)
    assert len(net.agents) == 3
    # p=1.0 means fully connected
    assert net.is_in_relation_with(oscar, lisa)
    assert net.is_in_relation_with(oscar, marcos)
    assert net.is_in_relation_with(lisa, marcos)


def test_factory_random_network_empty(setup):
    """Test Erdős–Rényi with p=0 gives no edges."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    agents = [oscar, lisa]

    net = TinySocialNetworkFactory.create_random_network("Empty Random", agents, p=0.0)
    assert len(net.agents) == 2
    assert not net.is_in_relation_with(oscar, lisa)


def test_factory_star_network(setup):
    """Test star/hub-spoke network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_star_network("Star", agents, hub=oscar)
    assert len(net.agents) == 3
    assert net.is_in_relation_with(oscar, lisa)
    assert net.is_in_relation_with(oscar, marcos)
    assert not net.is_in_relation_with(lisa, marcos)
    assert net.degree(oscar) == 2


def test_factory_corporate_hierarchy(setup):
    """Test corporate hierarchy tree."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_corporate_hierarchy(
        "Corp", agents, ceo=oscar, span_of_control=2
    )
    # oscar should be connected to both lisa and marcos
    assert net.is_in_relation_with(oscar, lisa, "reports_to")
    assert net.is_in_relation_with(oscar, marcos, "reports_to")
    assert len(net.agents) == 3


def test_factory_workflow_pipeline(setup):
    """Test workflow pipeline network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    stages = [[oscar], [lisa], [marcos]]
    net = TinySocialNetworkFactory.create_workflow_pipeline("Pipeline", [], stages=stages)

    # oscar->lisa, lisa->marcos
    assert net.is_in_relation_with(oscar, lisa, "workflow")
    assert net.is_in_relation_with(lisa, marcos, "workflow")
    # oscar should NOT be directly connected to marcos
    assert not net.is_in_relation_with(oscar, marcos, "workflow")


def test_factory_department_network(setup):
    """Test department-based network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    departments = {
        "Engineering": [oscar, lisa],
        "Medical": [marcos],
    }
    net = TinySocialNetworkFactory.create_department_network(
        "Dept Net", departments, inter_department_p=0.0
    )

    # oscar and lisa are in same department -> connected
    assert net.is_in_relation_with(oscar, lisa)
    # marcos is in a different department with 0 cross-dept probability
    assert not net.is_in_relation_with(oscar, marcos)
    assert not net.is_in_relation_with(lisa, marcos)


def test_factory_bipartite_network(setup):
    """Test bipartite network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    net = TinySocialNetworkFactory.create_bipartite_network(
        "Bipartite", [oscar], [lisa, marcos], p=1.0
    )
    # p=1.0 means all cross-group edges
    assert net.is_in_relation_with(oscar, lisa)
    assert net.is_in_relation_with(oscar, marcos)
    # same group should not be connected (bipartite)
    assert not net.is_in_relation_with(lisa, marcos)


def test_factory_scale_free_network(setup):
    """Test Barabási-Albert scale-free network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_scale_free_network("Scale Free", agents, m=1)
    assert len(net.agents) == 3
    # With m=1, we should have at least 2 edges (initial clique of 2, then one attachment)
    assert len(net._unique_edges()) >= 2


def test_factory_small_world_network(setup):
    """Test Watts-Strogatz small-world network."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_small_world_network(
        "Small World", agents, k=2, p=0.0
    )
    assert len(net.agents) == 3
    # k=2, p=0 on 3 nodes: ring lattice with 1 neighbour each side
    # => fully connected triangle
    assert net.is_connected()


###########################################################################
# Serialization / deserialization
###########################################################################

def test_encode_decode_complete_state(setup):
    """Test that TinySocialNetwork state can be encoded and decoded."""
    network = TinySocialNetwork("Serialization Full Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_relation(oscar, lisa, "colleagues", attributes={"dept": "Eng"})
    network.add_relation(lisa, marcos, "friends")
    network._update_agents_contexts()

    # simulate some messages
    network._handle_talk(oscar, "Hello Lisa!", lisa.name)

    # encode
    state = network.encode_complete_state()

    # verify encoded relations contain names, not objects
    assert "relations" in state
    assert "colleagues" in state["relations"]
    edge = state["relations"]["colleagues"][0]
    assert isinstance(edge[0], str)  # agent name
    assert isinstance(edge[1], str)  # agent name
    assert edge[2].get("dept") == "Eng"  # attributes preserved

    # verify message_log is encoded
    assert "message_log" in state
    assert len(state["message_log"]) == 1

    # Now modify the network state and then decode to restore
    network.remove_relation(oscar, lisa, "colleagues")
    network.remove_relation(lisa, marcos, "friends")
    network.clear_message_log()
    assert not network.is_in_relation_with(oscar, lisa, "colleagues")

    # Decode restores the original state
    network.decode_complete_state(state)

    assert network.is_in_relation_with(
        network.get_agent_by_name(oscar.name),
        network.get_agent_by_name(lisa.name),
        "colleagues"
    )
    assert network.is_in_relation_with(
        network.get_agent_by_name(lisa.name),
        network.get_agent_by_name(marcos.name),
        "friends"
    )
    assert len(network.message_log) == 1


###########################################################################
# Simulation trace caching (control module)
###########################################################################

@pytest.mark.core
def test_begin_checkpoint_end_with_social_network(setup):
    """Test simulation trace caching works correctly with TinySocialNetwork."""
    cache_file = "control_test_social_network.cache.json"
    remove_file_if_exists(cache_file)

    control.reset()
    assert control._current_simulations["default"] is None

    control.begin(cache_file)
    assert control._current_simulations["default"].status == Simulation.STATUS_STARTED

    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network = TinySocialNetwork("Cache Test Network", broadcast_if_no_target=True)
    network.add_relation(oscar, lisa, "colleagues")

    assert control._current_simulations["default"].cached_trace is not None
    assert control._current_simulations["default"].execution_trace is not None

    # Run a simulation step
    network.run(1)

    control.checkpoint()

    assert os.path.exists(cache_file), "Checkpoint file should have been created."

    control.end()
    assert control._current_simulations["default"].status == Simulation.STATUS_STOPPED

    # Clean up
    remove_file_if_exists(cache_file)


@pytest.mark.core
def test_social_network_cache_consistency(setup):
    """Test that two identical simulation runs with social network produce
    the same cached results (cache hit on second run)."""
    cache_file = "control_test_social_network_consistency.cache.json"
    remove_file_if_exists(cache_file)

    def run_simulation():
        control.reset()
        control.begin(cache_file)

        oscar = create_oscar_the_architect()
        lisa = create_lisa_the_data_scientist()

        network = TinySocialNetwork("Consistency Network")
        network.add_relation(oscar, lisa, "colleagues")
        network._update_agents_contexts()

        control.checkpoint()
        control.end()

        return network

    # First run
    assert control.cache_misses() == 0
    assert control.cache_hits() == 0
    net1 = run_simulation()

    # Second run: should hit cache
    net2 = run_simulation()
    assert control.cache_hits() > 0

    # Clean up
    remove_file_if_exists(cache_file)


###########################################################################
# Interactions with other TinyTroupe mechanisms
###########################################################################

def test_social_network_broadcast_thought(setup):
    """Test broadcast_thought still works on a social network."""
    network = TinySocialNetwork("Broadcast Thought Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    # broadcast_thought is inherited from TinyWorld and should work
    network.broadcast_thought("Think about innovation")
    # no error is success


def test_social_network_broadcast_internal_goal(setup):
    """Test broadcast_internal_goal still works on a social network."""
    network = TinySocialNetwork("Internal Goal Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")

    network.broadcast_internal_goal("Achieve synergy in the team")
    # no error is success


def test_social_network_broadcast_context_change(setup):
    """Test broadcast_context_change still works on a social network."""
    network = TinySocialNetwork("Context Change Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")

    network.broadcast_context_change(["The company just acquired a new startup."])
    # no error is success


def test_social_network_add_remove_agents(setup):
    """Test agent add/remove works correctly within social network."""
    network = TinySocialNetwork("Agent Management Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_agent(oscar)
    network.add_agent(lisa)
    assert len(network.agents) == 2
    assert network.get_agent_by_name("Oscar") is oscar

    network.remove_agent(lisa)
    assert len(network.agents) == 1
    assert network.get_agent_by_name("Lisa") is None


def test_social_network_make_everyone_accessible(setup):
    """Test make_everyone_accessible (inherited from TinyWorld)."""
    network = TinySocialNetwork("Everyone Accessible Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)

    network.make_everyone_accessible()

    assert lisa in oscar.accessible_agents
    assert marcos in oscar.accessible_agents
    assert oscar in lisa.accessible_agents


def test_social_network_run_convenience_methods(setup):
    """Test run_minutes, run_hours etc. work on TinySocialNetwork."""
    network = TinySocialNetwork("Run Convenience Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")

    # These should not raise; just verifying the interface works
    # (actual LLM calls are beyond our scope here, so we just test 1 step)
    network.run(steps=1)


def test_social_network_skip(setup):
    """Test that skip advances time without agent actions."""
    from datetime import datetime, timedelta

    network = TinySocialNetwork("Skip Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")

    initial_time = network.current_datetime
    network.skip(steps=3, timedelta_per_step=timedelta(hours=1))
    assert network.current_datetime == initial_time + timedelta(hours=3)


def test_social_network_pretty_current_interactions(setup):
    """Test pretty_current_interactions on a social network."""
    network = TinySocialNetwork("Pretty Print Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    result = network.pretty_current_interactions()
    assert isinstance(result, str)


def test_social_network_broadcast_only_to_connected(setup):
    """Test that broadcast only delivers to connected agents."""
    network = TinySocialNetwork("Broadcast Connected Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    network.add_agent(oscar)
    network.add_agent(lisa)
    network.add_agent(marcos)
    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    # Broadcast from oscar should only reach lisa (connected), not marcos
    network.broadcast("Hello everyone!", source=oscar)

    # Check message log: should only have 1 entry (oscar -> lisa)
    log = network.get_message_log(source=oscar)
    assert len(log) == 1
    assert log[0]["target"] == lisa.name


def test_social_network_broadcast_no_source(setup):
    """Test that broadcast with no source goes to all agents."""
    network = TinySocialNetwork("Broadcast No Source Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_agent(oscar)
    network.add_agent(lisa)

    network.broadcast("System announcement")

    # Should have been delivered to all agents
    assert network.get_message_count() == 2


def test_social_network_handle_actions(setup):
    """Test _handle_actions dispatches correctly."""
    network = TinySocialNetwork("Handle Actions Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues")
    network._update_agents_contexts()

    actions = [
        {"type": "TALK", "content": "Hi Lisa", "target": lisa.name},
    ]
    network._handle_actions(oscar, actions)

    assert network.get_message_count() == 1


def test_social_network_repr(setup):
    """Test __repr__ method."""
    network = TinySocialNetwork("Repr Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "c")
    r = repr(network)
    assert "TinySocialNetwork" in r
    assert "Repr Test" in r


###########################################################################
# Edge attributes → agent relation descriptions
###########################################################################

def test_edge_attributes_flow_to_agent_description_simple(setup):
    """Edge attributes with an explicit 'description' key should be used as-is."""
    network = TinySocialNetwork("Desc Flow Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleagues",
                         attributes={"description": "My close collaborator in the design team"})
    network._update_agents_contexts()

    # The relation_description visible to Oscar about Lisa should be the
    # explicit description, not just the relation name.
    accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    assert lisa_entry[0]["relation_description"] == "My close collaborator in the design team"


def test_edge_attributes_flow_rich_attrs(setup):
    """When no explicit 'description' is given, a rich description must be
    synthesised from the edge attributes (department, weight, etc.)."""
    network = TinySocialNetwork("Rich Attr Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleague",
                         attributes={"department": "Engineering", "weight": 0.8})
    network._update_agents_contexts()

    accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    desc = lisa_entry[0]["relation_description"]
    # The description should include the relation name AND the attributes
    assert "colleague" in desc
    assert "Engineering" in desc
    assert "0.8" in desc


def test_edge_attributes_hierarchy_roles(setup):
    """In a corporate hierarchy, the manager and report roles should appear
    in the relation description from the correct perspective."""
    network = TinySocialNetwork("Hierarchy Roles Test")
    oscar = create_oscar_the_architect()   # will be manager
    lisa = create_lisa_the_data_scientist() # will be report

    network.add_relation(oscar, lisa, "reports_to",
                         attributes={"manager": oscar.name, "report": lisa.name})
    network._update_agents_contexts()

    # From Lisa's perspective: Oscar is "your manager"
    lisa_accessible = lisa._mental_state["accessible_agents"]
    oscar_entry = [e for e in lisa_accessible if e["name"] == oscar.name]
    assert len(oscar_entry) == 1
    assert "manager" in oscar_entry[0]["relation_description"].lower()

    # From Oscar's perspective: Lisa is "your direct report"
    oscar_accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in oscar_accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    assert "report" in lisa_entry[0]["relation_description"].lower()


def test_edge_attributes_cross_department(setup):
    """The cross_department flag should be reflected in the description."""
    network = TinySocialNetwork("Cross Dept Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "colleague",
                         attributes={"cross_department": True})
    network._update_agents_contexts()

    accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    assert "cross-department" in lisa_entry[0]["relation_description"].lower()


def test_edge_attributes_default_fallback(setup):
    """With no attributes at all, the relation name itself should be used."""
    network = TinySocialNetwork("Fallback Test")
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()

    network.add_relation(oscar, lisa, "friends")
    network._update_agents_contexts()

    accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    assert "friends" in lisa_entry[0]["relation_description"].lower()


###########################################################################
# Factory — no empty nodes
###########################################################################

def test_factory_no_empty_nodes_random(setup):
    """Every agent in a factory-created random network must be a real
    TinyPerson — there are no 'empty' placeholder nodes."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_random_network("NoEmpty", agents, p=0.5)

    # All nodes in the network are actual TinyPerson objects
    assert len(net.agents) == 3
    for agent in net.agents:
        assert isinstance(agent, TinyPerson)
        assert agent.name  # every agent has a name


def test_factory_no_empty_nodes_hierarchy(setup):
    """Corporate hierarchy should also have no empty nodes."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()
    agents = [oscar, lisa, marcos]

    net = TinySocialNetworkFactory.create_corporate_hierarchy("NoEmpty", agents)

    assert len(net.agents) == 3
    for agent in net.agents:
        assert isinstance(agent, TinyPerson)
        assert agent.name


def test_factory_hierarchy_edge_attrs_reach_agent(setup):
    """Factory-generated hierarchy edges should produce rich descriptions
    that reach the agent prompt (not just 'reports_to')."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    net = TinySocialNetworkFactory.create_corporate_hierarchy(
        "HierDesc", [oscar, lisa, marcos], ceo=oscar, span_of_control=2
    )
    net._update_agents_contexts()

    # Lisa should see Oscar with a "manager" annotation
    lisa_accessible = lisa._mental_state["accessible_agents"]
    oscar_entry = [e for e in lisa_accessible if e["name"] == oscar.name]
    assert len(oscar_entry) == 1
    assert "manager" in oscar_entry[0]["relation_description"].lower()


def test_factory_department_edge_attrs_reach_agent(setup):
    """Factory-generated department edges should include department info
    in the description reaching the agent."""
    oscar = create_oscar_the_architect()
    lisa = create_lisa_the_data_scientist()
    marcos = create_marcos_the_physician()

    departments = {
        "Engineering": [oscar, lisa],
        "Medical": [marcos],
    }
    net = TinySocialNetworkFactory.create_department_network(
        "DeptDesc", departments, inter_department_p=0.0
    )
    net._update_agents_contexts()

    # Oscar and Lisa should see each other with "Engineering" mentioned
    oscar_accessible = oscar._mental_state["accessible_agents"]
    lisa_entry = [e for e in oscar_accessible if e["name"] == lisa.name]
    assert len(lisa_entry) == 1
    assert "Engineering" in lisa_entry[0]["relation_description"]
