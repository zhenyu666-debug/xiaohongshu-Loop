"""LDBC SNB Interactive and BI workload queries.

This module provides TigerGraph GSQL implementations of the LDBC Social
Network Benchmark (SNB) Interactive (IC/IS) and Business Intelligence (BI)
workloads.

Schema assumptions (LDBC SNB Interactive schema):
    - Person(id, firstName, lastName, birthday, gender, browserUsed, creationDate)
    - knows(Person, Person) — friendship edges
    - Place(id, name, url, type)
    - Country(id, name) → Place
    - Continent(id, name) → Place
    - Message(id, creationDate, content) — abstract base (abstract)
    - Post(id) → Message
    - Comment(id) → Message
    - hasCreator(Message → Person)
    - hasTag(Message → Tag)
    - hasInterest(Person → Tag)
    - Container(Forum → Post)
    - replyOf(Comment → Message)

Interactive Short (IC1-14):
    IC1: Person profile
    IC2: Friends of a person
    IC5: Are two persons friends?
    IC6: Posts about a specific tag by friends
    IC7: Friends' posts
    IC8: Friends' comments
    IC9: Common friends
    IC10: Person's interested tags
    IC11: Count friends with specific interest
    IC12: Friends of friends (2-hop)
    IC13: Shortest path (BFS)
    IC14: Person's messages in date range

Interactive Update (IS1-7):
    IS1: Update person lastName
    IS2: Add friend
    IS3: Add like
    IS4: Add comment
    IS5: Add forum
    IS6: Add forum member
    IS7: Remove forum member

BI Queries (BI1-5):
    BI1: Messages by year/month
    BI2: Popular tags by user count
    BI3: Active users by post count
    BI4: Friendships created by month
    BI5: Tag co-occurrence
"""

from __future__ import annotations

import pathlib
import random
from dataclasses import dataclass


# Resolve ldbc_snb/ directory relative to this file
_LDBC_SNB_DIR = pathlib.Path(__file__).parent / "ldbc_snb"


def _load(name: str) -> str:
    """Load a GSQL query file and strip trailing whitespace."""
    p = _LDBC_SNB_DIR / name
    return p.read_text(encoding="utf-8", errors="replace").rstrip()


# ─────────────────────────────────────────────────────────────────────────────
# SNB Query descriptor
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SNBQuery:
    """Descriptor for a single LDBC SNB query."""

    id: str  # e.g. "IC1", "BI2"
    name: str
    description: str
    params: list[str]  # parameter names in GSQL signature order
    gsql: str  # GSQL query body (includes CREATE QUERY header)
    expected_runtime_ms: int  # median runtime on SF1 at 2023 benchmark
    workload: str  # "interactive" | "bi"


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Short queries (IC1-14)
# ─────────────────────────────────────────────────────────────────────────────

IC1 = SNBQuery(
    id="IC1",
    name="Person Profile",
    description="Given a Person, return their profile info including location hierarchy.",
    params=["personId"],
    gsql=_load("IC1.gsql"),
    expected_runtime_ms=3,
    workload="interactive",
)

IC2 = SNBQuery(
    id="IC2",
    name="Friends of Person",
    description="Given a Person, return their friends ordered by lastName, firstName.",
    params=["personId", "limit"],
    gsql=_load("IC2.gsql"),
    expected_runtime_ms=10,
    workload="interactive",
)

IC5 = SNBQuery(
    id="IC5",
    name="Are Friends",
    description="Given two Persons, check if they are direct friends (knows edge).",
    params=["person1Id", "person2Id"],
    gsql=_load("IC5.gsql"),
    expected_runtime_ms=5,
    workload="interactive",
)

IC6 = SNBQuery(
    id="IC6",
    name="Friend's Posts about Tag",
    description="Given a Person and a Tag, find Posts about the Tag created after a date.",
    params=["personId", "tagName", "maxDate"],
    gsql=_load("IC6.gsql"),
    expected_runtime_ms=50,
    workload="interactive",
)

