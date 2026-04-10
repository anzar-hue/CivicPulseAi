"""
environment.py — OpenEnv Civic Grievance Decision Environment
Production-ready structured decision environment for complaint handling.
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class IssueUnit(BaseModel):
    set: str  # sanitation | electricity | infrastructure
    subtype: str
    root_cause: str
    visible_symptom: str
    public_private: str  # public | private | disputed | unclear
    urgency: str  # low | medium | high
    confidence_band: str  # low | medium | high
    authority_type: str  # government | local_private_solution | government_appeal | guidance_only | insufficient_information
    authority_name: str
    reasoning: str
    clarification_needed: bool
    clarification_question: str


class Action(BaseModel):
    issue_units: List[IssueUnit]
    overall_priority_order: List[int]
    manual_review_recommended: bool
    insufficient_information: bool
    disclaimer_needed: bool


class ExtractedSignals(BaseModel):
    keywords: List[str]
    hazard_clues: List[str]
    ownership_clues: List[str]
    domain_clues: List[str]
    urgency_level: str
    scale_clues: List[str]
    legal_clues: List[str]


class Observation(BaseModel):
    raw_text: str
    processed_text: str
    possible_sets: List[str]
    extracted_signals: ExtractedSignals
    location: Optional[str] = None
    image_tags: Optional[List[str]] = None
    memory_hits: List[Dict[str, Any]] = Field(default_factory=list)


class RewardResult(BaseModel):
    score: float
    breakdown: Dict[str, float]
    feedback: str


# ---------------------------------------------------------------------------
# In-memory Precedent Store
# ---------------------------------------------------------------------------

PRECEDENT_STORE: List[Dict[str, Any]] = [
    {
        "keywords": ["nali", "drain", "sewage", "naali", "blockage"],
        "set": "sanitation",
        "subtype": "drainage_blockage",
        "precedent_subtype": "drainage_blockage",
        "authority_name": "Nagar Nigam",
        "urgency": "medium",
        "public_private": "public",
    },
    {
        "keywords": ["bijli", "electricity", "light", "power", "current"],
        "set": "electricity",
        "subtype": "power_outage",
        "precedent_subtype": "power_outage",
        "authority_name": "MPPB",
        "urgency": "medium",
        "public_private": "public",
    },
    {
        "keywords": ["transformer", "blast", "fire", "explosion"],
        "set": "electricity",
        "subtype": "transformer_fault",
        "precedent_subtype": "transformer_fault",
        "authority_name": "MPPB",
        "urgency": "high",
        "public_private": "public",
    },
    {
        "keywords": ["road", "sadak", "pothole", "potholes", "gadda", "gadde", "khada", "toot"],
        "set": "infrastructure",
        "subtype": "road_damage",
        "precedent_subtype": "road_damage",
        "authority_name": "PWD",
        "urgency": "medium",
        "public_private": "public",
    },
    {
        "keywords": ["garbage", "kachra", "waste", "dump", "dustbin"],
        "set": "sanitation",
        "subtype": "garbage_collection",
        "precedent_subtype": "garbage_collection",
        "authority_name": "Nagar Nigam",
        "urgency": "low",
        "public_private": "public",
    },
    {
        "keywords": ["water", "paani", "supply", "tap", "pani"],
        "set": "sanitation",
        "subtype": "water_supply",
        "precedent_subtype": "water_supply",
        "authority_name": "Jal Nigam",
        "urgency": "high",
        "public_private": "public",
    },
    {
        "keywords": ["encroachment", "illegal", "construction"],
        "set": "infrastructure",
        "subtype": "illegal_construction",
        "precedent_subtype": "illegal_construction",
        "authority_name": "Town Planning Department",
        "urgency": "medium",
        "public_private": "disputed",
    },
    {
        "keywords": ["meter", "bill", "overcharge", "bijli", "billing"],
        "set": "electricity",
        "subtype": "billing_dispute",
        "precedent_subtype": "billing_dispute",
        "authority_name": "MPPB — Billing Unit",
        "urgency": "low",
        "public_private": "private",
    },
    {
        "keywords": ["wiring", "wire", "internal", "short", "circuit"],
        "set": "electricity",
        "subtype": "internal_wiring",
        "precedent_subtype": "internal_wiring",
        "authority_name": "Qualified Electrician",
        "urgency": "high",
        "public_private": "private",
    },
    {
        "keywords": ["contamination", "gandha", "smell", "dirty", "dirtwater"],
        "set": "sanitation",
        "subtype": "water_contamination",
        "precedent_subtype": "water_contamination",
        "authority_name": "Pollution Control Board",
        "urgency": "high",
        "public_private": "public",
    },
    {
        "keywords": ["theft", "chor", "connection", "illegal", "meter"],
        "set": "electricity",
        "subtype": "electricity_theft",
        "precedent_subtype": "electricity_theft",
        "authority_name": "MPPB — Vigilance/Enforcement",
        "urgency": "medium",
        "public_private": "public",
    },
    {
        "keywords": ["voltage", "fluctuation", "unstable"],
        "set": "electricity",
        "subtype": "voltage_fluctuation",
        "precedent_subtype": "voltage_fluctuation",
        "authority_name": "MPPB",
        "urgency": "medium",
        "public_private": "public",
    },
]

# ---------------------------------------------------------------------------
# Domain Signal Maps
# ---------------------------------------------------------------------------

SANITATION_KEYWORDS = {
    "sewage", "drain", "nali", "naali", "gutter", "sewer", "overflow", "blockage",
    "garbage", "kachra", "waste", "dump", "dustbin", "sweeping", "cleaning",
    "water", "paani", "pani", "supply", "tap", "pipeline", "leakage", "leak",
    "contamination", "gandha", "smell", "stench", "dirty", "pollution", "malba",
    "drainage", "nalaa", "nala", "flood", "waterlogging", "overflowing",
}

ELECTRICITY_KEYWORDS = {
    "bijli", "electricity", "electric", "light", "power", "current", "voltage",
    "transformer", "meter", "wire", "wiring", "outage", "cut", "shutdown",
    "overcharge", "bill", "theft", "chor", "spark", "short", "circuit",
    "blackout", "fluctuation", "generator", "pole", "line", "cable",
}

INFRASTRUCTURE_KEYWORDS = {
    "road", "sadak", "pothole", "potholes", "gadda", "gadde", "khada", "toot", "broken", "crack",
     "construction", "illegal", "encroachment", "kabja",
    "bridge", "pul", "footpath", "pavement", "wall", "boundary",
    "demolish", "dilapidated", "structure", "repair", "patchwork",
    "drainage", "storm", "gutter", "culvert",
}

HAZARD_KEYWORDS = {
    "fire", "blast", "explosion", "accident", "death", "emergency", "danger",
    "hazard", "risk", "unsafe", "children", "sick", "hospital", "life",
    "toxic", "poisonous", "chemical", "gas", "fumes", "electrocution",
    "khatra", "injury", "hurt", "medical",
}

OWNERSHIP_PUBLIC = {
    "road", "sadak", "nali", "public", "sarkari", "government", "municipal",
    "colony", "ward", "mohalla", "street", "park", "school", "hospital",
}

OWNERSHIP_PRIVATE = {
    "ghar", "house", "home", "flat", "apartment", "shop", "office",
    "internal", "inside", "personal", "private", "apna", "mere",
}

LEGAL_KEYWORDS = {
    "illegal", "encroachment", "violation", "dispute", "case", "court",
    "complaint", "FIR", "police", "law", "regulation", "permit",
    "unauthorized", "license", "ownership", "title",
}

TYPO_MAP = {
    "bijlee": "bijli",
    "bejli": "bijli",
    "biijli": "bijli",
    "nalli": "nali",
    "naalli": "naali",
    "paanee": "paani",
    "sadakk": "sadak",
    "garbase": "garbage",
    "elecrticity": "electricity",
    "electrcity": "electricity",
    "tranformer": "transformer",
    "transfromer": "transformer",
    "drainge": "drainage",
    "drainege": "drainage",
    "encroachement": "encroachment",
    "encroachment": "encroachment",
    "ilegal": "illegal",
    "constuction": "construction",
}


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, fix known typos."""
    text = text.strip()
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    # Collapse multiple spaces/newlines
    text = re.sub(r"\s+", " ", text)
    # Fix common typos
    for wrong, right in TYPO_MAP.items():
        text = re.sub(r"\b" + re.escape(wrong) + r"\b", right, text)
    return text


