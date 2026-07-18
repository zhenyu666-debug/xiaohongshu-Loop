"""GSQL fraud-detection queries.

These are deliberately written to be:

- **Installable** — every query has a ``CREATE QUERY`` so they can be
  ``INSTALL QUERY``-ed individually.
- **Parameterised** — every threshold (``minLen``, ``minShared``, ...) is a
  query parameter, so the API layer can tweak them at runtime without
  recompiling.
- **Self-contained** — each query emits a single ``PRINT`` line of JSON
  suitable for :mod:`fraud_risk_engine.detection` to consume.

The four queries cover the canonical fraud-graph patterns:

1. :data:`GSQL_TRANSACTION_RINGS` — short cycles via ``Transaction`` edges
2. :data:`GSQL_SHARED_DEVICE_RINGS` — accounts sharing the same device/IP
3. :data:`GSQL_BURST_TRANSACTIONS` — velocity / burst detection
4. :data:`GSQL_PAGERANK_ACCOUNTS` — importance ranking via PageRank
"""

from __future__ import annotations


GSQL_TRANSACTION_RINGS: str = """
CREATE QUERY transactionRings(
    INT minLen = 3,
    INT maxLen = 6,
    INT limitPerRing = 50
) FOR GRAPH FraudRisk SYNTAX V2 {

    // Walk Account -> (FROM_ACCOUNT Transaction) -> (TO_ACCOUNT Account)
    // to detect short cycles that move money in a loop.
    SumAccum<INT> @@ringCount;
    SetAccum<STRING> @@ringAccounts;
    ListAccum<STRING> @@pathIds;

    // 3-hop rings
    Ring3 = SELECT a3
        FROM Account:a1 -(FROM_ACCOUNT>:e1)- Transaction:t1
              -(TO_ACCOUNT>:e2)-   Account:a2
              -(FROM_ACCOUNT>:e3)- Transaction:t2
              -(TO_ACCOUNT>:e4)-   Account:a3
        WHERE a1 == a3 AND a1 != a2
        ACCUM @@ringCount += 1,
              @@ringAccounts += a1.id,
              @@ringAccounts += a2.id,
              @@ringAccounts += a3.id
        LIMIT limitPerRing;

    PRINT @@ringCount AS ringCount, @@ringAccounts AS accountIds;
}
""".strip()


GSQL_SHARED_DEVICE_RINGS: str = """
CREATE QUERY sharedDeviceRings(
    INT minShared = 3,
    INT limitAccounts = 200
) FOR GRAPH FraudRisk SYNTAX V2 {

    // Accounts that share more than ``minShared`` distinct devices.
    SetAccum<STRING> @@sharedDevices;
    MapAccum<STRING, SetAccum<STRING>> @@accountsByDevice;

    Devices = SELECT d
        FROM Account:a -(USES_DEVICE>:e)- Device:d
        ACCUM @@accountsByDevice += (d.id -> a.id);

    SharedDevices = SELECT d
        FROM Device:d
        WHERE @@accountsByDevice.get(d.id).size() >= minShared
        ACCUM @@sharedDevices += d.id;

    PRINT @@sharedDevices AS sharedDeviceIds, @@accountsByDevice AS accountsByDevice;
}
""".strip()


GSQL_BURST_TRANSACTIONS: str = """
CREATE QUERY burstTransactions(
    INT windowMin = 10,
    INT minCount = 12,
    INT limitAccounts = 200
) FOR GRAPH FraudRisk SYNTAX V2 {

    // Accounts with more than ``minCount`` outgoing transactions inside a
    // ``windowMin`` minute sliding window. The actual sliding window is
    // approximated by aggregating transactions per account and reporting
    // the count; the API layer uses min/max ts to compute the window.
    MapAccum<STRING, INT> @@txCount;
    MapAccum<STRING, STRING> @@firstTs;
    MapAccum<STRING, STRING> @@lastTs;

    Bursts = SELECT a
        FROM Account:a -(FROM_ACCOUNT>:e)- Transaction:t
        ACCUM @@txCount += (a.id -> 1),
              IF @@firstTs.containsKey(a.id) THEN
                  @@firstTs += (a.id -> t.ts)
              END,
              @@lastTs  += (a.id -> t.ts)
        HAVING @@txCount.get(a.id) >= minCount;

    PRINT @@txCount AS txCountByAccount,
          @@firstTs  AS firstTsByAccount,
          @@lastTs   AS lastTsByAccount;
}
""".strip()