IC7 = SNBQuery(
    id="IC7",
    name="Friend's Posts",
    description="Given a Person, find their friends' posts ordered by date.",
    params=["personId", "limit"],
    gsql=_load("IC7.gsql"),
    expected_runtime_ms=40,
    workload="interactive",
)

IC8 = SNBQuery(
    id="IC8",
    name="Friend's Comments",
    description="Given a Person, find their friends' comments on posts ordered by date.",
    params=["personId", "limit"],
    gsql=_load("IC8.gsql"),
    expected_runtime_ms=50,
    workload="interactive",
)

IC9 = SNBQuery(
    id="IC9",
    name="Common Friends",
    description="Given two Persons, return their common friends ordered by name.",
    params=["person1Id", "person2Id", "limit"],
    gsql=_load("IC9.gsql"),
    expected_runtime_ms=30,
    workload="interactive",
)

IC10 = SNBQuery(
    id="IC10",
    name="Person's Interests",
    description="Given a Person, return the Tags they are interested in.",
    params=["personId", "limit"],
    gsql=_load("IC10.gsql"),
    expected_runtime_ms=5,
    workload="interactive",
)

IC11 = SNBQuery(
    id="IC11",
    name="Friends with Tag Interest",
    description="Given a Person and Tag, count how many of their friends are also interested.",
    params=["personId", "tagName"],
    gsql=_load("IC11.gsql"),
    expected_runtime_ms=60,
    workload="interactive",
)

IC12 = SNBQuery(
    id="IC12",
    name="Friends of Friends",
    description="Given a Person, find their friends' friends (2-hop neighborhood, exclude self and direct friends).",
    params=["personId", "limit"],
    gsql=_load("IC12.gsql"),
    expected_runtime_ms=200,
    workload="interactive",
)

IC13 = SNBQuery(
    id="IC13",
    name="Shortest Path",
    description="Given two Persons, find the shortest path via KNOWS edges using BFS.",
    params=["person1Id", "person2Id"],
    gsql=_load("IC13.gsql"),
    expected_runtime_ms=500,
    workload="interactive",
)

IC14 = SNBQuery(
    id="IC14",
    name="Person's Messages",
    description="Given a Person and date range, return their Comments and Posts.",
    params=["personId", "startDate", "endDate", "limit"],
    gsql=_load("IC14.gsql"),
    expected_runtime_ms=20,
    workload="interactive",
)

INTERACTIVE_QUERIES: list[SNBQuery] = [
    IC1, IC2, IC5, IC6, IC7, IC8, IC9, IC10, IC11, IC12, IC13, IC14
]


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Update queries (IS1-7)
# ─────────────────────────────────────────────────────────────────────────────

IS1 = SNBQuery(
    id="IS1",
    name="Update Person LastName",
    description="Update a Person's lastName.",
    params=["personId", "newLastName"],
    gsql=_load("IS1.gsql"),
    expected_runtime_ms=5,
    workload="interactive",
)

IS2 = SNBQuery(
    id="IS2",
    name="Add Friend",
    description="Add a KNOWS edge between two Persons.",
    params=["person1Id", "person2Id"],
    gsql=_load("IS2.gsql"),
    expected_runtime_ms=10,
    workload="interactive",
)

IS3 = SNBQuery(
    id="IS3",
    name="Add Like",
    description="Add a LIKES edge from Person to Post or Comment.",
    params=["personId", "messageId"],
    gsql=_load("IS3.gsql"),
    expected_runtime_ms=8,
    workload="interactive",
)

IS4 = SNBQuery(
    id="IS4",
    name="Add Comment",
    description="Create a Comment on a Post or Comment.",
    params=["personId", "messageId", "content"],
    gsql=_load("IS4.gsql"),
    expected_runtime_ms=15,
    workload="interactive",
)

IS5 = SNBQuery(
    id="IS5",
    name="Add Forum",
    description="Create a new Forum.",
    params=["title", "creationDate"],
    gsql=_load("IS5.gsql"),
    expected_runtime_ms=10,
    workload="interactive",
)