def extract_location(text: str) -> Optional[str]:
    """Heuristic location extraction."""
    patterns = [
        r"(?:in|at|near|ward|sector|block|colony|mohalla|area)\s+([\w\s]+?)(?:\.|,|$)",
        r"(?:ward\s*no\.?\s*\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


# ---------------------------------------------------------------------------
# Signal Extraction
# ---------------------------------------------------------------------------

def extract_signals(processed_text: str) -> ExtractedSignals:
    words = set(re.findall(r"\b\w+\b", processed_text))

    domain_clues = []
    if words & SANITATION_KEYWORDS:
        domain_clues.append("sanitation")
    if words & ELECTRICITY_KEYWORDS:
        domain_clues.append("electricity")
    if words & INFRASTRUCTURE_KEYWORDS:
        domain_clues.append("infrastructure")

    hazard_clues = list(words & HAZARD_KEYWORDS)
    ownership_public = list(words & OWNERSHIP_PUBLIC)
    ownership_private = list(words & OWNERSHIP_PRIVATE)
    ownership_clues = (
        ["public"] * len(ownership_public) + ["private"] * len(ownership_private)
    )

    legal_clues = list(words & LEGAL_KEYWORDS)

    # Urgency level
    if hazard_clues or any(k in processed_text for k in ("fire", "blast", "death", "emergency", "khatra")):
        urgency_level = "high"
    elif any(k in processed_text for k in ("days", "weeks", "long time", "frequent", "regular")):
        urgency_level = "medium"
    else:
        urgency_level = "low"

    # Scale clues
    scale_clues = []
    if re.search(r"\b(many|multiple|all|entire|whole|sab|poori)\b", processed_text):
        scale_clues.append("large_scale")
    if re.search(r"\b(my|mere|apna|single|one)\b", processed_text):
        scale_clues.append("single_household")

    keywords = list(
        (words & SANITATION_KEYWORDS)
        | (words & ELECTRICITY_KEYWORDS)
        | (words & INFRASTRUCTURE_KEYWORDS)
    )

    return ExtractedSignals(
        keywords=keywords,
        hazard_clues=hazard_clues,
        ownership_clues=ownership_clues,
        domain_clues=domain_clues,
        urgency_level=urgency_level,
        scale_clues=scale_clues,
        legal_clues=legal_clues,
    )


# ---------------------------------------------------------------------------
# Precedent Matching
# ---------------------------------------------------------------------------

def match_precedents(keywords: List[str]) -> List[Dict[str, Any]]:
    hits = []
    kw_set = set(keywords)
    for record in PRECEDENT_STORE:
        overlap = kw_set & set(record["keywords"])
        if overlap:
            hits.append({
                "matched_keywords": list(overlap),
                "precedent_set": record["set"],
                "precedent_subtype": record.get("precedent_subtype", record.get("subtype", "")),
                "precedent_authority": record["authority_name"],
                "precedent_urgency": record["urgency"],
                "precedent_public_private": record["public_private"],
            })
    # Sort by overlap size descending so strongest match is first
    hits.sort(key=lambda h: len(h["matched_keywords"]), reverse=True)
    return hits[:3]


# ---------------------------------------------------------------------------
# Rule-Based Issue Detection
# ---------------------------------------------------------------------------

def detect_possible_sets(signals: ExtractedSignals, processed_text: str) -> List[str]:
    possible = list(signals.domain_clues)

    # Additional heuristics for ambiguous text
    if not possible:
        if re.search(r"\b(dark|andhera|light nahi|no light)\b", processed_text):
            possible.append("electricity")
        if re.search(r"\b(smell|stench|rot)\b", processed_text):
            possible.append("sanitation")

    return list(dict.fromkeys(possible))  # deduplicate preserving order


def infer_public_private(signals: ExtractedSignals) -> str:
    pub = signals.ownership_clues.count("public")
    priv = signals.ownership_clues.count("private")
    if pub > priv:
        return "public"
    if priv > pub:
        return "private"
    if signals.legal_clues:
        return "disputed"
    return "unclear"


def determine_authority(
    domain: str,
    public_private: str,
    subtype: str,
    legal_clues: List[str],
) -> Tuple[str, str]:
    """Returns (authority_type, authority_name)."""

    # Fix 5: Base guidance_only on actual legal_clues presence + ownership ambiguity,
    # not string matching on public_private value.
    has_legal = len(legal_clues) > 0
    ownership_ambiguous = public_private in ("disputed", "unclear")

    if has_legal and ownership_ambiguous:
        return "guidance_only", "Legal Aid / Consumer Forum"

    if domain == "sanitation":
        if public_private == "private":
            return "local_private_solution", "Licensed Plumber"
        if "contamination" in subtype or "pollution" in subtype:
            return "government", "Pollution Control Board"
        if "water" in subtype:
            return "government", "Jal Nigam"
        return "government", "Nagar Nigam"

    if domain == "electricity":
        if public_private == "private" or "internal" in subtype or "wiring" in subtype:
            return "local_private_solution", "Qualified Electrician"
        # Fix 4: Separate billing/meter from theft/enforcement
        if "billing" in subtype or "meter" in subtype:
            return "government", "MPPB — Billing Unit"
        if "theft" in subtype:
            return "government", "MPPB — Vigilance/Enforcement"
        return "government", "MPPB"

    if domain == "infrastructure":
        # Fix 5: Use legal_clues directly, not string matching
        if has_legal:
            return "guidance_only", "Town Planning Department / Legal Aid"
        if "encroachment" in subtype or "illegal" in subtype:
            return "government", "Town Planning Department"
        if "road" in subtype or "bridge" in subtype or "footpath" in subtype:
            return "government", "PWD"
        return "government", "Nagar Nigam"

    return "insufficient_information", "Unknown"


def apply_precedent_hints(
    domain: str,
    subtype: str,
    urgency: str,
    public_private: str,
    authority_name: str,
    memory_hits: List[Dict[str, Any]],
    confidence: str = "medium",
) -> Tuple[str, str, str, str]:
    """
    Use precedent memory to refine subtype, urgency, public_private, and authority_name.
    Fix 1: Uses precedent_subtype key (not precedent_set).
    Fix 2: Only applies precedent when overlap >= 2 OR confidence is low/medium.
           Does not override already-specific subtypes.
    Returns updated (subtype, urgency, public_private, authority_name).
    """
    # Subtypes that are considered generic — eligible for precedent override
    generic_subtypes = {
        "general_sanitation", "general_infrastructure", "general_electricity",
        "power_outage", "unknown",
    }
    urgency_rank = {"low": 0, "medium": 1, "high": 2}

    for hit in memory_hits:
        if hit.get("precedent_set") != domain:
            continue

        overlap_count = len(hit.get("matched_keywords", []))
        # Fix 2: Only apply if overlap >= 2 OR confidence is weak
        if overlap_count < 2 and confidence not in ("low", "medium"):
            continue

        # Fix 1 & 2: Only override subtype when current is generic
        precedent_subtype = hit.get("precedent_subtype", subtype)
        if subtype in generic_subtypes and precedent_subtype not in generic_subtypes:
            subtype = precedent_subtype

        # Escalate urgency if precedent signals higher urgency
        p_urgency = hit.get("precedent_urgency", urgency)
        if urgency_rank.get(p_urgency, 0) > urgency_rank.get(urgency, 0):
            urgency = p_urgency

        # Use precedent ownership only if current is unclear
        if public_private == "unclear":
            p_pp = hit.get("precedent_public_private", "unclear")
            if p_pp != "unclear":
                public_private = p_pp

        # Use precedent authority only if current is a generic fallback name
        p_auth = hit.get("precedent_authority", "")
        generic_authorities = {"Unknown", "Nagar Nigam", "MPPB", "PWD"}
        if p_auth and authority_name in generic_authorities:
            authority_name = p_auth

        break  # Apply only the strongest (first) qualifying precedent

    return subtype, urgency, public_private, authority_name


# Semantic duplicate groups: if more specific subtype is present, drop the generic alias
_SANITATION_SPECIFICITY_ORDER = [
    "water_contamination",   # more specific than water_supply
    "sewage_overflow",       # more specific than drainage_blockage
    "drainage_blockage",
    "water_supply",
    "garbage_collection",
    "general_sanitation",
]
_ELECTRICITY_SPECIFICITY_ORDER = [
    "transformer_fault",
    "internal_wiring",
    "electricity_theft",
    "billing_dispute",
    "voltage_fluctuation",
    "power_outage",
    "general_electricity",
]
_INFRASTRUCTURE_SPECIFICITY_ORDER = [
    "illegal_construction",
    "bridge_damage",
    "footpath_obstruction",
    "road_damage",
    "general_infrastructure",
]

# Pairs where the first makes the second redundant
_SANITATION_SUPERSEDES = {
    "water_contamination": {"water_supply"},   # contamination implies water is present
    "sewage_overflow": {"drainage_blockage"},  # sewage overflow is a type of blockage
}
_ELECTRICITY_SUPERSEDES: Dict[str, set] = {}
_INFRASTRUCTURE_SUPERSEDES: Dict[str, set] = {}


def _deduplicate_subtypes(candidates: List[str], domain: str) -> List[str]:
    """
    Fix 3: Remove semantically redundant subtypes.
    If a more specific subtype is present, drop its generic alias.
    """
    if len(candidates) <= 1:
        return candidates

    supersedes_map: Dict[str, set] = {}
    if domain == "sanitation":
        supersedes_map = _SANITATION_SUPERSEDES
    elif domain == "electricity":
        supersedes_map = _ELECTRICITY_SUPERSEDES
    elif domain == "infrastructure":
        supersedes_map = _INFRASTRUCTURE_SUPERSEDES

    to_remove: set = set()
    candidate_set = set(candidates)
    for specific, redundant_set in supersedes_map.items():
        if specific in candidate_set:
            to_remove |= redundant_set & candidate_set

    return [c for c in candidates if c not in to_remove]


# Fix 6: Detect multiple issue units within the same domain
def detect_issue_candidates(processed_text: str, domain: str) -> List[str]:
    """
    Returns a deduplicated list of subtypes detected within a single domain.
    Allows multiple issue units per domain (up to 2 per domain, 4 total).
    """
    candidates = []

    if domain == "sanitation":
        if any(k in processed_text for k in ("drain", "nali", "naali", "blockage", "overflow")):
            candidates.append("drainage_blockage")
        if any(k in processed_text for k in ("garbage", "kachra", "waste", "dump")):
            candidates.append("garbage_collection")
        if any(k in processed_text for k in ("water", "paani", "pani", "tap", "supply", "pipeline")):
            if any(k in processed_text for k in ("dirty", "contamination", "smell", "gandha", "toxic")):
                candidates.append("water_contamination")
            else:
                candidates.append("water_supply")
        if any(k in processed_text for k in ("sewage", "sewer")):
            candidates.append("sewage_overflow")
        if not candidates:
            candidates.append("general_sanitation")

    elif domain == "electricity":
        if any(k in processed_text for k in ("transformer", "blast", "fire", "explosion")):
            candidates.append("transformer_fault")
        if any(k in processed_text for k in ("wire", "wiring", "short", "circuit", "internal")):
            candidates.append("internal_wiring")
        if any(k in processed_text for k in ("meter", "bill", "overcharge")):
            candidates.append("billing_dispute")
        if any(k in processed_text for k in ("theft", "chor")):
            candidates.append("electricity_theft")
        if any(k in processed_text for k in ("voltage", "fluctuation")):
            candidates.append("voltage_fluctuation")
        if not candidates:
            candidates.append("power_outage")

    elif domain == "infrastructure":
        # Special building logic (avoid false positives)
        if "building" in processed_text and any(k in processed_text for k in [
         "collapse", "collapsing", "crack", "unsafe",
         "illegal", "construction", "encroachment"
        ]):
          candidates.append("building_issue")

        if any(k in processed_text for k in ("road", "sadak", "pothole", "potholes", "gadda", "gadde", "khada", "toota")):
            candidates.append("road_damage")
        if any(k in processed_text for k in ("encroachment", "kabja", "illegal", "unauthorized")):
            candidates.append("illegal_construction")
        if any(k in processed_text for k in ("bridge", "pul")):
            candidates.append("bridge_damage")
        if any(k in processed_text for k in ("footpath", "pavement")):
            candidates.append("footpath_obstruction")
        if not candidates:
            candidates.append("general_infrastructure")

    # Fix 3: Remove semantic duplicates before returning
    return _deduplicate_subtypes(candidates, domain)


def infer_subtype(domain: str, processed_text: str) -> str:
    """Return the primary (first) subtype for a domain. Kept for backward compatibility."""
    candidates = detect_issue_candidates(processed_text, domain)
    return candidates[0] if candidates else "unknown"


def needs_clarification(domain: str, signals: ExtractedSignals, processed_text: str):
    text = processed_text.lower()

    # Water
    if domain == "sanitation" and any(k in text for k in ("pani", "water", "jal")):
        if not any(k in text for k in ("area", "poore", "whole", "building", "colony", "ghar", "house")):
            return True, "Is the water issue only in your house or in the whole area?"

    # Electricity
    if domain == "electricity" and any(k in text for k in ("bijli", "electricity", "light", "power")):
        if not any(k in text for k in ("area", "poore", "whole", "building", "colony", "ghar", "house")):
            return True, "Is the electricity issue only in your house or in the whole area?"

    # Infrastructure (FIXED)
    if domain == "infrastructure":

    # Detect damage keywords (signal it's a problem)
     if any(k in text for k in ("toot", "damage", "broken", "crack", "pothole", "potholes", "gadda", "gadde", "khadda", "gadda")):

        # Check if scale is unclear
        if not any(k in text for k in ("area", "poore", "whole", "colony", "street", "near", "location")):
            return True, "Where exactly is the damage? Please specify the area or location."

    # Construction ambiguity
    if any(k in text for k in ("construction", "building", "structure")):
         if not any(k in text for k in ("illegal", "encroachment", "permission", "approved")):
             return True, "Is this construction authorized or illegal?"

    return False, ""

def is_invalid_input(raw_text: str, processed_text: str) -> bool:
    """
    Check if input is vague, abusive, or irrelevant.
    Fix 6: If no domain keyword AND no contextual pattern AND < 6 words → invalid.
    If >= 6 words but unclear → allow through (clarification will be triggered).
    """
    words = processed_text.split()

    # Too short to be a meaningful complaint regardless of content
    if len(words) < 3:
        return True

    # Check for domain keywords (token-level)
    token_set = set(words)
    domain_overlap = (
        (token_set & SANITATION_KEYWORDS)
        | (token_set & ELECTRICITY_KEYWORDS)
        | (token_set & INFRASTRUCTURE_KEYWORDS)
    )
    if domain_overlap:
        return False

    # Check for contextual action/complaint phrases (Hinglish, verbs, negations)
    contextual_patterns = [
        r"\b(nahi|nahin|nah[i]?)\b",
        r"\b(band|kharab|toot|broken|aa\s+rahi|aa\s+raha|mil\s+raha)\b",
        r"\b(problem|issue|complaint|fix|repair|request)\b",
        r"\b(se|hai|hain|ho|kar|hua|hui)\b",
        r"\b(no|not|without)\s+\w+",
        r"\b(since|days?|weeks?|months?|hours?)\b",
        r"\b(help|please|urgent|immediately|asap)\b",
    ]
    has_context = any(re.search(p, processed_text) for p in contextual_patterns)
    if has_context:
        return False

    # Fix 6: < 6 words with no signal → invalid; >= 6 words → allow, trigger clarification
    if len(words) < 6:
        return True

    return False


# ---------------------------------------------------------------------------
# Task Definitions
# ---------------------------------------------------------------------------

TASKS = {
    "easy": {
        "id": "easy_001",
        "description": "Simple single-domain complaint",
        "complaint": "The street drain near ward 5 is completely blocked and overflowing onto the road causing flooding.",
        "expected_set": "sanitation",
        "expected_subtype": "drainage_blockage",
        "expected_authority_type": "government",
        "expected_authority_name": "Nagar Nigam",
        "expected_urgency": "medium",
        "expected_public_private": "public",
    },
    "medium": {
        "id": "medium_001",
        "description": "Typo-heavy mixed issue complaint",
        "complaint": "The bijlee has been cut since 2 days and also the nalli in front is overflowing with dirty water making it very smelly.",
        "expected_sets": ["electricity", "sanitation"],
        "expected_authority_names": ["MPPB", "Nagar Nigam"],
        "expected_urgency": "medium",
    },
    "hard": {
        "id": "hard_001",
        "description": "Ambiguous legal case requiring guidance_only",
        "complaint": "My neighbour has done illegal construction and encroachment on the public pathway but the municipal office is not listening and I want to take legal action.",
        "expected_set": "infrastructure",
        "expected_subtype": "illegal_construction",
        "expected_authority_type": "guidance_only",
        "expected_public_private": "disputed",
    },
}


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
def generate_reason_text(domain: str, subtype: str, text: str) -> str:
    if domain == "sanitation" and subtype == "water_supply":
        return "Complaint indicates a disruption in public water supply."

    if domain == "electricity" and subtype == "power_outage":
        return "Complaint suggests a power outage affecting the area."

    if domain == "electricity" and subtype == "voltage_fluctuation":
        return "Complaint indicates unstable voltage supply."

    if domain == "infrastructure" and subtype == "road_damage":
        return "Complaint indicates damage to public road infrastructure."

    if domain == "infrastructure" and subtype == "illegal_construction":
        return "Complaint suggests unauthorized or illegal construction activity."

    if domain == "infrastructure" and subtype == "building_issue":
        return "Complaint suggests a potentially unsafe building condition."

    return "Complaint suggests a civic issue requiring attention."

class GrievanceEnvironment:
    """OpenEnv-compatible civic grievance routing environment."""

    def __init__(self):
        self._state: Optional[Dict[str, Any]] = None
        self._current_observation: Optional[Observation] = None
        self._current_task: Optional[str] = None
        self._step_count: int = 0

    def reset(self, complaint: str, task_id: Optional[str] = None) -> Observation:
        """Reset environment with a new complaint."""
        self._step_count = 0
        self._current_task = task_id

        processed = normalize_text(complaint)
        location = extract_location(processed)
        signals = extract_signals(processed)
        possible_sets = detect_possible_sets(signals, processed)
        memory_hits = match_precedents(signals.keywords)

        observation = Observation(
            raw_text=complaint,
            processed_text=processed,
            possible_sets=possible_sets,
            extracted_signals=signals,
            location=location,
            image_tags=None,
            memory_hits=memory_hits,
        )

        self._current_observation = observation
        self._state = {
            "phase": "awaiting_action",
            "step": 0,
            "observation": observation.model_dump(),
        }

        return observation

    def step(self, action: Action) -> Tuple[Observation, RewardResult, bool, Dict[str, Any]]:
        """Process an action and return (observation, reward, done, info)."""

        if self._current_observation is None or self._state is None:
            raise RuntimeError("Call reset() before step().")

        self._step_count += 1

        # Compute reward
        reward = self._compute_reward(action)

        # Update state
        self._state["phase"] = "completed"
        self._state["step"] = self._step_count
        self._state["last_action"] = action.model_dump()
        self._state["reward"] = reward.model_dump()

        done = True  # Single-step environment

        info = {
            "step_count": self._step_count,
            "task_id": self._current_task,
            "clarifications_pending": any(
                u.clarification_needed for u in action.issue_units
            ),
        }

        return self._current_observation, reward, done, info
    def state(self) -> Dict[str, Any]:
        """Return current environment state."""
        return self._state or {}

    def _compute_reward(self, action: Action) -> RewardResult:
        """Discrete reward computation."""
        if self._current_task is None:
         return RewardResult(
        score=0.1,
        breakdown={},
        feedback="No task loaded - cannot evaluate reward.",
    )

        if self._current_task not in TASKS:
         return RewardResult(
          score=0.1,
          breakdown={},
          feedback=f"Unknown task: {self._current_task}",
         )

         
        task = TASKS[self._current_task]
        breakdown: Dict[str, float] = {}

        if self._current_task == "easy":
            if not action.issue_units:
                return RewardResult(score=0.1, breakdown={}, feedback="No issue units produced.")
            unit = action.issue_units[0]
            set_correct = unit.set == task["expected_set"]
            auth_correct = unit.authority_type == task["expected_authority_type"]

            if set_correct and auth_correct:
                breakdown["set_match"] = 0.5
                breakdown["authority_match"] = 0.5
                score = 0.9
                feedback = "Correct domain and authority."
            elif set_correct:
                breakdown["set_match"] = 0.5
                breakdown["authority_mismatch"] = 0.1
                score = 0.6
                feedback = "Correct domain but wrong authority."
            elif action.insufficient_information:
                score = 0.3
                feedback = "Escalated to unknown — partial credit."
                breakdown["escalation"] = 0.3
            else:
                score = 0.1
                feedback = "Incorrect domain and authority."
                breakdown["incorrect"] = 0.1

        elif self._current_task == "medium":
            expected_sets = set(task.get("expected_sets", []))
            found_sets = {u.set for u in action.issue_units}
            overlap = found_sets & expected_sets
            if len(overlap) == len(expected_sets):
                score = 0.9
                feedback = "All domains correctly identified."
                breakdown["domain_coverage"] = 0.9
            elif overlap:
                score = 0.6
                feedback = f"Partially correct — identified {overlap}."
                breakdown["partial_domain"] = 0.6
            else:
                score = 0.1
                feedback = "No correct domains identified."
                breakdown["incorrect"] = 0.1

        elif self._current_task == "hard":
            if not action.issue_units:
                return RewardResult(score=0.1, breakdown={}, feedback="No issue units produced.")
            unit = action.issue_units[0]
            set_correct = unit.set == task["expected_set"]
            auth_correct = unit.authority_type == task["expected_authority_type"]

            if set_correct and auth_correct:
                score = 0.9
                breakdown["set_match"] = 0.6
                breakdown["guidance_only_correct"] = 0.6
                feedback = "Correctly identified legal case requiring guidance_only."
            elif set_correct:
                score = 0.6
                breakdown["set_match"] = 0.6
                feedback = "Correct domain but wrong authority type for legal case."
            elif action.insufficient_information or action.manual_review_recommended:
                score = 0.3
                breakdown["escalation"] = 0.3
                feedback = "Escalated — partial credit."
            else:
                score = 0.1
                breakdown["incorrect"] = 0.1
                feedback = "Incorrect handling of ambiguous legal case."

        else:
            score = 0.1
            feedback = "Unknown task."
            breakdown = {}

        score = max(0.1, min(0.99, score))
        return RewardResult(score=score, breakdown=breakdown, feedback=feedback)

    @staticmethod
    def build_rule_based_action(observation: Observation) -> Action:
        """
        Pure rule-based action builder (no LLM).
        Detects multiple issue units within the same domain.
        Uses precedent memory to influence subtype, urgency, and authority.
        """
        processed = observation.processed_text
        signals = observation.extracted_signals
        memory_hits = observation.memory_hits

        if is_invalid_input(observation.raw_text, processed):
            return Action(
                issue_units=[],
                overall_priority_order=[],
                manual_review_recommended=True,
                insufficient_information=True,
                disclaimer_needed=False,
            )

        possible_sets = observation.possible_sets
        if not possible_sets:
            return Action(
                issue_units=[],
                overall_priority_order=[],
                manual_review_recommended=True,
                insufficient_information=True,
                disclaimer_needed=False,
            )

        issue_units: List[IssueUnit] = []
        urgency_rank = {"high": 0, "medium": 1, "low": 2}
        has_precedent = bool(memory_hits)

        for domain in possible_sets:
            if len(issue_units) >= 4:
                break

            subtypes = detect_issue_candidates(processed, domain)

            for subtype in subtypes:
                if len(issue_units) >= 4:
                    break

                public_private = infer_public_private(signals)

                # Fix 4: Improved confidence using keyword count, hazard, and precedent
                kw_count = len(signals.keywords)
                if (kw_count > 3 and has_precedent) or signals.hazard_clues:
                    confidence = "high"
                elif kw_count > 1 or has_precedent:
                    confidence = "medium"
                else:
                    confidence = "low"

                urgency = signals.urgency_level
                # Safety-first urgency override
                if signals.hazard_clues:
                    urgency = "high"

                # Derive initial authority before precedent
                authority_type, authority_name = determine_authority(
                    domain, public_private, subtype, signals.legal_clues
                )

                # Apply precedent hints (Fix 1 & 2 already embedded in function)
                subtype, urgency, public_private, authority_name = apply_precedent_hints(
                    domain, subtype, urgency, public_private, authority_name,
                    memory_hits, confidence
                )

                # Re-derive authority_type after precedent may have changed public_private
                # Only re-derive type; use precedent authority_name if it was updated
                authority_type, derived_name = determine_authority(
                    domain, public_private, subtype, signals.legal_clues
                )
                # Keep the precedent-refined authority_name unless determine_authority
                # returned a more specific one (i.e., not a generic fallback)
                generic_fallbacks = {"Nagar Nigam", "MPPB", "PWD", "Unknown"}
                if derived_name not in generic_fallbacks:
                    authority_name = derived_name

                
                clarify, clarify_q = needs_clarification(domain, signals, processed)
                unit = IssueUnit(
                    set=domain,
                    subtype=subtype,
                    root_cause=generate_reason_text(domain, subtype, processed),
                    visible_symptom=f"User reported: {processed[:80]}",
                    public_private=public_private,
                    urgency=urgency,
                    confidence_band=confidence,
                    authority_type=authority_type,
                    authority_name=authority_name,
                    reasoning=(
                        f"Domain '{domain}', subtype '{subtype}' inferred from keywords. "
                        f"Ownership: {public_private}. "
                        f"Hazard signals: {signals.hazard_clues}. "
                        f"Legal signals: {signals.legal_clues}. "
                        f"Precedent applied: {has_precedent}."
                    ),
                    clarification_needed=clarify,
                    clarification_question=clarify_q,
                )
                issue_units.append(unit)

        # Fix 7: Priority sorting by urgency → hazard presence → public impact
        has_hazard = bool(signals.hazard_clues)

        def priority_key(i: int) -> Tuple[int, int, int]:
            unit = issue_units[i]
            u_score = urgency_rank.get(unit.urgency, 2)
            # Hazard bumps priority up (lower = higher priority)
            h_score = 0 if (has_hazard and unit.urgency == "high") else 1
            # Public issues take priority over private
            p_score = 0 if unit.public_private == "public" else 1
            return (u_score, h_score, p_score)

        sorted_indices = sorted(range(len(issue_units)), key=priority_key)

        return Action(
            issue_units=issue_units,
            overall_priority_order=sorted_indices,
            manual_review_recommended=any(u.confidence_band == "low" for u in issue_units),
            insufficient_information=False,
            disclaimer_needed=bool(signals.legal_clues),
        )