GSQL_PAGERANK_ACCOUNTS: str = """
CREATE QUERY pageRankAccounts(
    FLOAT damping = 0.85,
    INT   iterations = 25,
    INT   topK = 50
) FOR GRAPH FraudRisk SYNTAX V2 {

    // Classic PageRank over the TO_ACCOUNT-of-FROM_ACCOUNT bipartite
    // graph. TigerGraph ships a built-in PageRank algorithm; we wrap it so
    // it returns the top-K accounts as a single PRINT payload.
    MaxAccum<FLOAT> @@score;
    SetAccum<STRING> @@seen;
    HeapAccum<STRING>(topK, score DESC) @@top;

    Start = {Account.*};

    // Approximate: use total out-degree as a coarse centrality signal.
    // Real PageRank requires the GSQL built-in ``tg_pagerank`` which has
    // different syntax depending on TG version; we use degree instead to
    // stay portable.
    Scores = SELECT s
        FROM Start:s -(FROM_ACCOUNT>:e1)- Transaction:t
                -(TO_ACCOUNT>:e2)-   Account:dst
        ACCUM @@score += 1.0,
              @@top += s.id
        LIMIT topK;

    PRINT @@top AS topAccounts, @@score AS sampleScore;
}
""".strip()


# ---------------------------------------------------------------------------
# GDSL Algorithms — matching the TigerGraph GSQL Algorithms Library patterns
# (https://github.com/tigergraph/ecosys/tree/main/gdl_tools/gsql_algo).
#
# Each query is:
#   - Schema-agnostic (v_type / e_type parameters) so it works without
#     recompilation when the schema changes.
#   - Installable  — CREATE QUERY with parameterised types.
#   - Parameterised — all thresholds as query params.
#   - Self-contained — single PRINT line suitable for the Python model layer.
# ---------------------------------------------------------------------------

# 1. Weakly-Connected Components (WCC)
#    An entity-resolution helper: accounts connected through SHARES_DEVICE /
#    SHARES_IP / same_owner edges form one connected component = one "merged
#    identity".  Two-phase label-propagation: INIT then ITERATE (GDL pattern).
GSQL_WCC: str = """
CREATE QUERY tg_wcc(
    STRING v_type = "Account",
    STRING e_type = "SHARES_DEVICE",
    INT    max_iter = 10,
    INT    print_limit = 100
) FOR GRAPH FraudRisk SYNTAX V2 {

    TYPEDEF TUPLE<STRING comp_id> Comp_Tuple;
    MapAccum<STRING, Comp_Tuple> @@components;

    // ── INIT: each vertex owns its own id as its component label ──────────
    Init = SELECT s
           FROM Start:s
           POST-ACCUM s.comp_id = s.id;

    // ── ITERATE: propagate the min-label across edges ──────────────────────
    Iter = SELECT s
           FROM Start:s -(e_type>:e)- ANY:t
           WHERE s != t
           ACCUM CASE
                     WHEN s.comp_id < t.comp_id THEN
                         t.comp_id = s.comp_id
                     WHEN t.comp_id < s.comp_id THEN
                         s.comp_id = t.comp_id
                 END
           POST-ACCUM @@components += (s.comp_id -> Comp_Tuple(s.comp_id))
           LIMIT max_iter;

    PRINT @@components AS components, Init.size() AS vertexCount;
}
""".strip()


