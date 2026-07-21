"""Deterministic data generator for the LDBC SNB (Social Network Benchmark).

We synthesise a graph that follows the LDBC SNB *interactive-short* workload
shape — a social network of people who join forums, author posts and comments,
form friendships (KNOWS), and react to each other's content (LIKES).  The
generator is fully deterministic: the same ``seed`` always produces the same
dataset, which makes it suitable for regression tests and reproducible demos.

Only stdlib is used (``faker`` is intentionally excluded) so the module works
in air-gapped CI environments.

Reference: https://github.com/ldbc/ldbc_snb_datagen
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Wordlists / reference tables
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Alice", "Brian", "Cathy", "David", "Eva", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Peter",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zoe", "Aaron", "Bea", "Carlos", "Diana", "Evan", "Fay",
    "George", "Hannah", "Ivan", "Julia", "Karl", "Laura", "Marco", "Nora",
    "Oscar", "Paula", "Quinn", "Rita", "Steve", "Tara", "Ulrich", "Vera",
]
_LAST_NAMES = [
    "Aaronson", "Brown", "Chen", "Davis", "Evans", "Foster", "Garcia",
    "Hernandez", "Ito", "Johnson", "Kim", "Lopez", "Martinez", "Nguyen",
    "Obrien", "Patel", "Quintero", "Robinson", "Singh", "Tanaka",
    "Underwood", "Vargas", "Wright", "Xu", "Young", "Zhang", "Adams",
    "Baker", "Carter", "Dixon", "Edwards", "Fisher", "Green", "Harris",
    "Jackson", "Kelly", "Lewis", "Miller", "Nelson", "Ortiz", "Powell",
]
_GENDERS = ["male", "female"]
_BROWSERS = [
    "Chrome", "Firefox", "Safari", "Edge", "Opera", "Chrome Mobile",
    "Safari Mobile", "Firefox Mobile",
]
_LANGUAGES = [
    "en", "zh", "es", "ar", "pt", "fr", "de", "ja", "ko", "ru", "hi", "ms",
]
_TAG_NAMES = [
    "AI", "MachineLearning", "Blockchain", "CloudComputing", "DevOps",
    "Cybersecurity", "BigData", "IoT", "5G", "QuantumComputing",
    "AR", "VR", "OpenSource", "Web3", "SaaS", "EdgeComputing",
    "Microservices", "Serverless", "DataScience", "NLP",
    "ComputerVision", "Robotics", "SmartCity", "FinTech", "HealthTech",
    "EdTech", "Gaming", "Streaming", "Podcast", "SocialMedia",
    "Photography", "Travel", "Food", "Fitness", "Fashion", "Music",
    "Movies", "Books", "Science", "Space", "Environment", "Politics",
    "Economy", "Sports", "Art", "Design", "Marketing", "Education",
]
_TAGCLASS_NAMES = [
    "Technology", "Science", "Business", "Entertainment", "Lifestyle",
    "Health", "Sports", "Politics", "Art", "Education",
]
_PLACE_NAMES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
    "Austin", "Toronto", "Vancouver", "Montreal", "Calgary",
    "London", "Paris", "Berlin", "Madrid", "Rome", "Amsterdam",
    "Vienna", "Prague", "Warsaw", "Stockholm", "Oslo",
    "Tokyo", "Seoul", "Shanghai", "Beijing", "Singapore", "Hong Kong",
    "Mumbai", "Dubai", "Istanbul", "Moscow", "Cairo",
    "Sydney", "Melbourne", "Auckland", "Johannesburg",
]
_CONTINENTS = [
    ("Asia", 1),
    ("Europe", 2),
    ("North America", 3),
    ("South America", 4),
    ("Africa", 5),
    ("Oceania", 6),
    ("Antarctica", 7),
]
_COMPANY_PREFIXES = [
    "Acme", "Globex", "Initech", "Soylent", "Umbrella", "Hooli",
    "Wonka", "Stark", "Wayne", "PiedPiper", "Cyberdyne", "MassiveDynamic",
    "Tyrell", "Aperture", "BlackMesa", "Vandelay", "Sirius", "Tycho",
]
_UNIVERSITY_PREFIXES = [
    "MIT", "Stanford", "Harvard", "Oxford", "Cambridge", "ETH Zurich",
    "Tokyo", "Tsinghua", "NUS", "IIT", "INSEAD", "HEC Paris",
    "Heidelberg", "LMU", "Sorbonne", "UCL", "Imperial",
]
_POST_TITLES = [
    "My thoughts on {}", "Deep dive: {}", "Why {} matters",
    "Exploring {}", "A guide to {}", "{} for beginners",
    "The future of {}", "{} explained", "Understanding {}",
]
_COMMENT_OPENERS = [
    "Great post!", "Interesting perspective.", "I agree with this.",
    "Have you considered {}?", "This is {}!",
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _rstring(rng: random.Random, chars: str, n: int) -> str:
    return "".join(rng.choices(chars, k=n))


def _date(rng: random.Random, years_ago: int = 5) -> str:
    """Return an ISO-8601 datetime string."""
    now = datetime.now(timezone.utc)
    start = now.replace(year=now.year - years_ago)
    offset = rng.randint(0, int((now - start).total_seconds()))
    return (start + timedelta(seconds=offset)).isoformat(timespec="seconds")


def _birthday_int(rng: random.Random, min_age: int = 18, max_age: int = 75) -> int:
    """Return birth date as YYYYMMDD int (LDBC convention)."""
    now = datetime.now(timezone.utc)
    year = now.year - rng.randint(min_age, max_age)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return year * 10_000 + month * 100 + day


def _ip(rng: random.Random) -> str:
    return f"{rng.randint(1,223)}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class GeneratedLDBCSNB:
    """Container for a synthesised LDBC SNB graph."""

    # Vertices
    persons: list[dict] = field(default_factory=list)
    comments: list[dict] = field(default_factory=list)
    posts: list[dict] = field(default_factory=list)
    forums: list[dict] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)
    tagclasses: list[dict] = field(default_factory=list)
    places: list[dict] = field(default_factory=list)
    countries: list[dict] = field(default_factory=list)
    cities: list[dict] = field(default_factory=list)
    continents: list[dict] = field(default_factory=list)
    organisations: list[dict] = field(default_factory=list)
    companies: list[dict] = field(default_factory=list)
    universities: list[dict] = field(default_factory=list)

    # Edges
    knows: list[dict] = field(default_factory=list)
    likes: list[dict] = field(default_factory=list)
    likes_post: list[dict] = field(default_factory=list)
    has_creator_comment: list[dict] = field(default_factory=list)
    has_creator_post: list[dict] = field(default_factory=list)
    reply_of_comment: list[dict] = field(default_factory=list)
    reply_of_post: list[dict] = field(default_factory=list)
    container_of: list[dict] = field(default_factory=list)
    has_member: list[dict] = field(default_factory=list)
    has_tag_forum: list[dict] = field(default_factory=list)
    has_tag_comment: list[dict] = field(default_factory=list)
    has_tag_post: list[dict] = field(default_factory=list)
    has_interest: list[dict] = field(default_factory=list)
    is_located_person: list[dict] = field(default_factory=list)
    is_located_comment: list[dict] = field(default_factory=list)
    is_located_post: list[dict] = field(default_factory=list)
    is_located_org: list[dict] = field(default_factory=list)
    is_part_of: list[dict] = field(default_factory=list)
    study_at: list[dict] = field(default_factory=list)
    work_at: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "person": len(self.persons),
            "comment": len(self.comments),
            "post": len(self.posts),
            "forum": len(self.forums),
            "tag": len(self.tags),
            "tagclass": len(self.tagclasses),
            "place": len(self.places),
            "country": len(self.countries),
            "city": len(self.cities),
            "continent": len(self.continents),
            "organisation": len(self.organisations),
            "company": len(self.companies),
            "university": len(self.universities),
            "knows": len(self.knows),
            "likes": len(self.likes),
            "likes_post": len(self.likes_post),
            "has_creator_comment": len(self.has_creator_comment),
            "has_creator_post": len(self.has_creator_post),
            "reply_of_comment": len(self.reply_of_comment),
            "reply_of_post": len(self.reply_of_post),
            "container_of": len(self.container_of),
            "has_member": len(self.has_member),
            "has_tag_forum": len(self.has_tag_forum),
            "has_tag_comment": len(self.has_tag_comment),
            "has_tag_post": len(self.has_tag_post),
            "has_interest": len(self.has_interest),
            "is_located_person": len(self.is_located_person),
            "is_located_comment": len(self.is_located_comment),
            "is_located_post": len(self.is_located_post),
            "is_located_org": len(self.is_located_org),
            "is_part_of": len(self.is_part_of),
            "study_at": len(self.study_at),
            "work_at": len(self.work_at),
        }


# ---------------------------------------------------------------------------
# Dataset builder
# ---------------------------------------------------------------------------

def build_ldbc_snb_dataset(sf: float = 1.0, seed: int = 42) -> GeneratedLDBCSNB:
    """Build a deterministic LDBC SNB-style graph.

    Parameters
    ----------
    sf : float
        Scale factor.  Defaults to 1.0 (SF1).  Population scales linearly.
    seed : int
        RNG seed for reproducibility.
    """
    rng = random.Random(seed)
    ds = GeneratedLDBCSNB()

    # ── Derived counts ──────────────────────────────────────────────────────
    n_persons = max(1, round(3_904 * sf))
    n_posts = max(1, round(499_968 * sf))
    n_comments = max(1, round(2_498_528 * sf))
    n_forums = max(1, round(9_985 * sf))
    n_tags = max(1, round(16_088 * sf))      # SF1 base: 16 088
    n_tagclasses = 10
    n_countries = 30
    n_cities = max(1, round(3_996 * sf))
    n_companies = max(1, round(1_490 * sf))
    n_universities = max(1, round(3_478 * sf))

    # ── Places ─────────────────────────────────────────────────────────────
    # Continents
    for name, cid in _CONTINENTS:
        cid_int = 200_000 + cid
        ds.continents.append({"id": cid_int, "name": name, "url": f"http://dbpedia.org/resource/{name.replace(' ','_')}", "type": "Continent"})
        ds.places.append({"id": cid_int, "name": name, "url": f"http://dbpedia.org/resource/{name.replace(' ','_')}", "type": "Continent"})

    # Countries
    country_ids: list[int] = []
    for i, name in enumerate(_PLACE_NAMES[:n_countries], start=1):
        cid_int = 100_000 + i
        country_ids.append(cid_int)
        ds.countries.append({"id": cid_int, "name": name, "url": f"http://dbpedia.org/resource/{name.replace(' ','_')}", "type": "Country"})
        ds.places.append({"id": cid_int, "name": name, "url": f"http://dbpedia.org/resource/{name.replace(' ','_')}", "type": "Country"})
        # Country → Continent
        continent_id = 200_000 + ((i - 1) % 7) + 1
        ds.is_part_of.append({"from_id": cid_int, "to_id": continent_id, "creationDate": _date(rng)})

    # Cities
    city_ids: list[int] = []
    for i in range(n_cities):
        cid_int = 300_000 + i
        city_ids.append(cid_int)
        country_fk = country_ids[i % len(country_ids)]
        ds.cities.append({"id": cid_int, "name": f"City_{i:06d}", "url": f"http://dbpedia.org/resource/City_{i:06d}", "type": "City"})
        ds.places.append({"id": cid_int, "name": f"City_{i:06d}", "url": f"http://dbpedia.org/resource/City_{i:06d}", "type": "City"})
        ds.is_part_of.append({"from_id": cid_int, "to_id": country_fk, "creationDate": _date(rng)})

    # ── TagClasses ──────────────────────────────────────────────────────────
    tagclass_ids: list[int] = []
    for i, name in enumerate(_TAGCLASS_NAMES[:n_tagclasses]):
        tc_id = 400_000 + i
        tagclass_ids.append(tc_id)
        ds.tagclasses.append({"id": tc_id, "name": name, "url": f"http://dbpedia.org/resource/{name}"})

    # ── Tags ────────────────────────────────────────────────────────────────
    tag_ids: list[int] = []
    for i in range(n_tags):
        tid = 500_000 + i
        tag_ids.append(tid)
        name = _TAG_NAMES[i % len(_TAG_NAMES)]
        ds.tags.append({"id": tid, "name": name, "url": f"http://dbpedia.org/resource/{name}"})

    # ── Organisations ──────────────────────────────────────────────────────
    company_ids: list[int] = []
    for i in range(n_companies):
        oid = 600_000 + i
        company_ids.append(oid)
        name = f"{rng.choice(_COMPANY_PREFIXES)} Corp {i}"
        ds.companies.append({"id": oid, "name": name, "url": f"http://example.com/org/{oid}", "type": "Company"})
        ds.organisations.append({"id": oid, "name": name, "url": f"http://example.com/org/{oid}", "type": "Company"})
        # Company → Country
        country_fk = country_ids[i % len(country_ids)]
        ds.is_located_org.append({"from_id": oid, "to_id": country_fk})

    university_ids: list[int] = []
    for i in range(n_universities):
        oid = 700_000 + i
        university_ids.append(oid)
        name = f"{rng.choice(_UNIVERSITY_PREFIXES)} University {i}"
        ds.universities.append({"id": oid, "name": name, "url": f"http://example.com/org/{oid}", "type": "University"})
        ds.organisations.append({"id": oid, "name": name, "url": f"http://example.com/org/{oid}", "type": "University"})
        # University → Country
        country_fk = country_ids[i % len(country_ids)]
        ds.is_located_org.append({"from_id": oid, "to_id": country_fk})

    # ── Persons ─────────────────────────────────────────────────────────────
    person_ids: list[int] = []
    for i in range(n_persons):
        pid = 1_000_000 + i
        person_ids.append(pid)
        first_name = rng.choice(_FIRST_NAMES)
        last_name = rng.choice(_LAST_NAMES)
        birthday = _birthday_int(rng)
        city_fk = city_ids[i % len(city_ids)]
        ds.persons.append({
            "id": pid,
            "firstName": first_name,
            "lastName": last_name,
            "gender": rng.choice(_GENDERS),
            "birthday": birthday,
            "creationDate": _date(rng),
            "locationIP": _ip(rng),
            "browserUsed": rng.choice(_BROWSERS),
            "cityId": city_fk,
        })
        ds.is_located_person.append({"from_id": pid, "to_id": city_fk})

        # STUDY_AT (~27 % of persons)
        if rng.random() < 0.27 and university_ids:
            uid = rng.choice(university_ids)
            ds.study_at.append({"from_id": pid, "to_id": uid, "classYear": rng.randint(1990, 2024)})

        # WORK_AT (~51 % of persons)
        if rng.random() < 0.51 and company_ids:
            cid = rng.choice(company_ids)
            ds.work_at.append({"from_id": pid, "to_id": cid, "workFrom": rng.randint(1995, 2024)})

        # HAS_INTEREST (tags)
        for _ in range(rng.randint(1, 3)):
            ds.has_interest.append({"from_id": pid, "to_id": rng.choice(tag_ids)})

    # ── Forums ──────────────────────────────────────────────────────────────
    for i in range(n_forums):
        fid = 2_000_000 + i
        owner = rng.choice(person_ids)
        ds.forums.append({
            "id": fid,
            "title": f"Forum #{i}: {rng.choice(_TAG_NAMES)}",
            "creationDate": _date(rng),
        })
        # Owner joins
        ds.has_member.append({
            "from_id": fid,
            "to_id": owner,
            "joinDate": _date(rng),
        })
        # Forum tags
        for _ in range(rng.randint(1, 3)):
            ds.has_tag_forum.append({"from_id": fid, "to_id": rng.choice(tag_ids)})

    # ── Posts ───────────────────────────────────────────────────────────────
    for i in range(n_posts):
        pid = 3_000_000 + i
        author = rng.choice(person_ids)
        forum = rng.choice([f["id"] for f in ds.forums]) if ds.forums else 0
        city_fk = city_ids[i % len(city_ids)]
        has_content = rng.random() < 0.8
        content = " ".join(rng.choices(_FIRST_NAMES, k=rng.randint(5, 30))) if has_content else None
        ds.posts.append({
            "id": pid,
            "creationDate": _date(rng),
            "locationIP": _ip(rng),
            "browserUsed": rng.choice(_BROWSERS),
            "content": content,
            "length": len(content) if content else None,
            "language": rng.choice(_LANGUAGES),
            "imageFile": f"img/{_rstring(rng, 'abcdef0123456789', 12)}.jpg" if rng.random() < 0.3 else None,
        })
        ds.has_creator_post.append({"from_id": pid, "to_id": author})
        ds.is_located_post.append({"from_id": pid, "to_id": city_fk})
        ds.container_of.append({"from_id": forum, "to_id": pid, "creationDate": _date(rng)})
        # Post tags
        for _ in range(rng.randint(1, 2)):
            ds.has_tag_post.append({"from_id": pid, "to_id": rng.choice(tag_ids)})
        # LIKES on post (~30 % of posts get likes)
        if rng.random() < 0.30 and person_ids:
            liker = rng.choice(person_ids)
            ds.likes_post.append({"from_id": liker, "to_id": pid, "creationDate": _date(rng)})

    # ── Comments ────────────────────────────────────────────────────────────
    post_ids_list = [p["id"] for p in ds.posts]
    for i in range(n_comments):
        cid = 4_000_000 + i
        author = rng.choice(person_ids)
        city_fk = city_ids[i % len(city_ids)]
        # ~75 % reply to a comment, ~25 % to a post
        if rng.random() < 0.75 and ds.comments:
            reply_to = rng.choice([c["id"] for c in ds.comments])
            ds.reply_of_comment.append({"from_id": cid, "to_id": reply_to, "creationDate": _date(rng)})
        elif post_ids_list:
            reply_to = rng.choice(post_ids_list)
            ds.reply_of_post.append({"from_id": cid, "to_id": reply_to, "creationDate": _date(rng)})

        has_content = rng.random() < 0.9
        content = rng.choice(_COMMENT_OPENERS).format(rng.choice(_TAG_NAMES)) if has_content else None
        ds.comments.append({
            "id": cid,
            "creationDate": _date(rng),
            "locationIP": _ip(rng),
            "browserUsed": rng.choice(_BROWSERS),
            "content": content,
            "length": len(content) if content else None,
        })
        ds.has_creator_comment.append({"from_id": cid, "to_id": author})
        ds.is_located_comment.append({"from_id": cid, "to_id": city_fk})
        # Comment tags
        if rng.random() < 0.4 and tag_ids:
            ds.has_tag_comment.append({"from_id": cid, "to_id": rng.choice(tag_ids)})
        # LIKES on comment (~40 % of comments get likes)
        if rng.random() < 0.40 and person_ids:
            liker = rng.choice(person_ids)
            ds.likes.append({"from_id": liker, "to_id": cid, "creationDate": _date(rng)})

    # ── KNOWS ───────────────────────────────────────────────────────────────
    # Each person has a small circle of friends
    for i, pid in enumerate(person_ids):
        n_friends = rng.randint(1, min(10, len(person_ids) - 1))
        seen: set[int] = set()
        for _ in range(n_friends):
            friend = rng.choice(person_ids)
            if friend == pid or friend in seen:
                continue
            seen.add(friend)
            ds.knows.append({
                "from_id": pid,
                "to_id": friend,
                "creationDate": _date(rng),
            })

    return ds


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def _write_csv(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def dataset_to_jsonl_bundles(ds: GeneratedLDBCSNB, root: Path) -> dict[str, int]:
    """Write one JSONL file per vertex / edge type under *root*."""
    root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    # Vertices
    for name, rows in [
        ("Person", ds.persons),
        ("Comment", ds.comments),
        ("Post", ds.posts),
        ("Forum", ds.forums),
        ("Tag", ds.tags),
        ("TagClass", ds.tagclasses),
        ("Place", ds.places),
        ("Country", ds.countries),
        ("City", ds.cities),
        ("Continent", ds.continents),
        ("Organisation", ds.organisations),
        ("Company", ds.companies),
        ("University", ds.universities),
    ]:
        counts[name.lower()] = _write_jsonl(root / f"vertex_{name}.jsonl", rows)

    # Edges
    for name, rows in [
        ("KNOWS", ds.knows),
        ("LIKES", ds.likes),
        ("LIKES_Post", ds.likes_post),
        ("HAS_CREATOR_Comment", ds.has_creator_comment),
        ("HAS_CREATOR_Post", ds.has_creator_post),
        ("REPLY_OF_Comment", ds.reply_of_comment),
        ("REPLY_OF_Post", ds.reply_of_post),
        ("CONTAINER_OF", ds.container_of),
        ("HAS_MEMBER", ds.has_member),
        ("HAS_TAG_Forum", ds.has_tag_forum),
        ("HAS_TAG_Comment", ds.has_tag_comment),
        ("HAS_TAG_Post", ds.has_tag_post),
        ("HAS_INTEREST", ds.has_interest),
        ("IS_LOCATED_IN_Person", ds.is_located_person),
        ("IS_LOCATED_IN_Comment", ds.is_located_comment),
        ("IS_LOCATED_IN_Post", ds.is_located_post),
        ("IS_LOCATED_IN_Org", ds.is_located_org),
        ("IS_PART_OF", ds.is_part_of),
        ("STUDY_AT", ds.study_at),
        ("WORK_AT", ds.work_at),
    ]:
        key = name.lower().replace("_", "_")
        counts[key] = _write_jsonl(root / f"edge_{name}.jsonl", rows)

    return counts


def dataset_to_csv_bundles(ds: GeneratedLDBCSNB, root: Path) -> dict[str, int]:
    """Write one CSV file per vertex / edge type under *root*."""
    root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for name, rows in [
        ("Person", ds.persons),
        ("Comment", ds.comments),
        ("Post", ds.posts),
        ("Forum", ds.forums),
        ("Tag", ds.tags),
        ("TagClass", ds.tagclasses),
        ("Place", ds.places),
        ("Country", ds.countries),
        ("City", ds.cities),
        ("Continent", ds.continents),
        ("Organisation", ds.organisations),
        ("Company", ds.companies),
        ("University", ds.universities),
        ("KNOWS", ds.knows),
        ("LIKES", ds.likes),
        ("LIKES_Post", ds.likes_post),
        ("HAS_CREATOR_Comment", ds.has_creator_comment),
        ("HAS_CREATOR_Post", ds.has_creator_post),
        ("REPLY_OF_Comment", ds.reply_of_comment),
        ("REPLY_OF_Post", ds.reply_of_post),
        ("CONTAINER_OF", ds.container_of),
        ("HAS_MEMBER", ds.has_member),
        ("HAS_TAG_Forum", ds.has_tag_forum),
        ("HAS_TAG_Comment", ds.has_tag_comment),
        ("HAS_TAG_Post", ds.has_tag_post),
        ("HAS_INTEREST", ds.has_interest),
        ("IS_LOCATED_IN_Person", ds.is_located_person),
        ("IS_LOCATED_IN_Comment", ds.is_located_comment),
        ("IS_LOCATED_IN_Post", ds.is_located_post),
        ("IS_LOCATED_IN_Org", ds.is_located_org),
        ("IS_PART_OF", ds.is_part_of),
        ("STUDY_AT", ds.study_at),
        ("WORK_AT", ds.work_at),
    ]:
        counts[name] = _write_csv(root / f"{name}.csv", rows)

    return counts


# ---------------------------------------------------------------------------
# Convenience entry-point
# ---------------------------------------------------------------------------

def load_ldbc_snb(sf: float = 0.1, seed: int = 42) -> GeneratedLDBCSNB:
    """Generate and persist an LDBC SNB dataset.

    Writes JSONL bundles to ``data/ldbc_snb/sf{sf}/``.
    """
    ds = build_ldbc_snb_dataset(sf=sf, seed=seed)
    root = Path(__file__).parent.parent.parent / "data" / "ldbc_snb" / f"sf{sf}"
    dataset_to_jsonl_bundles(ds, root)
    return ds
