"""
inference.py — OpenEnv Inference Runner for Civic Grievance Decision System
Imports and uses environment.py. Do NOT run environment.py directly.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import json
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

from openai import OpenAI

from environment import (
    Action,
    GrievanceEnvironment,
    IssueUnit,
    Observation,
    TASKS,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL: str = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME: str = os.getenv("MODEL_NAME") or "openai/gpt-oss-20b"
HF_TOKEN: str = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or ""

client: Optional[OpenAI] = None
if HF_TOKEN:
 client = OpenAI(
    api_key=HF_TOKEN,
    base_url=API_BASE_URL,
 )

BENCHMARK_NAME = "CivicGrievanceEnv"

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a civic grievance routing system for Indian municipalities.

RESPOND WITH VALID JSON ONLY. No explanation, no markdown, no preamble. Just JSON.

ROUTING RULES:
1. Safety > Public health > Disruption > Inconvenience
2. Root cause reasoning takes priority over surface wording
3. Public infrastructure -> government authority
4. Private property -> local_private_solution
5. Legal/ownership disputes -> guidance_only
6. Vague, abusive, or irrelevant input -> set insufficient_information=true, issue_units=[]

DOMAIN AUTHORITIES:
- sanitation:
    drainage/nali/sewage        -> Nagar nigam
    water supply/paani          -> Jal nigam
    contamination/smell/dirty   -> pradurshan niyantran board
    private plumbing            -> Licensed Plumber 
- electricity:
    outage/transformer/voltage  -> MPEB/Bijli vibhag
    billing/meter/overcharge    -> Bijli vibhag — Billing Unit
    theft/chor/illegal conn.    -> Bijli vibhag — Vigilance/Enforcement
    internal wiring/short circ. -> Qualified Electrician 
- infrastructure:
    road/sadak/pothole/bridge   -> PWD 
    illegal construction        -> Town planning department
    legal dispute/encroachment  -> town planning department / Legal Aid 

URGENCY:
- high:   fire, blast, death, toxic, electrocution, no water for days, emergency
- medium: frequent outage, blocked drain, days without service, disruption
- low:    minor inconvenience, cosmetic issue, occasional problem

AUTHORITY_TYPE — use exactly one of:
  government | local_private_solution | government_appeal | guidance_only | insufficient_information

CLARIFICATION — trigger only when:
- ownership is genuinely unclear (both public and private signals)
- domain collision with very weak signals
- root cause cannot be determined
- NOT based on complaint length alone

OUTPUT SCHEMA — follow exactly, do not add extra keys:
{
  "issue_units": [
    {
      "set": "sanitation | electricity | infrastructure",
      "subtype": "string",
      "root_cause": "string",
      "visible_symptom": "string",
      "public_private": "public | private | disputed | unclear",
      "urgency": "low | medium | high",
      "confidence_band": "low | medium | high",
      "authority_type": "government | local_private_solution | government_appeal | guidance_only | insufficient_information",
      "authority_name": "string",
      "reasoning": "string",
      "clarification_needed": false,
      "clarification_question": ""
    }
  ],
  "overall_priority_order": [0],
  "manual_review_recommended": false,
  "insufficient_information": false,
  "disclaimer_needed": false
}

CONSTRAINTS:
- Maximum 4 issue_units
- clarification_question must be empty string "" when clarification_needed is false
- overall_priority_order is a 0-based index list into issue_units, sorted by priority
- Do not invent departments not listed above
- Do not hallucinate laws, case numbers, or FIR references
"""

# ---------------------------------------------------------------------------
# Fallback Action Dict
# ---------------------------------------------------------------------------

FALLBACK_ACTION_DICT: Dict[str, Any] = {
    "issue_units": [],
    "overall_priority_order": [],
    "manual_review_recommended": True,
    "insufficient_information": True,
    "disclaimer_needed": False,
}