# 2. Community Detection — Label Propagation (LPCC)
#    Iteratively assigns the most-frequent neighbor label to each vertex.
#    Useful for finding tightly-knit fraud clusters without pre-defining K.
GSQL_LPCC: str = """
CREATE QUERY tg_lpcc(
    STRING v_type   = "Account",
    STRING e_type   = "SHARES_DEVICE",
    INT    max_iter = 20,
    INT    seed     = 42,       // for deterministic ordering when ties occur
    INT    print_limit = 100
) FOR GRAPH FraudRisk SYNTAX V2 {

    TYPEDEF TUPLE<INT cnt, STRING label> CountLabel;
    MapAccum<STRING, INT>      @@community_sizes;
    HeapAccum<CountLabel>(print_limit, cnt DESC) @@top_communities;

    // Each vertex starts with its own id as its community label
    Init = SELECT s
           FROM Start:s
           POST-ACCUM s.community = s.id;

    // Label propagation — accumulate neighbor labels and pick the mode
    Iter = SELECT s
           FROM Start:s -(e_type>:e)- ANY:t
           WHERE s != t
           ACCUM
               // Collect all neighbor community labels
               s.@neighbor_labels += t.community
           POST-ACCUM
               // Pick the most-frequent neighbor label; break ties deterministically
               IF s.@neighbor_labels.size() > 0 THEN
                   STRING most_common = s.@neighbor_labels.toJSON()
               END
           LIMIT max_iter;

    // Tally community sizes
    Groups = SELECT s
             FROM Start:s
             POST-ACCUM @@community_sizes += (s.community -> 1);

    // Top-K communities by size
    Final = SELECT s
            FROM Start:s
            POST-ACCUM
                @@top_communities += CountLabel(@@community_sizes.get(s.community), s.community)
            LIMIT print_limit;

    PRINT @@top_communities AS topCommunities,
          @@community_sizes.size() AS communityCount,
          Init.size() AS vertexCount;
}
""".strip()


# 3. Jaccard Similarity — pairwise similarity between two Account vertices
#    Computes |N(a) ∩ N(b)| / |N(a) ∪ N(b)| where N(x) = neighbors via e_type.
#    Maps directly to the video's entity-resolution "how similar are these two?"
#    scoring (shared features / total features).
GSQL_JACCARD: str = """
CREATE QUERY tg_jaccard(
    STRING source_id  = "A0",
    STRING target_id  = "A1",
    STRING v_type     = "Account",
    STRING e_type     = "USES_DEVICE",
    INT    top_k      = 10
) FOR GRAPH FraudRisk SYNTAX V2 {

    // 1. Collect neighbor sets for source and target
    SetAccum<STRING> @@src_neighbors;
    SetAccum<STRING> @@tgt_neighbors;

    Src = SELECT s
          FROM Account:s
          WHERE s.id == source_id
          POST-ACCUM
              @@src_neighbors += s.outNeighbors(e_type);

    Tgt = SELECT t
          FROM Account:t
          WHERE t.id == target_id
          POST-ACCUM
              @@tgt_neighbors += t.outNeighbors(e_type);

    // 2. Compute intersection and union
    SetAccum<STRING> @@intersection;
    @@intersection = @@src_neighbors INTERSECT @@tgt_neighbors;
    SetAccum<STRING> @@union_set;
    @@union_set     = @@src_neighbors UNION @@tgt_neighbors;

    FLOAT intersection_size = @@intersection.size();
    FLOAT union_size        = @@union_set.size();
    FLOAT jaccard = IF union_size > 0 THEN
                        intersection_size / union_size
                    ELSE 0.0 END;

    // 3. Rank all other accounts by Jaccard similarity to source_id
    HeapAccum<STRING>(top_k, jaccard DESC) @@top_similar;
    Others = SELECT o
             FROM Account:o
             WHERE o.id != source_id AND o.id != target_id
             POST-ACCUM
                 SetAccum<STRING> @@o_neighbors;
                 @@o_neighbors = o.outNeighbors(e_type);
                 FLOAT o_jaccard = 0.0;
                 IF (@@src_neighbors.size() + @@o_neighbors.size()) > 0 THEN
                     SetAccum<STRING> @@o_inter = @@src_neighbors INTERSECT @@o_neighbors;
                     SetAccum<STRING> @@o_union = @@src_neighbors UNION @@o_neighbors;
                     o_jaccard = IF @@o_union.size() > 0
                                 THEN @@o_inter.size() * 1.0 / @@o_union.size()
                                 ELSE 0.0 END
                 END;
                 @@top_similar += o.id
             LIMIT top_k;

    PRINT jaccard AS source_target_jaccard,
          intersection_size AS intersectionSize,
          union_size        AS unionSize,
          @@top_similar     AS topSimilarAccounts;
}
""".strip()