IS6 = SNBQuery(
    id="IS6",
    name="Add Forum Member",
    description="Add a Person as a member of a Forum.",
    params=["forumId", "personId", "joinDate"],
    gsql=_load("IS6.gsql"),
    expected_runtime_ms=8,
    workload="interactive",
)

IS7 = SNBQuery(
    id="IS7",
    name="Remove Forum Member",
    description="Remove a Person from a Forum's membership.",
    params=["forumId", "personId"],
    gsql=_load("IS7.gsql"),
    expected_runtime_ms=8,
    workload="interactive",
)

UPDATE_QUERIES: list[SNBQuery] = [
    IS1, IS2, IS3, IS4, IS5, IS6, IS7
]


# ─────────────────────────────────────────────────────────────────────────────
# BI queries (BI1-5)
# ─────────────────────────────────────────────────────────────────────────────

BI1 = SNBQuery(
    id="BI1",
    name="Messages by Year/Month",
    description="Count the number of Messages (Posts + Comments) created in each year and month.",
    params=["startDate", "endDate"],
    gsql=_load("BI1.gsql"),
    expected_runtime_ms=2000,
    workload="bi",
)

BI2 = SNBQuery(
    id="BI2",
    name="Popular Tags by User Count",
    description="For each Tag, count the number of distinct Persons interested in it.",
    params=["startDate", "endDate"],
    gsql=_load("BI2.gsql"),
    expected_runtime_ms=3000,
    workload="bi",
)

BI3 = SNBQuery(
    id="BI3",
    name="Active Users by Post Count",
    description="Find the most-active Persons by number of Posts created in a date range.",
    params=["startDate", "endDate", "limit"],
    gsql=_load("BI3.gsql"),
    expected_runtime_ms=2500,
    workload="bi",
)

BI4 = SNBQuery(
    id="BI4",
    name="Friendships by Month",
    description="Count the number of KNOWS edges created in each year and month.",
    params=["startDate", "endDate"],
    gsql=_load("BI4.gsql"),
    expected_runtime_ms=2000,
    workload="bi",
)

BI5 = SNBQuery(
    id="BI5",
    name="Tag Co-occurrence",
    description="Find pairs of Tags that appear together on the same Message, ordered by frequency.",
    params=["startDate", "endDate", "minCooccurrence"],
    gsql=_load("BI5.gsql"),
    expected_runtime_ms=5000,
    workload="bi",
)

BI_QUERIES: list[SNBQuery] = [
    BI1, BI2, BI3, BI4, BI5
]


# ─────────────────────────────────────────────────────────────────────────────
# All queries registry
# ─────────────────────────────────────────────────────────────────────────────

_ALL_QUERIES: dict[str, SNBQuery] = {
    q.id: q
    for q in INTERACTIVE_QUERIES + UPDATE_QUERIES + BI_QUERIES
}


def get_query(query_id: str) -> SNBQuery:
    """Return the SNBQuery with the given id (e.g. "IC1", "BI3")."""
    if query_id not in _ALL_QUERIES:
        available = ", ".join(sorted(_ALL_QUERIES))
        raise ValueError(f"Unknown query id {query_id!r}. Available: {available}")
    return _ALL_QUERIES[query_id]


def list_queries(workload: str | None = None) -> list[SNBQuery]:
    """Return all SNB queries, optionally filtered by workload.

    Args:
        workload: One of "interactive", "bi", or None for all.
    """
    if workload is None:
        return list(_ALL_QUERIES.values())
    valid = {"interactive", "bi"}
    if workload not in valid:
        raise ValueError(f"workload must be one of {valid}, got {workload!r}")
    return [q for q in _ALL_QUERIES.values() if q.workload == workload]


# ─────────────────────────────────────────────────────────────────────────────
# Parameter generation (deterministic, seeded by SF factor and seed)
# ─────────────────────────────────────────────────────────────────────────────

