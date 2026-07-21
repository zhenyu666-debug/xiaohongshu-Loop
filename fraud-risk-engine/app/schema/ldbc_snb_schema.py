"""TigerGraph GSQL DDL for the LDBC SNB (Social Network Benchmark).

This schema models the interactive-short workload — the variant closest to a
real social-media graph.  Vertices are people, posts, comments, forums, tags,
and places; edges encode friendships (KNOWS), reactions (LIKES), authorship
(HAS_CREATOR), containment (CONTAINER_OF, REPLY_OF), membership (HAS_MEMBER),
and location / affiliation (IS_LOCATED_IN, IS_PART_OF, STUDY_AT, WORK_AT).

TigerGraph 3.x inheritance is used for the six sub-types::

    Country / City / Continent  — inherit from Place
    Company  / University        — inherit from Organisation

Reference: https://github.com/ldbc/ldbc_snb_datagen
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Vertex types
# ---------------------------------------------------------------------------

VERTEX_TYPES: dict[str, str] = {
    # ── Core social entities ────────────────────────────────────────────────

    "Person": """
        CREATE VERTEX Person (
            PRIMARY_ID id INT,
            firstName STRING,
            lastName STRING,
            gender STRING,
            birthday INT,
            creationDate STRING,
            locationIP STRING,
            browserUsed STRING,
            cityId INT
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Comment": """
        CREATE VERTEX Comment (
            PRIMARY_ID id INT,
            creationDate STRING,
            locationIP STRING,
            browserUsed STRING,
            content STRING,
            length INT
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Post": """
        CREATE VERTEX Post (
            PRIMARY_ID id INT,
            creationDate STRING,
            locationIP STRING,
            browserUsed STRING,
            content STRING,
            length INT,
            language STRING,
            imageFile STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Forum": """
        CREATE VERTEX Forum (
            PRIMARY_ID id INT,
            title STRING,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Tag": """
        CREATE VERTEX Tag (
            PRIMARY_ID id INT,
            name STRING,
            url STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "TagClass": """
        CREATE VERTEX TagClass (
            PRIMARY_ID id INT,
            name STRING,
            url STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Geography ────────────────────────────────────────────────────────────

    "Place": """
        CREATE VERTEX Place (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Country": """
        CREATE VERTEX Country (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH INHERITS = Place
    """,
    "City": """
        CREATE VERTEX City (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH INHERITS = Place
    """,
    "Continent": """
        CREATE VERTEX Continent (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH INHERITS = Place
    """,
    # ── Organisations ────────────────────────────────────────────────────────

    "Organisation": """
        CREATE VERTEX Organisation (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "Company": """
        CREATE VERTEX Company (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH INHERITS = Organisation
    """,
    "University": """
        CREATE VERTEX University (
            PRIMARY_ID id INT,
            name STRING,
            url STRING,
            type STRING
        ) WITH INHERITS = Organisation
    """,
}


# ---------------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------------

EDGE_TYPES: dict[str, str] = {
    # ── Social ──────────────────────────────────────────────────────────────

    "KNOWS": """
        CREATE UNDIRECTED EDGE KNOWS (
            FROM Person, TO Person,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "LIKES": """
        CREATE UNDIRECTED EDGE LIKES (
            FROM Person, TO Comment,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # TigerGraph does not allow a single edge type to span two vertex types
    # natively.  We emit one edge class per target so that the loader can use
    # whichever pattern the target DB prefers at load time.
    "LIKES_Post": """
        CREATE UNDIRECTED EDGE LIKES_Post (
            FROM Person, TO Post,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Authorship ──────────────────────────────────────────────────────────

    "HAS_CREATOR_Comment": """
        CREATE DIRECTED EDGE HAS_CREATOR_Comment (
            FROM Comment, TO Person
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "HAS_CREATOR_Post": """
        CREATE DIRECTED EDGE HAS_CREATOR_Post (
            FROM Post, TO Person
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Thread structure ────────────────────────────────────────────────────

    "REPLY_OF_Comment": """
        CREATE DIRECTED EDGE REPLY_OF_Comment (
            FROM Comment, TO Comment,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "REPLY_OF_Post": """
        CREATE DIRECTED EDGE REPLY_OF_Post (
            FROM Comment, TO Post,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Forum membership ────────────────────────────────────────────────────

    "CONTAINER_OF": """
        CREATE DIRECTED EDGE CONTAINER_OF (
            FROM Forum, TO Post,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "HAS_MEMBER": """
        CREATE DIRECTED EDGE HAS_MEMBER (
            FROM Forum, TO Person,
            joinDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Tagging ─────────────────────────────────────────────────────────────

    "HAS_TAG_Forum": """
        CREATE DIRECTED EDGE HAS_TAG_Forum (
            FROM Forum, TO Tag
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "HAS_TAG_Comment": """
        CREATE DIRECTED EDGE HAS_TAG_Comment (
            FROM Comment, TO Tag
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "HAS_TAG_Post": """
        CREATE DIRECTED EDGE HAS_TAG_Post (
            FROM Post, TO Tag
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "HAS_INTEREST": """
        CREATE DIRECTED EDGE HAS_INTEREST (
            FROM Person, TO Tag
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Location / hierarchy ───────────────────────────────────────────────

    "IS_LOCATED_IN_Person": """
        CREATE DIRECTED EDGE IS_LOCATED_IN_Person (
            FROM Person, TO Place
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "IS_LOCATED_IN_Comment": """
        CREATE DIRECTED EDGE IS_LOCATED_IN_Comment (
            FROM Comment, TO Place
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "IS_LOCATED_IN_Post": """
        CREATE DIRECTED EDGE IS_LOCATED_IN_Post (
            FROM Post, TO Place
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "IS_LOCATED_IN_Org": """
        CREATE DIRECTED EDGE IS_LOCATED_IN_Org (
            FROM Organisation, TO Place
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "IS_PART_OF": """
        CREATE DIRECTED EDGE IS_PART_OF (
            FROM Place, TO Place,
            creationDate STRING
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    # ── Affiliation ─────────────────────────────────────────────────────────

    "STUDY_AT": """
        CREATE DIRECTED EDGE STUDY_AT (
            FROM Person, TO University,
            classYear INT
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
    "WORK_AT": """
        CREATE DIRECTED EDGE WORK_AT (
            FROM Person, TO Company,
            workFrom INT
        ) WITH STATS = "OUTDEGREE_BY_EDGETYPE"
    """,
}


# ---------------------------------------------------------------------------
# Assembled GSQL block
# ---------------------------------------------------------------------------

def _strip(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


GSQL_SCHEMA: str = (
    "-- Auto-generated by fraud_risk_engine.schema.ldbc_snb_schema\n"
    "CREATE GRAPH LDBCSNB(*)\n\n"
    + "\n\n".join(_strip(ddl) for ddl in VERTEX_TYPES.values())
    + "\n\n"
    + "\n\n".join(_strip(ddl) for ddl in EDGE_TYPES.values())
    + "\n"
)


# ---------------------------------------------------------------------------
# Scale-factor → vertex-count estimates
# ---------------------------------------------------------------------------

def scale_factor(sf: float) -> dict[str, int]:
    """Return estimated vertex counts for a given LDBC SNB scale factor.

    The SNB data generator is not open-source so we use the empirically
    observed ratios from the official benchmark (sf*.csv files).

    Parameters
    ----------
    sf : float
        Scale factor — one of 0.1, 0.3, 1, 3, 10, 30, 100.

    Returns
    -------
    dict[str, int]
        Estimated counts per vertex type.
    """
    # Base counts at SF1 (per LDBC published stats)
    base: dict[str, float] = {
        "person": 3904,
        "post": 499_968,
        "comment": 2_498_528,
        "forum": 9_985,
        "tag": 16_088,
        "tagclass": 71,
        "place": 4_114,      # 111 countries + ~4 000 cities + 7 continents
        "organisation": 4_968,
        "country": 111,
        "city": 3_996,
        "continent": 7,
        "company": 1_490,
        "university": 3_478,
    }

    def _scale(key: str) -> int:
        return max(1, round(base[key] * sf))

    return {key: _scale(key) for key in base}


# ---------------------------------------------------------------------------
# Edge-count estimates (for sanity checking)
# ---------------------------------------------------------------------------

def edge_count_estimates(sf: float) -> dict[str, int]:
    """Approximate edge counts by type for a given scale factor."""
    persons = scale_factor(sf)["person"]

    # KNOWS: ~6.3 per person (Gaussian, mean≈19)
    # LIKES: ~1.6 comments per person + likes on posts
    # HAS_CREATOR: one per Post and Comment
    # REPLY_OF: ~0.75 replies per comment
    # CONTAINER_OF: ~12 posts per forum
    # HAS_MEMBER: ~22 members per forum
    # HAS_TAG: roughly 2 tags per post/comment/forum
    # HAS_INTEREST: ~1.8 tags per person
    # IS_LOCATED_IN: one per Person, Comment, Post, Organisation
    # IS_PART_OF: one per City (→Country) + one per Country (→Continent)
    # STUDY_AT / WORK_AT: ~27 % / ~51 % of persons

    posts = scale_factor(sf)["post"]
    comments = scale_factor(sf)["comment"]
    forums = scale_factor(sf)["forum"]
    tags = scale_factor(sf)["tag"]
    orgs = scale_factor(sf)["organisation"]
    cities = scale_factor(sf)["city"]
    countries = scale_factor(sf)["country"]

    return {
        "knows": round(persons * 6.3),
        "likes": round(persons * 1.6),
        "likes_post": round(persons * 1.0),
        "has_creator_comment": comments,
        "has_creator_post": posts,
        "reply_of_comment": round(comments * 0.75),
        "reply_of_post": round(comments * 0.25),
        "container_of": round(forums * 12),
        "has_member": round(forums * 22),
        "has_tag_forum": round(forums * 2),
        "has_tag_comment": round(comments * 1.5),
        "has_tag_post": round(posts * 1.5),
        "has_interest": round(persons * 1.8),
        "is_located_person": persons,
        "is_located_comment": comments,
        "is_located_post": posts,
        "is_located_org": orgs,
        "is_part_of_city": cities,
        "is_part_of_country": countries,
        "study_at": round(persons * 0.27),
        "work_at": round(persons * 0.51),
    }