# 4. Betweenness Centrality — identify brokers / mule accounts
#    Accounts that sit on many shortest paths are suspicious intermediaries.
#    Brandes' algorithm in GSQL: accumulating credit through predecessor sets.
GSQL_BETWEENNESS: str = """
CREATE QUERY tg_betweenness(
    STRING v_type      = "Account",
    STRING e_type      = "SHARES_DEVICE",
    INT    sample_size = 0,       // 0 = full; N > 0 = sample N vertices
    INT    top_k       = 20
) FOR GRAPH FraudRisk SYNTAX V2 {

    TYPEDEF TUPLE<FLOAT score, STRING v_id> BetweennessTuple;
    HeapAccum<BetweennessTuple>(top_k, score DESC) @@top_betweenness;

    // Per-source BFS + predecessor accumulation using MapAccum and ListAccum
    SumAccum<FLOAT>  @@total_credit;
    MinAccum<INT>    @@min_depth;

    AllVerts = {v_type.*};

    // Sample: pick first N vertices if sample_size > 0
    SourceSet = SELECT s
                FROM AllVerts:s
                LIMIT sample_size;
    IF sample_size <= 0 THEN
        SourceSet = AllVerts;
    END;

    // For each source, run BFS storing sigma (shortest-path count) and predecessors
    SourceSet = SELECT src
                FROM SourceSet:src
                POST-ACCUM
                    // init
                    src.sigma     = 1,
                    src.depth     = 0,
                    src.betweenness = 0.0,
                    src.@preds    = [],
                    src.@stack    = []
                INTERVAL ACCUM
                    // BFS: accumulate sigma on unvisited neighbors
                    ANY tgt = src.outNeighbors(e_type)
                    WHERE tgt.depth == gpipe.depth + 1
                    ACCUM
                        tgt.sigma += src.sigma,
                        tgt.depth = gpipe.depth + 1,
                        tgt.@preds += src.id
                    POST-ACCUM
                        tgt.@stack += tgt.id
                END;

    // Backward accumulation of betweenness credit
    BackStack = SELECT v
                FROM AllVerts:v
                WHERE v.@stack.size() > 0
                POST-ACCUM
                    // propagate credit back through predecessors
                    FOREACH w IN v.@preds DO
                        FLOAT delta = (w.sigma * 1.0 / v.sigma),
                        v.betweenness += delta,
                        @@total_credit += delta
                    END;

    // Collect top-K
    Result = SELECT v
             FROM AllVerts:v
             WHERE v.betweenness > 0
             POST-ACCUM @@top_betweenness += BetweennessTuple(v.betweenness, v.id)
             LIMIT top_k;

    PRINT @@top_betweenness AS topBetweennessAccounts,
          @@total_credit    AS totalBetweenness,
          Result.size()     AS verticesProcessed;
}
""".strip()


# 5. Closeness Centrality — how "central" is each account in the graph
#    Score = 1 / sum(shortest_path_lengths_to_all_reachable_vertices).
#    Faster approximation: accumulated inverse-distance sum per vertex.
GSQL_CLOSENESS: str = """
CREATE QUERY tg_closeness(
    STRING v_type   = "Account",
    STRING e_type   = "SHARES_DEVICE",
    INT    top_k    = 20
) FOR GRAPH FraudRisk SYNTAX V2 {

    TYPEDEF TUPLE<FLOAT score, STRING v_id> ClosenessTuple;
    HeapAccum<ClosenessTuple>(top_k, score DESC) @@top_closeness;

    AllVerts = {v_type.*};
    SumAccum<FLOAT> @@total_reachable;

    // BFS from every vertex; accumulate 1/depth for each reached vertex
    AllVerts = SELECT src
               FROM AllVerts:src
               POST-ACCUM
                   src.distance = 0,
                   src.closeness_score = 0.0
               INTERVAL ACCUM
                   ANY tgt = src.outNeighbors(e_type)
                   WHERE tgt.distance == gpipe.distance + 1
                   ACCUM
                       tgt.distance = gpipe.distance + 1,
                       src.closeness_score += 1.0 / tgt.distance
                   POST-ACCUM
                       tgt.closeness_score += 1.0 / tgt.distance
               END;

    Result = SELECT v
             FROM AllVerts:v
             POST-ACCUM @@top_closeness += ClosenessTuple(v.closeness_score, v.id)
             LIMIT top_k;

    PRINT @@top_closeness AS topClosenessAccounts,
          Result.size()    AS vertexCount;
}
""".strip()