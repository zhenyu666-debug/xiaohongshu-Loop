"""LDBC SNB Benchmark — synthetic benchmark runner and sample generator.

This module provides:
- Sample graph data generation for visualization
- Benchmark execution with configurable scale factor, workload, and mode
- In-memory result storage for historical queries

Reference: https://github.com/ldbc/ldbc_snb_docs
"""

from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .loader.ldbc_snb_loader import build_ldbc_snb_dataset


# ---------------------------------------------------------------------------
# Scale-factor configurations
# ---------------------------------------------------------------------------

SCALE_FACTORS = [0.1, 1.0, 3.0, 10.0]
WORKLOADS = ["interactive", "bi"]
QUERY_COUNT = {
    "interactive": 21,
    "bi": 20,
}

# Interactive workload query templates (simplified for simulation)
INTERACTIVE_QUERIES = [
    "Q1", "Q2", "Q3", "Q4", "Q5",  # 1-hop traversals
    "Q6", "Q7", "Q8", "Q9", "Q10",  # 2-hop traversals
    "Q11", "Q12", "Q13", "Q14", "Q15",  # Aggregation
    "Q16", "Q17", "Q18", "Q19", "Q20", "Q21",  # Pattern matching
]

BI_QUERIES = [
    "BI-Q1", "BI-Q2", "BI-Q3", "BI-Q4", "BI-Q5",  # Complex analytical
    "BI-Q6", "BI-Q7", "BI-Q8", "BI-Q9", "BI-Q10",  # Aggregation
    "BI-Q11", "BI-Q12", "BI-Q13", "BI-Q14", "BI-Q15",  # Window functions
    "BI-Q16", "BI-Q17", "BI-Q18", "BI-Q19", "BI-Q20",  # Deep analysis
]


# ---------------------------------------------------------------------------
# Sample graph generator for visualization
# ---------------------------------------------------------------------------

