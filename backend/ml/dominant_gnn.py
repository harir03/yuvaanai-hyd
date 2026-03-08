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
# Adaptive threshold: if computed, use mean + k*std of reconstruction errors
ADAPTIVE_THRESHOLD_K = 2.0

# Enhanced feature dimensions: structural (5) + financial (6) + entity-type one-hot (5) = 16
FEAT_DIM = 16

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
    """Build adjacency matrix and 16-dim feature matrix from raw graph data.

    Feature layout (16 dims):
      Structural [0-4]: degree, in_amount, out_amount, reciprocity_ratio, concentration_index
      Financial  [5-10]: revenue, debt_equity, dscr, promoter_pledge_pct, net_worth, rating_score
      Entity-type one-hot [11-15]: is_company, is_director, is_supplier, is_customer, is_bank

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
        return np.zeros((0, 0)), np.zeros((0, FEAT_DIM)), {}

    # Build directed adjacency (keep direction for reciprocity analysis)
    adj_directed = np.zeros((n, n), dtype=np.float32)
    for edge in edges:
        src = edge.get("source", edge.get("from"))
        tgt = edge.get("target", edge.get("to"))
        if src in id_to_idx and tgt in id_to_idx:
            i, j = id_to_idx[src], id_to_idx[tgt]
            weight = float(edge.get("properties", {}).get("amount", 1.0))
            adj_directed[i][j] += weight

    # Symmetric adjacency for GCN / heuristic scoring
    adj = adj_directed + adj_directed.T

    # Build 16-dim feature matrix
    features = np.zeros((n, FEAT_DIM), dtype=np.float32)

    for idx, node in enumerate(nodes):
        label = node.get("label", "").lower()
        props = node.get("properties", {})

        # -- Structural features [0-4] --
        # 0: Degree
        features[idx, 0] = np.sum(adj[idx] > 0)
        # 1: Total incoming amount
        features[idx, 1] = np.sum(adj_directed[:, idx])
        # 2: Total outgoing amount
        features[idx, 2] = np.sum(adj_directed[idx, :])
        # 3: Reciprocity ratio — fraction of edges that are bidirectional
        out_neighbors = set(np.where(adj_directed[idx] > 0)[0])
        in_neighbors = set(np.where(adj_directed[:, idx] > 0)[0])
        total_neighbors = out_neighbors | in_neighbors
        reciprocal = out_neighbors & in_neighbors
        features[idx, 3] = len(reciprocal) / max(len(total_neighbors), 1)
        # 4: Concentration index — Herfindahl of outgoing amounts
        out_amounts = adj_directed[idx, :]
        out_total = np.sum(out_amounts)
        if out_total > 0:
            shares = out_amounts[out_amounts > 0] / out_total
            features[idx, 4] = float(np.sum(shares ** 2))  # HHI: 1.0 = all to one node

        # -- Financial attributes [5-10] --
        features[idx, 5] = float(props.get("revenue", props.get("turnover", 0)) or 0)
        features[idx, 6] = float(props.get("debt_equity_ratio", props.get("de_ratio", 0)) or 0)
        features[idx, 7] = float(props.get("dscr", 0) or 0)
        features[idx, 8] = float(props.get("promoter_pledge_pct", props.get("pledge_pct", 0)) or 0)
        features[idx, 9] = float(props.get("net_worth", 0) or 0)
        features[idx, 10] = float(props.get("rating_score", 0) or 0)

        # -- Entity-type one-hot [11-15] --
        features[idx, 11] = 1.0 if label in ("company", "borrower") else 0.0
        features[idx, 12] = 1.0 if label == "director" else 0.0
        features[idx, 13] = 1.0 if label == "supplier" else 0.0
        features[idx, 14] = 1.0 if label == "customer" else 0.0
        features[idx, 15] = 1.0 if label in ("bank", "lender") else 0.0

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


def _label_propagation(adj: np.ndarray, max_iter: int = 30) -> np.ndarray:
    """Simple label propagation community detection.

    Each node starts as its own community. Iteratively adopts the most
    frequent label among neighbours. Converges to stable communities.

    Returns array of community IDs per node.
    """
    n = adj.shape[0]
    if n == 0:
        return np.array([], dtype=int)
    labels = np.arange(n, dtype=int)
    rng = np.random.RandomState(42)
    for _ in range(max_iter):
        order = np.arange(n)
        rng.shuffle(order)
        changed = False
        for i in order:
            neighbors = np.where(adj[i] > 0)[0]
            if len(neighbors) == 0:
                continue
            # Count neighbour labels
            counts: Dict[int, float] = {}
            for nb in neighbors:
                lbl = labels[nb]
                counts[lbl] = counts.get(lbl, 0) + adj[i][nb]
            best_label = max(counts, key=lambda k: counts[k])
            if labels[i] != best_label:
                labels[i] = best_label
                changed = True
        if not changed:
            break
    return labels


def _heuristic_detect(
    adj: np.ndarray,
    features: np.ndarray,
    id_to_idx: Dict[str, int],
    nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Enhanced heuristic graph anomaly detection (fallback).

    Uses structural + financial features to identify suspicious nodes:
    1. Degree anomaly — nodes with unusually high/low connectivity
    2. Amount asymmetry — nodes where in ≠ out by large margins
    3. Cycle participation — nodes in circular trading paths
    4. Clustering coefficient anomaly — unusually dense local neighbourhoods
    5. Reciprocity anomaly — nodes with unusually high bidirectional edges (round-tripping)
    6. Fund flow concentration — nodes sending most funds to a single counterparty
    7. Community bridge detection — nodes connecting different communities
    """
    n = adj.shape[0]
    idx_to_id = {v: k for k, v in id_to_idx.items()}

    if n == 0:
        return {
            "node_scores": {},
            "anomalous_nodes": [],
            "cycles_detected": [],
            "patterns": [],
            "communities": {},
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
            neighbor_edges = 0
            for a in range(len(neighbors)):
                for b in range(a + 1, len(neighbors)):
                    if adj[neighbors[a]][neighbors[b]] > 0:
                        neighbor_edges += 1
            max_edges = k * (k - 1) / 2
            clustering[i] = neighbor_edges / max_edges if max_edges > 0 else 0

    # 5. Reciprocity ratio (from feature col 3)
    reciprocity = features[:, 3] if features.shape[1] > 3 else np.zeros(n)

    # 6. Fund flow concentration (from feature col 4 — Herfindahl index)
    concentration = features[:, 4] if features.shape[1] > 4 else np.zeros(n)

    # 7. Community detection + bridge scoring
    communities = _label_propagation(adj)
    community_map: Dict[str, int] = {}
    bridge_score = np.zeros(n)
    for i in range(n):
        nid = idx_to_id.get(i, str(i))
        community_map[nid] = int(communities[i])
        # Bridge: node whose neighbours span multiple communities
        neighbors = np.where(adj[i] > 0)[0]
        if len(neighbors) > 0:
            neighbor_comms = set(communities[nb] for nb in neighbors)
            if len(neighbor_comms) > 1:
                bridge_score[i] = len(neighbor_comms) / max(len(neighbors), 1)

    # Composite anomaly score: weighted combination
    scores = np.zeros(n)
    scores += 0.15 * np.minimum(degree_z / 3.0, 1.0)        # Degree anomaly
    scores += 0.10 * asymmetry                                 # Amount asymmetry
    scores += 0.25 * cycle_participation                       # Cycle participation (heaviest)
    scores += 0.10 * (1.0 - clustering)                        # Low clustering = bridge/shell
    scores += 0.15 * reciprocity                               # High reciprocity = round-tripping
    scores += 0.15 * concentration                             # High concentration = dependent
    scores += 0.10 * bridge_score                              # Community bridge

    # Adaptive threshold: mean + k*std
    threshold = ANOMALY_THRESHOLD
    if n >= 5:
        threshold = max(ANOMALY_THRESHOLD, float(np.mean(scores) + ADAPTIVE_THRESHOLD_K * np.std(scores)))

    # Build per-node results
    node_scores = {}
    anomalous_nodes = []
    for node_id, idx in id_to_idx.items():
        node_label = nodes[idx].get("label", "unknown") if idx < len(nodes) else "unknown"
        node_name = nodes[idx].get("name", node_id) if idx < len(nodes) else node_id

        score = float(scores[idx])
        node_scores[node_id] = round(score, 4)

        if score >= threshold:
            reasons = []
            if degree_z[idx] > 2.0:
                reasons.append(f"unusual degree ({int(degrees[idx])} connections, mean={mean_deg:.1f})")
            if asymmetry[idx] > 0.5:
                reasons.append(f"high amount asymmetry ({asymmetry[idx]:.1%})")
            if cycle_participation[idx] > 0:
                reasons.append("participates in circular trading cycle")
            if clustering[idx] < 0.1 and degrees[idx] > 2:
                reasons.append("low clustering (potential bridge/shell node)")
            if reciprocity[idx] > 0.6:
                reasons.append(f"high reciprocity ({reciprocity[idx]:.0%} bidirectional edges — potential round-tripping)")
            if concentration[idx] > 0.8:
                reasons.append(f"fund flow concentrated (HHI={concentration[idx]:.2f} — single-counterparty dependency)")
            if bridge_score[idx] > 0.3:
                reasons.append(f"community bridge (connects {int(bridge_score[idx] * max(degrees[idx], 1))} communities)")

            anomalous_nodes.append({
                "node_id": node_id,
                "node_name": node_name,
                "node_label": node_label,
                "anomaly_score": round(score, 4),
                "community": int(communities[idx]),
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
        high_degree = [nd for nd in anomalous_nodes if any("degree" in r for r in nd.get("reasons", []))]
        if high_degree:
            patterns.append({
                "pattern_type": "hub_node",
                "description": f"{len(high_degree)} hub node(s) with unusually high connectivity",
                "entities": [nd["node_name"] for nd in high_degree],
                "severity": "MEDIUM",
            })

        reciprocal_nodes = [nd for nd in anomalous_nodes if any("reciprocity" in r for r in nd.get("reasons", []))]
        if reciprocal_nodes:
            patterns.append({
                "pattern_type": "round_tripping",
                "description": f"{len(reciprocal_nodes)} node(s) with suspicious bidirectional fund flows",
                "entities": [nd["node_name"] for nd in reciprocal_nodes],
                "severity": "HIGH",
            })

        concentrated = [nd for nd in anomalous_nodes if any("concentrated" in r for r in nd.get("reasons", []))]
        if concentrated:
            patterns.append({
                "pattern_type": "fund_concentration",
                "description": f"{len(concentrated)} node(s) routing funds predominantly to single counterparty",
                "entities": [nd["node_name"] for nd in concentrated],
                "severity": "MEDIUM",
            })

    # Count unique communities
    unique_communities = len(set(int(c) for c in communities))

    return {
        "node_scores": node_scores,
        "anomalous_nodes": anomalous_nodes,
        "cycles_detected": [
            {"cycle": c, "chain": " → ".join(c) + f" → {c[0]}", "length": len(c)}
            for c in cycles
        ],
        "patterns": patterns,
        "communities": community_map,
        "num_communities": unique_communities,
        "adaptive_threshold": round(threshold, 4),
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
    """DOMINANT GNN-based anomaly detection using PyTorch Geometric.

    Dual-objective autoencoder: reconstructs both node attributes AND
    graph structure. Anomaly score = weighted sum of attribute error +
    structure error.  Adaptive threshold via mean + k*std.
    """
    import torch
    from torch_geometric.nn import GCNConv
    from torch_geometric.utils import dense_to_sparse

    n = adj.shape[0]
    idx_to_id = {v: k for k, v in id_to_idx.items()}

    # Convert to PyG format
    adj_binary = (adj > 0).astype(np.float32)
    adj_tensor = torch.FloatTensor(adj_binary)
    edge_index, _ = dense_to_sparse(adj_tensor)
    x = torch.FloatTensor(features)
    adj_target = torch.FloatTensor(adj_binary)  # Structure reconstruction target

    feat_dim = features.shape[1]

    # DOMINANT-inspired dual-objective autoencoder
    class DOMINANTAutoEncoder(torch.nn.Module):
        """Attribute encoder/decoder + structure decoder."""

        def __init__(self):
            super().__init__()
            # Shared encoder
            self.enc1 = GCNConv(feat_dim, HIDDEN_DIM)
            self.enc2 = GCNConv(HIDDEN_DIM, HIDDEN_DIM // 2)
            # Attribute decoder
            self.attr_dec1 = GCNConv(HIDDEN_DIM // 2, HIDDEN_DIM)
            self.attr_dec2 = GCNConv(HIDDEN_DIM, feat_dim)
            # Structure decoder (inner product of embeddings)

        def encode(self, x, edge_index):
            z = torch.relu(self.enc1(x, edge_index))
            z = self.enc2(z, edge_index)
            return z

        def decode_attr(self, z, edge_index):
            h = torch.relu(self.attr_dec1(z, edge_index))
            return self.attr_dec2(h, edge_index)

        def decode_struct(self, z):
            # Inner product → adjacency reconstruction
            return torch.sigmoid(z @ z.T)

        def forward(self, x, edge_index):
            z = self.encode(x, edge_index)
            x_hat = self.decode_attr(z, edge_index)
            adj_hat = self.decode_struct(z)
            return x_hat, adj_hat

    model = DOMINANTAutoEncoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    # Train
    model.train()
    for epoch in range(NUM_EPOCHS):
        optimizer.zero_grad()
        x_hat, adj_hat = model(x, edge_index)
        attr_loss = torch.nn.functional.mse_loss(x_hat, x)
        struct_loss = torch.nn.functional.binary_cross_entropy(adj_hat, adj_target)
        loss = 0.5 * attr_loss + 0.5 * struct_loss
        loss.backward()
        optimizer.step()

    # Compute per-node anomaly scores
    model.eval()
    with torch.no_grad():
        x_hat, adj_hat = model(x, edge_index)
        attr_err = torch.mean((x - x_hat) ** 2, dim=1)
        struct_err = torch.mean((adj_target - adj_hat) ** 2, dim=1)
        errors = 0.5 * attr_err + 0.5 * struct_err

        # Adaptive threshold: mean + k*std
        err_mean = float(errors.mean())
        err_std = float(errors.std()) if n > 1 else 0.0
        threshold = max(ANOMALY_THRESHOLD, err_mean + ADAPTIVE_THRESHOLD_K * err_std)

        # Normalize to [0, 1]
        if errors.max() > errors.min():
            scores = (errors - errors.min()) / (errors.max() - errors.min())
        else:
            scores = torch.zeros_like(errors)

    scores_np = scores.numpy()

    # Community detection + cycles
    cycles = _detect_cycles(adj, id_to_idx)
    communities = _label_propagation(adj)
    community_map: Dict[str, int] = {}

    cycle_nodes: Set[str] = set()
    for cycle in cycles:
        cycle_nodes.update(cycle)

    node_scores = {}
    anomalous_nodes = []
    for node_id, idx in id_to_idx.items():
        node_label = nodes[idx].get("label", "unknown") if idx < len(nodes) else "unknown"
        node_name = nodes[idx].get("name", node_id) if idx < len(nodes) else node_id
        community_map[node_id] = int(communities[idx])

        score = float(scores_np[idx])
        if node_id in cycle_nodes:
            score = min(1.0, score + 0.3)
        node_scores[node_id] = round(score, 4)

        # Use raw error for threshold comparison (scores are normalized)
        raw_err = float(errors[idx])
        if raw_err > threshold or score >= ANOMALY_THRESHOLD:
            reasons = []
            if float(attr_err[idx]) > float(attr_err.mean() + attr_err.std()):
                reasons.append("high attribute reconstruction error (unusual financial profile)")
            if float(struct_err[idx]) > float(struct_err.mean() + struct_err.std()):
                reasons.append("high structure reconstruction error (unusual connectivity pattern)")
            if node_id in cycle_nodes:
                reasons.append("participates in circular trading cycle")
            if features[idx, 3] > 0.6:
                reasons.append(f"high reciprocity ({features[idx, 3]:.0%} bidirectional edges)")
            if features[idx, 4] > 0.8:
                reasons.append(f"concentrated fund flow (HHI={features[idx, 4]:.2f})")

            anomalous_nodes.append({
                "node_id": node_id,
                "node_name": node_name,
                "node_label": node_label,
                "anomaly_score": round(score, 4),
                "community": int(communities[idx]),
                "attr_error": round(float(attr_err[idx]), 4),
                "struct_error": round(float(struct_err[idx]), 4),
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

    unique_communities = len(set(int(c) for c in communities))

    return {
        "node_scores": node_scores,
        "anomalous_nodes": anomalous_nodes,
        "cycles_detected": [
            {"cycle": c, "chain": " → ".join(c) + f" → {c[0]}", "length": len(c)}
            for c in cycles
        ],
        "patterns": patterns,
        "communities": community_map,
        "num_communities": unique_communities,
        "adaptive_threshold": round(threshold, 4),
        "total_nodes": n,
        "total_edges": int(np.sum(adj > 0) / 2),
        "training_loss": round(float(loss), 6),
        "attr_loss": round(float(attr_loss), 6),
        "struct_loss": round(float(struct_loss), 6),
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
