from tinytroupe.environment.tiny_world import TinyWorld
from tinytroupe.environment import logger

import copy
import json
import random
import math
import textwrap
from collections import deque
from datetime import datetime, timedelta

from tinytroupe.agent import *
from tinytroupe.control import transactional

from rich.console import Console

from typing import Any, TypeVar, Union
from tinytroupe.utils import name_or_empty

AgentOrWorld = Union["TinyPerson", "TinyWorld"]


class TinySocialNetwork(TinyWorld):
    """
    A social-network environment where agent interactions are constrained by
    an explicit graph of relations. Only agents that share at least one relation
    edge can communicate with each other. The graph is undirected.
    """

    def __init__(self, name, broadcast_if_no_target=True):
        """
        Create a new TinySocialNetwork environment.

        Args:
            name (str): The name of the environment.
            broadcast_if_no_target (bool): If True, broadcast actions through an
                agent's available relations if the target of an action is not found.
        """
        super().__init__(name, broadcast_if_no_target=broadcast_if_no_target)

        # {relation_name: [(agent_1, agent_2, attributes_dict), ...]}
        self.relations = {}

        # Message log for tracking all communications
        self.message_log = []

        # Internal step counter for message logging
        self._current_step = 0

    #######################################################################
    # Relation management
    #######################################################################

    @transactional()
    def add_relation(self, agent_1, agent_2, name="default", attributes=None):
        """
        Adds a relation between two agents. If the agents are not yet in the
        network they are automatically added.

        Args:
            agent_1 (TinyPerson): The first agent.
            agent_2 (TinyPerson): The second agent.
            name (str): The name of the relation.
            attributes (dict, optional): Arbitrary metadata for this edge
                (e.g. role, weight).

        Returns:
            Self: This network, for method chaining.
        """
        logger.debug(f"Adding relation '{name}' between {agent_1.name} and {agent_2.name}.")

        # auto-add agents to the network if they are not already present
        if agent_1 not in self.agents:
            self.add_agent(agent_1)
        if agent_2 not in self.agents:
            self.add_agent(agent_2)

        attrs = attributes if attributes is not None else {}

        if name not in self.relations:
            self.relations[name] = []

        # avoid duplicate edges
        for a1, a2, _ in self.relations[name]:
            if (a1 is agent_1 and a2 is agent_2) or (a1 is agent_2 and a2 is agent_1):
                logger.debug(f"Relation '{name}' between {agent_1.name} and {agent_2.name} already exists.")
                return self

        self.relations[name].append((agent_1, agent_2, attrs))

        # Immediately refresh agent accessibility so that neighbors are
        # visible right away — the user should never have to call
        # _update_agents_contexts() manually.
        self._update_agents_contexts()

        return self

    @transactional()
    def remove_relation(self, agent_1, agent_2, name=None):
        """
        Removes relations between two agents. If *name* is given only that
        specific relation is removed; otherwise **all** relations between the
        pair are removed.

        Args:
            agent_1 (TinyPerson): The first agent.
            agent_2 (TinyPerson): The second agent.
            name (str, optional): The relation name to remove, or None for all.

        Returns:
            Self: This network, for method chaining.
        """
        logger.debug(f"Removing relation(s) between {agent_1.name} and {agent_2.name} (name={name}).")

        names_to_check = [name] if name is not None else list(self.relations.keys())

        for rel_name in names_to_check:
            if rel_name in self.relations:
                self.relations[rel_name] = [
                    (a1, a2, attrs)
                    for a1, a2, attrs in self.relations[rel_name]
                    if not ((a1 is agent_1 and a2 is agent_2) or (a1 is agent_2 and a2 is agent_1))
                ]
                # clean up empty relation lists
                if not self.relations[rel_name]:
                    del self.relations[rel_name]

        # Immediately refresh agent accessibility so that removed neighbors
        # are no longer visible.
        self._update_agents_contexts()

        return self

    def is_in_relation_with(self, agent_1: TinyPerson, agent_2: TinyPerson, relation_name=None) -> bool:
        """
        Checks whether two agents share a relation. Relations are undirected so
        order does not matter.

        Args:
            agent_1 (TinyPerson): The first agent.
            agent_2 (TinyPerson): The second agent.
            relation_name (str, optional): If given, only check this relation.

        Returns:
            bool: True if the agents share the specified (or any) relation.
        """
        if agent_1 is None or agent_2 is None:
            return False

        names_to_check = [relation_name] if relation_name is not None else list(self.relations.keys())

        for rel_name in names_to_check:
            if rel_name in self.relations:
                for a1, a2, _ in self.relations[rel_name]:
                    if (a1 is agent_1 and a2 is agent_2) or (a1 is agent_2 and a2 is agent_1):
                        return True
        return False

    def get_relation_attributes(self, agent_1, agent_2, name) -> dict:
        """
        Returns the attributes dictionary for a specific relation edge.

        Args:
            agent_1 (TinyPerson): The first agent.
            agent_2 (TinyPerson): The second agent.
            name (str): The relation name.

        Returns:
            dict: The attributes, or None if the relation does not exist.
        """
        if name not in self.relations:
            return None
        for a1, a2, attrs in self.relations[name]:
            if (a1 is agent_1 and a2 is agent_2) or (a1 is agent_2 and a2 is agent_1):
                return attrs
        return None

    def get_agents_in_relation(self, relation_name) -> list:
        """
        Returns all agents that participate in at least one edge of the named
        relation.

        Args:
            relation_name (str): The relation name to query.

        Returns:
            list: A list of agents (no duplicates).
        """
        agents = set()
        if relation_name in self.relations:
            for a1, a2, _ in self.relations[relation_name]:
                agents.add(a1)
                agents.add(a2)
        return list(agents)

    def get_relations_for(self, agent, relation_name=None) -> list:
        """
        Returns all relation edges an agent participates in.

        Args:
            agent (TinyPerson): The agent to query.
            relation_name (str, optional): Filter to a specific relation name.

        Returns:
            list: A list of tuples ``(other_agent, relation_name, attributes)``.
        """
        results = []
        names_to_check = [relation_name] if relation_name is not None else list(self.relations.keys())

        for rel_name in names_to_check:
            if rel_name in self.relations:
                for a1, a2, attrs in self.relations[rel_name]:
                    if a1 is agent:
                        results.append((a2, rel_name, attrs))
                    elif a2 is agent:
                        results.append((a1, rel_name, attrs))
        return results

    #######################################################################
    # Helpers — connected neighbours
    #######################################################################

    def _get_connected_agents(self, agent) -> list:
        """Returns the list of agents directly connected to *agent* via any relation."""
        neighbours = set()
        for edges in self.relations.values():
            for a1, a2, _ in edges:
                if a1 is agent:
                    neighbours.add(a2)
                elif a2 is agent:
                    neighbours.add(a1)
        return list(neighbours)

    def _build_adjacency(self) -> dict:
        """Returns an adjacency dict mapping each agent to its set of neighbours."""
        adj = {agent: set() for agent in self.agents}
        for edges in self.relations.values():
            for a1, a2, _ in edges:
                adj.setdefault(a1, set()).add(a2)
                adj.setdefault(a2, set()).add(a1)
        return adj

    #######################################################################
    # Simulation overrides
    #######################################################################

    @staticmethod
    def _build_relation_description(relation_name: str, attrs: dict, perspective_agent=None, other_agent=None) -> str:
        """
        Builds a human-readable description of a relation edge that will be
        communicated to agents via the prompt. The description incorporates
        all meaningful edge attributes so that the LLM understands the nature
        of the relationship.

        Args:
            relation_name (str): The relation type name (e.g. ``"reports_to"``).
            attrs (dict): The edge attributes dictionary.
            perspective_agent (TinyPerson, optional): The agent receiving this
                description (used for directional roles like manager/report).
            other_agent (TinyPerson, optional): The other agent in the relation.

        Returns:
            str: A descriptive string for use in the agent's social context.
        """
        # If the user provided an explicit "description", use it directly.
        if "description" in attrs:
            return attrs["description"]

        parts = [f"Relation: {relation_name}"]

        # Directional role hints (e.g. manager / report)
        if perspective_agent is not None and other_agent is not None:
            if attrs.get("manager") == other_agent.name and attrs.get("report") == perspective_agent.name:
                parts.append(f"(your manager)")
            elif attrs.get("report") == other_agent.name and attrs.get("manager") == perspective_agent.name:
                parts.append(f"(your direct report)")

        # Include selected common attributes in a readable form.
        for key in ("department", "stage", "stage_from", "stage_to", "weight", "role"):
            if key in attrs:
                parts.append(f"{key}={attrs[key]}")

        if attrs.get("cross_department"):
            parts.append("(cross-department link)")

        return "; ".join(parts)

    @transactional()
    def _update_agents_contexts(self):
        """
        Updates agent accessibility based on the current relation graph. Only
        agents that share a relation edge can see each other.

        The relation description communicated to each agent is built from **all**
        meaningful edge attributes (not just a ``"description"`` key), so the
        agent's LLM prompt includes contextual information such as the relation
        type, departmental affiliation, hierarchical role, edge weight, etc.
        """
        for agent in self.agents:
            agent.make_all_agents_inaccessible()

        for relation_name, edges in self.relations.items():
            logger.debug(f"Updating agents' observations for relation '{relation_name}'.")
            for agent_1, agent_2, attrs in edges:
                desc_for_1 = self._build_relation_description(
                    relation_name, attrs,
                    perspective_agent=agent_1, other_agent=agent_2,
                )
                desc_for_2 = self._build_relation_description(
                    relation_name, attrs,
                    perspective_agent=agent_2, other_agent=agent_1,
                )
                agent_1.make_agent_accessible(agent_2, relation_description=desc_for_1)
                agent_2.make_agent_accessible(agent_1, relation_description=desc_for_2)

    @transactional()
    def _step(self, timedelta_per_step=None, randomize_agents_order=True, parallelize=True):
        """
        Performs a single simulation step: updates agent contexts based on
        relations, then delegates to the parent implementation.
        """
        self._current_step += 1
        self._update_agents_contexts()
        return super()._step(
            timedelta_per_step=timedelta_per_step,
            randomize_agents_order=randomize_agents_order,
            parallelize=parallelize,
        )

    #######################################################################
    # Action handlers
    #######################################################################

    @transactional()
    def _handle_actions(self, source: TinyPerson, actions: list):
        """
        Handles the actions issued by agents, enforcing network constraints
        for **all** action types that target another agent.

        Any action (not just TALK or REACH_OUT) whose ``target`` refers to an
        agent present in the environment but **not** connected to the source
        via any relation is blocked, and the source agent is notified.

        Actions without a target, or whose target is not found in the
        environment, are passed through to the parent handler which
        dispatches to the type-specific handlers.

        Args:
            source (TinyPerson): The agent that issued the actions.
            actions (list): A list of action dicts (each with at least a
                ``"type"`` key, and optionally ``"content"`` and ``"target"``).
        """
        allowed_actions = []
        for action in actions:
            action_type = action["type"]
            target = action.get("target")

            # Actions that don't target anyone pass through unconditionally.
            if not target:
                allowed_actions.append(action)
                continue

            target_agent = self.get_agent_by_name(target)

            if target_agent is not None and not self.is_in_relation_with(source, target_agent):
                # Target exists in the environment but is NOT reachable via
                # the network — block and notify.
                logger.debug(
                    f"[{self.name}] {action_type} blocked: "
                    f"{name_or_empty(source)} -> {target} (no relation)."
                )
                source.socialize(
                    f"{target} is not reachable from your current social "
                    f"network, so your {action_type} action was not delivered.",
                    source=self,
                )
            else:
                # Either the target is connected, or the target name doesn't
                # match any agent in the environment (the specific handler
                # can decide what to do).
                allowed_actions.append(action)

        # Delegate the surviving actions to the parent's dispatcher.
        if allowed_actions:
            super()._handle_actions(source, allowed_actions)

    @transactional()
    def _handle_reach_out(self, source_agent: TinyPerson, content: str, target: str):
        """
        Handles the REACH_OUT action. Only succeeds when the source and
        target agents share at least one relation.

        Args:
            source_agent (TinyPerson): The agent that issued the action.
            content (str): The content of the message.
            target (str): The name of the target agent.
        """
        target_agent = self.get_agent_by_name(target)

        if target_agent is not None and self.is_in_relation_with(source_agent, target_agent):
            self._log_message(source_agent, target_agent, content, "REACH_OUT")
            super()._handle_reach_out(source_agent, content, target)
        else:
            logger.debug(
                f"[{self.name}] REACH_OUT blocked: {name_or_empty(source_agent)} -> {target} (no relation)."
            )
            source_agent.socialize(
                f"{target} is not in the same relation as you, so you cannot reach out to them.",
                source=self,
            )

    @transactional()
    def _handle_talk(self, source_agent: TinyPerson, content: str, target: str):
        """
        Handles the TALK action. Messages are only delivered between connected
        agents. If a specific target is named but is not reachable via the
        network, the action is **blocked** and the source agent is notified.
        If no specific target is given (or the target name is not found in
        the environment) and *broadcast_if_no_target* is True, the message is
        broadcast to all connected agents.

        Args:
            source_agent (TinyPerson): The agent that issued the action.
            content (str): The content of the message.
            target (str): The name of the target agent, or None.
        """
        target_agent = self.get_agent_by_name(target) if target else None

        if target_agent is not None and self.is_in_relation_with(source_agent, target_agent):
            # Target exists and is connected — deliver normally.
            logger.debug(
                f"[{self.name}] Delivering message from {name_or_empty(source_agent)} to {name_or_empty(target_agent)}."
            )
            self._log_message(source_agent, target_agent, content, "TALK")
            target_agent.listen(content, source=source_agent)

        elif target_agent is not None:
            # Target exists in the environment but is NOT connected to the
            # source — block the message and let the source know.
            logger.debug(
                f"[{self.name}] TALK blocked: {name_or_empty(source_agent)} -> {target} (no relation)."
            )
            source_agent.socialize(
                f"{target} is not reachable from your current social network, so your message was not delivered.",
                source=self,
            )

        elif self.broadcast_if_no_target:
            # No specific target (or target not found) — broadcast to
            # connected agents.
            self.broadcast(content, source=source_agent)

        else:
            logger.debug(
                f"[{self.name}] TALK blocked: {name_or_empty(source_agent)} -> {target} (not found and broadcast disabled)."
            )

    @transactional()
    def broadcast(self, speech: str, source: AgentOrWorld = None):
        """
        Broadcasts a message to agents connected to the *source*. If *source*
        is not an agent in the network (or is None), falls back to all agents.

        Args:
            speech (str): The content of the message.
            source (AgentOrWorld, optional): The originator of the message.
        """
        logger.debug(f"[{self.name}] Broadcasting message from {name_or_empty(source)}: '{speech}'.")

        if source is not None and source in self.agents:
            connected = self._get_connected_agents(source)
            for agent in connected:
                self._log_message(source, agent, speech, "TALK")
                agent.listen(speech, source=source)
        else:
            for agent in self.agents:
                if agent != source:
                    self._log_message(source, agent, speech, "TALK")
                    agent.listen(speech, source=source)

    #######################################################################
    # Message logging
    #######################################################################

    def _log_message(self, source, target, content, action_type):
        """Records a message in the internal log."""
        self.message_log.append({
            "step": self._current_step,
            "timestamp": self.current_datetime.isoformat() if self.current_datetime else None,
            "source": name_or_empty(source),
            "target": name_or_empty(target),
            "content": content,
            "action_type": action_type,
        })

    def get_message_count(self, source=None, target=None) -> int:
        """
        Returns the number of logged messages, optionally filtered by source
        and/or target agent name.

        Args:
            source (str or TinyPerson, optional): Filter by source name.
            target (str or TinyPerson, optional): Filter by target name.

        Returns:
            int: The count of matching messages.
        """
        return len(self.get_message_log(source=source, target=target))

    def get_message_log(self, source=None, target=None, step=None) -> list:
        """
        Returns the message log, optionally filtered.

        Args:
            source (str or TinyPerson, optional): Filter by source name.
            target (str or TinyPerson, optional): Filter by target name.
            step (int, optional): Filter by simulation step.

        Returns:
            list: A list of message dicts matching the filters.
        """
        src_name = source.name if hasattr(source, "name") else source
        tgt_name = target.name if hasattr(target, "name") else target

        results = self.message_log
        if src_name is not None:
            results = [m for m in results if m["source"] == src_name]
        if tgt_name is not None:
            results = [m for m in results if m["target"] == tgt_name]
        if step is not None:
            results = [m for m in results if m["step"] == step]
        return results

    def clear_message_log(self):
        """Resets the message log."""
        self.message_log = []

    #######################################################################
    # Network statistics
    #######################################################################

    def _unique_edges(self):
        """Returns a set of unique undirected edges as frozensets of agents."""
        edges = set()
        for edge_list in self.relations.values():
            for a1, a2, _ in edge_list:
                edges.add(frozenset((a1, a2)))
        return edges

    def get_adjacency_matrix(self):
        """
        Returns the adjacency matrix of the network.

        Returns:
            tuple: (matrix, agent_list) where matrix is a list-of-lists of 0/1
                and agent_list is the ordered list of agents indexing rows/cols.
        """
        agent_list = list(self.agents)
        idx = {agent: i for i, agent in enumerate(agent_list)}
        n = len(agent_list)
        matrix = [[0] * n for _ in range(n)]

        for edge in self._unique_edges():
            a1, a2 = list(edge)
            i, j = idx[a1], idx[a2]
            matrix[i][j] = 1
            matrix[j][i] = 1

        return matrix, agent_list

    def degree(self, agent=None):
        """
        Returns the degree of *agent*, or a dict mapping every agent to its
        degree if *agent* is None.

        Args:
            agent (TinyPerson, optional): A specific agent.

        Returns:
            int or dict: The degree(s).
        """
        adj = self._build_adjacency()
        if agent is not None:
            return len(adj.get(agent, set()))
        return {a: len(neighbours) for a, neighbours in adj.items()}

    def density(self) -> float:
        """
        Returns the density of the network: ``2 * |E| / (n * (n - 1))``.

        Returns:
            float: The graph density, or 0.0 if fewer than 2 agents.
        """
        n = len(self.agents)
        if n < 2:
            return 0.0
        e = len(self._unique_edges())
        return (2.0 * e) / (n * (n - 1))

    def clustering_coefficient(self, agent=None):
        """
        Returns the local clustering coefficient for *agent*, or the average
        clustering coefficient across all agents if *agent* is None.

        Args:
            agent (TinyPerson, optional): A specific agent.

        Returns:
            float or dict: The clustering coefficient(s).
        """
        adj = self._build_adjacency()

        def _local_cc(a):
            neighbours = list(adj.get(a, set()))
            k = len(neighbours)
            if k < 2:
                return 0.0
            triangles = 0
            for i in range(k):
                for j in range(i + 1, k):
                    if neighbours[j] in adj.get(neighbours[i], set()):
                        triangles += 1
            return (2.0 * triangles) / (k * (k - 1))

        if agent is not None:
            return _local_cc(agent)

        if not self.agents:
            return 0.0
        return sum(_local_cc(a) for a in self.agents) / len(self.agents)

    def connected_components(self) -> list:
        """
        Returns the connected components of the network.

        Returns:
            list: A list of sets, each set containing the agents of one
                connected component.
        """
        adj = self._build_adjacency()
        visited = set()
        components = []

        for agent in self.agents:
            if agent not in visited:
                component = set()
                queue = deque([agent])
                while queue:
                    current = queue.popleft()
                    if current in visited:
                        continue
                    visited.add(current)
                    component.add(current)
                    for neighbour in adj.get(current, set()):
                        if neighbour not in visited:
                            queue.append(neighbour)
                components.append(component)

        return components

    def is_connected(self) -> bool:
        """
        Returns True if the network graph is connected.

        Returns:
            bool: Whether all agents are reachable from any other agent.
        """
        if len(self.agents) <= 1:
            return True
        components = self.connected_components()
        return len(components) == 1

    def shortest_path(self, agent_1, agent_2) -> list:
        """
        Returns the shortest path between two agents using BFS.

        Args:
            agent_1 (TinyPerson): The start agent.
            agent_2 (TinyPerson): The end agent.

        Returns:
            list: An ordered list of agents from *agent_1* to *agent_2*,
                or an empty list if no path exists.
        """
        if agent_1 is agent_2:
            return [agent_1]

        adj = self._build_adjacency()
        visited = {agent_1}
        queue = deque([(agent_1, [agent_1])])

        while queue:
            current, path = queue.popleft()
            for neighbour in adj.get(current, set()):
                if neighbour is agent_2:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append((neighbour, path + [neighbour]))

        return []  # no path

    def diameter(self) -> int:
        """
        Returns the diameter of the network (the longest shortest path). If
        the graph is disconnected, returns -1.

        Returns:
            int: The diameter, or -1 if disconnected.
        """
        if not self.is_connected():
            return -1
        if len(self.agents) <= 1:
            return 0

        max_dist = 0
        for agent in self.agents:
            distances = self._bfs_distances(agent)
            local_max = max(distances.values())
            if local_max > max_dist:
                max_dist = local_max
        return max_dist

    def _bfs_distances(self, start) -> dict:
        """BFS from *start*, returning {agent: distance}."""
        adj = self._build_adjacency()
        distances = {start: 0}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbour in adj.get(current, set()):
                if neighbour not in distances:
                    distances[neighbour] = distances[current] + 1
                    queue.append(neighbour)
        return distances

    def betweenness_centrality(self, agent=None):
        """
        Returns the (normalised) betweenness centrality for *agent*, or a dict
        for all agents if *agent* is None.  Uses Brandes' algorithm.

        Args:
            agent (TinyPerson, optional): A specific agent.

        Returns:
            float or dict: Betweenness centrality value(s).
        """
        adj = self._build_adjacency()
        bc = {a: 0.0 for a in self.agents}
        n = len(self.agents)

        for s in self.agents:
            # BFS from s
            stack = []
            pred = {a: [] for a in self.agents}
            sigma = {a: 0.0 for a in self.agents}
            sigma[s] = 1.0
            dist = {a: -1 for a in self.agents}
            dist[s] = 0
            queue = deque([s])

            while queue:
                v = queue.popleft()
                stack.append(v)
                for w in adj.get(v, set()):
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        pred[w].append(v)

            delta = {a: 0.0 for a in self.agents}
            while stack:
                w = stack.pop()
                for v in pred[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w is not s:
                    bc[w] += delta[w]

        # normalise for undirected graph
        norm = (n - 1) * (n - 2) if n > 2 else 1.0
        for a in bc:
            bc[a] /= norm

        if agent is not None:
            return bc.get(agent, 0.0)
        return bc

    def degree_centrality(self, agent=None):
        """
        Returns the normalised degree centrality for *agent*, or a dict for all
        agents if *agent* is None.

        Args:
            agent (TinyPerson, optional): A specific agent.

        Returns:
            float or dict: Degree centrality value(s).
        """
        n = len(self.agents)
        norm = (n - 1) if n > 1 else 1.0
        degrees = self.degree()

        dc = {a: d / norm for a, d in degrees.items()}
        if agent is not None:
            return dc.get(agent, 0.0)
        return dc

    def get_network_summary(self) -> dict:
        """
        Returns a dictionary with key network metrics.

        Returns:
            dict: Summary containing agents, edges, density, components,
                is_connected, diameter, avg_clustering, degrees, degree
                centrality, and betweenness centrality.
        """
        return {
            "num_agents": len(self.agents),
            "num_edges": len(self._unique_edges()),
            "density": self.density(),
            "num_components": len(self.connected_components()),
            "is_connected": self.is_connected(),
            "diameter": self.diameter(),
            "avg_clustering_coefficient": self.clustering_coefficient(),
            "degrees": {a.name: d for a, d in self.degree().items()},
            "degree_centrality": {a.name: v for a, v in self.degree_centrality().items()},
            "betweenness_centrality": {a.name: v for a, v in self.betweenness_centrality().items()},
        }

    #######################################################################
    # Serialization
    #######################################################################

    def encode_complete_state(self) -> dict:
        """
        Encodes the complete state of the social network, including relations
        and message log, into a serialisable dictionary.

        Returns:
            dict: The encoded state.
        """
        # Encode relations with agent names instead of objects *before*
        # calling super(), because the parent does a deepcopy of __dict__
        # and agent objects contain unpicklable fields (Console, RLock).
        encoded_relations = {}
        for rel_name, edges in self.relations.items():
            encoded_relations[rel_name] = [
                (a1.name, a2.name, copy.deepcopy(attrs))
                for a1, a2, attrs in edges
            ]

        # Temporarily swap in the serialisable version
        original_relations = self.relations
        self.relations = encoded_relations
        try:
            state = super().encode_complete_state()
        finally:
            self.relations = original_relations

        state["relations"] = encoded_relations
        state["message_log"] = copy.deepcopy(self.message_log)
        state["_current_step"] = self._current_step

        return state

    def decode_complete_state(self, state: dict):
        """
        Restores the social network state from a previously encoded dictionary.

        Args:
            state (dict): The encoded state dictionary.

        Returns:
            Self: This network instance.
        """
        state = copy.deepcopy(state)

        # Extract our custom fields before the parent consumes the state
        encoded_relations = state.pop("relations", {})
        message_log = state.pop("message_log", [])
        current_step = state.pop("_current_step", 0)

        # Let the parent restore agents and other base fields
        super().decode_complete_state(state)

        # Reconstruct relation tuples from agent names
        self.relations = {}
        for rel_name, edges in encoded_relations.items():
            self.relations[rel_name] = []
            for a1_name, a2_name, attrs in edges:
                agent_1 = self.get_agent_by_name(a1_name)
                agent_2 = self.get_agent_by_name(a2_name)
                if agent_1 is not None and agent_2 is not None:
                    self.relations[rel_name].append((agent_1, agent_2, attrs))
                else:
                    logger.warning(
                        f"[{self.name}] Could not restore relation '{rel_name}' edge "
                        f"({a1_name}, {a2_name}): agent(s) not found."
                    )

        self.message_log = message_log
        self._current_step = current_step

        return self

    #######################################################################
    # Representation
    #######################################################################

    def __repr__(self):
        return f"TinySocialNetwork(name='{self.name}', agents={len(self.agents)}, edges={len(self._unique_edges())})"


###########################################################################
# Factory
###########################################################################

class TinySocialNetworkFactory:
    """
    Factory for creating pre-configured :class:`TinySocialNetwork` instances
    with various well-known graph topologies.

    All ``create_*`` methods require a list of pre-created ``TinyPerson``
    instances.  To conveniently generate those agents from a
    ``TinyPersonFactory``, use the :meth:`populate_agents` helper first::

        factory = TinyPersonFactory("A tech startup in Austin.")
        agents = TinySocialNetworkFactory.populate_agents(
            factory, number_of_agents=10,
            agent_particularities="Software engineers with varied seniority."
        )
        net = TinySocialNetworkFactory.create_random_network("startup", agents)
    """

    @staticmethod
    def populate_agents(
        person_factory,
        number_of_agents: int,
        agent_particularities: str = None,
    ) -> list:
        """
        Uses a :class:`TinyPersonFactory` to generate agents that can then be
        passed to any of the ``create_*`` topology methods.

        This is the recommended way to obtain agents when you do not want to
        create them manually. Every returned agent is a fully initialised
        ``TinyPerson`` — there are **no empty nodes**.

        Args:
            person_factory: A ``TinyPersonFactory`` instance (already
                configured with a context / sampling space).
            number_of_agents (int): How many agents to create.
            agent_particularities (str, optional): An additional prompt hint
                passed to ``generate_people`` to steer persona generation.

        Returns:
            list: A list of ``TinyPerson`` instances ready for use with any
                ``create_*`` method.
        """
        return person_factory.generate_people(
            number_of_people=number_of_agents,
            agent_particularities=agent_particularities,
        )

    @staticmethod
    def create_random_network(name, agents, p=0.3, relation_name="connected"):
        """
        Creates an Erdős–Rényi random graph where each pair of agents is
        connected independently with probability *p*.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            p (float): Edge probability.
            relation_name (str): The relation name for edges.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)
        for agent in agents:
            net.add_agent(agent)
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                if random.random() < p:
                    net.add_relation(agents[i], agents[j], name=relation_name)
        return net

    @staticmethod
    def create_small_world_network(name, agents, k=4, p=0.1, relation_name="connected"):
        """
        Creates a Watts-Strogatz small-world graph. Agents are arranged in a
        ring and each is connected to its *k* nearest neighbours; then each
        edge is rewired with probability *p*.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            k (int): Number of nearest neighbours (must be even).
            p (float): Rewiring probability.
            relation_name (str): The relation name for edges.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        n = len(agents)
        net = TinySocialNetwork(name)
        for agent in agents:
            net.add_agent(agent)

        if n < 2:
            return net

        k = min(k, n - 1)
        half_k = k // 2

        # Build regular ring lattice edges as index pairs
        edges = set()
        for i in range(n):
            for j in range(1, half_k + 1):
                target = (i + j) % n
                edge = (min(i, target), max(i, target))
                edges.add(edge)

        # Rewire
        rewired_edges = set()
        for i, j in list(edges):
            if random.random() < p:
                # rewire edge (i, j): keep i, pick a new target
                candidates = [c for c in range(n) if c != i and (min(i, c), max(i, c)) not in edges and (min(i, c), max(i, c)) not in rewired_edges]
                if candidates:
                    new_j = random.choice(candidates)
                    edges.discard((i, j))
                    new_edge = (min(i, new_j), max(i, new_j))
                    rewired_edges.add(new_edge)

        all_edges = edges | rewired_edges
        for i, j in all_edges:
            net.add_relation(agents[i], agents[j], name=relation_name)

        return net

    @staticmethod
    def create_scale_free_network(name, agents, m=2, relation_name="connected"):
        """
        Creates a Barabási-Albert scale-free graph using preferential
        attachment. Each new node attaches to *m* existing nodes.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            m (int): Number of edges to attach from each new node.
            relation_name (str): The relation name for edges.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        n = len(agents)
        net = TinySocialNetwork(name)

        if n == 0:
            return net

        m = min(m, n - 1) if n > 1 else 0

        # Start with a fully connected set of m+1 nodes
        initial_count = min(m + 1, n)
        for i in range(initial_count):
            net.add_agent(agents[i])
        for i in range(initial_count):
            for j in range(i + 1, initial_count):
                net.add_relation(agents[i], agents[j], name=relation_name)

        # Degree list for preferential attachment (repeat node for each edge)
        degree_list = []
        for i in range(initial_count):
            degree_list.extend([i] * (initial_count - 1))

        # Add remaining nodes
        for idx in range(initial_count, n):
            net.add_agent(agents[idx])
            targets = set()
            while len(targets) < m and degree_list:
                chosen = degree_list[random.randint(0, len(degree_list) - 1)]
                targets.add(chosen)

            for t in targets:
                net.add_relation(agents[idx], agents[t], name=relation_name)
                degree_list.append(idx)
                degree_list.append(t)

        return net

    @staticmethod
    def create_corporate_hierarchy(name, agents, ceo=None, managers=None, span_of_control=3, relation_name="reports_to", context=None):
        """
        Creates a tree-shaped corporate hierarchy. If *ceo* is not specified
        the first agent is used. If *managers* is not specified, they are
        selected automatically based on *span_of_control*.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            ceo (TinyPerson, optional): The root agent.
            managers (list, optional): Agents to serve as managers.
            span_of_control (int): Maximum direct reports per manager.
            relation_name (str): The relation name for edges.
            context (str, optional): Free-form description of the
                organizational context or desired constraints (not used by this
                deterministic variant — see
                :meth:`create_corporate_hierarchy_with_llm` for the LLM-based
                version).

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)

        if not agents:
            return net

        if ceo is None:
            ceo = agents[0]

        for agent in agents:
            net.add_agent(agent)

        remaining = [a for a in agents if a is not ceo]

        # Build tree level by level using BFS
        current_level = [ceo]
        while remaining:
            next_level = []
            for manager in current_level:
                reports = remaining[:span_of_control]
                remaining = remaining[span_of_control:]
                for report in reports:
                    net.add_relation(manager, report, name=relation_name,
                                     attributes={"manager": manager.name, "report": report.name})
                    next_level.append(report)
                if not remaining:
                    break
            if not next_level:
                break
            current_level = next_level

        return net

    @staticmethod
    def create_workflow_pipeline(name, agents, stages=None, relation_name="workflow", context=None):
        """
        Creates a sequential pipeline. If *stages* is not given, each agent
        forms its own stage. Agents within the same stage are fully connected,
        and adjacent stages are connected.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            stages (list of lists, optional): Grouping of agents into stages.
            relation_name (str): The relation name for edges.
            context (str, optional): Free-form description of the workflow
                context or desired constraints (not used by this deterministic
                variant — see :meth:`create_workflow_pipeline_with_llm`).

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)

        if stages is None:
            stages = [[a] for a in agents]

        all_agents = [a for stage in stages for a in stage]
        for agent in all_agents:
            if agent not in net.agents:
                net.add_agent(agent)

        for stage_idx, stage in enumerate(stages):
            # Intra-stage: fully connected
            for i in range(len(stage)):
                for j in range(i + 1, len(stage)):
                    net.add_relation(stage[i], stage[j], name=relation_name,
                                     attributes={"stage": stage_idx})

            # Inter-stage: connect to the next stage
            if stage_idx < len(stages) - 1:
                next_stage = stages[stage_idx + 1]
                for a in stage:
                    for b in next_stage:
                        net.add_relation(a, b, name=relation_name,
                                         attributes={"stage_from": stage_idx, "stage_to": stage_idx + 1})

        return net

    @staticmethod
    def create_star_network(name, agents, hub=None, relation_name="connected"):
        """
        Creates a star (hub-and-spoke) network. If *hub* is not given, the
        first agent is used.

        Args:
            name (str): Name of the network.
            agents (list): List of TinyPerson instances.
            hub (TinyPerson, optional): The hub agent.
            relation_name (str): The relation name for edges.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)

        if not agents:
            return net

        if hub is None:
            hub = agents[0]

        for agent in agents:
            net.add_agent(agent)

        for agent in agents:
            if agent is not hub:
                net.add_relation(hub, agent, name=relation_name)

        return net

    @staticmethod
    def create_bipartite_network(name, group_a, group_b, p=0.5, relation_name="cross_group"):
        """
        Creates a bipartite graph with random cross-group connections. Each
        pair of agents from different groups is connected with probability *p*.

        Args:
            name (str): Name of the network.
            group_a (list): First group of agents.
            group_b (list): Second group of agents.
            p (float): Edge probability between groups.
            relation_name (str): The relation name for edges.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)

        for agent in group_a + group_b:
            net.add_agent(agent)

        for a in group_a:
            for b in group_b:
                if random.random() < p:
                    net.add_relation(a, b, name=relation_name)

        return net

    @staticmethod
    def create_department_network(name, departments, inter_department_p=0.1, relation_name="colleague", context=None):
        """
        Creates a network from a department mapping. Agents within the same
        department are fully connected; agents in different departments are
        connected with probability *inter_department_p*.

        Args:
            name (str): Name of the network.
            departments (dict): Mapping of ``{dept_name: [agents]}``.
            inter_department_p (float): Cross-department edge probability.
            relation_name (str): The relation name for edges.
            context (str, optional): Free-form description of the
                organizational context or desired constraints (not used by this
                deterministic variant — see
                :meth:`create_department_network_with_llm`).

        Returns:
            TinySocialNetwork: The constructed network.
        """
        net = TinySocialNetwork(name)

        all_agents = []
        dept_list = list(departments.items())

        for dept_name, members in dept_list:
            for agent in members:
                if agent not in net.agents:
                    net.add_agent(agent)
                all_agents.append(agent)

            # Fully connect within department
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    net.add_relation(members[i], members[j], name=relation_name,
                                     attributes={"department": dept_name})

        # Random inter-department connections
        for d1 in range(len(dept_list)):
            for d2 in range(d1 + 1, len(dept_list)):
                members_1 = dept_list[d1][1]
                members_2 = dept_list[d2][1]
                for a in members_1:
                    for b in members_2:
                        if random.random() < inter_department_p:
                            net.add_relation(a, b, name=relation_name,
                                             attributes={"cross_department": True})

        return net

    #######################################################################
    # LLM-based factory methods
    #######################################################################

    # Rough token-per-char ratio for modern tokenizers (≈ 4 chars/token).
    _CHARS_PER_TOKEN = 4
    # Conservative default context window used when we cannot determine the
    # actual model limit.  We leave headroom for the LLM response.
    _DEFAULT_MAX_INPUT_TOKENS = 100_000

    @staticmethod
    def _estimate_prompt_tokens(text: str) -> int:
        """Returns a rough token-count estimate for *text*."""
        return max(1, len(text) // TinySocialNetworkFactory._CHARS_PER_TOKEN)

    @staticmethod
    def _validate_prompt_length(prompt_text: str, max_input_tokens: int = None):
        """Raises ``ValueError`` if *prompt_text* is too long for the model."""
        limit = max_input_tokens or TinySocialNetworkFactory._DEFAULT_MAX_INPUT_TOKENS
        est = TinySocialNetworkFactory._estimate_prompt_tokens(prompt_text)
        if est > limit:
            raise ValueError(
                f"The composed prompt is approximately {est} tokens, which "
                f"exceeds the configured limit of {limit} tokens.  Reduce "
                f"the number of agents or shorten agent biographies."
            )

    @staticmethod
    def _build_agent_roster(agents) -> str:
        """Returns a numbered roster of agent mini-bios for use in prompts."""
        lines = []
        for idx, agent in enumerate(agents, 1):
            bio = agent.minibio(extended=True)
            lines.append(f"  {idx}. **{agent.name}** — {bio}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Corporate hierarchy (LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def create_corporate_hierarchy_with_llm(
        name: str,
        agents: list,
        context: str = "",
        relation_name: str = "reports_to",
        max_input_tokens: int = None,
    ) -> "TinySocialNetwork":
        """
        Uses an LLM to assign agents to corporate-hierarchy positions
        (CEO, senior management, middle management, individual contributors)
        based on each agent's mini-biography, then builds the reporting tree.

        The LLM produces a JSON plan of ``{manager_name: [report_name, …]}``
        entries. The plan is executed deterministically.

        Args:
            name (str): Name of the network.
            agents (list): Pre-created ``TinyPerson`` instances.
            context (str): Free-form description of the organisation, its
                industry, culture, or any constraints the user wants to
                impose (e.g. "a mid-size fintech startup in Berlin").
            relation_name (str): Relation name for edges.
            max_input_tokens (int, optional): Override the default maximum
                input-prompt size.  If the prompt exceeds this limit a
                ``ValueError`` is raised.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        from tinytroupe.utils.llm import LLMChat

        if len(agents) < 2:
            return TinySocialNetworkFactory.create_corporate_hierarchy(
                name, agents, relation_name=relation_name)

        roster = TinySocialNetworkFactory._build_agent_roster(agents)
        agent_names_json = json.dumps([a.name for a in agents])

        system_prompt = textwrap.dedent("""\
            You are an expert organisational designer. Given a roster of
            people and an organisational context you must decide who should
            occupy which position in a realistic corporate hierarchy.

            Rules:
            1. Choose exactly ONE person as CEO / top leader.
            2. Assign a realistic number of middle managers — not everyone
               can be a manager and not everyone should be a leaf.  Use a
               span-of-control between 2 and 6 direct reports per manager.
            3. The remaining people are individual contributors who report
               to the manager most appropriate for them (based on skills,
               experience, seniority, domain, etc.).
            4. Every person must appear exactly once as a report (except the
               CEO who appears only as a manager).
            5. Output **only** valid JSON — no commentary.

            Output format (a JSON object):
            {
              "hierarchy": {
                "<manager_name>": ["<report_name>", ...],
                ...
              }
            }

            Every name in the output **must** be taken verbatim from the
            roster — do not invent new names.
        """)

        user_prompt = textwrap.dedent(f"""\
            ## Organisational context
            {context if context else "A typical business organisation."}

            ## Available people
            {roster}

            ## Complete list of valid names
            {agent_names_json}

            Based on each person's background, skills and experience,
            produce the hierarchy JSON described above.  Make sure the
            assignments are realistic: senior / experienced people should
            lead, and domain experts should be grouped under the most
            relevant manager.
        """)

        full_prompt = system_prompt + "\n" + user_prompt
        TinySocialNetworkFactory._validate_prompt_length(full_prompt, max_input_tokens)

        result = LLMChat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        ).call()

        plan = TinySocialNetworkFactory._parse_llm_json(result, expected_key="hierarchy")
        return TinySocialNetworkFactory._execute_hierarchy_plan(
            name, agents, plan, relation_name)

    @staticmethod
    def _execute_hierarchy_plan(name, agents, plan, relation_name):
        """Deterministically builds a hierarchy from a ``{manager: [reports]}`` plan."""
        net = TinySocialNetwork(name)
        name_to_agent = {a.name: a for a in agents}

        for agent in agents:
            net.add_agent(agent)

        for manager_name, report_names in plan.items():
            manager = name_to_agent.get(manager_name)
            if manager is None:
                logger.warning(
                    f"LLM plan references unknown manager '{manager_name}'; skipping.")
                continue
            for rname in report_names:
                report = name_to_agent.get(rname)
                if report is None:
                    logger.warning(
                        f"LLM plan references unknown report '{rname}'; skipping.")
                    continue
                net.add_relation(manager, report, name=relation_name,
                                 attributes={"manager": manager.name, "report": report.name})

        return net

    # ------------------------------------------------------------------
    # Workflow pipeline (LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def create_workflow_pipeline_with_llm(
        name: str,
        agents: list,
        context: str = "",
        relation_name: str = "workflow",
        max_input_tokens: int = None,
    ) -> "TinySocialNetwork":
        """
        Uses an LLM to assign agents to workflow-pipeline stages based on
        their mini-biographies, then builds the stage graph.

        Args:
            name (str): Name of the network.
            agents (list): Pre-created ``TinyPerson`` instances.
            context (str): Free-form description of the workflow, process
                or value-chain (e.g. "a software development lifecycle from
                requirements through deployment").
            relation_name (str): Relation name for edges.
            max_input_tokens (int, optional): Maximum input-prompt size.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        from tinytroupe.utils.llm import LLMChat

        if len(agents) < 2:
            return TinySocialNetworkFactory.create_workflow_pipeline(
                name, agents, relation_name=relation_name)

        roster = TinySocialNetworkFactory._build_agent_roster(agents)
        agent_names_json = json.dumps([a.name for a in agents])

        system_prompt = textwrap.dedent("""\
            You are an expert workflow and process designer. Given a roster
            of people and a process context you must assign each person to
            the pipeline stage that best matches their skills and role.

            Rules:
            1. Create between 2 and 6 named stages that form a sequential
               pipeline (e.g. "Requirements → Design → Implementation →
               Testing → Deployment").
            2. Every person must appear in exactly one stage.
            3. Each stage must have at least one person.
            4. Assign people to stages based on their expertise and
               background — the assignments must be realistic.
            5. Output **only** valid JSON — no commentary.

            Output format:
            {
              "stages": [
                {"stage_name": "<name>", "members": ["<person_name>", ...]},
                ...
              ]
            }

            Stage order matters: the first entry is the start of the
            pipeline, the last entry is the end. Every name in the output
            **must** be taken verbatim from the roster.
        """)

        user_prompt = textwrap.dedent(f"""\
            ## Workflow / process context
            {context if context else "A typical business workflow."}

            ## Available people
            {roster}

            ## Complete list of valid names
            {agent_names_json}

            Assign each person to the most appropriate stage and produce
            the JSON described above.
        """)

        full_prompt = system_prompt + "\n" + user_prompt
        TinySocialNetworkFactory._validate_prompt_length(full_prompt, max_input_tokens)

        result = LLMChat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        ).call()

        plan = TinySocialNetworkFactory._parse_llm_json(result, expected_key="stages")
        return TinySocialNetworkFactory._execute_pipeline_plan(
            name, agents, plan, relation_name)

    @staticmethod
    def _execute_pipeline_plan(name, agents, stage_plan, relation_name):
        """Deterministically builds a pipeline from a list of stage dicts."""
        name_to_agent = {a.name: a for a in agents}
        stages = []
        for entry in stage_plan:
            stage_agents = []
            for pname in entry.get("members", []):
                agent = name_to_agent.get(pname)
                if agent is not None:
                    stage_agents.append(agent)
                else:
                    logger.warning(
                        f"LLM plan references unknown agent '{pname}'; skipping.")
            if stage_agents:
                stages.append(stage_agents)

        return TinySocialNetworkFactory.create_workflow_pipeline(
            name, agents, stages=stages, relation_name=relation_name)

    # ------------------------------------------------------------------
    # Department network (LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def create_department_network_with_llm(
        name: str,
        agents: list,
        context: str = "",
        inter_department_p: float = 0.1,
        relation_name: str = "colleague",
        max_input_tokens: int = None,
    ) -> "TinySocialNetwork":
        """
        Uses an LLM to assign agents to departments based on their
        mini-biographies, then builds the department network.

        Args:
            name (str): Name of the network.
            agents (list): Pre-created ``TinyPerson`` instances.
            context (str): Free-form description of the organisation or
                desired department structure (e.g. "a hospital with
                clinical, research and administrative departments").
            inter_department_p (float): Random cross-department edge
                probability (passed through to
                :meth:`create_department_network`).
            relation_name (str): Relation name for edges.
            max_input_tokens (int, optional): Maximum input-prompt size.

        Returns:
            TinySocialNetwork: The constructed network.
        """
        from tinytroupe.utils.llm import LLMChat

        if len(agents) < 2:
            return TinySocialNetworkFactory.create_department_network(
                name, {"default": agents}, relation_name=relation_name)

        roster = TinySocialNetworkFactory._build_agent_roster(agents)
        agent_names_json = json.dumps([a.name for a in agents])

        system_prompt = textwrap.dedent("""\
            You are an expert organisational designer. Given a roster of
            people and an organisational context you must assign each
            person to the department that best matches their background,
            skills and role.

            Rules:
            1. Create between 2 and 8 departments with realistic names
               that fit the context (e.g. "Engineering", "Sales",
               "Finance", "Operations", …).
            2. Every person must appear in exactly one department.
            3. Each department must have at least one person.
            4. Assignments must be realistic — match people to departments
               based on their expertise and experience.
            5. Output **only** valid JSON — no commentary.

            Output format:
            {
              "departments": {
                "<department_name>": ["<person_name>", ...],
                ...
              }
            }

            Every name in the output **must** be taken verbatim from the
            roster.
        """)

        user_prompt = textwrap.dedent(f"""\
            ## Organisational context
            {context if context else "A typical business organisation."}

            ## Available people
            {roster}

            ## Complete list of valid names
            {agent_names_json}

            Assign each person to the most appropriate department and
            produce the JSON described above.
        """)

        full_prompt = system_prompt + "\n" + user_prompt
        TinySocialNetworkFactory._validate_prompt_length(full_prompt, max_input_tokens)

        result = LLMChat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        ).call()

        plan = TinySocialNetworkFactory._parse_llm_json(result, expected_key="departments")
        return TinySocialNetworkFactory._execute_department_plan(
            name, agents, plan, inter_department_p, relation_name)

    @staticmethod
    def _execute_department_plan(name, agents, dept_plan, inter_department_p, relation_name):
        """Deterministically builds a department network from a dept mapping."""
        name_to_agent = {a.name: a for a in agents}
        departments = {}
        for dept_name, member_names in dept_plan.items():
            members = []
            for pname in member_names:
                agent = name_to_agent.get(pname)
                if agent is not None:
                    members.append(agent)
                else:
                    logger.warning(
                        f"LLM plan references unknown agent '{pname}'; skipping.")
            if members:
                departments[dept_name] = members

        return TinySocialNetworkFactory.create_department_network(
            name, departments, inter_department_p=inter_department_p,
            relation_name=relation_name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_json(raw, expected_key: str):
        """Extracts JSON from the LLM response and returns the value under
        *expected_key*.  Raises ``ValueError`` on failure."""
        from tinytroupe.utils.llm import extract_json

        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            raise ValueError(
                f"LLM returned a non-object JSON value: {type(parsed).__name__}")

        if expected_key in parsed:
            return parsed[expected_key]

        # The LLM might have returned the expected structure at the top level
        # (without wrapping it under the expected key).  Fall back gracefully.
        if expected_key in ("hierarchy", "departments") and any(
            isinstance(v, list) for v in parsed.values()
        ):
            return parsed

        raise ValueError(
            f"LLM response JSON missing expected key '{expected_key}'.  "
            f"Keys found: {list(parsed.keys())}"
        )