def generate_snb_sample(sf: float = 0.1, limit: int = 100) -> dict[str, Any]:
    """Generate sample LDBC SNB graph data for frontend visualization.

    Parameters
    ----------
    sf : float
        Scale factor (0.1, 1, 3, 10)
    limit : int
        Maximum number of Person vertices to include

    Returns
    -------
    dict with keys: vertices, edges, counts
    """
    rng = random.Random(42)
    ds = build_ldbc_snb_dataset(sf=sf, seed=42)

    # Limit persons for visualization
    persons = ds.persons[:limit]
    person_ids = set(p["id"] for p in persons)

    # Collect related vertices (comments, posts, forums from these persons)
    related_comments = [c for c in ds.comments if c.get("_creator_id") in person_ids][:limit * 5]
    related_posts = [p for p in ds.posts if p.get("_creator_id") in person_ids][:limit * 2]
    related_forums = ds.forums[:20]  # Limit forums

    # Build vertices list
    vertices = []

    for p in persons:
        vertices.append({
            "id": str(p["id"]),
            "label": f"{p['firstName']} {p['lastName']}",
            "type": "Person",
            "properties": {
                "gender": p.get("gender", ""),
                "cityId": p.get("cityId", 0),
            },
        })

    for c in related_comments:
        vertices.append({
            "id": str(c["id"]),
            "label": f"Comment {c['id']}",
            "type": "Comment",
            "properties": {
                "length": c.get("length", 0),
            },
        })

    for p in related_posts:
        vertices.append({
            "id": str(p["id"]),
            "label": f"Post {p['id']}",
            "type": "Post",
            "properties": {
                "language": p.get("language", ""),
            },
        })

    for f in related_forums:
        vertices.append({
            "id": str(f["id"]),
            "label": f["title"],
            "type": "Forum",
            "properties": {},
        })

    # Build edges
    edges = []

    # KNOWS edges between persons
    for k in ds.knows[:limit * 3]:
        if k["from_id"] in person_ids and k["to_id"] in person_ids:
            edges.append({
                "id": f"k_{k['from_id']}_{k['to_id']}",
                "source": str(k["from_id"]),
                "target": str(k["to_id"]),
                "type": "KNOWS",
                "properties": {"creationDate": k.get("creationDate", "")},
            })

    # Sample other edges
    for lp in ds.likes_post[:limit * 2]:
        edges.append({
            "id": f"lp_{lp['from_id']}_{lp['to_id']}",
            "source": str(lp["from_id"]),
            "target": str(lp["to_id"]),
            "type": "LIKES_Post",
            "properties": {"creationDate": lp.get("creationDate", "")},
        })

    for hm in ds.has_member[:50]:
        edges.append({
            "id": f"hm_{hm['from_id']}_{hm['to_id']}",
            "source": str(hm["from_id"]),
            "target": str(hm["to_id"]),
            "type": "HAS_MEMBER",
            "properties": {"joinDate": hm.get("joinDate", "")},
        })

    # Build counts
    counts = {
        "Person": len(persons),
        "Comment": len(related_comments),
        "Post": len(related_posts),
        "Forum": len(related_forums),
    }

    return {
        "vertices": vertices,
        "edges": edges,
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# Query simulator (synthetic latency for benchmark)
# ---------------------------------------------------------------------------

def _simulate_query_latency(query_name: str, sf: float) -> float:
    """Simulate realistic query latency based on query complexity and scale factor."""
    rng = random.Random(hash(query_name))
    base_latencies = {
        "interactive": {
            "Q1": 2.5, "Q2": 3.1, "Q3": 4.2, "Q4": 5.8, "Q5": 8.3,  # 1-hop: 2-8ms
            "Q6": 12.5, "Q7": 18.2, "Q8": 22.7, "Q9": 31.4, "Q10": 45.6,  # 2-hop: 12-45ms
            "Q11": 28.3, "Q12": 35.1, "Q13": 42.8, "Q14": 56.2, "Q15": 68.4,  # Aggregation: 28-68ms
            "Q16": 55.3, "Q17": 72.1, "Q18": 89.5, "Q19": 102.3, "Q20": 125.6, "Q21": 148.9,  # Pattern: 55-150ms
        },
        "bi": {
            "BI-Q1": 150.2, "BI-Q2": 185.5, "BI-Q3": 220.8, "BI-Q4": 256.1, "BI-Q5": 312.4,
            "BI-Q6": 180.3, "BI-Q7": 215.6, "BI-Q8": 280.9, "BI-Q9": 340.2, "BI-Q10": 410.5,
            "BI-Q11": 250.4, "BI-Q12": 320.7, "BI-Q13": 390.1, "BI-Q14": 460.8, "BI-Q15": 530.2,
            "BI-Q16": 380.5, "BI-Q17": 450.8, "BI-Q18": 520.3, "BI-Q19": 590.6, "BI-Q20": 680.9,
        },
    }

    workload = "bi" if query_name.startswith("BI-") else "interactive"
    base = base_latencies.get(workload, {}).get(query_name, 50.0)

    # Scale with sf factor (larger data = higher latency)
    sf_factor = 1.0 + (sf - 1.0) * 0.15

    # Add jitter (±10%)
    jitter = 0.9 + rng.random() * 0.2

    return round(base * sf_factor * jitter, 2)


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    sf: float = 1.0,
    workload: str = "interactive",
    mode: str = "power",
    duration: int = 60,
    concurrency: int = 4,
) -> dict[str, Any]:
    """Run LDBC SNB benchmark simulation.

    Parameters
    ----------
    sf : float
        Scale factor (0.1, 1, 3, 10)
    workload : str
        Workload type ("interactive" or "bi")
    mode : str
        Test mode: "power", "throughput", or "both"
    duration : int
        Test duration in seconds (10-300)
    concurrency : int
        Number of concurrent workers (1, 4, 8, 16)

    Returns
    -------
    dict with benchmark report
    """
    queries = INTERACTIVE_QUERIES if workload == "interactive" else BI_QUERIES
    n_queries = QUERY_COUNT.get(workload, 21)

    # Power test: run all queries once, measure latency
    power_start = time.time()
    query_stats: dict[str, dict[str, Any]] = {}

    for q in queries:
        latencies = []
        runs = 3 if mode == "power" else 1  # Multiple runs for power test
        for _ in range(runs):
            latency = _simulate_query_latency(q, sf)
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        p50 = sorted(latencies)[len(latencies) // 2]
        p99_idx = min(int(len(latencies) * 0.99), len(latencies) - 1)
        p99 = sorted(latencies)[p99_idx] if latencies else 0

        query_stats[q] = {
            "avg_ms": round(avg_latency, 2),
            "p50_ms": round(p50, 2),
            "p99_ms": round(p99, 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
            "runs": runs,
        }

    power_elapsed_ms = (time.time() - power_start) * 1000

    # Throughput test: estimate QPS based on avg latency and concurrency
    avg_latency = sum(s["avg_ms"] for s in query_stats.values()) / len(query_stats)
    base_qps = 1000.0 / avg_latency if avg_latency > 0 else 0
    estimated_qps = round(base_qps * concurrency * 0.85, 2)  # 85% efficiency factor

    # Calculate aggregate metrics
    all_p99 = [s["p99_ms"] for s in query_stats.values()]
    overall_p99 = round(sorted(all_p99)[int(len(all_p99) * 0.99)] if all_p99 else 0, 2)
    all_p50 = [s["p50_ms"] for s in query_stats.values()]
    overall_p50 = round(sorted(all_p50)[len(all_p50) // 2] if all_p50 else 0, 2)

    report = {
        "benchmark_name": "LDBC SNB",
        "scale_factor": sf,
        "workload": workload,
        "mode": mode,
        "power_test_elapsed_ms": round(power_elapsed_ms, 2),
        "throughput_test_qps": estimated_qps,
        "concurrency": concurrency,
        "duration_seconds": duration,
        "query_count": n_queries,
        "query_stats": query_stats,
        "summary": {
            "overall_p50_ms": overall_p50,
            "overall_p99_ms": overall_p99,
            "total_queries": len(queries),
            "success_rate": 100.0,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    return report
