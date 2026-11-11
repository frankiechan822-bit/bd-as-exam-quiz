import os
import json
import requests
from datetime import datetime, timezone, timedelta

def get_hong_kong_time():
    # Hong Kong Time (UTC+8)
    hk_tz = timezone(timedelta(hours=8))
    return datetime.now(hk_tz)

def load_history_summary(history_file="history_log.txt", limit=120):
    """Reads past tested statutory scenarios to prevent duplicate questions."""
    if not os.path.exists(history_file):
        return "No historical records yet."
    with open(history_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return "\n".join(lines[-limit:])

def append_to_history(new_questions, history_file="history_log.txt"):
    """Appends newly generated scenarios to the tracking ledger."""
    with open(history_file, "a", encoding="utf-8") as f:
        for q in new_questions:
            ref = q.get("statutoryRef", "General")
            scenario_snippet = q.get("scenario", "")[:60].replace("\n", " ")
            f.write(f"[{ref}] {scenario_snippet}\n")

def call_gemini_api(api_key, past_topics, session_label):
    # Using Gemini 2.5 Flash endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
    
    # Prompt explicitly enforcing ENGLISH questions, scenarios, choices, and rationales
    system_prompt = f"""
You are a senior Chief Building Surveyor at the Hong Kong Buildings Department (BD) and an expert examiner for the Contractors Registration Committee (CRC).
Your mission is to generate exactly 30 high-difficulty, realistic, scenario-based Multiple Choice questions in English for candidates taking the Registered General Building Contractor (RGBC) Authorized Signatory (AS) Examination (under PNRC 38 Appendix P).

All scenarios, questions, options, and explanations MUST BE WRITTEN IN ENGLISH.

[STATUTORY DISTRIBUTION - 30 QUESTIONS IN TOTAL]:
1. Buildings Ordinance (Cap. 123) Core Duties & Criminal Liabilities (8 Questions):
   - Section 9: Non-delegable duty of continuous supervision, Section 9(5)(b) mandatory notification of material divergences/defects, Section 9(5)(c) fitness of materials.
   - Section 14(1) & Section 17: Plan approval vs Consent (3-month validity), statutory conditions on consent (proof drilling, geotechnical monitoring).
   - Section 21: Statutory grounds for refusing an Occupation Permit (OP).
   - Enforcement orders: Section 23 (Cease Works Order), Section 24 (Demolition of UBW), Section 24A (Closure Order), Section 26/27A (Dangerous buildings & hillsides).
   - Criminal offenses: Section 40(1AA) knowingly false certification ($1M fine + 3 yrs imprisonment), Section 40(2A) material deviation, Section 40(2B) injury/damage.
   - Disciplinary proceedings: Section 13 powers (fines, deregistration; NO custodial powers).

2. Statutory Specified Forms & Operational Lifecycles (7 Questions):
   - Forms BA8, BA10 (minimum 7-day prior notice), BA12, BA13 (application for OP), BA14 (completion certification by RGBC), BA14A (specialist works).
   - Minor Works Control System (MWCS): Class I, II, III criteria and forms MW01 through MW06.

3. Subsidiary Regulations & Engineering Standards (8 Questions):
   - Building (Administration) Regulations: Reg. 10 (statutory records kept on site), Reg. 11 (minimum 12 months record retention), Reg. 26 (continuous supervision), Reg. 27 (resumption notice after >2 months suspension).
   - Building (Planning) Regulations: Part IX temporary structures, Means of Escape (MOE) clear widths.
   - Building (Demolition Works) Regulations: Intermediate slab debris limits, cantilevered catch platforms.

4. Practice Notes for Registered Contractors (PNRC) & Safety Supervision (SSPS) (7 Questions):
   - PNRC 4: Hoardings and covered walkways (minimum 2.5m clear headroom, 1.1m clear width).
   - PNRC 14: Railway Protection Zone (RPZ) Alert (20mm), Alarm, Action triggers and MTRC consultation.
   - PNRC 38: Qualification pathways, sole AS resignation (mandatory immediate stop work).
   - PNAP APP-55 / PNRC 52: Minor Amendment criteria vs unauthorized material divergence.
   - SSPS Code: Contractor Stream TCP grades (T1 to T5), logbook maintenance, strict ban on cross-stream concurrent appointments.

[EXAM RIGOR RULES]:
- NO trivial or comical distractors. All 4 options must use authentic statutory phrasing ("shall" vs "may", "prior approval" vs "prior consent", "AP" vs "AS").
- Scenarios must involve realistic multi-party site dilemmas (e.g. Client commercial pressure, AP verbal site memo, sub-contractor faults).
- AVOID DUPLICATION: Do NOT repeat the following recently tested scenario concepts:
{past_topics}

[REQUIRED OUTPUT FORMAT]:
Return strictly valid raw JSON without any markdown formatting wrappers (do not include ```json or ```). Format:
{{
  "session_title": "{session_label}",
  "total_questions": 30,
  "questions": [
    {{
      "id": 1,
      "scenario": "A 2-4 sentence realistic site dilemma in English...",
      "options": [
        "A. First plausible option in English",
        "B. Second plausible option in English",
        "C. Third plausible option in English",
        "D. Fourth plausible option in English"
      ],
      "correctIndex": 1,
      "statutoryRef": "Exact statutory section/regulation/practice note code (e.g., BO Section 9(5)(b))",
      "rationale": "Comprehensive legal rationale in English explaining why the chosen option is correct and why other options represent statutory traps."
    }}
  ]
}}
"""

    payload = {
        "contents": [{"parts": [{"text": system_prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(url, json=payload, timeout=120)
    if response.status_code != 200:
        raise Exception(f"Gemini API request failed [{response.status_code}]: {response.text}")
    
    result = response.json()
    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    return json.loads(raw_text)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("CRITICAL ERROR: GEMINI_API_KEY environment variable is missing!")
        return

    hk_now = get_hong_kong_time()
    hour = hk_now.hour
    date_str = hk_now.strftime("%Y-%m-%d")
    
    # Morning session (08:00 HKT) vs Evening session (18:00 HKT)
    if 8 <= hour < 18:
        session_label = f"Morning Simulation Paper ({date_str} 08:00 HKT)"
    else:
        session_label = f"Evening Simulation Paper ({date_str} 18:00 HKT)"

    print(f"Triggering Gemini 2.5 Flash for [{session_label}]...")
    past_topics = load_history_summary()
    
    quiz_data = call_gemini_api(api_key, past_topics, session_label)
    quiz_data["updated_at"] = hk_now.strftime("%Y-%m-%d %H:%M:%S")

    # Save to current_quiz.json for the front-end interface
    with open("current_quiz.json", "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, ensure_ascii=False, indent=2)

    # Append to history log
    append_to_history(quiz_data.get("questions", []))
    print(f"Successfully generated 30 authentic English questions into current_quiz.json!")

if __name__ == "__main__":
    main()
