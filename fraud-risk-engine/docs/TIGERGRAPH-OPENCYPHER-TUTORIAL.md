# TigerGraph OpenCypher Tutorial

> Reference material received from user on 2026-07-23. To be used once
> `B:docker-daemon` is unblocked and TigerGraph can be pulled via
> `pull-tigergraph.ps1`.
>
> Source: TigerGraph OpenCypher tutorial (sample `financialGraph` schema —
> 5 Account vertices, 8 transfer edges, City / Phone vertices).

## How this doc maps to the repo

- The Docker image referenced in §Setup Environment is pulled by
  `pull-tigergraph.ps1` (uses mirror `docker.1ms.run/tigergraph/tigergraph:latest`).
- Schema / loading scripts in the tutorial's `gsql/` and `cypher/` folders
  should land under `fraud-risk-engine/app/queries/opencypher/` once we
  pick them up (per AGENTS.md scope `app/queries/` is in-scope).
- Runtime port mapping matches what `app/api.py` already expects:
  `tigergraph` → `http://localhost:14240`.

## Quick start (target state once Docker is back)

```bash
docker load -i ./tigergraph-4.2.0-community-docker-image.tar.gz
docker images                                  # find image id
docker run -d -p 14240:14240 --name mySandbox <imageId>
docker exec -it mySandbox /bin/bash
gadmin start all                               # start TG components
gadmin status                                  # verify all up
```

Browser: <http://localhost:14240/> — `tigergraph` / `tigergraph`.

## Sample graph

`financialGraph`: 5 Account vertices, 8 transfer edges. An account may be
associated with a City and a Phone. The use case: analyze which other
accounts are connected to `isBlocked` accounts.

## Setup schema

```sql
// install gds functions
import package gds
install function gds.**

CREATE VERTEX Account ( name STRING PRIMARY KEY, isBlocked BOOL)
CREATE VERTEX City    ( name STRING PRIMARY KEY)
CREATE VERTEX Phone   (number STRING PRIMARY KEY, isBlocked BOOL)

CREATE DIRECTED EDGE transfer (FROM Account, TO Account,
                               DISCRIMINATOR(date DATETIME),
                               amount UINT) WITH REVERSE_EDGE="transfer_reverse"
CREATE UNDIRECTED EDGE hasPhone (FROM Account, TO Phone)
CREATE DIRECTED EDGE isLocatedIn (FROM Account, TO City)

CREATE GRAPH financialGraph (*)
```

## Load data (sample)

```sql
USE GRAPH financialGraph
CREATE LOADING JOB load_local_file {
  DEFINE FILENAME account="/home/tigergraph/data/account.csv";
  DEFINE FILENAME phone="/home/tigergraph/data/phone.csv";
  DEFINE FILENAME city="/home/tigergraph/data/city.csv";
  DEFINE FILENAME hasPhone="/home/tigergraph/data/hasPhone.csv";
  DEFINE FILENAME locatedIn="/home/tigergraph/data/locate.csv";
  DEFINE FILENAME transferdata="/home/tigergraph/data/transfer.csv";
  LOAD account TO VERTEX Account VALUES ($"name", gsql_to_bool(gsql_trim($"isBlocked"))) USING header="true", separator=",";
  LOAD phone TO VERTEX Phone VALUES ($"number", gsql_to_bool(gsql_trim($"isBlocked"))) USING header="true", separator=",";
  LOAD city TO VERTEX City VALUES ($"name") USING header="true", separator=",";
  LOAD hasPhone TO Edge hasPhone VALUES ($"accnt", gsql_trim($"phone")) USING header="true", separator=",";
  LOAD locatedIn TO Edge isLocatedIn VALUES ($"accnt", gsql_trim($"city")) USING header="true", separator=",";
  LOAD transferdata TO Edge transfer VALUES ($"src", $"tgt", $"date", $"amount") USING header="true", separator=",";
}
run loading job load_local_file
```

## 1-block ad-hoc queries (Cypher ≥ 4.2.0)

