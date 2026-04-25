from __future__ import annotations

import json
import os
import traceback
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_cors import CORS  # optional
except Exception:  # pragma: no cover
    CORS = None

from openai import OpenAI
from pydantic import ValidationError

from environment import GrievanceEnvironment, Action, IssueUnit


# -----------------------------------------------------------------------------
# Flask app setup
# -----------------------------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=APP_DIR, static_url_path="")
if CORS is not None:
    CORS(app) 
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# -----------------------------------------------------------------------------
# LLM configuration
# -----------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "openai/gpt-oss-20b"
HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or ""

SYSTEM_PROMPT = """You are a civic grievance routing system for Indian municipalities.

Respond with VALID JSON ONLY. No markdown. No explanation outside JSON.

Your job:
- analyze the complaint
- identify one or more issue units
- classify each issue as sanitation, electricity, or infrastructure
- assign urgency
- assign authority
- ask a clarification question only when genuinely needed

Rules:
1. Safety > public health > disruption > inconvenience
2. Root cause is more important than surface wording
3. Public issues -> government authority
4. Private internal issues -> local_private_solution
5. Legal/ownership disputes -> guidance_only
6. If complaint is too vague -> insufficient_information=true

Authority map:
- sanitation:
  - drainage/sewage/garbage -> Nagar Nigam
  - water supply -> Jal Nigam
  - contamination -> Pollution Control Board
  - private plumbing -> Licensed Plumber
- electricity:
  - outage/transformer/voltage -> MPPB
  - billing/meter -> MPPB - Billing Unit
  - theft/illegal connection -> MPPB - Vigilance/Enforcement
  - internal wiring -> Qualified Electrician
- infrastructure:
  - roads/bridges/footpaths -> PWD
  - illegal construction/encroachment -> Town Planning Department
  - legal dispute -> Town Planning Department / Legal Aid

Allowed authority_type values:
government | local_private_solution | government_appeal | guidance_only | insufficient_information

Output schema:
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
"""


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def safe_parse_json(raw: str) -> Dict[str, Any]:
    """Parse model JSON safely. Return fallback dict on failure."""
    fallback = {
        "issue_units": [],
        "overall_priority_order": [],
        "manual_review_recommended": True,
        "insufficient_information": True,
        "disclaimer_needed": False,
    }

    if not raw:
        return fallback

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    text = raw.strip()

    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return fallback


def build_action_from_dict(data: Dict[str, Any]) -> Optional[Action]:
    """Convert dict into Action. Return None if invalid."""
    issue_units = []
    raw_units = data.get("issue_units", [])
    if isinstance(raw_units, list):
        for item in raw_units[:4]:
            if not isinstance(item, dict):
                continue
            try:
                issue_units.append(
                    IssueUnit(
                        set=str(item.get("set", "sanitation")),
                        subtype=str(item.get("subtype", "unknown")),
                        root_cause=str(item.get("root_cause", "")),
                        visible_symptom=str(item.get("visible_symptom", "")),
                        public_private=str(item.get("public_private", "unclear")),
                        urgency=str(item.get("urgency", "low")),
                        confidence_band=str(item.get("confidence_band", "low")),
                        authority_type=str(item.get("authority_type", "insufficient_information")),
                        authority_name=str(item.get("authority_name", "Unknown")),
                        reasoning=str(item.get("reasoning", "")),
                        clarification_needed=bool(item.get("clarification_needed", False)),
                        clarification_question=str(item.get("clarification_question", "")),
                    )
                )
            except ValidationError:
                continue

    priority = data.get("overall_priority_order", list(range(len(issue_units))))
    if not isinstance(priority, list):
        priority = list(range(len(issue_units)))

    try:
        return Action(
            issue_units=issue_units,
            overall_priority_order=priority,
            manual_review_recommended=bool(data.get("manual_review_recommended", False)),
            insufficient_information=bool(data.get("insufficient_information", False)),
            disclaimer_needed=bool(data.get("disclaimer_needed", False)),
        )
    except ValidationError:
        return None


