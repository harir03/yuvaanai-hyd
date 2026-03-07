"""
Intelli-Credit — Neo4j Knowledge Graph Client

Async Neo4j client with in-memory fallback for graph operations.
Follows the same pattern as redis_client.py — InMemoryGraph class
provides full functionality without Neo4j for development/demo.

Node Types: Company, Director, Supplier, Customer, Bank, Auditor,
            RatingAgency, Court, Case
Relationship Types: SUPPLIES_TO, BUYS_FROM, IS_DIRECTOR_OF, FAMILY_OF,
                    HAS_CHARGE, OUTSTANDING_RECEIVABLE, IS_AUDITOR_OF,
                    HAS_RATING_FROM, FILED_CASE_AGAINST
"""

import logging
import json
from typing import Optional, Dict, List, Any, Tuple, Set
from enum import Enum


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Node and Relationship Type Enums
# ──────────────────────────────────────────────

class NodeType(str, Enum):
    COMPANY = "Company"
    DIRECTOR = "Director"
    SUPPLIER = "Supplier"
    CUSTOMER = "Customer"
    BANK = "Bank"
    AUDITOR = "Auditor"
    RATING_AGENCY = "RatingAgency"
    COURT = "Court"
    CASE = "Case"


class RelationshipType(str, Enum):
    SUPPLIES_TO = "SUPPLIES_TO"
    BUYS_FROM = "BUYS_FROM"
    IS_DIRECTOR_OF = "IS_DIRECTOR_OF"
    FAMILY_OF = "FAMILY_OF"
    HAS_CHARGE = "HAS_CHARGE"
    OUTSTANDING_RECEIVABLE = "OUTSTANDING_RECEIVABLE"
    IS_AUDITOR_OF = "IS_AUDITOR_OF"
    HAS_RATING_FROM = "HAS_RATING_FROM"
    FILED_CASE_AGAINST = "FILED_CASE_AGAINST"


# ──────────────────────────────────────────────
# In-Memory Graph Fallback
# ──────────────────────────────────────────────