```cypher
USE GRAPH financialGraph

-- Filters
MATCH (s:Account) RETURN s LIMIT 2
MATCH (s:Account {name: "Scott"}) RETURN s
MATCH (s:Account) WHERE s.name IN ["Scott","Steven"] RETURN s
MATCH (s:Account)-[e:transfer]->(t:Account) WHERE s <> t RETURN s, e, t

-- Aggregations
MATCH (s) RETURN COUNT(s)
MATCH (s:Account:City) RETURN COUNT(*)
MATCH (s:Account {name: "Scott"})-[e]->(t) RETURN COUNT(DISTINCT t) AS cnt
MATCH (s:Account)-[e:transfer|isLocatedIn]->(t)
  RETURN COUNT(e), STDEV(e.amount), AVG(e.amount)
MATCH (a:Account)-[e:transfer]->(b:Account)-[e2:transfer]->(c:Account)
  RETURN a, sum(e.amount) AS amount1, sum(e2.amount) AS amount2

-- Sort / skip / limit
MATCH (s:Account) RETURN s.name ORDER BY s.name SKIP 1 LIMIT 3

-- Expressions
MATCH (s:Account {name:"Scott"})-[e:transfer]->(t)
  WITH s, e.amount*0.01 AS amt RETURN s, amt
MATCH (s:Account {name:"Scott"})-[e:transfer]->(t)
  RETURN s.name + "->" + toString(e.amount) + "->" + t.name AS path

-- CRUD (ad-hoc)
CREATE (p:Account {name: "Abby", isBlocked: false})
MATCH (s:Account {name: "Abby"}) SET s.isBlocked = true
MATCH (s:Account {name: "Abby"}) DELETE s
```

## Stored procedures (catalog queries)

### Node patterns

```cypher
// c1 — match all Account vertices
USE GRAPH financialGraph
CREATE OR REPLACE OPENCYPHER QUERY c1() {
  MATCH (a:Account) RETURN a
}
install query c1
run query c1()

// c2 — with filter
CREATE OR REPLACE OPENCYPHER QUERY c2() {
  MATCH (a:Account) WHERE a.name = "Scott" RETURN a
}
install query c2
run query c2()
```

### Edge patterns

```cypher
// c3 — 1-hop with parameter
CREATE OR REPLACE OPENCYPHER QUERY c3(STRING accntName) {
  MATCH (a:Account {name:$accntName})-[e:transfer]->(b:Account)
  RETURN b, sum(e.amount) AS totalTransfer
}
install query c3
run query c3("Scott")

// c4 — group by src, total transfer per dst
CREATE OR REPLACE OPENCYPHER QUERY c4() {
  MATCH (a:Account)-[e:transfer]->(b:Account)
  RETURN a, b, sum(e.amount) AS transfer_total
}
install query c4
run query c4()
```

### Path patterns

```cypher
// c5 — fixed 2-hop with date + amount filter
CREATE OR REPLACE OPENCYPHER QUERY c5(DATETIME low, DATETIME high, STRING accntName) {
  MATCH (a:Account {name:$accntName})-[e:transfer]->()-[e2:transfer]->(b:Account)
  WHERE e.date >= $low AND e.date <= $high AND e.amount>500 AND e2.amount>500
  RETURN b.isBlocked, b.name
}
install query c5
run query c5("2024-01-01","2024-12-31","Scott")

// c6 — variable length (shortest path)
CREATE OR REPLACE OPENCYPHER QUERY c6(STRING accntName) {
  MATCH (a:Account {name:$accntName})-[:transfer*1..]->(b:Account)
  RETURN a, b
}
install query c6
run query c6("Scott")

// c8 — distinct-sum per hop
CREATE OR REPLACE OPENCYPHER QUERY c8(DATETIME low, DATETIME high) {
  MATCH (a:Account)-[e:transfer]->(b)-[e2:transfer]->(c:Account)
  WHERE e.date >= $low AND e.date <= $high
  RETURN a, b, c, sum(DISTINCT e.amount) AS hop_1_sum, sum(DISTINCT e2.amount) AS hop_2_sum
}
install query c8
run query c8("2024-01-01","2024-12-31")
```

