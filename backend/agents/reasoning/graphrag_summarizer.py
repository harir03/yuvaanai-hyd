"""
Intelli-Credit — GraphRAG Hierarchical Graph Summarizer

Provides hierarchical graph summarization for the 5 reasoning passes.
Builds multi-level community summaries from the Neo4j knowledge graph,
enabling LLM-based reasoning over global graph context instead of
just local neighborhoods.

Uses Microsoft GraphRAG patterns:
1. Extract communities from the entity graph
2. Summarize each community at multiple levels (entity → cluster → global)
3. Provide context windows for each reasoning pass

Falls back to basic graph stats when GraphRAG is unavailable.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from backend.storage.neo4j_client import get_neo4j_client, NodeType, RelationshipType

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Community Summary Models
# ──────────────────────────────────────────────

class EntitySummary:
    """Summary of a single entity with its key properties and connections."""

    __slots__ = ("label", "name", "properties", "connections", "risk_signals")

    def __init__(
        self,
        label: str,
        name: str,
        properties: Dict[str, Any],
        connections: List[str],
        risk_signals: List[str],
    ):
        self.label = label
        self.name = name
        self.properties = properties
        self.connections = connections
        self.risk_signals = risk_signals

    def to_text(self) -> str:
        """Render as concise text for LLM context."""
        lines = [f"[{self.label}] {self.name}"]
        for k, v in self.properties.items():
            if k not in ("label", "name", "node_id"):
                lines.append(f"  {k}: {v}")
        if self.connections:
            lines.append(f"  Connections: {', '.join(self.connections[:10])}")
        if self.risk_signals:
            lines.append(f"  Risk signals: {'; '.join(self.risk_signals)}")
        return "\n".join(lines)


class CommunitySummary:
    """Summary of a community (cluster) of related entities."""

    __slots__ = ("community_id", "entities", "relationship_count",
                 "key_relationships", "risk_level", "narrative")

    def __init__(
        self,
        community_id: int,
        entities: List[EntitySummary],
        relationship_count: int,
        key_relationships: List[str],
        risk_level: str,
        narrative: str,
    ):
        self.community_id = community_id
        self.entities = entities
        self.relationship_count = relationship_count
        self.key_relationships = key_relationships
        self.risk_level = risk_level
        self.narrative = narrative

    def to_text(self) -> str:
        """Render as text for LLM reasoning context."""
        header = (
            f"=== Community {self.community_id} "
            f"({len(self.entities)} entities, "
            f"{self.relationship_count} relationships, "
            f"risk: {self.risk_level}) ===\n"
        )
        entity_text = "\n".join(e.to_text() for e in self.entities[:20])
        rel_text = "\n".join(f"  - {r}" for r in self.key_relationships[:15])
        return f"{header}{self.narrative}\n\nEntities:\n{entity_text}\n\nKey Relationships:\n{rel_text}"


class GraphSummary:
    """Global graph summary at the highest level."""

    __slots__ = ("total_nodes", "total_relationships", "total_communities",
                 "communities", "global_risk_narrative", "entity_types")

    def __init__(
        self,
        total_nodes: int,
        total_relationships: int,
        total_communities: int,
        communities: List[CommunitySummary],
        global_risk_narrative: str,
        entity_types: Dict[str, int],
    ):
        self.total_nodes = total_nodes
        self.total_relationships = total_relationships
        self.total_communities = total_communities
        self.communities = communities
        self.global_risk_narrative = global_risk_narrative
        self.entity_types = entity_types

    def to_context_window(self, max_chars: int = 8000) -> str:
        """Build a context window string for LLM reasoning."""
        lines = [
            f"KNOWLEDGE GRAPH SUMMARY ({self.total_nodes} entities, "
            f"{self.total_relationships} relationships, "
            f"{self.total_communities} communities)",
            "",
            f"Entity Types: {', '.join(f'{k}({v})' for k, v in self.entity_types.items())}",
            "",
            f"Global Assessment: {self.global_risk_narrative}",
            "",
        ]
        text = "\n".join(lines)

        for community in self.communities:
            community_text = community.to_text() + "\n\n"
            if len(text) + len(community_text) > max_chars:
                text += f"... ({len(self.communities) - self.communities.index(community)} more communities truncated)\n"
                break
            text += community_text

        return text

    def get_community_for_entity(self, entity_name: str) -> Optional[CommunitySummary]:
        """Find the community containing a specific entity."""
        name_lower = entity_name.lower().strip()
        for community in self.communities:
            for entity in community.entities:
                if entity.name.lower().strip() == name_lower:
                    return community
        return None


# ──────────────────────────────────────────────
# GraphRAG Summarizer
# ──────────────────────────────────────────────

class GraphRAGSummarizer:
    """
    Builds hierarchical graph summaries from the knowledge graph.

    Architecture:
    1. Level 0 (Entity): Properties + direct connections
    2. Level 1 (Community): Connected component cluster + narrative
    3. Level 2 (Global): Cross-community patterns + risk assessment
    """

    def __init__(self):
        self._client = get_neo4j_client()

    async def build_summary(self, company_name: Optional[str] = None) -> GraphSummary:
        """
        Build a full hierarchical graph summary.

        Args:
            company_name: If provided, prioritizes communities containing this company.
        """
        await self._client._ensure_initialized()

        # Get graph stats
        stats = await self._client.get_stats()
        total_nodes = stats.get("total_nodes", 0)
        total_rels = stats.get("total_relationships", 0)
        entity_types = stats.get("nodes_by_label", {})

        if total_nodes == 0:
            return GraphSummary(
                total_nodes=0,
                total_relationships=0,
                total_communities=0,
                communities=[],
                global_risk_narrative="No entities in knowledge graph — graph reasoning will use document data only.",
                entity_types={},
            )

        # Level 1: Build community summaries
        raw_clusters = await self._client.get_community_clusters()
        communities = await self._build_community_summaries(raw_clusters)

        # Prioritize community containing the target company
        if company_name:
            communities = self._prioritize_target(communities, company_name)

        # Level 2: Build global narrative
        global_narrative = self._build_global_narrative(communities, entity_types)

        return GraphSummary(
            total_nodes=total_nodes,
            total_relationships=total_rels,
            total_communities=len(communities),
            communities=communities,
            global_risk_narrative=global_narrative,
            entity_types=entity_types,
        )

    async def get_context_for_pass(
        self,
        pass_name: str,
        company_name: Optional[str] = None,
        max_chars: int = 6000,
    ) -> str:
        """
        Build a focused context window for a specific reasoning pass.

        Each pass gets context tailored to what it needs:
        - contradictions: entity properties + verification status
        - cascade: supply chain + customer relationships
        - hidden_relationships: director links + community structure
        - temporal: financial metrics over time
        - positive: ratings + institutional backing + diversification
        """
        summary = await self.build_summary(company_name)

        if summary.total_nodes == 0:
            return f"[{pass_name}] No graph data available."

        # Filter context based on pass focus
        focus_types = _PASS_FOCUS.get(pass_name, set())
        if focus_types:
            focused_communities = []
            for community in summary.communities:
                # Keep community if it has relevant entity types
                relevant_entities = [
                    e for e in community.entities
                    if e.label in focus_types
                ]
                if relevant_entities:
                    focused = CommunitySummary(
                        community_id=community.community_id,
                        entities=relevant_entities,
                        relationship_count=community.relationship_count,
                        key_relationships=community.key_relationships,
                        risk_level=community.risk_level,
                        narrative=community.narrative,
                    )
                    focused_communities.append(focused)

            if focused_communities:
                focused_summary = GraphSummary(
                    total_nodes=summary.total_nodes,
                    total_relationships=summary.total_relationships,
                    total_communities=len(focused_communities),
                    communities=focused_communities,
                    global_risk_narrative=summary.global_risk_narrative,
                    entity_types=summary.entity_types,
                )
                return focused_summary.to_context_window(max_chars)

        return summary.to_context_window(max_chars)

    async def _build_community_summaries(
        self, raw_clusters: List[List[str]]
    ) -> List[CommunitySummary]:
        """Build CommunitySummary objects from raw community clusters."""
        communities = []

        for idx, cluster_names in enumerate(raw_clusters):
            if not cluster_names:
                continue

            # Build entity summaries for each member
            entities = []
            for name in cluster_names[:30]:  # Cap per community
                entity = await self._build_entity_summary(name)
                if entity:
                    entities.append(entity)

            # Count relationships within community
            rel_count = 0
            key_rels: List[str] = []
            for entity in entities:
                for conn in entity.connections:
                    rel_count += 1
                    if len(key_rels) < 15:
                        key_rels.append(f"{entity.name} → {conn}")

            # Determine risk level
            risk_level = self._assess_community_risk(entities)

            # Generate narrative
            narrative = self._generate_community_narrative(entities, key_rels, risk_level)

            communities.append(CommunitySummary(
                community_id=idx,
                entities=entities,
                relationship_count=rel_count,
                key_relationships=key_rels,
                risk_level=risk_level,
                narrative=narrative,
            ))

        # Sort by risk level (CRITICAL first)
        risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        communities.sort(key=lambda c: risk_order.get(c.risk_level, 4))

        return communities

    async def _build_entity_summary(self, name: str) -> Optional[EntitySummary]:
        """Build an EntitySummary for a named entity."""
        # Search across all node types
        for node_type in NodeType:
            node = await self._client.get_node(node_type.value, name)
            if node:
                # Get direct connections
                outgoing = await self._client.get_relationships(
                    from_label=node_type.value, from_name=name,
                )
                incoming = await self._client.get_relationships(
                    to_label=node_type.value, to_name=name,
                )

                connections = []
                for rel in outgoing:
                    to_name = rel.get("to", {}).get("name", "?")
                    connections.append(f"{rel['relationship']} → {to_name}")
                for rel in incoming:
                    from_name = rel.get("from", {}).get("name", "?")
                    connections.append(f"{from_name} → {rel['relationship']}")

                # Identify risk signals from properties
                risk_signals = _extract_risk_signals(node)

                return EntitySummary(
                    label=node_type.value,
                    name=name,
                    properties={k: v for k, v in node.items()
                                if k not in ("label", "name", "node_id")},
                    connections=connections,
                    risk_signals=risk_signals,
                )
        return None

    def _assess_community_risk(self, entities: List[EntitySummary]) -> str:
        """Assess the overall risk level of a community."""
        critical_signals = 0
        high_signals = 0
        for entity in entities:
            for signal in entity.risk_signals:
                signal_lower = signal.lower()
                if any(w in signal_lower for w in ("nclt", "defaulter", "fraud", "criminal")):
                    critical_signals += 1
                elif any(w in signal_lower for w in ("npa", "litigation", "downgrade", "pledge")):
                    high_signals += 1

        if critical_signals > 0:
            return "CRITICAL"
        if high_signals >= 2:
            return "HIGH"
        if high_signals > 0:
            return "MEDIUM"
        return "LOW"

    def _generate_community_narrative(
        self,
        entities: List[EntitySummary],
        key_rels: List[str],
        risk_level: str,
    ) -> str:
        """Generate a human-readable narrative for a community."""
        entity_labels = {}
        for e in entities:
            entity_labels.setdefault(e.label, []).append(e.name)

        parts = []
        for label, names in entity_labels.items():
            if len(names) <= 3:
                parts.append(f"{label}: {', '.join(names)}")
            else:
                parts.append(f"{label}: {', '.join(names[:3])} +{len(names)-3} more")

        narrative = f"Community contains {len(entities)} entities: {'; '.join(parts)}."

        risk_items = []
        for e in entities:
            risk_items.extend(e.risk_signals)
        if risk_items:
            narrative += f" Risk signals: {'; '.join(risk_items[:5])}."

        if risk_level in ("CRITICAL", "HIGH"):
            narrative += f" ⚠️ Elevated risk — requires deep analysis in reasoning passes."

        return narrative

    def _prioritize_target(
        self,
        communities: List[CommunitySummary],
        company_name: str,
    ) -> List[CommunitySummary]:
        """Move the community containing the target company to the front."""
        target_lower = company_name.lower().strip()
        target_idx = None

        for i, community in enumerate(communities):
            for entity in community.entities:
                if entity.name.lower().strip() == target_lower:
                    target_idx = i
                    break
            if target_idx is not None:
                break

        if target_idx is not None and target_idx > 0:
            target = communities.pop(target_idx)
            communities.insert(0, target)

        return communities

    def _build_global_narrative(
        self,
        communities: List[CommunitySummary],
        entity_types: Dict[str, int],
    ) -> str:
        """Build a global-level narrative across all communities."""
        if not communities:
            return "Graph is empty — no entities or relationships discovered."

        total_entities = sum(len(c.entities) for c in communities)
        risk_counts = {}
        for c in communities:
            risk_counts[c.risk_level] = risk_counts.get(c.risk_level, 0) + 1

        narrative = (
            f"Knowledge graph contains {total_entities} entities across "
            f"{len(communities)} communities. "
        )

        if risk_counts.get("CRITICAL", 0) > 0:
            narrative += f"⚠️ {risk_counts['CRITICAL']} CRITICAL-risk communities detected. "
        if risk_counts.get("HIGH", 0) > 0:
            narrative += f"{risk_counts['HIGH']} HIGH-risk communities. "

        # Entity type distribution
        type_parts = [f"{v} {k}(s)" for k, v in entity_types.items() if v > 0]
        if type_parts:
            narrative += f"Composition: {', '.join(type_parts[:6])}."

        return narrative


# ──────────────────────────────────────────────
# Pass-specific focus types
# ──────────────────────────────────────────────

_PASS_FOCUS: Dict[str, set] = {
    "contradictions": {
        NodeType.COMPANY.value, NodeType.COURT.value,
        NodeType.CASE.value, NodeType.RATING_AGENCY.value,
    },
    "cascade": {
        NodeType.COMPANY.value, NodeType.SUPPLIER.value,
        NodeType.CUSTOMER.value, NodeType.BANK.value,
    },
    "hidden_relationships": {
        NodeType.COMPANY.value, NodeType.DIRECTOR.value,
        NodeType.SUPPLIER.value, NodeType.CUSTOMER.value,
    },
    "temporal": {
        NodeType.COMPANY.value, NodeType.RATING_AGENCY.value,
    },
    "positive": {
        NodeType.COMPANY.value, NodeType.BANK.value,
        NodeType.RATING_AGENCY.value, NodeType.CUSTOMER.value,
    },
}


# ──────────────────────────────────────────────
# Risk signal extraction
# ──────────────────────────────────────────────

def _extract_risk_signals(node: Dict[str, Any]) -> List[str]:
    """Extract risk signals from node properties."""
    signals = []

    status = str(node.get("status", "")).lower()
    if status in ("npa", "defaulter", "nclt", "suspended", "cancelled"):
        signals.append(f"Status: {status.upper()}")

    if node.get("wilful_defaulter"):
        signals.append("Wilful defaulter (RBI)")

    litigation = node.get("active_cases", node.get("pending_cases", 0))
    if isinstance(litigation, (int, float)) and litigation > 0:
        signals.append(f"Active litigation: {int(litigation)} case(s)")

    rating = str(node.get("rating", "")).upper()
    if rating and any(x in rating for x in ("D", "C", "BB")):
        signals.append(f"Low credit rating: {rating}")

    pledge_pct = node.get("pledge_pct", node.get("promoter_pledge_pct"))
    if isinstance(pledge_pct, (int, float)) and pledge_pct > 40:
        signals.append(f"High pledge: {pledge_pct}%")

    return signals