def call_llm(observation, language) -> str:
    """Call LLM if token exists. Raise RuntimeError when unavailable."""
    if not HF_TOKEN:
        raise RuntimeError("No HF_TOKEN/API_KEY configured")

    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

    user_message = (
        f"LANGUAGE: {language}\n\n"
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
        "Return JSON only."
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.0,
        max_tokens=1800,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    content = completion.choices[0].message.content
    return content.strip() if content else ""


def format_issue_title(subtype: str, language: str = "en") -> str:
    titles = {
        "en": {
            "water_supply": "Water Supply Problem",
            "water_contamination": "Water Contamination",
            "drainage_blockage": "Drainage Blockage",
            "sewage_overflow": "Sewage Overflow",
            "garbage_collection": "Garbage Collection Issue",
            "power_outage": "Power Outage",
            "voltage_fluctuation": "Voltage Fluctuation",
            "transformer_fault": "Transformer Fault",
            "billing_dispute": "Electricity Billing Issue",
            "electricity_theft": "Electricity Theft / Illegal Connection",
            "internal_wiring": "Internal Wiring Issue",
            "road_damage": "Road Damage",
            "bridge_damage": "Bridge Damage",
            "footpath_obstruction": "Footpath Obstruction",
            "illegal_construction": "Illegal Construction",
            "building_issue": "Unsafe Building Issue",
            "general_sanitation": "Sanitation Issue",
            "general_infrastructure": "Infrastructure Issue",
            "general_electricity": "Electricity Issue",
        },
        "hi": {
            "water_supply": "पानी की सप्लाई की समस्या",
            "water_contamination": "दूषित पानी की समस्या",
            "drainage_blockage": "नाली/ड्रेनेज ब्लॉकेज",
            "sewage_overflow": "सीवेज ओवरफ्लो",
            "garbage_collection": "कचरा संग्रहण समस्या",
            "power_outage": "बिजली कटौती",
            "voltage_fluctuation": "वोल्टेज उतार-चढ़ाव",
            "transformer_fault": "ट्रांसफॉर्मर खराबी",
            "billing_dispute": "बिजली बिल समस्या",
            "electricity_theft": "बिजली चोरी / अवैध कनेक्शन",
            "internal_wiring": "घर की वायरिंग समस्या",
            "road_damage": "सड़क क्षति / गड्ढे",
            "bridge_damage": "पुल क्षति",
            "footpath_obstruction": "फुटपाथ बाधा",
            "illegal_construction": "अवैध निर्माण",
            "building_issue": "असुरक्षित भवन समस्या",
            "general_sanitation": "स्वच्छता समस्या",
            "general_infrastructure": "इन्फ्रास्ट्रक्चर समस्या",
            "general_electricity": "बिजली समस्या",
        },
        "kn": {
            "water_supply": "ನೀರಿನ ಸರಬರಾಜು ಸಮಸ್ಯೆ",
            "water_contamination": "ಕಲುಷಿತ ನೀರಿನ ಸಮಸ್ಯೆ",
            "drainage_blockage": "ಡ್ರೆನೇಜ್ ತಡೆ",
            "sewage_overflow": "ಮಲಿನ ನೀರಿನ ಓವರ್‌ಫ್ಲೋ",
            "garbage_collection": "ಕಸ ಸಂಗ್ರಹಣೆ ಸಮಸ್ಯೆ",
            "power_outage": "ವಿದ್ಯುತ್ ಕಡಿತ",
            "voltage_fluctuation": "ವೋಲ್ಟೇಜ್ ಏರಿಳಿತ",
            "transformer_fault": "ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್ ದೋಷ",
            "billing_dispute": "ವಿದ್ಯುತ್ ಬಿಲ್ ಸಮಸ್ಯೆ",
            "electricity_theft": "ವಿದ್ಯುತ್ ಕಳ್ಳತನ / ಅಕ್ರಮ ಸಂಪರ್ಕ",
            "internal_wiring": "ಆಂತರಿಕ ವೈರಿಂಗ್ ಸಮಸ್ಯೆ",
            "road_damage": "ರಸ್ತೆ ಹಾನಿ / ಗುಂಡಿಗಳು",
            "bridge_damage": "ಸೇತುವೆ ಹಾನಿ",
            "footpath_obstruction": "ಫುಟ್‌ಪಾತ್ ಅಡ್ಡಿ",
            "illegal_construction": "ಅಕ್ರಮ ನಿರ್ಮಾಣ",
            "building_issue": "ಅಸುರಕ್ಷಿತ ಕಟ್ಟಡ ಸಮಸ್ಯೆ",
            "general_sanitation": "ಸ್ವಚ್ಛತೆ ಸಮಸ್ಯೆ",
            "general_infrastructure": "ಮೂಲಸೌಕರ್ಯ ಸಮಸ್ಯೆ",
            "general_electricity": "ವಿದ್ಯುತ್ ಸಮಸ್ಯೆ",
        }
    }

    selected = titles.get(language, titles["en"])
    return selected.get(subtype, subtype.replace("_", " ").title())


def to_ui_payload(action: Action, reward_result, note: Optional[str], language: str = "en") -> Dict[str, Any]:
    issues = []
    clarification_question = ""

    text_pack = {
        "en": {
            "default_reason": "Complaint suggests a civic issue requiring attention.",
            "recommend": "Recommended next step: contact your local {authority} office or register a complaint through the official civic helpline for the {title}.",
            "clearer": "Please provide a clearer complaint so the system can route it correctly.",
        },
        "hi": {
            "default_reason": "शिकायत से नागरिक समस्या का संकेत मिलता है जिस पर ध्यान देने की आवश्यकता है।",
            "recommend": "सुझाया गया अगला कदम: {title} के लिए अपने स्थानीय {authority} कार्यालय से संपर्क करें या आधिकारिक नागरिक हेल्पलाइन पर शिकायत दर्ज करें।",
            "clearer": "कृपया शिकायत को और स्पष्ट लिखें ताकि सिस्टम सही विभाग तक भेज सके।",
        },
        "kn": {
            "default_reason": "ದೂರು ನಾಗರಿಕ ಸಮಸ್ಯೆಯನ್ನು ಸೂಚಿಸುತ್ತದೆ ಮತ್ತು ಗಮನ ಅಗತ್ಯವಿದೆ.",
            "recommend": "ಮುಂದಿನ ಸಲಹೆ: {title}ಗಾಗಿ ನಿಮ್ಮ ಸ್ಥಳೀಯ {authority} ಕಚೇರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ ಅಥವಾ ಅಧಿಕೃತ ನಾಗರಿಕ ಸಹಾಯವಾಣಿಯಲ್ಲಿ ದೂರು ದಾಖಲಿಸಿ.",
            "clearer": "ಸಿಸ್ಟಮ್ ಸರಿಯಾದ ಇಲಾಖೆಗೆ ಕಳುಹಿಸಲು ದಯವಿಟ್ಟು ದೂರನ್ನು ಇನ್ನಷ್ಟು ಸ್ಪಷ್ಟವಾಗಿ ಬರೆಯಿರಿ.",
        }
    }

    t = text_pack.get(language, text_pack["en"])

    for unit in action.issue_units:
        title = format_issue_title(unit.subtype, language)

        issues.append({
            "title": title,
            "set": unit.set.title(),
            "subtype": unit.subtype,
            "urgency": unit.urgency.title(),
            "ownership": unit.public_private.title(),
            "authority": unit.authority_name,
            "authority_type": unit.authority_type.replace("_", " ").title(),
            "reason": unit.root_cause or unit.reasoning or t["default_reason"],
        })

        if unit.clarification_needed and unit.clarification_question.strip() and not clarification_question:
            clarification_question = unit.clarification_question.strip()

    recommendation = ""
    if issues:
        idx = action.overall_priority_order[0] if action.overall_priority_order else 0
        idx = idx if 0 <= idx < len(issues) else 0
        top_issue = issues[idx]
        recommendation = t["recommend"].format(
            authority=top_issue["authority"],
            title=top_issue["title"].lower()
        )
    elif action.insufficient_information:
        recommendation = t["clearer"]

    return {
        "status": "ok",
        "clarification_needed": bool(clarification_question),
        "clarification_question": clarification_question,
        "issues": issues,
        "priority_order": action.overall_priority_order,
        "feedback": reward_result.feedback,
        "reward_score": reward_result.score,
        "final_recommendation": recommendation,
        "manual_review_recommended": action.manual_review_recommended,
        "insufficient_information": action.insufficient_information,
        "backend_note": note or "",
    }


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@app.get("/")
def index() -> Any:
    return send_from_directory(APP_DIR, "index.html")


@app.get("/app.js")
def serve_js() -> Any:
    return send_from_directory(APP_DIR, "app.js")


@app.get("/styles.css")
def serve_css() -> Any:
    return send_from_directory(APP_DIR, "styles.css")

CURRENT_ENV = GrievanceEnvironment()
CURRENT_OBS = None

@app.route("/reset", methods=["POST"])
def reset_env():
    global CURRENT_ENV, CURRENT_OBS

    data = request.get_json(silent=True) or {}
    language = data.get("language", "en")
    complaint = str(data.get("complaint", "")).strip()
    task_id = str(data.get("task_id", "")).strip() or None

    if not complaint:
        complaint = "No water supply in my area since morning."

    CURRENT_ENV = GrievanceEnvironment()
    CURRENT_OBS = CURRENT_ENV.reset(complaint, task_id=task_id)

    return jsonify({
        "observation": CURRENT_OBS.model_dump(),
        "reward":0,
        "done":False
    })


@app.route("/step", methods=["POST"])
def step_env():
    global CURRENT_ENV

    data = request.get_json(silent=True) or {}
    language = data.get("language", "en")
    action_data = data.get("action", {}) or {}

    action = Action(**action_data)
    observation, reward, done, info = CURRENT_ENV.step(action)

    return jsonify({
        "state":observation.model_dump(),
        "reward": reward.score if hasattr(reward, "score") else reward,
        "done": done
    })


@app.route("/state", methods=["GET"])
def get_state():
    global CURRENT_ENV
    return jsonify(CURRENT_ENV.state())

@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze() -> Any:
    print("ANALYZE ENDPOINT HIT", flush=True)
    if request.method == "OPTIONS":
        response = jsonify({})
        response.status_code = 200
        return response
    print("ANALYZE HIT FROM:",__file__)
    
    payload = request.get_json(silent=True) or {}
    language = payload.get("language", "en")
    print("Payload:", payload)

    complaint = str(payload.get("complaint", "")).strip()
    clarification = str(payload.get("clarification", "")).strip()
    task_id = str(payload.get("task_id", "")).strip() or None

    print("Complaint:", complaint)

    if not complaint:
        return jsonify({"status": "error", "message": "Complaint text is required."}), 400

    merged_text = complaint

    if clarification:
        clar = clarification.lower()

        if any(k in clar for k in ("poori", "whole", "building", "colony", "area")):
            merged_text += " whole area"
        elif any(k in clar for k in ("ghar", "house", "home", "flat", "room")):
            merged_text += " house only"

        if any(k in clar for k in ("public", "road", "street")):
            merged_text += " public place"

        if any(k in clar for k in ("near", "location", "paas")):
            merged_text += f" location {clar}"

    print("Merged text:", merged_text)

    env = GrievanceEnvironment()
    observation = env.reset(merged_text, task_id=task_id)

    action: Optional[Action] = None
    note: Optional[str] = None

    try:
        raw = call_llm(observation, language)
        parsed = safe_parse_json(raw)
        action = build_action_from_dict(parsed)
        if action is None:
            note = "LLM response could not be parsed. Rule-based fallback used."
    except Exception as exc:
        note = f"LLM unavailable. Rule-based fallback used ({type(exc).__name__})."

    if action is None:
        action = GrievanceEnvironment.build_rule_based_action(observation)
        note = note or "Rule-based decision mode."

    #print("ACTION OBJECT:", action)
    #print("ISSUE UNITS:", action.issue_units)

    _, reward_result, _, _ = env.step(action)

    payload = to_ui_payload(action, reward_result, note, language)
    print("FINAL PAYLOAD:", payload)
    return jsonify(payload)
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)
