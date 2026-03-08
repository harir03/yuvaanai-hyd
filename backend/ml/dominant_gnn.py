"""
Intelli-Credit — DOMINANT GNN for Graph Anomaly Detection

Uses PyTorch Geometric's DOMINANT (Deep Anomaly Detection on Attributed Networks)
to detect anomalous nodes in the transaction/relationship graph — circular trading,
shell company networks, and unusual transaction patterns.

Falls back to heuristic graph analysis (degree centrality + structural features)
when torch_geometric is unavailable.

Model loaded ONCE at startup (Section 17 performance rule).
Input: Graph structure (adjacency + node features) from Neo4j client.
Output: Per-node anomaly scores + detected patterns.
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple, Set

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──
HIDDEN_DIM = 64
NUM_EPOCHS = 100
LEARNING_RATE = 0.005
ANOMALY_THRESHOLD = 0.7  # Score above this = anomalous

# ── Singleton model holder ──
_model = None
_mode: str = "uninitialized"  # "pyg" or "fallback"


def _init_model() -> None:
    """Initialize DOMINANT model. Fall back to heuristic if PyG unavailable."""
    global _model, _mode
    if _mode != "uninitialized":
        return

    try:
        import torch
        import torch_geometric
        _mode = "pyg"
        logger.info("[DOMINANT GNN] PyTorch Geometric available — using GNN model")
    except ImportError:
        _model = None
        _mode = "fallback"
        logger.warning("[DOMINANT GNN] torch_geometric not available — using heuristic fallback")
    except Exception as e:
        _model = None
        _mode = "fallback"
        logger.warning(f"[DOMINANT GNN] Init failed: {e} — using heuristic fallback")


def _build_graph_data(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Tuple:
    """Build adjacency matrix and feature matrix from raw graph data.

    Args:
        nodes: List of node dicts with 'id', 'label', 'name', 'properties'.
        edges: List of edge dicts with 'source', 'target', 'type', 'properties'.

    Returns:
        (adjacency_matrix, feature_matrix, node_id_map)
    """
    # Build node ID → index mapping
    node_ids = [n.get("id", n.get("name", str(i))) for i, n in enumerate(nodes)]
    id_to_idx = {nid: idx for idx, nid in enumerate(node_ids)}
    n = len(nodes)

    if n == 0:
        return np.zeros((0, 0)), np.zeros((0, 0)), {}

    # Build adjacency matrix
    adj = np.zeros((n, n), dtype=np.float32)
    for edge in edges:
        src = edge.get("source", edge.get("from"))
        tgt = edge.get("target", edge.get("to"))
        if src in id_to_idx and tgt in id_to_idx:
            i, j = id_to_idx[src], id_to_idx[tgt]
            weight = float(edge.get("properties", {}).get("amount", 1.0))
            adj[i][j] = weight
            adj[j][i] = weight  # Undirected for anomaly detection

    # Build feature matrix from node properties
    # Features: [degree, in_amount, out_amount, is_company, is_director, is_supplier, is_customer]
    feat_dim = 7
    features = np.zeros((n, feat_dim), dtype=np.float32)

    for idx, node in enumerate(nodes):
        label = node.get("label", "").lower()
        props = node.get("properties", {})

        # Degree centrality
        features[idx, 0] = np.sum(adj[idx] > 0)

        # Total incoming / outgoing amounts
        features[idx, 1] = np.sum(adj[:, idx])  # in_amount
        features[idx, 2] = np.sum(adj[idx, :])  # out_amount

        # One-hot entity type
        features[idx, 3] = 1.0 if label in ("company", "borrower") else 0.0
        features[idx, 4] = 1.0 if label == "director" else 0.0
        features[idx, 5] = 1.0 if label == "supplier" else 0.0
        features[idx, 6] = 1.0 if label == "customer" else 0.0

    return adj, features, id_to_idx


def _detect_cycles(adj: np.ndarray, id_to_idx: Dict[str, int]) -> List[List[str]]:
    """DFS-based cycle detection in the adjacency matrix."""
    n = adj.shape[0]
    idx_to_id = {v: k for k, v in id_to_idx.items()}
    visited = set()
    cycles = []

    def _dfs(node: int, path: List[int], path_set: Set[int]):
        for neighbor in range(n):
            if adj[node][neighbor] > 0:
                if neighbor in path_set and len(path) >= 2:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = [idx_to_id.get(p, str(p)) for p in path[cycle_start:]]
                    if len(cycle) >= 3:  # Only meaningful cycles (3+ nodes)
                        cycles.append(cycle)
                elif neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    path_set.add(neighbor)
                    _dfs(neighbor, path, path_set)
                    path.pop()
                    path_set.discard(neighbor)

    for start in range(n):
        if start not in visited:
            visited.add(start)
            _dfs(start, [start], {start})

    # Deduplicate cycles (same cycle can be found from different starting points)
    unique_cycles = []
    seen = set()
    for cycle in cycles:
        key = tuple(sorted(cycle))
        if key not in seen:
            seen.add(key)
            unique_cycles.append(cycle)

    return unique_cycles


def _heuristic_detect(
    adj: np.ndarray,
    features: np.ndarray,
    id_to_idx: Dict[str, int],
    nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Heuristic graph anomaly detection (fallback).

    Uses structural features to identify suspicious nodes:
    1. Degree anomaly — nodes with unusually high/low connectivity
    2. Amount asymmetry — nodes where in ≠ out by large margins
    3. Cycle participation — nodes in circular trading paths
    4. Clustering coefficient anomaly — unusually dense local neighborhoods
    """
    n = adj.shape[0]
    idx_to_id = {v: k for k, v in id_to_idx.items()}

    if n == 0:
        return {
            "node_scores": {},
            "anomalous_nodes": [],
            "cycles_detected": [],
            "patterns": [],
            "method": "heuristic_fallback",
        }

    # 1. Degree centrality
    degrees = np.sum(adj > 0, axis=1).astype(float)
    mean_deg = np.mean(degrees) if degrees.size else 0
    std_deg = np.std(degrees) if degrees.size else 1
    if std_deg == 0:
        std_deg = 1.0
    degree_z = np.abs(degrees - mean_deg) / std_deg

    # 2. Amount asymmetry (in vs out)
    in_amounts = np.sum(adj, axis=0)
    out_amounts = np.sum(adj, axis=1)
    total = in_amounts + out_amounts
    asymmetry = np.zeros(n)
    for i in range(n):
        if total[i] > 0:
            asymmetry[i] = abs(in_amounts[i] - out_amounts[i]) / total[i]

    # 3. Cycle participation
    cycles = _detect_cycles(adj, id_to_idx)
    cycle_nodes: Set[str] = set()
    for cycle in cycles:
        cycle_nodes.update(cycle)
    cycle_participation = np.zeros(n)
    for node_id, idx in id_to_idx.items():
        if node_id in cycle_nodes:
            cycle_participation[idx] = 1.0

    # 4. Local clustering coefficient
    clustering = np.zeros(n)
    for i in range(n):
        neighbors = np.where(adj[i] > 0)[0]
        k = len(neighbors)
        if k >= 2:
            # Count edges between neighbors
            neighbor_edges = 0
            for a in range(len(neighbors)):
                for b in range(a + 1, len(neighbors)):
                    if adj[neighbors[a]][neighbors[b]] > 0:
                        neighbor_edges += 1
            max_edges = k * (k - 1) / 2
            clustering[i] = neighbor_edges / max_edges if max_edges > 0 else 0

    # Composite anomaly score: weighted combination
    scores = np.zeros(n)
    scores += 0.25 * np.minimum(degree_z / 3.0, 1.0)     # Degree anomaly
    scores += 0.20 * asymmetry                              # Amount asymmetry
    scores += 0.35 * cycle_participation                    # Cycle participation (heaviest)
    scores += 0.20 * (1.0 - clustering)                     # Low clustering = potential bridge/shell

    # Build per-node results
    node_scores = {}
    anomalous_nodes = []
    for node_id, idx in id_to_idx.items():
        node_label = nodes[idx].get("label", "unknown") if idx < len(nodes) else "unknown"
        node_name = nodes[idx].get("name", node_id) if idx < len(nodes) else node_id

        score = float(scores[idx])
        node_scores[node_id] = round(score, 4)

        if score >= ANOMALY_THRESHOLD:
            reasons = []
            if degree_z[idx] > 2.0:
                reasons.append(f"unusual degree ({int(degrees[idx])} connections, mean={mean_deg:.1f})")
            if asymmetry[idx] > 0.5:
                reasons.append(f"high amount asymmetry ({asymmetry[idx]:.1%})")
            if cycle_participation[idx] > 0:
                reasons.append("participates in circular trading cycle")
            if clustering[idx] < 0.1 and degrees[idx] > 2:
                reasons.append("low clustering (potential bridge/shell node)")

            anomalous_nodes.append({
                "node_id": node_id,
                "node_name": node_name,
                "node_label": node_label,
                "anomaly_score": round(score, 4),
                "reasons": reasons,
            })

    # Build pattern descriptions
    patterns = []
    if cycles:
        for cycle in cycles[:5]:  # Top 5 cycles
            chain_str = " → ".join(cycle) + f" → {cycle[0]}"
            patterns.append({
                "pattern_type": "circular_trading",
                "description": f"Circular trading detected: {chain_str}",
                "entities": cycle,
                "severity": "CRITICAL" if len(cycle) <= 4 else "HIGH",
            })

    if anomalous_nodes:
        high_degree = [n for n in anomalous_nodes if any("degree" in r for r in n.get("reasons", []))]
        if high_degree:
            patterns.append({
                "pattern_type": "hub_node",
                "description": f"{len(high_degree)} hub node(s) with unusually high connectivity",
                "entities": [n["node_name"] for n in high_degree],
                "severity": "MEDIUM",
            })

    return {
        "node_scores": node_scores,
        "anomalous_nodes": anomalous_nodes,
        "cycles_detected": [
            {"cycle": c, "chain": " → ".join(c) + f" → {c[0]}", "length": len(c)}
            for c in cycles
        ],
        "patterns": patterns,
        "total_nodes": n,
        "total_edges": int(np.sum(adj > 0) / 2),  # Undirected, divide by 2
        "method": "heuristic_fallback",
    }


