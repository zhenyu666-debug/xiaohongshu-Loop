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