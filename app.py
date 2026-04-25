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

def get_authority_guidance(authority: str, language: str = "en") -> list[str]:
    authority_lower = (authority or "").lower()

    guidance_en = {
        "jal": [
            "Note your exact location, ward/area name, and duration of the water issue.",
            "Contact the local Jal Nigam or water supply office.",
            "Submit the complaint under water supply / water contamination category.",
            "Ask for a complaint/reference number.",
            "Follow up if there is no response within 24–48 hours."
        ],
        "nagar": [
            "Take a photo/video of the sanitation or drainage issue if possible.",
            "Note the location, nearby landmark, and ward number.",
            "Contact Nagar Nigam through office, helpline, or official portal.",
            "Submit the issue under sanitation, garbage, drainage, or sewage category.",
            "Ask for a complaint/reference number for follow-up."
        ],
        "mppb": [
            "Check whether the issue is only in your house or the whole area.",
            "Note your meter number/location if available.",
            "Contact MPPB customer care or local electricity office.",
            "Submit the complaint under outage, voltage, transformer, billing, or theft category.",
            "For dangerous faults like sparks/fire, avoid touching anything and report urgently."
        ],
        "pwd": [
            "Take a photo/video of the road, bridge, or footpath issue.",
            "Note the exact location and nearby landmark.",
            "Contact the local PWD office or civic helpline.",
            "Submit the issue under road damage / public infrastructure category.",
            "Ask for complaint acknowledgement and follow up if delayed."
        ],
        "town": [
            "Collect basic details such as location, type of construction, and public obstruction.",
            "Avoid direct confrontation with the person involved.",
            "Report the issue to Town Planning Department or municipal authority.",
            "If it involves legal ownership dispute, seek legal guidance.",
            "Keep proof such as photos, notices, or written details."
        ],
        "default": [
            "Write down the issue clearly with location and date/time.",
            "Attach photo/video proof if available.",
            "Contact the relevant local civic authority.",
            "Ask for a complaint/reference number.",
            "Follow up regularly until action is taken."
        ]
    }

    guidance_hi = {
        "jal": [
            "अपना सही स्थान, वार्ड/क्षेत्र और समस्या कितने समय से है यह लिखें।",
            "स्थानीय जल निगम या पानी सप्लाई कार्यालय से संपर्क करें।",
            "शिकायत को पानी सप्लाई / दूषित पानी की श्रेणी में दर्ज करें।",
            "शिकायत या रेफरेंस नंबर जरूर लें।",
            "24–48 घंटे में जवाब न मिले तो फॉलो-अप करें।"
        ],
        "nagar": [
            "संभव हो तो समस्या की फोटो या वीडियो लें।",
            "स्थान, नजदीकी पहचान और वार्ड नंबर लिखें।",
            "नागर निगम कार्यालय, हेल्पलाइन या पोर्टल से संपर्क करें।",
            "शिकायत को स्वच्छता, कचरा, नाली या सीवेज श्रेणी में दर्ज करें।",
            "फॉलो-अप के लिए शिकायत नंबर जरूर लें।"
        ],
        "mppb": [
            "पहले देखें समस्या सिर्फ घर में है या पूरे क्षेत्र में।",
            "यदि उपलब्ध हो तो मीटर नंबर या स्थान लिखें।",
            "MPPB ग्राहक सेवा या स्थानीय बिजली कार्यालय से संपर्क करें।",
            "शिकायत को बिजली कटौती, वोल्टेज, ट्रांसफॉर्मर या बिलिंग श्रेणी में दर्ज करें।",
            "स्पार्क/आग जैसी खतरनाक स्थिति में कुछ न छुएं और तुरंत रिपोर्ट करें।"
        ],
        "pwd": [
            "सड़क, पुल या फुटपाथ की समस्या की फोटो/वीडियो लें।",
            "सही स्थान और नजदीकी पहचान लिखें।",
            "स्थानीय PWD कार्यालय या नागरिक हेल्पलाइन से संपर्क करें।",
            "शिकायत को सड़क क्षति / सार्वजनिक ढांचा श्रेणी में दर्ज करें।",
            "शिकायत की पावती लें और देरी होने पर फॉलो-अप करें।"
        ],
        "town": [
            "स्थान, निर्माण का प्रकार और सार्वजनिक बाधा की जानकारी लिखें।",
            "संबंधित व्यक्ति से सीधे टकराव से बचें।",
            "टाउन प्लानिंग विभाग या नगर निगम को रिपोर्ट करें।",
            "कानूनी विवाद होने पर कानूनी सलाह लें।",
            "फोटो, नोटिस या लिखित जानकारी जैसे प्रमाण रखें।"
        ],
        "default": [
            "समस्या को स्थान और समय के साथ साफ़ लिखें।",
            "यदि संभव हो तो फोटो/वीडियो प्रमाण जोड़ें।",
            "संबंधित स्थानीय विभाग से संपर्क करें।",
            "शिकायत या रेफरेंस नंबर लें।",
            "समाधान तक नियमित फॉलो-अप करें।"
        ]
    }

    guidance = guidance_hi if language == "hi" else guidance_en

    if "jal" in authority_lower:
        return guidance["jal"]
    if "nagar" in authority_lower or "municipal" in authority_lower:
        return guidance["nagar"]
    if "mppb" in authority_lower or "electric" in authority_lower:
        return guidance["mppb"]
    if "pwd" in authority_lower:
        return guidance["pwd"]
    if "town" in authority_lower or "planning" in authority_lower or "legal" in authority_lower:
        return guidance["town"]

    return guidance["default"]

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
            "approach_steps": get_authority_guidance(unit.authority_name, language),
        })

        if unit.clarification_needed and unit.clarification_question.strip() and not clarification_question:
            clarification_question = unit.clarification_question.strip()

    recommendation = ""
    if issues:
        idx = action.overall_priority_order[0] if action.overall_priority_order else 0
        idx = idx if 0 <= idx < len(issues) else 0
        top_issue = issues[idx]
        safe_title = str(top_issue.get("title", "civic issue")).lower()

        recommendation = t["recommend"].format(
          authority=top_issue.get("authority", "relevant civic authority"),
          title=safe_title
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
