"""
Intelli-Credit — ML Model Evaluation Framework

Evaluates all ML models against Indian corporate financial datasets:
  - Isolation Forest: tabular anomaly detection on Indian company metrics
  - DOMINANT GNN: graph anomaly detection on Indian corporate networks
  - FinBERT: financial text risk classification

Metrics: Precision, Recall, F1-Score, ROC-AUC (where applicable).

Indian corporate ground-truth data sourced from:
  - RBI wilful defaulter patterns
  - SEBI enforcement action patterns
  - NCLT proceedings financial profiles
  - MCA strike-off histories
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Indian Corporate Benchmark Datasets (curated for demo)
#
# Each entry represents a real-world archetype based on publicly
# known Indian corporate fraud/default patterns. No actual company
# data is used — these are synthetic composites.
# ──────────────────────────────────────────────────────────────────

# Ground-truth labels: True = anomalous/fraudulent, False = clean
INDIAN_COMPANY_METRICS: List[Dict[str, Any]] = [
    # --- CLEAN companies (Indian mid-cap archetype) ---
    {
        "name": "Bharat Forge Components (Clean)",
        "metrics": {
            "dscr": 1.65, "current_ratio": 1.42, "debt_equity_ratio": 0.80,
            "revenue_cagr_3yr": 0.12, "ebitda_margin": 0.18, "pat_margin": 0.10,
            "interest_coverage_ratio": 4.2, "gst_bank_divergence_pct": 0.02,
            "promoter_pledge_pct": 0.0, "working_capital_days": 95,
        },
        "is_anomaly": False,
        "sector": "steel",
    },
    {
        "name": "Mahalaxmi Textiles (Clean)",
        "metrics": {
            "dscr": 1.35, "current_ratio": 1.28, "debt_equity_ratio": 1.10,
            "revenue_cagr_3yr": 0.08, "ebitda_margin": 0.14, "pat_margin": 0.06,
            "interest_coverage_ratio": 2.8, "gst_bank_divergence_pct": 0.04,
            "promoter_pledge_pct": 5.0, "working_capital_days": 120,
        },
        "is_anomaly": False,
        "sector": "fmcg",
    },
    {
        "name": "Vasavi Tech Solutions (Clean)",
        "metrics": {
            "dscr": 2.10, "current_ratio": 2.05, "debt_equity_ratio": 0.30,
            "revenue_cagr_3yr": 0.22, "ebitda_margin": 0.25, "pat_margin": 0.18,
            "interest_coverage_ratio": 8.5, "gst_bank_divergence_pct": 0.01,
            "promoter_pledge_pct": 0.0, "working_capital_days": 45,
        },
        "is_anomaly": False,
        "sector": "it",
    },
    {
        "name": "Godavari Infrastructure Ltd (Clean)",
        "metrics": {
            "dscr": 1.20, "current_ratio": 1.15, "debt_equity_ratio": 1.80,
            "revenue_cagr_3yr": 0.06, "ebitda_margin": 0.12, "pat_margin": 0.04,
            "interest_coverage_ratio": 1.9, "gst_bank_divergence_pct": 0.06,
            "promoter_pledge_pct": 10.0, "working_capital_days": 180,
        },
        "is_anomaly": False,
        "sector": "infrastructure",
    },
    {
        "name": "Deccan Pharma Industries (Clean)",
        "metrics": {
            "dscr": 1.80, "current_ratio": 1.55, "debt_equity_ratio": 0.55,
            "revenue_cagr_3yr": 0.15, "ebitda_margin": 0.22, "pat_margin": 0.14,
            "interest_coverage_ratio": 5.8, "gst_bank_divergence_pct": 0.03,
            "promoter_pledge_pct": 2.0, "working_capital_days": 100,
        },
        "is_anomaly": False,
        "sector": "pharma",
    },

    # --- ANOMALOUS companies (based on RBI/SEBI enforcement archetypes) ---
    {
        "name": "Zenith Steel Corp (Wilful Default Pattern)",
        "metrics": {
            "dscr": 0.45, "current_ratio": 0.62, "debt_equity_ratio": 5.80,
            "revenue_cagr_3yr": -0.25, "ebitda_margin": -0.08, "pat_margin": -0.22,
            "interest_coverage_ratio": 0.3, "gst_bank_divergence_pct": 0.35,
            "promoter_pledge_pct": 92.0, "working_capital_days": 320,
        },
        "is_anomaly": True,
        "sector": "steel",
    },
    {
        "name": "Paramount Housing (NCLT Pattern)",
        "metrics": {
            "dscr": 0.70, "current_ratio": 0.88, "debt_equity_ratio": 4.20,
            "revenue_cagr_3yr": -0.15, "ebitda_margin": 0.02, "pat_margin": -0.10,
            "interest_coverage_ratio": 0.8, "gst_bank_divergence_pct": 0.42,
            "promoter_pledge_pct": 78.0, "working_capital_days": 280,
        },
        "is_anomaly": True,
        "sector": "infrastructure",
    },
    {
        "name": "Meghna Exports (GST Fraud Pattern)",
        "metrics": {
            "dscr": 1.10, "current_ratio": 1.05, "debt_equity_ratio": 2.50,
            "revenue_cagr_3yr": 0.45, "ebitda_margin": 0.03, "pat_margin": 0.01,
            "interest_coverage_ratio": 1.5, "gst_bank_divergence_pct": 0.55,
            "promoter_pledge_pct": 40.0, "working_capital_days": 200,
        },
        "is_anomaly": True,
        "sector": "fmcg",
    },
    {
        "name": "Saffron IT Solutions (Revenue Inflation)",
        "metrics": {
            "dscr": 0.85, "current_ratio": 0.92, "debt_equity_ratio": 3.50,
            "revenue_cagr_3yr": 0.60, "ebitda_margin": 0.05, "pat_margin": -0.05,
            "interest_coverage_ratio": 1.0, "gst_bank_divergence_pct": 0.48,
            "promoter_pledge_pct": 65.0, "working_capital_days": 250,
        },
        "is_anomaly": True,
        "sector": "it",
    },
    {
        "name": "Durga Pharma Ltd (Diversion Pattern)",
        "metrics": {
            "dscr": 0.55, "current_ratio": 0.70, "debt_equity_ratio": 4.80,
            "revenue_cagr_3yr": -0.30, "ebitda_margin": -0.05, "pat_margin": -0.18,
            "interest_coverage_ratio": 0.5, "gst_bank_divergence_pct": 0.38,
            "promoter_pledge_pct": 88.0, "working_capital_days": 350,
        },
        "is_anomaly": True,
        "sector": "pharma",
    },
]


# Ground-truth graph for circular trading detection
INDIAN_GRAPH_BENCHMARK: Dict[str, Any] = {
    "description": "Synthetic Indian corporate supply chain with embedded circular trading",
    "nodes": [
        # Clean supply chain
        {"id": "XYZ_Steel", "label": "Company", "name": "XYZ Steel Ltd",
         "properties": {"revenue": 247.0, "debt_equity_ratio": 1.2, "dscr": 1.38}},
        {"id": "Tata_Steel_Supply", "label": "Supplier", "name": "Tata Steel Supply Co",
         "properties": {"revenue": 500.0}},
        {"id": "JSW_Customer", "label": "Customer", "name": "JSW Engineering",
         "properties": {"revenue": 300.0}},
        {"id": "SBI", "label": "Bank", "name": "State Bank of India",
         "properties": {}},
        {"id": "Dir_Rajesh", "label": "Director", "name": "Rajesh Kumar",
         "properties": {"promoter_pledge_pct": 15.0}},
        # Circular trading ring (A→B→C→A)
        {"id": "Shell_A", "label": "Company", "name": "Anand Trading Pvt Ltd",
         "properties": {"revenue": 12.0, "debt_equity_ratio": 8.0}},
        {"id": "Shell_B", "label": "Company", "name": "Balaji Enterprises",
         "properties": {"revenue": 8.0, "debt_equity_ratio": 6.5}},
        {"id": "Shell_C", "label": "Company", "name": "Chandra Commerce",
         "properties": {"revenue": 5.0, "debt_equity_ratio": 7.2}},
        # Shared director across shells (red flag)
        {"id": "Dir_Suspicious", "label": "Director", "name": "Vikram Mehta",
         "properties": {"promoter_pledge_pct": 90.0}},
    ],
    "edges": [
        # Clean supply chain
        {"source": "Tata_Steel_Supply", "target": "XYZ_Steel", "type": "SUPPLIES_TO",
         "properties": {"amount": 45.0}},
        {"source": "XYZ_Steel", "target": "JSW_Customer", "type": "SUPPLIES_TO",
         "properties": {"amount": 60.0}},
        {"source": "SBI", "target": "XYZ_Steel", "type": "LENDS_TO",
         "properties": {"amount": 50.0}},
        {"source": "Dir_Rajesh", "target": "XYZ_Steel", "type": "IS_DIRECTOR_OF",
         "properties": {"amount": 1.0}},
        # Circular trading: Shell_A → Shell_B → Shell_C → Shell_A
        {"source": "Shell_A", "target": "Shell_B", "type": "SUPPLIES_TO",
         "properties": {"amount": 10.0}},
        {"source": "Shell_B", "target": "Shell_C", "type": "SUPPLIES_TO",
         "properties": {"amount": 9.5}},
        {"source": "Shell_C", "target": "Shell_A", "type": "SUPPLIES_TO",
         "properties": {"amount": 9.0}},
        # Suspicious director links
        {"source": "Dir_Suspicious", "target": "Shell_A", "type": "IS_DIRECTOR_OF",
         "properties": {"amount": 1.0}},
        {"source": "Dir_Suspicious", "target": "Shell_B", "type": "IS_DIRECTOR_OF",
         "properties": {"amount": 1.0}},
        {"source": "Dir_Suspicious", "target": "Shell_C", "type": "IS_DIRECTOR_OF",
         "properties": {"amount": 1.0}},
    ],
    "expected_anomalous": ["Shell_A", "Shell_B", "Shell_C", "Dir_Suspicious"],
    "expected_cycles": [["Shell_A", "Shell_B", "Shell_C"]],
}


# FinBERT ground-truth texts (Indian financial context)
INDIAN_FINBERT_BENCHMARK: List[Dict[str, Any]] = [
    {
        "text": "The company has maintained stable revenue growth of 12% CAGR with improving EBITDA margins and no material litigation pending.",
        "expected_risk": False,
        "description": "Clean company with stable financials",
    },
    {
        "text": "CRISIL has upgraded the rating to AA- reflecting strong cash flows and debt reduction trajectory.",
        "expected_risk": False,
        "description": "Positive rating action",
    },
    {
        "text": "Promoter has pledged 92% of shareholding. SEBI has issued a show-cause notice for related party transaction disclosure violations.",
        "expected_risk": True,
        "description": "High pledge + regulatory action (SEBI)",
    },
    {
        "text": "The company has been classified as wilful defaulter by RBI. Criminal proceedings initiated against the managing director for fund diversion.",
        "expected_risk": True,
        "description": "Wilful default + criminal proceedings",
    },
    {
        "text": "NCLT has admitted insolvency proceedings under IBC. Revenue declined 40% YoY with negative EBITDA.",
        "expected_risk": True,
        "description": "NCLT insolvency + revenue collapse",
    },
    {
        "text": "Auditor has qualified the report citing inability to verify inventory worth ₹350 crores. Management has not provided adequate explanation.",
        "expected_risk": True,
        "description": "Audit qualification — inventory unverifiable",
    },
    {
        "text": "GST department has detected discrepancy of ₹45 crores between GSTR-2A and GSTR-3B returns indicating potential ITC fraud.",
        "expected_risk": True,
        "description": "GST fraud detection",
    },
    {
        "text": "The board approved corporate social responsibility expenditure of ₹2.5 crores for FY2024, in compliance with Section 135 of Companies Act.",
        "expected_risk": False,
        "description": "Routine CSR compliance",
    },
]


# ──────────────────────────────────────────────────────────────────
# Evaluation Functions
# ──────────────────────────────────────────────────────────────────

def _compute_metrics(
    y_true: List[bool],
    y_pred: List[bool],
    scores: Optional[List[float]] = None,
) -> Dict[str, float]:
    """Compute precision, recall, F1, accuracy, and optionally ROC-AUC.

    Args:
        y_true: Ground-truth binary labels.
        y_pred: Predicted binary labels.
        scores: Optional continuous anomaly scores for ROC-AUC.

    Returns:
        Dict with precision, recall, f1, accuracy, and optionally roc_auc.
    """
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(y_true) if len(y_true) > 0 else 0.0

    result = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
    }

    # ROC-AUC approximation (trapezoidal, no sklearn dependency)
    if scores is not None and len(set(y_true)) == 2:
        result["roc_auc"] = round(_compute_roc_auc(y_true, scores), 4)

    return result


def _compute_roc_auc(y_true: List[bool], scores: List[float]) -> float:
    """Compute ROC-AUC without sklearn using the trapezoidal rule.

    Sorts by score descending, sweeps thresholds, computes TPR/FPR pairs.
    """
    pairs = sorted(zip(scores, y_true), key=lambda x: -x[0])
    total_pos = sum(1 for _, t in pairs if t)
    total_neg = len(pairs) - total_pos
    if total_pos == 0 or total_neg == 0:
        return 0.5  # Undefined — return chance level

    tp = 0
    fp = 0
    prev_tpr = 0.0
    prev_fpr = 0.0
    auc = 0.0

    for score, label in pairs:
        if label:
            tp += 1
        else:
            fp += 1
        tpr = tp / total_pos
        fpr = fp / total_neg
        # Trapezoidal rule
        auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2
        prev_tpr = tpr
        prev_fpr = fpr

    return auc


def evaluate_isolation_forest() -> Dict[str, Any]:
    """Evaluate Isolation Forest on Indian corporate benchmark data.

    Returns evaluation metrics + per-company results.
    """
    from backend.ml.isolation_forest import detect_anomalies, reset

    reset()

    y_true: List[bool] = []
    y_pred: List[bool] = []
    scores: List[float] = []
    details: List[Dict[str, Any]] = []

    for company in INDIAN_COMPANY_METRICS:
        result = detect_anomalies(company["metrics"], sector=company.get("sector"))
        y_true.append(company["is_anomaly"])
        y_pred.append(result["is_anomaly"])
        scores.append(result["anomaly_score"])
        details.append({
            "name": company["name"],
            "expected": company["is_anomaly"],
            "predicted": result["is_anomaly"],
            "score": result["anomaly_score"],
            "top_features": [f["feature"] for f in result.get("anomalous_features", [])[:3]],
            "correct": company["is_anomaly"] == result["is_anomaly"],
        })

    metrics = _compute_metrics(y_true, y_pred, scores)
    return {
        "model": "IsolationForest",
        "dataset": "Indian Corporate Benchmark (10 companies)",
        "metrics": metrics,
        "details": details,
    }


def evaluate_gnn() -> Dict[str, Any]:
    """Evaluate DOMINANT GNN on Indian corporate graph benchmark.

    Returns detection metrics for circular trading + anomalous nodes.
    """
    from backend.ml.dominant_gnn import detect_graph_anomalies, reset

    reset()

    bench = INDIAN_GRAPH_BENCHMARK
    result = detect_graph_anomalies(bench["nodes"], bench["edges"])

    # Evaluate node-level anomaly detection
    expected_set = set(bench["expected_anomalous"])
    detected_set = set(n["node_id"] for n in result.get("anomalous_nodes", []))
    all_node_ids = [n["id"] for n in bench["nodes"]]

    # Use raw scores with a fixed evaluation threshold (0.4) since the
    # adaptive threshold is designed for production conservatism, not eval
    EVAL_THRESHOLD = 0.4
    eval_detected = set(
        nid for nid in all_node_ids
        if result.get("node_scores", {}).get(nid, 0.0) >= EVAL_THRESHOLD
    )

    y_true = [nid in expected_set for nid in all_node_ids]
    y_pred = [nid in eval_detected for nid in all_node_ids]
    scores_list = [result.get("node_scores", {}).get(nid, 0.0) for nid in all_node_ids]

    node_metrics = _compute_metrics(y_true, y_pred, scores_list)

    # Evaluate cycle detection
    expected_cycles = bench.get("expected_cycles", [])
    detected_cycles = [c["cycle"] for c in result.get("cycles_detected", [])]
    cycles_found = 0
    for ec in expected_cycles:
        ec_set = set(ec)
        for dc in detected_cycles:
            if ec_set == set(dc):
                cycles_found += 1
                break

    return {
        "model": "DOMINANT_GNN",
        "dataset": "Indian Corporate Graph Benchmark (9 nodes, 10 edges)",
        "node_detection_metrics": node_metrics,
        "cycle_detection": {
            "expected_cycles": len(expected_cycles),
            "detected_cycles": len(detected_cycles),
            "correct_cycles": cycles_found,
            "cycle_recall": round(cycles_found / max(len(expected_cycles), 1), 4),
        },
        "communities_found": result.get("num_communities", 0),
        "patterns_detected": len(result.get("patterns", [])),
        "method": result.get("method", "unknown"),
    }


def evaluate_finbert() -> Dict[str, Any]:
    """Evaluate FinBERT on Indian financial text benchmark.

    Returns risk classification metrics.
    """
    from backend.ml.finbert_model import analyze_text, reset

    reset()

    y_true: List[bool] = []
    y_pred: List[bool] = []
    scores: List[float] = []
    details: List[Dict[str, Any]] = []

    for entry in INDIAN_FINBERT_BENCHMARK:
        result = analyze_text(entry["text"])
        y_true.append(entry["expected_risk"])
        y_pred.append(result.get("risk_detected", False))
        scores.append(result.get("risk_score", 0.0))
        details.append({
            "description": entry["description"],
            "expected_risk": entry["expected_risk"],
            "predicted_risk": result.get("risk_detected", False),
            "risk_score": result.get("risk_score", 0.0),
            "sentiment": result.get("sentiment", "unknown"),
            "correct": entry["expected_risk"] == result.get("risk_detected", False),
        })

    metrics = _compute_metrics(y_true, y_pred, scores)
    return {
        "model": "FinBERT",
        "dataset": "Indian Financial Text Benchmark (8 samples)",
        "metrics": metrics,
        "details": details,
    }


def evaluate_all() -> Dict[str, Any]:
    """Run evaluation on all ML models and return consolidated report."""
    results = {}

    try:
        results["isolation_forest"] = evaluate_isolation_forest()
    except Exception as e:
        logger.error(f"[ModelEval] Isolation Forest evaluation failed: {e}")
        results["isolation_forest"] = {"error": str(e)}

    try:
        results["dominant_gnn"] = evaluate_gnn()
    except Exception as e:
        logger.error(f"[ModelEval] DOMINANT GNN evaluation failed: {e}")
        results["dominant_gnn"] = {"error": str(e)}

    try:
        results["finbert"] = evaluate_finbert()
    except Exception as e:
        logger.error(f"[ModelEval] FinBERT evaluation failed: {e}")
        results["finbert"] = {"error": str(e)}

    # Summary
    model_summaries = []
    for name, res in results.items():
        if "error" in res:
            model_summaries.append({"model": name, "status": "FAILED", "error": res["error"]})
        else:
            m = res.get("metrics") or res.get("node_detection_metrics", {})
            model_summaries.append({
                "model": name,
                "status": "OK",
                "f1": m.get("f1_score", 0.0),
                "precision": m.get("precision", 0.0),
                "recall": m.get("recall", 0.0),
                "roc_auc": m.get("roc_auc"),
            })

    results["summary"] = model_summaries
    return results