### Optional match

```cypher
CREATE OR REPLACE OPENCYPHER QUERY c21(STRING accntName) {
  MATCH (srcAccount:Account {name:$accntName})
  OPTIONAL MATCH (srcAccount)-[e:transfer]->(tgtAccount:Account)
  WHERE srcAccount.isBlocked
  RETURN srcAccount, tgtAccount
}
install query c21
run query c21("Jenny")
```

### WITH — filter / aggregate / scope

```cypher
// c9 — filter intermediate
CREATE OR REPLACE OPENCYPHER QUERY c9() {
  MATCH (a:Account) WHERE a.name STARTS WITH "J" WITH a RETURN a.name
}
// c10 — aggregate
CREATE OR REPLACE OPENCYPHER QUERY c10() {
  MATCH (a:Account) WITH a.isBlocked AS Blocked, COUNT(a) AS blocked_count
  RETURN Blocked, blocked_count
}
// c11 — narrow scope
CREATE OR REPLACE OPENCYPHER QUERY c11() {
  MATCH (a:Account) WITH a.name AS name
  WHERE name STARTS WITH "J" RETURN name
}
```

### Sort + limit

```cypher
// c12 — ORDER BY in WITH, then SKIP/LIMIT
CREATE OR REPLACE OPENCYPHER QUERY c12() {
  MATCH (src)-[e:transfer]->(tgt1)
  MATCH (tgt1)-[e:transfer]->(tgt2)
  WITH src.name AS srcAccountName, COUNT(tgt2) AS tgt2Cnt
  ORDER BY tgt2Cnt DESC, srcAccountName DESC SKIP 1 LIMIT 3
  RETURN srcAccountName, tgt2Cnt
}
// c13 — ORDER BY after RETURN (same final shape, different op order)
CREATE OR REPLACE OPENCYPHER QUERY c13() {
  MATCH (src)-[e:transfer]->(tgt1)
  MATCH (tgt1)-[e:transfer]->(tgt2)
  WITH src.name AS srcAccountName, COUNT(tgt2) AS tgt2Cnt
  RETURN srcAccountName, tgt2Cnt
  ORDER BY tgt2Cnt DESC, srcAccountName DESC SKIP 1 LIMIT 3
}
```

### Lists — UNWIND, COLLECT

```cypher
// c14 — UNWIND inflate
CREATE OR REPLACE OPENCYPHER QUERY c14() {
  MATCH (src)-[e:transfer]->(tgt1)
  WHERE src.name IN ["Jenny","Paul"]
  UNWIND [1,2,3] AS x
  WITH src AS srcAccount, e.amount*x AS res
  RETURN srcAccount, res
}

// c15 — COLLECT list per source
CREATE OR REPLACE OPENCYPHER QUERY c15() {
  MATCH (src)-[e:transfer]->(tgt)
  WHERE src.name IN ["Jenny","Paul"]
  WITH src AS srcAccount, COLLECT(e.amount) AS amounts
  RETURN srcAccount, amounts
}

// c16 — UNWIND + double
CREATE OR REPLACE OPENCYPHER QUERY c16() {
  MATCH (src)-[e:transfer]->(tgt)
  WHERE src.name IN ["Jenny","Paul"]
  WITH src AS srcAccount, COLLECT(e.amount) AS amounts
  UNWIND amounts AS amount
  WITH srcAccount, amount*2 AS doubleAmount
  RETURN srcAccount, doubleAmount
}
```

### Combining matches — UNION / UNION ALL

```cypher
// c17 — UNION removes dupes
CREATE OR REPLACE OPENCYPHER QUERY c17() {
  MATCH (s:Account {name:"Paul"}) RETURN s AS srcAccount
  UNION
  MATCH (s:Account) WHERE s.isBlocked RETURN s AS srcAccount
}

// c18 — UNION ALL keeps dupes
CREATE OR REPLACE OPENCYPHER QUERY c18() {
  MATCH (s:Account {name:"Steven"}) RETURN s AS srcAccount
  UNION ALL
  MATCH (s:Account) WHERE s.isBlocked RETURN s AS srcAccount
}
```