class InMemoryGraph:
    """
    In-memory graph store that mimics Neo4j operations.
    Used when Neo4j is unavailable (dev, demo, tests).

    Stores nodes as dicts keyed by (label, name) tuples.
    Stores relationships as a list of (from_key, rel_type, to_key, properties) tuples.
    """

    def __init__(self):
        # nodes: {node_id: {"label": str, "name": str, ...properties}}
        self._nodes: Dict[str, Dict[str, Any]] = {}
        # relationships: [(from_id, rel_type, to_id, {properties})]
        self._relationships: List[Tuple[str, str, str, Dict[str, Any]]] = []
        # Counters for tracking
        self._next_id: int = 1

    def _make_node_id(self, label: str, name: str) -> str:
        """Create a deterministic node ID from label + name."""
        return f"{label}::{name.lower().strip()}"

    async def create_node(
        self, label: str, name: str, properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or update a node. Returns the node ID."""
        node_id = self._make_node_id(label, name)
        if node_id in self._nodes:
            # Merge properties into existing node
            if properties:
                self._nodes[node_id].update(properties)
            return node_id

        node_data = {"label": label, "name": name, "node_id": node_id}
        if properties:
            node_data.update(properties)
        self._nodes[node_id] = node_data
        return node_id

    async def create_relationship(
        self,
        from_label: str,
        from_name: str,
        rel_type: str,
        to_label: str,
        to_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a relationship between two nodes. Creates nodes if they don't exist."""
        from_id = await self.create_node(from_label, from_name)
        to_id = await self.create_node(to_label, to_name)

        # Check for existing relationship
        for f_id, r_type, t_id, _ in self._relationships:
            if f_id == from_id and r_type == rel_type and t_id == to_id:
                return False  # Already exists

        self._relationships.append(
            (from_id, rel_type, to_id, properties or {})
        )
        return True

    async def get_node(self, label: str, name: str) -> Optional[Dict[str, Any]]:
        """Get a node by label and name."""
        node_id = self._make_node_id(label, name)
        return self._nodes.get(node_id)

    async def get_nodes_by_label(self, label: str) -> List[Dict[str, Any]]:
        """Get all nodes with a given label."""
        return [
            n for n in self._nodes.values()
            if n.get("label") == label
        ]

    async def get_relationships(
        self,
        from_label: Optional[str] = None,
        from_name: Optional[str] = None,
        rel_type: Optional[str] = None,
        to_label: Optional[str] = None,
        to_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query relationships with optional filters."""
        results = []
        from_id = self._make_node_id(from_label, from_name) if from_label and from_name else None
        to_id = self._make_node_id(to_label, to_name) if to_label and to_name else None

        for f_id, r_type, t_id, props in self._relationships:
            if from_id and f_id != from_id:
                continue
            if to_id and t_id != to_id:
                continue
            if rel_type and r_type != rel_type:
                continue

            results.append({
                "from": self._nodes.get(f_id, {}),
                "relationship": r_type,
                "to": self._nodes.get(t_id, {}),
                "properties": props,
            })
        return results

    async def multi_hop_query(
        self, start_label: str, start_name: str, max_hops: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        BFS traversal from a starting node, returning all paths up to max_hops.
        Returns list of paths, each path is a list of (node, rel_type, node) steps.
        """
        start_id = self._make_node_id(start_label, start_name)
        if start_id not in self._nodes:
            return []

        # Build adjacency list from relationships
        adjacency: Dict[str, List[Tuple[str, str, str]]] = {}
        for f_id, r_type, t_id, _ in self._relationships:
            adjacency.setdefault(f_id, []).append((r_type, t_id, "outgoing"))
            adjacency.setdefault(t_id, []).append((r_type, f_id, "incoming"))

        # BFS
        paths: List[Dict[str, Any]] = []
        visited: Set[str] = {start_id}
        # Queue entries: (current_node_id, path_so_far, hop_count)
        queue = [(start_id, [], 0)]

        while queue:
            current_id, path, hops = queue.pop(0)
            if hops >= max_hops:
                continue

            for r_type, neighbor_id, direction in adjacency.get(current_id, []):
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)

                step = {
                    "from": self._nodes.get(current_id, {}),
                    "relationship": r_type,
                    "direction": direction,
                    "to": self._nodes.get(neighbor_id, {}),
                    "hop": hops + 1,
                }
                new_path = path + [step]
                paths.append({
                    "end_node": self._nodes.get(neighbor_id, {}),
                    "hops": hops + 1,
                    "path": new_path,
                })
                queue.append((neighbor_id, new_path, hops + 1))

        return paths

    async def find_shared_directors(self) -> List[Dict[str, Any]]:
        """Find directors who are linked to multiple companies."""
        director_companies: Dict[str, List[str]] = {}

        for f_id, r_type, t_id, _ in self._relationships:
            if r_type == RelationshipType.IS_DIRECTOR_OF:
                director_name = self._nodes.get(f_id, {}).get("name", "")
                company_name = self._nodes.get(t_id, {}).get("name", "")
                director_companies.setdefault(director_name, []).append(company_name)

        return [
            {"director": director, "companies": companies}
            for director, companies in director_companies.items()
            if len(companies) > 1
        ]

    async def detect_circular_trading(self) -> List[List[str]]:
        """
        Detect circular supply chains (A→B→C→A).
        Returns a list of cycles found.
        """
        supply_rels = [
            (f_id, t_id) for f_id, r_type, t_id, _ in self._relationships
            if r_type in (RelationshipType.SUPPLIES_TO, RelationshipType.BUYS_FROM)
        ]

        # Build directed adjacency for supply chain
        adj: Dict[str, List[str]] = {}
        for f_id, t_id in supply_rels:
            adj.setdefault(f_id, []).append(t_id)

        cycles: List[List[str]] = []
        visited: Set[str] = set()

        def dfs(node: str, path: List[str], path_set: Set[str]):
            for neighbor in adj.get(node, []):
                if neighbor == path[0] and len(path) >= 3:
                    # Cycle found
                    cycle_names = [
                        self._nodes.get(n, {}).get("name", n) for n in path
                    ]
                    cycles.append(cycle_names)
                elif neighbor not in path_set and neighbor not in visited:
                    path.append(neighbor)
                    path_set.add(neighbor)
                    dfs(neighbor, path, path_set)
                    path.pop()
                    path_set.discard(neighbor)

        for start in adj:
            if start not in visited:
                dfs(start, [start], {start})
                visited.add(start)

        return cycles

    async def get_community_clusters(self) -> List[List[str]]:
        """
        Detect community clusters using connected components.
        Uses simple BFS (NetworkX Louvain used when available in full pipeline).
        """
        all_node_ids = set(self._nodes.keys())
        visited: Set[str] = set()
        clusters: List[List[str]] = []

        # Build undirected adjacency
        undirected: Dict[str, Set[str]] = {}
        for f_id, _, t_id, _ in self._relationships:
            undirected.setdefault(f_id, set()).add(t_id)
            undirected.setdefault(t_id, set()).add(f_id)

        for node_id in all_node_ids:
            if node_id in visited:
                continue
            # BFS to find connected component
            component: List[str] = []
            queue = [node_id]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(self._nodes[current].get("name", current))
                for neighbor in undirected.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            if component:
                clusters.append(component)

        return clusters

    async def get_node_count(self) -> int:
        return len(self._nodes)

    async def get_relationship_count(self) -> int:
        return len(self._relationships)

    async def get_stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        labels: Dict[str, int] = {}
        for node in self._nodes.values():
            label = node.get("label", "Unknown")
            labels[label] = labels.get(label, 0) + 1

        rel_types: Dict[str, int] = {}
        for _, r_type, _, _ in self._relationships:
            rel_types[r_type] = rel_types.get(r_type, 0) + 1

        return {
            "total_nodes": len(self._nodes),
            "total_relationships": len(self._relationships),
            "nodes_by_label": labels,
            "relationships_by_type": rel_types,
        }

    async def clear(self):
        """Clear all graph data."""
        self._nodes.clear()
        self._relationships.clear()

    async def close(self):
        pass


# ──────────────────────────────────────────────
# Neo4j Client
# ──────────────────────────────────────────────

class Neo4jClient:
    """
    Async Neo4j client with in-memory fallback.

    Wraps the Neo4j async driver for production, falls back to
    InMemoryGraph for development/testing/demo without Docker.
    """

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        self._uri = uri
        self._user = user
        self._password = password
        self._driver = None
        self._graph: Optional[InMemoryGraph] = None
        self._use_neo4j = False
        self._initialized = False

    async def initialize(self):
        """Connect to Neo4j or fall back to in-memory graph."""
        if self._initialized:
            return

        if self._uri:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(
                    self._uri, auth=(self._user, self._password),
                )
                # Verify connectivity
                async with self._driver.session() as session:
                    await session.run("RETURN 1")
                self._use_neo4j = True
                self._graph = None
                logger.info("[Neo4j] Connected to Neo4j")
            except Exception as e:
                logger.warning(f"[Neo4j] Unavailable ({e}), using in-memory fallback")
                self._driver = None
                self._graph = InMemoryGraph()
                self._use_neo4j = False
        else:
            logger.info("[Neo4j] No URI configured, using in-memory fallback")
            self._graph = InMemoryGraph()
            self._use_neo4j = False

        self._initialized = True

    # ──────────────────────────────────────────────
    # Node Operations
    # ──────────────────────────────────────────────

    async def create_node(
        self, label: str, name: str, properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or merge a node. Returns its identifier."""
        await self._ensure_initialized()

        if self._use_neo4j:
            props = properties or {}
            props["name"] = name
            prop_str = ", ".join(f"n.{k} = ${k}" for k in props if k != "name")
            set_clause = f"SET {prop_str}" if prop_str else ""
            query = f"MERGE (n:{label} {{name: $name}}) {set_clause} RETURN n.name AS name"
            async with self._driver.session() as session:
                result = await session.run(query, **props)
                record = await result.single()
                return record["name"] if record else name
        else:
            return await self._graph.create_node(label, name, properties)

    async def create_relationship(
        self,
        from_label: str,
        from_name: str,
        rel_type: str,
        to_label: str,
        to_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Create a relationship between two nodes (MERGE semantics)."""
        await self._ensure_initialized()

        if self._use_neo4j:
            props = properties or {}
            prop_str = ""
            if props:
                set_pairs = ", ".join(f"r.{k} = $rel_{k}" for k in props)
                prop_str = f"SET {set_pairs}"
                props = {f"rel_{k}": v for k, v in props.items()}

            query = (
                f"MERGE (a:{from_label} {{name: $from_name}}) "
                f"MERGE (b:{to_label} {{name: $to_name}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"{prop_str} "
                f"RETURN type(r) AS rel"
            )
            async with self._driver.session() as session:
                result = await session.run(
                    query, from_name=from_name, to_name=to_name, **props,
                )
                record = await result.single()
                return record is not None
        else:
            return await self._graph.create_relationship(
                from_label, from_name, rel_type, to_label, to_name, properties,
            )

    async def get_node(self, label: str, name: str) -> Optional[Dict[str, Any]]:
        """Get a node by label and name."""
        await self._ensure_initialized()

        if self._use_neo4j:
            query = f"MATCH (n:{label} {{name: $name}}) RETURN properties(n) AS props"
            async with self._driver.session() as session:
                result = await session.run(query, name=name)
                record = await result.single()
                return dict(record["props"]) if record else None
        else:
            return await self._graph.get_node(label, name)

    async def get_nodes_by_label(self, label: str) -> List[Dict[str, Any]]:
        """Get all nodes with a given label."""
        await self._ensure_initialized()

        if self._use_neo4j:
            query = f"MATCH (n:{label}) RETURN properties(n) AS props"
            async with self._driver.session() as session:
                result = await session.run(query)
                records = await result.data()
                return [dict(r["props"]) for r in records]
        else:
            return await self._graph.get_nodes_by_label(label)

    async def get_relationships(
        self,
        from_label: Optional[str] = None,
        from_name: Optional[str] = None,
        rel_type: Optional[str] = None,
        to_label: Optional[str] = None,
        to_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query relationships with optional filters."""
        await self._ensure_initialized()

        if self._use_neo4j:
            from_match = f"(a:{from_label} {{name: $from_name}})" if from_label and from_name else "(a)"
            to_match = f"(b:{to_label} {{name: $to_name}})" if to_label and to_name else "(b)"
            rel_match = f"[r:{rel_type}]" if rel_type else "[r]"
            query = (
                f"MATCH {from_match}-{rel_match}->{to_match} "
                f"RETURN properties(a) AS from_props, type(r) AS rel_type, "
                f"properties(r) AS rel_props, properties(b) AS to_props"
            )
            params = {}
            if from_name:
                params["from_name"] = from_name
            if to_name:
                params["to_name"] = to_name

            async with self._driver.session() as session:
                result = await session.run(query, **params)
                records = await result.data()
                return [
                    {
                        "from": dict(r["from_props"]),
                        "relationship": r["rel_type"],
                        "to": dict(r["to_props"]),
                        "properties": dict(r["rel_props"]) if r["rel_props"] else {},
                    }
                    for r in records
                ]
        else:
            return await self._graph.get_relationships(
                from_label, from_name, rel_type, to_label, to_name,
            )

    # ──────────────────────────────────────────────
    # Graph Intelligence Queries
    # ──────────────────────────────────────────────

    async def multi_hop_query(
        self, start_label: str, start_name: str, max_hops: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Multi-hop BFS traversal from a starting node.
        Used by Agent 2.5 for cascade risk and hidden relationship detection.
        """
        await self._ensure_initialized()

        if self._use_neo4j:
            query = (
                f"MATCH path = (start:{start_label} {{name: $name}})"
                f"-[*1..{max_hops}]-(end) "
                f"RETURN [n IN nodes(path) | properties(n)] AS nodes, "
                f"[r IN relationships(path) | type(r)] AS rel_types, "
                f"length(path) AS hops"
            )
            async with self._driver.session() as session:
                result = await session.run(query, name=start_name)
                records = await result.data()
                return [
                    {
                        "end_node": dict(r["nodes"][-1]) if r["nodes"] else {},
                        "hops": r["hops"],
                        "path": [
                            {
                                "from": dict(r["nodes"][i]),
                                "relationship": r["rel_types"][i] if i < len(r["rel_types"]) else "",
                                "to": dict(r["nodes"][i + 1]) if i + 1 < len(r["nodes"]) else {},
                                "hop": i + 1,
                            }
                            for i in range(len(r["nodes"]) - 1)
                        ],
                    }
                    for r in records
                ]
        else:
            return await self._graph.multi_hop_query(start_label, start_name, max_hops)

    async def find_shared_directors(self) -> List[Dict[str, Any]]:
        """Find directors linked to multiple companies (cross-directorship)."""
        await self._ensure_initialized()

        if self._use_neo4j:
            query = (
                "MATCH (d:Director)-[:IS_DIRECTOR_OF]->(c:Company) "
                "WITH d, collect(c.name) AS companies "
                "WHERE size(companies) > 1 "
                "RETURN d.name AS director, companies"
            )
            async with self._driver.session() as session:
                result = await session.run(query)
                records = await result.data()
                return [dict(r) for r in records]
        else:
            return await self._graph.find_shared_directors()

    async def detect_circular_trading(self) -> List[List[str]]:
        """Detect circular supply chains (A→B→C→A)."""
        await self._ensure_initialized()

        if self._use_neo4j:
            query = (
                "MATCH path = (a:Company)-[:SUPPLIES_TO*2..5]->(a) "
                "RETURN [n IN nodes(path) | n.name] AS cycle "
                "LIMIT 50"
            )
            async with self._driver.session() as session:
                result = await session.run(query)
                records = await result.data()
                return [r["cycle"] for r in records]
        else:
            return await self._graph.detect_circular_trading()

    async def get_community_clusters(self) -> List[List[str]]:
        """Detect community clusters in the graph."""
        await self._ensure_initialized()

        # Always use in-memory approach (NetworkX Louvain for production)
        # Even with Neo4j, we export to NetworkX for community detection
        if self._use_neo4j:
            # Fetch all nodes and relationships, then run community detection
            all_rels = await self.get_relationships()
            temp_graph = InMemoryGraph()
            for rel in all_rels:
                from_node = rel.get("from", {})
                to_node = rel.get("to", {})
                await temp_graph.create_node(
                    from_node.get("label", "Unknown"), from_node.get("name", ""),
                )
                await temp_graph.create_node(
                    to_node.get("label", "Unknown"), to_node.get("name", ""),
                )
                await temp_graph.create_relationship(
                    from_node.get("label", "Unknown"), from_node.get("name", ""),
                    rel["relationship"],
                    to_node.get("label", "Unknown"), to_node.get("name", ""),
                )
            return await temp_graph.get_community_clusters()
        else:
            return await self._graph.get_community_clusters()

    # ──────────────────────────────────────────────
    # Stats & Lifecycle
    # ──────────────────────────────────────────────

    async def get_stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        await self._ensure_initialized()

        if self._use_neo4j:
            query = (
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt "
                "UNION ALL "
                "MATCH ()-[r]->() RETURN type(r) AS label, count(r) AS cnt"
            )
            async with self._driver.session() as session:
                result = await session.run(query)
                records = await result.data()
                stats = {"nodes_by_label": {}, "relationships_by_type": {}}
                total_nodes = 0
                total_rels = 0
                for r in records:
                    # First half are node labels, second half are rel types
                    stats["nodes_by_label"][r["label"]] = r["cnt"]
                return stats
        else:
            return await self._graph.get_stats()

    async def clear(self):
        """Clear all graph data."""
        await self._ensure_initialized()

        if self._use_neo4j:
            async with self._driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")
        else:
            await self._graph.clear()

    async def close(self):
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            logger.info("[Neo4j] Connection closed")
        elif self._graph:
            await self._graph.close()

    async def _ensure_initialized(self):
        """Auto-initialize if not already done."""
        if not self._initialized:
            await self.initialize()

    @property
    def backend(self) -> str:
        return "neo4j" if self._use_neo4j else "memory"

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# ── Singleton ──
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client(
    uri: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Neo4jClient:
    """Get or create the singleton Neo4jClient."""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient(uri, user, password)
    return _neo4j_client


def reset_neo4j_client():
    """Reset the singleton (for testing)."""
    global _neo4j_client
    _neo4j_client = None