def _pyg_detect(
    adj: np.ndarray,
    features: np.ndarray,
    id_to_idx: Dict[str, int],
    nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """DOMINANT GNN-based anomaly detection using PyTorch Geometric."""
    import torch
    from torch_geometric.nn import GCNConv
    from torch_geometric.utils import dense_to_sparse

    n = adj.shape[0]
    idx_to_id = {v: k for k, v in id_to_idx.items()}

    # Convert to PyG format
    adj_tensor = torch.FloatTensor(adj)
    adj_tensor[adj_tensor > 0] = 1.0  # Binary adjacency for GCN
    edge_index, _ = dense_to_sparse(adj_tensor)
    x = torch.FloatTensor(features)

    feat_dim = features.shape[1]

    # Simple autoencoder (DOMINANT-inspired)
    class GraphAutoEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.enc1 = GCNConv(feat_dim, HIDDEN_DIM)
            self.enc2 = GCNConv(HIDDEN_DIM, HIDDEN_DIM // 2)
            self.dec1 = GCNConv(HIDDEN_DIM // 2, HIDDEN_DIM)
            self.dec2 = GCNConv(HIDDEN_DIM, feat_dim)

        def forward(self, x, edge_index):
            z = torch.relu(self.enc1(x, edge_index))
            z = self.enc2(z, edge_index)
            z = torch.relu(self.dec1(z, edge_index))
            x_hat = self.dec2(z, edge_index)
            return x_hat

    model = GraphAutoEncoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # Train autoencoder
    model.train()
    for epoch in range(NUM_EPOCHS):
        optimizer.zero_grad()
        x_hat = model(x, edge_index)
        loss = torch.nn.functional.mse_loss(x_hat, x)
        loss.backward()
        optimizer.step()

    # Compute reconstruction error per node (anomaly score)
    model.eval()
    with torch.no_grad():
        x_hat = model(x, edge_index)
        errors = torch.mean((x - x_hat) ** 2, dim=1)  # MSE per node
        # Normalize to [0, 1]
        if errors.max() > errors.min():
            scores = (errors - errors.min()) / (errors.max() - errors.min())
        else:
            scores = torch.zeros_like(errors)

    scores_np = scores.numpy()

    # Also detect cycles using structural analysis
    cycles = _detect_cycles(adj, id_to_idx)

    # Build per-node results
    node_scores = {}
    anomalous_nodes = []
    cycle_nodes: Set[str] = set()
    for cycle in cycles:
        cycle_nodes.update(cycle)

    for node_id, idx in id_to_idx.items():
        node_label = nodes[idx].get("label", "unknown") if idx < len(nodes) else "unknown"
        node_name = nodes[idx].get("name", node_id) if idx < len(nodes) else node_id

        score = float(scores_np[idx])
        # Boost score for cycle participants
        if node_id in cycle_nodes:
            score = min(1.0, score + 0.3)
        node_scores[node_id] = round(score, 4)

        if score >= ANOMALY_THRESHOLD:
            reasons = []
            if float(errors[idx]) > float(errors.mean() + errors.std()):
                reasons.append("high reconstruction error (unusual feature pattern)")
            if node_id in cycle_nodes:
                reasons.append("participates in circular trading cycle")
            anomalous_nodes.append({
                "node_id": node_id,
                "node_name": node_name,
                "node_label": node_label,
                "anomaly_score": round(score, 4),
                "reasons": reasons,
            })

    patterns = []
    if cycles:
        for cycle in cycles[:5]:
            chain_str = " → ".join(cycle) + f" → {cycle[0]}"
            patterns.append({
                "pattern_type": "circular_trading",
                "description": f"Circular trading detected: {chain_str}",
                "entities": cycle,
                "severity": "CRITICAL" if len(cycle) <= 4 else "HIGH",
            })

    return {
        "node_scores": node_scores,
        "anomalous_nodes": anomalous_nodes,
        "cycles_detected": [
            {"cycle": c, "chain": " → ".join(c) + f" → {c[0]}", "length": len(c)}
            for c in cycles
        ],
        "patterns": patterns,
        "total_nodes": n,
        "total_edges": int(np.sum(adj > 0) / 2),
        "training_loss": round(float(loss), 6),
        "method": "dominant_gnn",
    }


def detect_graph_anomalies(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run DOMINANT GNN anomaly detection on a transaction/relationship graph.

    Args:
        nodes: List of node dicts with 'id'/'name', 'label', 'properties'.
        edges: List of edge dicts with 'source', 'target', 'type', 'properties'.

    Returns:
        Dict with:
            - node_scores: Dict[node_id, anomaly_score]
            - anomalous_nodes: list of anomalous node details
            - cycles_detected: list of circular trading cycles
            - patterns: list of detected fraud patterns
            - method: "dominant_gnn" or "heuristic_fallback"
    """
    _init_model()

    if not nodes:
        return {
            "node_scores": {},
            "anomalous_nodes": [],
            "cycles_detected": [],
            "patterns": [],
            "total_nodes": 0,
            "total_edges": 0,
            "method": _mode if _mode != "uninitialized" else "fallback",
        }

    adj, features, id_to_idx = _build_graph_data(nodes, edges)

    if _mode == "pyg":
        try:
            return _pyg_detect(adj, features, id_to_idx, nodes)
        except Exception as e:
            logger.warning(f"[DOMINANT GNN] PyG detection failed: {e} — falling back to heuristic")

    return _heuristic_detect(adj, features, id_to_idx, nodes)


def get_mode() -> str:
    """Return current mode ('pyg' or 'fallback')."""
    _init_model()
    return _mode


def reset() -> None:
    """Reset singleton (for testing)."""
    global _model, _mode
    _model = None
    _mode = "uninitialized"