def generate_ic_params(sf: float, seed: int) -> list[dict]:
    """Generate valid parameter sets for Interactive Short queries.

    The SF (scale factor) controls the approximate vertex ID ranges:
    - SF1   -> ~3k Persons
    - SF10  -> ~30k Persons
    - SF100 -> ~300k Persons

    This uses a seeded random generator so the same (sf, seed) always
    produces the same parameters, which is useful for reproducible benchmarks.

    Returns:
        A list of dicts, one per IC query, with keys matching the query's
        ``params`` field.
    """
    rng = random.Random(seed)
    sf_int = int(sf)

    # Approximate person id range based on scale factor
    # SF1: ~3072 persons, SF10: ~30726, SF100: ~307262
    max_person = 3072 * sf_int
    max_tag = 400 * sf_int
    max_forum = 500 * sf_int

    # Helper: pick a random person id
    def person_id() -> int:
        return rng.randint(0, max_person - 1)

    # Helper: pick a random tag name (deterministic set)
    _tag_names = [
        "Monarchy", "Baseball", "Tennis", "Basketball", "Soccer",
        "Ice_Hockey", "American_Football", "Rugby_League", "Rugby_Union",
        "Political_Event", "Government", "Agriculture", "Science",
        "Biology", "Chemistry", "Physics", "Computer_Science",
        "Programming", "Opera", "Theatre", "Literature", "Philosophy",
    ]
    def tag_name() -> str:
        return rng.choice(_tag_names)

    return [
        # IC1: personId
        {"personId": person_id()},
        # IC2: personId, limit
        {"personId": person_id(), "limit": 20},
        # IC5: person1Id, person2Id
        {"person1Id": person_id(), "person2Id": person_id()},
        # IC6: personId, tagName, maxDate
        {"personId": person_id(), "tagName": tag_name(), "maxDate": "2012-01-01"},
        # IC7: personId, limit
        {"personId": person_id(), "limit": 20},
        # IC8: personId, limit
        {"personId": person_id(), "limit": 20},
        # IC9: person1Id, person2Id, limit
        {"person1Id": person_id(), "person2Id": person_id(), "limit": 20},
        # IC10: personId, limit
        {"personId": person_id(), "limit": 10},
        # IC11: personId, tagName
        {"personId": person_id(), "tagName": tag_name()},
        # IC12: personId, limit
        {"personId": person_id(), "limit": 10},
        # IC13: person1Id, person2Id (pick distinct)
        {"person1Id": person_id(), "person2Id": person_id()},
        # IC14: personId, startDate, endDate, limit
        {
            "personId": person_id(),
            "startDate": "2012-01-01",
            "endDate": "2012-12-31",
            "limit": 100,
        },
    ]


def generate_bi_params(sf: float, seed: int) -> list[dict]:
    """Generate valid parameter sets for BI queries.

    BI queries run over date ranges and are typically single invocations
    with fixed start/end dates that span the benchmark data window.

    Returns:
        A list of dicts, one per BI query.
    """
    rng = random.Random(seed + 1000)  # different seed from IC

    return [
        # BI1: Messages by year/month
        {
            "startDate": "2010-01-01",
            "endDate": "2012-12-31",
        },
        # BI2: Popular tags by user count
        {
            "startDate": "2010-01-01",
            "endDate": "2012-12-31",
        },
        # BI3: Active users by post count
        {
            "startDate": "2012-01-01",
            "endDate": "2012-12-31",
            "limit": 100,
        },
        # BI4: Friendships by month
        {
            "startDate": "2010-01-01",
            "endDate": "2012-12-31",
        },
        # BI5: Tag co-occurrence
        {
            "startDate": "2012-01-01",
            "endDate": "2012-12-31",
            "minCooccurrence": 10,
        },
    ]


__all__ = [
    "SNBQuery",
    "INTERACTIVE_QUERIES",
    "UPDATE_QUERIES",
    "BI_QUERIES",
    "get_query",
    "list_queries",
    "generate_ic_params",
    "generate_bi_params",
]
