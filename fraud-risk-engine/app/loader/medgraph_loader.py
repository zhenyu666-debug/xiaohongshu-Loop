"""MedGraph synthetic data generator — Synthea-style patient graph.

Reproduces the TigerGraph DevLabs / Synthea-Medgraph demo pattern:
patients, encounters, conditions, medications, providers, payers — all
linked in a graph that the frontend can visualise with D3.

Source: Synthea_Medgraph.ipynb
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# ── Static reference tables ─────────────────────────────────────────────────────

FIRST_NAMES = [
    "Jina", "Cole", "Lee", "Antony", "Johns", "Orn",
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin",
    "Amelia", "Lucas", "Harper", "Henry", "Evelyn",
]

LAST_NAMES = [
    "Johns", "Bayer", "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
    "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
]

GENDERS = ["M", "F"]
RACES = ["white", "black", "asian", "native", "other"]
ETHNICITIES = ["not_hispanic", "hispanic"]

CONDITIONS = [
    (" hypertension", "401.1", 0.12),
    (" diabetes mellitus", "250.0", 0.08),
    (" asthma", "493.0", 0.06),
    (" allergic rhinitis", "477.0", 0.10),
    (" acute bronchitis", "466.0", 0.07),
    (" back pain", "724.5", 0.09),
    (" anxiety", "300.0", 0.05),
    (" depression", "296.3", 0.06),
    (" osteoarthritis", "715.3", 0.04),
    (" urinary tract infection", "599.0", 0.05),
]

MEDICATIONS = [
    (" Metformin 500mg", "A10BA02", 15.0),
    (" Lisinopril 10mg", "C09AA03", 8.0),
    (" Albuterol inhaler", "R03AC02", 35.0),
    (" Amoxicillin 500mg", "J01CA04", 12.0),
    (" Ibuprofen 400mg", "M01AE01", 6.0),
    (" Atorvastatin 20mg", "C10AA01", 20.0),
    (" Omeprazole 20mg", "A02BC01", 18.0),
    (" Levothyroxine 50mcg", "H03AA01", 10.0),
    (" Gabapentin 300mg", "N02AX02", 25.0),
    (" Amlodipine 5mg", "C08CA01", 12.0),
]

PROVIDER_SPECIALITIES = [
    "Internal Medicine", "Family Practice", "Pediatrics",
    "Cardiology", "Pulmonology", "Endocrinology",
]

PAYER_NAMES = [
    "Medicare", "Medicaid", "BlueCross", "Aetna",
    "UnitedHealthcare", "Cigna", "Humana",
]

CITIES = [
    ("Boston", 42.3601, -71.0589, "MA"),
    ("New York", 40.7128, -74.0060, "NY"),
    ("Los Angeles", 34.0522, -118.2437, "CA"),
    ("Chicago", 41.8781, -87.6298, "IL"),
    ("Houston", 29.7604, -95.3698, "TX"),
    ("Phoenix", 33.4484, -112.0740, "AZ"),
    ("Philadelphia", 39.9526, -75.1652, "PA"),
    ("San Antonio", 29.4241, -98.4936, "TX"),
]


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class MedPatient:
    patient_id: str
    first_name: str
    last_name: str
    gender: str
    race: str
    ethnicity: str
    birthday: str
    lat: float
    lon: float
    city: str
    encounter_ids: list[str] = field(default_factory=list)
    condition_ids: list[str] = field(default_factory=list)
    medication_ids: list[str] = field(default_factory=list)


@dataclass
class MedEncounter:
    encounter_id: str
    patient_id: str
    provider_id: str
    payer_id: str
    class_type: str
    base_cost: float
    total_cost: float
    start_time: str
    condition_ids: list[str] = field(default_factory=list)
    medication_ids: list[str] = field(default_factory=list)


@dataclass
class MedCondition:
    condition_id: str
    code: str
    description: str
    start_date: str


@dataclass
class MedMedication:
    medication_id: str
    code: str
    description: str
    base_cost: float
    start_date: str


@dataclass
class MedProvider:
    provider_id: str
    name: str
    speciality: str


@dataclass
class MedPayer:
    payer_id: str
    name: str


@dataclass
class MedGraph:
    patients: list[MedPatient]
    encounters: list[MedEncounter]
    conditions: list[MedCondition]
    medications: list[MedMedication]
    providers: list[MedProvider]
    payers: list[MedPayer]


# ── Generator ─────────────────────────────────────────────────────────────────

def _iso_date(days_ago: int) -> str:
    d = datetime.utcnow() - timedelta(days=days_ago)
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def _birthday(age: int) -> str:
    d = datetime.utcnow() - timedelta(days=365 * age + random.randint(0, 364))
    return d.strftime("%Y-%m-%dT00:00:00")


_id_seq = 0

def _id(prefix: str) -> str:
    global _id_seq
    _id_seq += 1
    return f"{prefix}-{_id_seq:08X}"


def gen_medgraph(n_patients: int = 80, seed: int = 42) -> MedGraph:
    global _id_seq
    random.seed(seed)
    _id_seq = 0

    providers = [
        MedProvider(
            provider_id=_id("PROV"),
            name=f"Dr. {random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            speciality=random.choice(PROVIDER_SPECIALITIES),
        )
        for _ in range(10)
    ]
    payers = [
        MedPayer(payer_id=_id("PAYER"), name=name)
        for name in PAYER_NAMES
    ]

    patients: list[MedPatient] = []
    encounters: list[MedEncounter] = []
    all_conditions: list[MedCondition] = []
    all_medications: list[MedMedication] = []
    condition_map: dict[tuple[str, str], str] = {}  # (patient, condition_desc) -> id

    for _ in range(n_patients):
        pid = _id("PAT")
        city, lat, lon, _ = random.choice(CITIES)
        age = random.randint(18, 80)
        birthday_str = _birthday(age)

        # Generate conditions
        patient_cond_ids: list[str] = []
        for desc, code, prob in CONDITIONS:
            if random.random() < prob:
                cid = _id("COND")
                patient_cond_ids.append(cid)
                condition_map[(pid, desc)] = cid
                all_conditions.append(MedCondition(
                    condition_id=cid,
                    code=code,
                    description=desc.strip(),
                    start_date=_iso_date(random.randint(1, 730)),
                ))

        # Generate medications (based on conditions)
        patient_med_ids: list[str] = []
        for desc, code, cost in MEDICATIONS:
            if patient_cond_ids and random.random() < 0.6:
                mid = _id("MED")
                patient_med_ids.append(mid)
                all_medications.append(MedMedication(
                    medication_id=mid,
                    code=code,
                    description=desc.strip(),
                    base_cost=cost,
                    start_date=_iso_date(random.randint(1, 180)),
                ))

        # Generate 1-4 encounters per patient
        patient_enc_ids: list[str] = []
        for _ in range(random.randint(1, 4)):
            eid = _id("ENC")
            provider = random.choice(providers)
            payer = random.choice(payers)
            days_ago = random.randint(0, 365)
            base = random.uniform(50, 500)
            encounters.append(MedEncounter(
                encounter_id=eid,
                patient_id=pid,
                provider_id=provider.provider_id,
                payer_id=payer.payer_id,
                class_type=random.choice(["ambulatory", "emergency", "inpatient"]),
                base_cost=round(base, 2),
                total_cost=round(base * random.uniform(0.8, 1.2), 2),
                start_time=_iso_date(days_ago),
                condition_ids=list(patient_cond_ids),
                medication_ids=list(patient_med_ids),
            ))
            patient_enc_ids.append(eid)

        patients.append(MedPatient(
            patient_id=pid,
            first_name=random.choice(FIRST_NAMES),
            last_name=random.choice(LAST_NAMES),
            gender=random.choice(GENDERS),
            race=random.choice(RACES),
            ethnicity=random.choice(ETHNICITIES),
            birthday=birthday_str,
            lat=round(lat + random.uniform(-0.1, 0.1), 4),
            lon=round(lon + random.uniform(-0.1, 0.1), 4),
            city=city,
            encounter_ids=patient_enc_ids,
            condition_ids=patient_cond_ids,
            medication_ids=patient_med_ids,
        ))

    return MedGraph(
        patients=patients,
        encounters=encounters,
        conditions=all_conditions,
        medications=all_medications,
        providers=providers,
        payers=payers,
    )


# ── API response builder ────────────────────────────────────────────────────────

def build_medgraph_response(n_patients: int = 80, seed: int = 42) -> dict[str, Any]:
    """Return a D3-friendly graph + stats from synthetic MedGraph data."""
    g = gen_medgraph(n_patients=n_patients, seed=seed)

    # ── D3 nodes ───────────────────────────────────────────────────────────────
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    def add_node(nid: str, label: str, kind: str, **attrs: Any) -> None:
        if nid in node_ids:
            return
        node_ids.add(nid)
        nodes.append({"id": nid, "label": label, "kind": kind, **attrs})

    # Patient nodes
    for p in g.patients:
        add_node(p.patient_id, f"{p.first_name} {p.last_name}", "patient",
                 gender=p.gender, race=p.race, city=p.city, age=2026 - int(p.birthday[:4]))

    # Encounter nodes
    for e in g.encounters:
        add_node(e.encounter_id, e.class_type.title(), "encounter",
                 cost=e.total_cost, start=e.start_time)

    # Condition nodes
    for c in g.conditions:
        add_node(c.condition_id, c.description, "condition", code=c.code)

    # Medication nodes
    for m in g.medications:
        add_node(m.medication_id, m.description, "medication", code=m.code, cost=m.base_cost)

    # Provider nodes
    for p in g.providers:
        add_node(p.provider_id, p.name, "provider", speciality=p.speciality)

    # Payer nodes
    for p in g.payers:
        add_node(p.payer_id, p.name, "payer")

    # ── D3 edges ────────────────────────────────────────────────────────────────
    for e in g.encounters:
        edges.append({"source": e.patient_id, "target": e.encounter_id, "kind": "HAS_ENCOUNTER"})
        edges.append({"source": e.encounter_id, "target": e.provider_id, "kind": "ENCOUNTER_PROVIDER"})
        edges.append({"source": e.encounter_id, "target": e.payer_id, "kind": "ENCOUNTER_PAYER"})
        for cid in e.condition_ids:
            edges.append({"source": e.encounter_id, "target": cid, "kind": "ENCOUNTER_HAS_CONDITION"})
        for mid in e.medication_ids:
            edges.append({"source": e.encounter_id, "target": mid, "kind": "ENCOUNTER_HAS_MEDICATION"})

    # ── Stats ─────────────────────────────────────────────────────────────────
    patient_count = len(g.patients)
    encounter_count = len(g.encounters)
    condition_count = len(g.conditions)
    medication_count = len(g.medications)
    avg_cost = round(sum(e.total_cost for e in g.encounters) / max(encounter_count, 1), 2)

    # Condition distribution
    condition_dist: dict[str, int] = {}
    for c in g.conditions:
        condition_dist[c.description] = condition_dist.get(c.description, 0) + 1

    return {
        "ok": True,
        "source": "Synthea MedGraph (synthetic)",
        "seed": seed,
        "stats": {
            "patient_count": patient_count,
            "encounter_count": encounter_count,
            "condition_count": condition_count,
            "medication_count": medication_count,
            "provider_count": len(g.providers),
            "payer_count": len(g.payers),
            "avg_encounter_cost": avg_cost,
            "condition_distribution": condition_dist,
        },
        "patients": [
            {
                "id": p.patient_id,
                "name": f"{p.first_name} {p.last_name}",
                "gender": p.gender,
                "race": p.race,
                "city": p.city,
                "encounter_count": len(p.encounter_ids),
                "condition_count": len(p.condition_ids),
            }
            for p in g.patients
        ],
        "nodes": nodes,
        "edges": edges,
    }