# ---------------------------------------------------------------------------
# Safe JSON Parsing
# ---------------------------------------------------------------------------

def safe_parse_json(raw: str) -> Dict[str, Any]:
    """
    Attempt to parse raw LLM output as a JSON dict.
    Returns FALLBACK_ACTION_DICT on any failure.
    """
    if not raw:
        return FALLBACK_ACTION_DICT

    # Pass 1: direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Pass 2: strip markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Pass 3: extract first { ... } substring
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end + 1])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return FALLBACK_ACTION_DICT


# ---------------------------------------------------------------------------
# Build Action from Parsed Dict
# ---------------------------------------------------------------------------

def build_action_from_dict(data: Dict[str, Any]) -> Optional[Action]:
    """
    Construct an Action Pydantic model from a parsed dict.
    Returns None if construction fails.
    """
    raw_units = data.get("issue_units", [])
    if not isinstance(raw_units, list):
        return None

    issue_units: List[IssueUnit] = []
    for ru in raw_units[:4]:
        if not isinstance(ru, dict):
            continue
        try:
            unit = IssueUnit(
                set=str(ru.get("set", "sanitation")),
                subtype=str(ru.get("subtype", "unknown")),
                root_cause=str(ru.get("root_cause", "")),
                visible_symptom=str(ru.get("visible_symptom", "")),
                public_private=str(ru.get("public_private", "unclear")),
                urgency=str(ru.get("urgency", "low")),
                confidence_band=str(ru.get("confidence_band", "low")),
                authority_type=str(ru.get("authority_type", "insufficient_information")),
                authority_name=str(ru.get("authority_name", "Unknown")),
                reasoning=str(ru.get("reasoning", "")),
                clarification_needed=bool(ru.get("clarification_needed", False)),
                clarification_question=str(ru.get("clarification_question", "")),
            )
            issue_units.append(unit)
        except Exception:
            continue

    priority_order = data.get("overall_priority_order", list(range(len(issue_units))))
    if not isinstance(priority_order, list):
        priority_order = list(range(len(issue_units)))

    try:
        return Action(
            issue_units=issue_units,
            overall_priority_order=priority_order,
            manual_review_recommended=bool(data.get("manual_review_recommended", False)),
            insufficient_information=bool(data.get("insufficient_information", False)),
            disclaimer_needed=bool(data.get("disclaimer_needed", False)),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LLM Call
# ---------------------------------------------------------------------------

def call_llm(observation: Observation) -> str:
    """
    Send the observation to the LLM and return raw response string.
    Raises on API failure — caller handles fallback.
    """
    if client is None: raise RuntimeError("No HF_TOKEN/API_KEY configured")
    user_message = (
        f"COMPLAINT:\n{observation.raw_text}\n\n"
        f"PROCESSED TEXT:\n{observation.processed_text}\n\n"
        f"DETECTED DOMAINS: {observation.possible_sets}\n"
        f"KEYWORDS: {observation.extracted_signals.keywords}\n"
        f"HAZARD CLUES: {observation.extracted_signals.hazard_clues}\n"
        f"OWNERSHIP CLUES: {observation.extracted_signals.ownership_clues}\n"
        f"LEGAL CLUES: {observation.extracted_signals.legal_clues}\n"
        f"RULE-BASED URGENCY: {observation.extracted_signals.urgency_level}\n"
        f"LOCATION: {observation.location}\n\n"
        f"SIMILAR PAST CASES:\n"
        f"{json.dumps(observation.memory_hits, ensure_ascii=False, indent=2)}\n\n"
        "Produce a structured JSON decision following the schema exactly."
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.0,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    content = completion.choices[0].message.content
    raw = content.strip() if content else ""
    return raw


# ---------------------------------------------------------------------------
# Output Formatting
# ---------------------------------------------------------------------------

def fmt_bool(value: bool) -> str:
    return "true" if value else "false"


def fmt_action_summary(action: Action) -> str:
    return f"issues:{len(action.issue_units)}|priority:{action.overall_priority_order}"


def print_start(task_id: str) -> None:
    print(f"[START] task={task_id} env={BENCHMARK_NAME} model={MODEL_NAME}", flush=True)


def print_step(
    step: int,
    action: Action,
    reward: float,
    done: bool,
    error: Optional[str],
) -> None:
    action_str = fmt_action_summary(action)
    error_str = error if error else "null"
    print(
        f"[STEP] step={step} action={action_str} "
        f"reward={reward:.2f} done={fmt_bool(done)} error={error_str}",
        flush=True
    )


def print_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={fmt_bool(success)} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True 
    )


def print_routing_detail(action: Action, reward_score: float, feedback: str) -> None:
    """Human-readable routing decision block printed between STEP and END."""
    print()
    print("=" * 60)
    print("ROUTING DECISION")
    print("=" * 60)

    flags = []
    if action.insufficient_information:
        flags.append("INSUFFICIENT INFORMATION")
    if action.manual_review_recommended:
        flags.append("MANUAL REVIEW RECOMMENDED")
    if action.disclaimer_needed:
        flags.append("LEGAL DISCLAIMER APPLIES")
    if flags:
        for f in flags:
            print(f"  >> {f}")
        print()

    if not action.issue_units:
        print("  No issue units routed.")
    else:
        for i, unit in enumerate(action.issue_units):
            print(f"  Issue {i + 1}: [{unit.set.upper()}] {unit.subtype}")
            print(f"    Urgency    : {unit.urgency}")
            print(f"    Ownership  : {unit.public_private}")
            print(f"    Authority  : {unit.authority_name} ({unit.authority_type})")
            print(f"    Confidence : {unit.confidence_band}")
            print(f"    Root cause : {unit.root_cause}")
            if unit.clarification_needed:
                print(f"    Clarify?   : {unit.clarification_question}")
            print()

        if action.overall_priority_order:
            print(f"  Priority order : {action.overall_priority_order}")

    print()
    print(f"  Reward : {reward_score:.2f}  |  {feedback}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------

def run_single_task(task_id: str, complaint: str) -> None:
    rewards: List[float] = []
    step_count = 0
    score = 0.1
    success = False
    action: Optional[Action] = None
    error_msg: Optional[str] = None

    try:
        env = GrievanceEnvironment()
        observation = env.reset(complaint, task_id=task_id)

        print_start(task_id)

        raw_llm = ""
        try:
            raw_llm = call_llm(observation)
        except Exception as exc:
            error_msg = f"LLM error: {type(exc).__name__}"

        if raw_llm:
            parsed = safe_parse_json(raw_llm)
            action = build_action_from_dict(parsed)
            if action is None and error_msg is None:
                error_msg = "LLM parse failed — used rule-based fallback"

        if action is None:
            action = GrievanceEnvironment.build_rule_based_action(observation)

        # No interactive clarification in automated evaluation

        _, reward_result, done, info = env.step(action)
        step_count = info.get("step_count", 1)

        raw_score = float(reward_result.score)
        score = max(0.1, min(0.9, raw_score))
        rewards.append(score)

        print_step(step_count, action, score, done, error_msg)
        print_routing_detail(action, score, reward_result.feedback)

        success = True

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"

        fallback_action = Action(
            issue_units=[],
            overall_priority_order=[],
            manual_review_recommended=True,
            insufficient_information=True,
            disclaimer_needed=False,
        )

        step_count = 1
        score = 0.1
        rewards = [score]

        print_step(step_count, fallback_action, score, True, error_msg)

    finally:
        print_end(success, step_count or 1, score, rewards)


def main() -> None:
    task_order = ["easy", "medium", "hard"]

    for task_id in task_order:
        complaint = TASKS[task_id]["complaint"]
        run_single_task(task_id, complaint)


if __name__ == "__main__":
    main()