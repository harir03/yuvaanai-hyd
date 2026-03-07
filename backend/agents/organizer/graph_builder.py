"""
Intelli-Credit — Graph Builder (Agent 1.5 sub-module)

Builds the INTERNAL knowledge graph from worker-extracted document data.
Reads worker outputs (W1-W9) and creates Neo4j nodes + relationships
representing companies, directors, suppliers, customers, banks, auditors,
courts, and their connections.

Called by Agent 1.5 (Organizer) during Stage 4.
External enrichment (MCA21/NJDG) is done separately by neo4j_enricher.py in Agent 2.
"""

import logging
from typing import Dict, Any, List, Optional

from backend.storage.neo4j_client import (
    get_neo4j_client,
    Neo4jClient,
    NodeType,
    RelationshipType,
)

logger = logging.getLogger(__name__)


async def build_knowledge_graph(
    session_id: str,
    worker_outputs: Dict[str, Dict[str, Any]],
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the internal knowledge graph from all worker outputs.

    Extracts entities and relationships from each worker's data,
    creates them in Neo4j (or InMemoryGraph fallback).

    Args:
        session_id: Current assessment session ID
        worker_outputs: Dict of {worker_id: extracted_data}
        company_name: The target company being assessed

    Returns:
        Dict with counts: {"nodes_created", "relationships_created", "entities"}
    """
    client = get_neo4j_client()
    await client._ensure_initialized()

    nodes_created = 0
    relationships_created = 0
    entities: List[Dict[str, Any]] = []

    # Determine company name from W1 data or parameter
    target_company = company_name
    w1_data = worker_outputs.get("W1", {})
    if not target_company and w1_data:
        target_company = w1_data.get("company_name", "Unknown Company")

    if not target_company:
        target_company = "Unknown Company"

    # Create the target company node
    await client.create_node(
        NodeType.COMPANY, target_company,
        {"session_id": session_id, "role": "target", "cin": w1_data.get("cin", "")},
    )
    nodes_created += 1
    entities.append({"type": "Company", "name": target_company, "role": "target"})

    # Extract from each worker
    w1_nodes, w1_rels = await _extract_from_w1(client, target_company, w1_data)
    nodes_created += w1_nodes
    relationships_created += w1_rels

    w2_data = worker_outputs.get("W2", {})
    w2_nodes, w2_rels = await _extract_from_w2(client, target_company, w2_data)
    nodes_created += w2_nodes
    relationships_created += w2_rels

    w3_data = worker_outputs.get("W3", {})
    w3_nodes, w3_rels = await _extract_from_w3(client, target_company, w3_data)
    nodes_created += w3_nodes
    relationships_created += w3_rels

    # W4 (ITR), W5 (Legal), W6 (Board Minutes), W7 (Shareholding),
    # W8 (Rating), W9 (Site Visit) — extract when workers are available
    w5_data = worker_outputs.get("W5", {})
    w5_nodes, w5_rels = await _extract_from_w5(client, target_company, w5_data)
    nodes_created += w5_nodes
    relationships_created += w5_rels

    w6_data = worker_outputs.get("W6", {})
    w6_nodes, w6_rels = await _extract_from_w6(client, target_company, w6_data)
    nodes_created += w6_nodes
    relationships_created += w6_rels

    w8_data = worker_outputs.get("W8", {})
    w8_nodes, w8_rels = await _extract_from_w8(client, target_company, w8_data)
    nodes_created += w8_nodes
    relationships_created += w8_rels

    # Collect all entities for tracking
    stats = await client.get_stats()
    for label, count in stats.get("nodes_by_label", {}).items():
        entities.append({"type": label, "count": count})

    logger.info(
        f"[GraphBuilder] Built graph: {nodes_created} nodes, "
        f"{relationships_created} relationships for session {session_id}"
    )

    return {
        "nodes_created": nodes_created,
        "relationships_created": relationships_created,
        "entities": entities,
        "stats": stats,
    }


# ──────────────────────────────────────────────
# Worker-specific extractors
# ──────────────────────────────────────────────

async def _extract_from_w1(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W1 (Annual Report):
    - Directors → IS_DIRECTOR_OF → Company
    - Auditor → IS_AUDITOR_OF → Company
    - RPT parties → SUPPLIES_TO / BUYS_FROM → Company
    - Litigation → Court/Case → FILED_CASE_AGAINST → Company
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    # Directors
    for director in data.get("directors", []):
        name = director.get("name", "")
        if not name:
            continue
        await client.create_node(
            NodeType.DIRECTOR, name,
            {
                "din": director.get("din", ""),
                "designation": director.get("designation", ""),
                "source": "W1_annual_report",
            },
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.DIRECTOR, name,
            RelationshipType.IS_DIRECTOR_OF,
            NodeType.COMPANY, company,
            {"designation": director.get("designation", ""), "source": "W1"},
        )
        if created:
            rels += 1

    # Auditor
    auditor = data.get("auditor", {})
    if auditor and auditor.get("name"):
        auditor_name = auditor["name"]
        await client.create_node(
            NodeType.AUDITOR, auditor_name,
            {
                "type": auditor.get("type", ""),
                "opinion": auditor.get("opinion", ""),
                "source": "W1_annual_report",
            },
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.AUDITOR, auditor_name,
            RelationshipType.IS_AUDITOR_OF,
            NodeType.COMPANY, company,
            {"opinion": auditor.get("opinion", ""), "source": "W1"},
        )
        if created:
            rels += 1

    # RPT parties — determine relationship type from transaction nature
    rpts = data.get("rpts", {})
    for txn in rpts.get("transactions", []):
        party_name = txn.get("party", "")
        if not party_name:
            continue

        nature = txn.get("nature", "").lower()
        amount = txn.get("amount", 0)

        # Determine entity type and relationship from nature
        if "purchase" in nature:
            # Company buys FROM this party → party is Supplier
            await client.create_node(
                NodeType.SUPPLIER, party_name,
                {"rpt_amount": amount, "source": "W1_rpt"},
            )
            nodes += 1
            created = await client.create_relationship(
                NodeType.SUPPLIER, party_name,
                RelationshipType.SUPPLIES_TO,
                NodeType.COMPANY, company,
                {"amount_lakhs": amount, "nature": nature, "source": "W1_rpt"},
            )
            if created:
                rels += 1
        elif "service" in nature or "donation" in nature:
            # Company buys services FROM this party → party is Supplier
            await client.create_node(
                NodeType.SUPPLIER, party_name,
                {"rpt_amount": amount, "source": "W1_rpt"},
            )
            nodes += 1
            created = await client.create_relationship(
                NodeType.COMPANY, company,
                RelationshipType.BUYS_FROM,
                NodeType.SUPPLIER, party_name,
                {"amount_lakhs": amount, "nature": nature, "source": "W1_rpt"},
            )
            if created:
                rels += 1
        else:
            # Generic supplier relationship
            await client.create_node(
                NodeType.SUPPLIER, party_name,
                {"rpt_amount": amount, "source": "W1_rpt"},
            )
            nodes += 1
            created = await client.create_relationship(
                NodeType.SUPPLIER, party_name,
                RelationshipType.SUPPLIES_TO,
                NodeType.COMPANY, company,
                {"amount_lakhs": amount, "nature": nature, "source": "W1_rpt"},
            )
            if created:
                rels += 1

    # Litigation — Courts and Cases
    litigation = data.get("litigation_disclosure", {})
    for case in litigation.get("cases", []):
        case_type = case.get("type", "unknown")
        forum = case.get("forum", "Unknown Court")
        amount = case.get("amount", 0)

        # Create Court node
        await client.create_node(
            NodeType.COURT, forum,
            {"type": "judicial_forum", "source": "W1_litigation"},
        )
        nodes += 1

        # Create Case node
        case_name = f"{case_type}_{forum}_{amount}"
        await client.create_node(
            NodeType.CASE, case_name,
            {
                "case_type": case_type,
                "amount_lakhs": amount,
                "status": case.get("status", ""),
                "forum": forum,
                "source": "W1_litigation",
            },
        )
        nodes += 1

        # Case → FILED_CASE_AGAINST → Company
        created = await client.create_relationship(
            NodeType.CASE, case_name,
            RelationshipType.FILED_CASE_AGAINST,
            NodeType.COMPANY, company,
            {"amount_lakhs": amount, "status": case.get("status", ""), "source": "W1"},
        )
        if created:
            rels += 1

    return nodes, rels


async def _extract_from_w2(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W2 (Bank Statement):
    - Bank → HAS_CHARGE → Company (banking relationship)
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    bank_name = data.get("bank_name", "")
    if not bank_name:
        return 0, 0

    await client.create_node(
        NodeType.BANK, bank_name,
        {
            "account_type": data.get("account_type", ""),
            "source": "W2_bank_statement",
        },
    )
    nodes += 1

    # Bank HAS_CHARGE on company (lending relationship)
    created = await client.create_relationship(
        NodeType.BANK, bank_name,
        RelationshipType.HAS_CHARGE,
        NodeType.COMPANY, company,
        {
            "account_type": data.get("account_type", ""),
            "emi_amount_lakhs": data.get("emi_regularity", {}).get("monthly_emi_amount", 0),
            "source": "W2",
        },
    )
    if created:
        rels += 1

    return nodes, rels


async def _extract_from_w3(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W3 (GST Returns):
    - GSTIN-linked suppliers (from GSTR-2A if available)

    Note: W3 primarily provides financial aggregates. Supplier-level
    details come from GSTR-2A reconciliation if available.
    """
    if not data:
        return 0, 0

    # W3 currently doesn't have individual supplier GSTIN data
    # (would come from detailed GSTR-2A in full implementation)
    # For now, just ensure company GSTIN is stored
    gstin = data.get("gstin", "")
    if gstin:
        client_instance = get_neo4j_client()
        node = await client_instance.get_node(NodeType.COMPANY, company)
        if node:
            await client_instance.create_node(
                NodeType.COMPANY, company, {"gstin": gstin},
            )

    return 0, 0


async def _extract_from_w5(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W5 (Legal Notice):
    - Claimants, courts, case details
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    for case in data.get("cases", []):
        claimant = case.get("claimant", "")
        forum = case.get("forum", case.get("court", "Unknown Court"))
        amount = case.get("amount", 0)

        if forum:
            await client.create_node(
                NodeType.COURT, forum,
                {"source": "W5_legal_notice"},
            )
            nodes += 1

        case_name = f"{case.get('type', 'legal')}_{forum}_{amount}"
        await client.create_node(
            NodeType.CASE, case_name,
            {
                "claimant": claimant,
                "amount_lakhs": amount,
                "status": case.get("status", ""),
                "source": "W5_legal_notice",
            },
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.CASE, case_name,
            RelationshipType.FILED_CASE_AGAINST,
            NodeType.COMPANY, company,
            {"amount_lakhs": amount, "source": "W5"},
        )
        if created:
            rels += 1

    return nodes, rels


async def _extract_from_w6(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W6 (Board Minutes):
    - Additional RPT parties (cross-reference with W1)
    - Director attendance records (update existing Director nodes)
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    # Board Minutes RPT approvals
    for rpt in data.get("rpt_approvals", []):
        party_name = rpt.get("party", "")
        if not party_name:
            continue

        amount = rpt.get("amount", 0)
        await client.create_node(
            NodeType.SUPPLIER, party_name,
            {"rpt_board_approved": True, "source": "W6_board_minutes"},
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.SUPPLIER, party_name,
            RelationshipType.SUPPLIES_TO,
            NodeType.COMPANY, company,
            {"board_approved": True, "amount_lakhs": amount, "source": "W6"},
        )
        if created:
            rels += 1

    return nodes, rels


async def _extract_from_w8(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Extract entities from W8 (Rating Report):
    - RatingAgency → HAS_RATING_FROM → Company
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    agency_name = data.get("agency", data.get("rating_agency", ""))
    if not agency_name:
        return 0, 0

    current_rating = data.get("current_rating", data.get("rating", ""))

    await client.create_node(
        NodeType.RATING_AGENCY, agency_name,
        {"source": "W8_rating_report"},
    )
    nodes += 1

    created = await client.create_relationship(
        NodeType.COMPANY, company,
        RelationshipType.HAS_RATING_FROM,
        NodeType.RATING_AGENCY, agency_name,
        {
            "rating": current_rating,
            "outlook": data.get("outlook", ""),
            "source": "W8",
        },
    )
    if created:
        rels += 1

    return nodes, rels
