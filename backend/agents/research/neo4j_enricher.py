"""
Intelli-Credit — Neo4j Enricher (Agent 2 sub-module)

Adds EXTERNAL entities to the knowledge graph from research sources:
- MCA21: Director history, company registrations, charges
- NJDG: Court cases, litigation history
- SEBI: Regulatory actions, insider trading
- RBI: Wilful defaulter list, NBFC registration

Called by Agent 2 (Research Agent) during Stage 5.
Internal graph (from documents) is built by graph_builder.py in Agent 1.5.

T0/T1: Stub implementation with mock data.
T2+: Will integrate with actual scraper outputs from
backend/agents/research/scrapers/.
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


async def enrich_graph_from_research(
    session_id: str,
    company_name: str,
    research_findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Enrich the knowledge graph with external research findings.

    Reads structured research results from Agent 2's scrapers and
    adds external entities/relationships to Neo4j.

    Args:
        session_id: Current assessment session ID
        company_name: Target company name
        research_findings: List of findings from scrapers

    Returns:
        Dict with {nodes_added, relationships_added}
    """
    client = get_neo4j_client()
    await client._ensure_initialized()

    nodes_added = 0
    rels_added = 0

    for finding in research_findings:
        source = finding.get("source", "")
        data = finding.get("data", {})

        if source == "mca21":
            n, r = await _enrich_from_mca21(client, company_name, data)
            nodes_added += n
            rels_added += r
        elif source == "njdg":
            n, r = await _enrich_from_njdg(client, company_name, data)
            nodes_added += n
            rels_added += r
        elif source == "sebi":
            n, r = await _enrich_from_sebi(client, company_name, data)
            nodes_added += n
            rels_added += r
        elif source == "rbi":
            n, r = await _enrich_from_rbi(client, company_name, data)
            nodes_added += n
            rels_added += r

    logger.info(
        f"[Neo4jEnricher] Added {nodes_added} nodes, {rels_added} relationships "
        f"from research for session {session_id}"
    )

    return {
        "nodes_added": nodes_added,
        "relationships_added": rels_added,
    }


async def _enrich_from_mca21(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Enrich from MCA21 scraper output:
    - External directorships (directors on other company boards)
    - Company charges (loans, encumbrances)
    - Group companies (common directors)
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    # External directorships — directors serving on other companies
    for directorship in data.get("external_directorships", []):
        director_name = directorship.get("director", "")
        other_company = directorship.get("company", "")
        if not director_name or not other_company:
            continue

        await client.create_node(
            NodeType.DIRECTOR, director_name,
            {"source": "mca21", "din": directorship.get("din", "")},
        )
        nodes += 1

        await client.create_node(
            NodeType.COMPANY, other_company,
            {"source": "mca21", "cin": directorship.get("cin", "")},
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.DIRECTOR, director_name,
            RelationshipType.IS_DIRECTOR_OF,
            NodeType.COMPANY, other_company,
            {
                "appointment_date": directorship.get("appointment_date", ""),
                "source": "mca21",
            },
        )
        if created:
            rels += 1

    # Company charges
    for charge in data.get("charges", []):
        bank_name = charge.get("charge_holder", "")
        if not bank_name:
            continue

        await client.create_node(
            NodeType.BANK, bank_name,
            {"source": "mca21"},
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.BANK, bank_name,
            RelationshipType.HAS_CHARGE,
            NodeType.COMPANY, company,
            {
                "amount_lakhs": charge.get("amount", 0),
                "creation_date": charge.get("date", ""),
                "status": charge.get("status", ""),
                "source": "mca21",
            },
        )
        if created:
            rels += 1

    return nodes, rels


async def _enrich_from_njdg(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Enrich from NJDG scraper output:
    - Court cases filed against the company
    - Cases filed by the company
    """
    if not data:
        return 0, 0

    nodes = 0
    rels = 0

    for case in data.get("cases", []):
        court_name = case.get("court", "Unknown Court")
        case_type = case.get("type", "civil")
        amount = case.get("amount", 0)

        await client.create_node(
            NodeType.COURT, court_name,
            {"source": "njdg"},
        )
        nodes += 1

        case_name = f"njdg_{case_type}_{court_name}_{amount}"
        await client.create_node(
            NodeType.CASE, case_name,
            {
                "case_type": case_type,
                "amount_lakhs": amount,
                "status": case.get("status", ""),
                "filing_date": case.get("filing_date", ""),
                "source": "njdg",
            },
        )
        nodes += 1

        created = await client.create_relationship(
            NodeType.CASE, case_name,
            RelationshipType.FILED_CASE_AGAINST,
            NodeType.COMPANY, company,
            {"amount_lakhs": amount, "source": "njdg"},
        )
        if created:
            rels += 1

    return nodes, rels


async def _enrich_from_sebi(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Enrich from SEBI scraper output:
    - Regulatory actions against company or directors
    """
    if not data:
        return 0, 0

    # SEBI data enriches existing nodes with regulatory flags
    # Full implementation in T2 when scrapers are built
    return 0, 0


async def _enrich_from_rbi(
    client: Neo4jClient, company: str, data: Dict[str, Any],
) -> tuple[int, int]:
    """
    Enrich from RBI scraper output:
    - Wilful defaulter status
    - NBFC registration status
    """
    if not data:
        return 0, 0

    # RBI data enriches existing Company node with regulatory flags
    # Full implementation in T2 when scrapers are built
    return 0, 0


async def enrich_with_mock_mca21(
    session_id: str,
    company_name: str,
) -> Dict[str, Any]:
    """
    Mock MCA21 enrichment for demo/testing.

    Simulates discovering that a director of XYZ Steel also sits on
    the board of another company (Agarwal Holdings — NPA account).
    This creates cross-directorship patterns for graph reasoning.
    """
    mock_mca21_data = {
        "external_directorships": [
            {
                "director": "Rajesh Kumar",
                "din": "00123456",
                "company": "Agarwal Holdings Pvt Ltd",
                "cin": "U51909MH2010PTC987654",
                "appointment_date": "2015-03-20",
            },
            {
                "director": "Rajesh Kumar",
                "din": "00123456",
                "company": "AK Traders LLP",
                "cin": "AAB-1234",
                "appointment_date": "2018-07-10",
            },
        ],
        "charges": [
            {
                "charge_holder": "State Bank of India",
                "amount": 5000,
                "date": "2021-06-15",
                "status": "active",
            },
        ],
    }

    return await enrich_graph_from_research(
        session_id, company_name,
        [{"source": "mca21", "data": mock_mca21_data}],
    )


async def enrich_with_mock_njdg(
    session_id: str,
    company_name: str,
) -> Dict[str, Any]:
    """
    Mock NJDG enrichment for demo/testing.

    Simulates discovering undisclosed litigation — cases found in NJDG
    but NOT in the Annual Report's litigation disclosure section.
    """
    mock_njdg_data = {
        "cases": [
            {
                "court": "NCLT Mumbai Bench",
                "type": "insolvency",
                "amount": 450,
                "status": "pending",
                "filing_date": "2023-01-15",
            },
            {
                "court": "High Court Bombay",
                "type": "commercial",
                "amount": 280,
                "status": "active",
                "filing_date": "2022-08-03",
            },
        ],
    }

    return await enrich_graph_from_research(
        session_id, company_name,
        [{"source": "njdg", "data": mock_njdg_data}],
    )