### Conditional logic — CASE

```cypher
CREATE OR REPLACE OPENCYPHER QUERY c19() {
  MATCH (s:Account {name:"Steven"})-[e:transfer]->(t)
  WITH s.name AS srcAccount, t.name AS tgtAccount,
       CASE WHEN s.isBlocked = true THEN 0 ELSE 1 END AS tgt
  RETURN srcAccount, SUM(tgt) AS tgtCnt
}
```

### Aggregations

```cypher
CREATE OR REPLACE OPENCYPHER QUERY c20() {
  MATCH (src)-[e:transfer]->(tgt)
  WITH src.name AS srcAccount,
       COUNT(DISTINCT tgt) AS transferCount,
       SUM(e.amount) AS totalAmount,
       STDEV(e.amount) AS stdevAmmount
  RETURN srcAccount, transferCount, totalAmount, stdevAmmount
}
```

Available aggregates: `COUNT(*/DISTINCT col)`, `SUM`, `AVG`, `MIN`,
`MAX`, `COLLECT`, `STDEV`, `STDEVP`.

### CRUD via stored procs

```cypher
// insert node
CREATE OR REPLACE OPENCYPHER QUERY insertVertex(STRING name, BOOL isBlocked) {
  CREATE (p:Account {name:$name, isBlocked:$isBlocked})
}
interpret query insertVertex("Abby", true)

// insert edge
CREATE OR REPLACE OPENCYPHER QUERY insertEdge(VERTEX<Account> s, VERTEX<Account> t,
                                              DATETIME dt, UINT amt) {
  CREATE (s)-[:transfer {date:$dt, amount:$amt}]->(t)
}
interpret query insertEdge("Abby","Ed","2025-01-01",100)

// delete node
CREATE OR REPLACE OPENCYPHER QUERY deleteOneVertex(STRING name="Abby") {
  MATCH (s:Account {name:$name}) DELETE s
}
interpret query deleteOneVertex()

// delete all of a type
CREATE OR REPLACE OPENCYPHER QUERY deleteAllVertexWithType01() {
  MATCH (s:Account) DELETE s
}
interpret query deleteAllVertexWithType01()

// delete all (everything)
CREATE OR REPLACE OPENCYPHER QUERY deleteAllVertex() {
  MATCH (s:_) DELETE s
}
interpret query deleteAllVertex()

// delete edges with filter
CREATE OR REPLACE OPENCYPHER QUERY deleteEdge(STRING name="Abby", DATETIME filterDate="2024-02-01") {
  MATCH (s:Account {name:$name})-[e:transfer]->(t:Account)
  WHERE e.date < $filterDate
  DELETE e
}
interpret query deleteEdge()

// update vertex attr
CREATE OR REPLACE OPENCYPHER QUERY updateAccountAttr(STRING name="Abby") {
  MATCH (s:Account {name:$name}) SET s.isBlocked = false
}
interpret query updateAccountAttr()

// update edge attr (only when target not blocked)
CREATE OR REPLACE OPENCYPHER QUERY updateTransferAmt(STRING startAcct="Jenny", UINT newAmt=100) {
  MATCH (s:Account {name:$startAcct})-[e:transfer]->(t)
  WHERE NOT t.isBlocked
  SET e.amount = $newAmt
}
interpret query updateTransferAmt(_, 300)
```

## Stop / reset (when done)

```bash
gadmin stop all
gadmin status                 # confirm gsql down before reset
gsql 'drop all'               # clear DB
```

## Cross-refs

- Schema definition format matches the GSQL pattern used in
  `fraud-risk-engine/app/queries/medgraph/medgraph_schema.gsql` (also
  vertex + edge + GRAPH create). The Cypher wrappers here will be a useful
  reference when porting financialGraph → medgraph or ldbc_snb schemas
  into `app/queries/opencypher/`.
- The community / commercial contact info at the bottom of the upstream
  tutorial is preserved here as a future signal — TG Savanna is the
  managed-service alternative when this Docker-based setup is no longer
  the bottleneck.
