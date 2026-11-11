import os
import json
import requests
import time
from datetime import datetime, timezone, timedelta

def get_hong_kong_time():
    hk_tz = timezone(timedelta(hours=8))
    return datetime.now(hk_tz)

def load_history_summary(history_file="history_log.txt", limit=120):
    if not os.path.exists(history_file):
        return "No historical records yet."
    with open(history_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return "\n".join(lines[-limit:])

def append_to_history(new_questions, history_file="history_log.txt"):
    with open(history_file, "a", encoding="utf-8") as f:
        for q in new_questions:
            ref = q.get("statutoryRef", "General")
            snippet = q.get("scenario", "")[:60].replace("\n", " ")
            f.write(f"[{ref}] {snippet}\n")

def call_gemini_with_retry(api_key, prompt, max_retries=3):
    # 候選穩定模型列表（按穩定度輪流調用）
    candidate_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json"
        }
    }

    last_error = None
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        for attempt in range(1, max_retries + 1):
            try:
                print(f"Requesting {model_name} (Attempt {attempt})...")
                response = requests.post(url, json=payload, timeout=120)
                
                # 如果遇到 503 或 429 暫時繁忙，等待後重試
                if response.status_code in [429, 503]:
                    print(f"Server busy [{response.status_code}], retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                
                if response.status_code == 200:
                    result = response.json()
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return json.loads(raw_text).get("questions", [])
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    print(f"Model {model_name} failed: {last_error}")
                    break # 換下一個模型嘗試
            except requests.exceptions.Timeout:
                print(f"Timeout on {model_name}, retrying...")
                time.sleep(3)
            except Exception as e:
                last_error = str(e)
                print(f"Error on {model_name}: {last_error}")
                break

    raise Exception(f"All model candidates failed. Last error: {last_error}")

def generate_batch(api_key, past_topics, batch_num, start_id):
    if batch_num == 1:
        syllabus = """
1. Buildings Ordinance (Cap. 123) Core Duties & Criminal Liabilities (8 Questions):
   - Section 9: Continuous supervision, Section 9(5)(b) mandatory notification of material divergences/defects.
   - Section 14(1) & Section 17: Consent validity (3 months), proof drilling and site conditions.
   - Section 21: Statutory grounds for refusing an Occupation Permit (OP).
   - Orders & Criminal penalties: Section 23 (Cease Works), Section 24 (UBW Demolition), Section 24A, Section 40(1AA), Section 40(2A), Section 40(2B).
2. Statutory Specified Forms & Lifecycles (7 Questions):
   - Forms BA8, BA10 (minimum 7-day prior notice), BA12, BA13, BA14, BA14A.
   - Minor Works Control System (MWCS): Class I, II, III criteria and forms MW01 through MW06.
"""
    else:
        syllabus = """
3. Subsidiary Regulations & Engineering Standards (8 Questions):
   - Building (Administration) Regulations: Reg. 10 (statutory records on site), Reg. 11 (minimum 12 months record retention), Reg. 26 (continuous supervision), Reg. 27 (resumption notice after >2 months suspension).
   - Building (Planning) Regulations: Part IX temporary structures, Means of Escape (MOE) clear widths.
   - Building (Demolition Works) Regulations: Intermediate slab debris limits, cantilevered catch platforms.
4. Practice Notes for Registered Contractors (PNRC) & Safety Supervision (SSPS) (7 Questions):
   - PNRC 4: Hoardings and covered walkways (minimum 2.5m clear headroom, 1.1m clear width).
   - PNRC 14: Railway Protection Zone (RPZ) Alert (20mm), Alarm, Action triggers and MTRC consultation.
   - PNRC 38: Qualification pathways, sole AS resignation (mandatory immediate stop work).
   - PNAP APP-55 / PNRC 52: Minor Amendment criteria vs unauthorized material divergence.
   - SSPS Code: Contractor Stream TCP grades (T1 to T5), logbook maintenance, strict ban on cross-stream concurrent appointments.
"""

    prompt = f"""
You are a senior Chief Building Surveyor at the Hong Kong Buildings Department (BD) and an expert examiner for the Contractors Registration Committee (CRC).
Generate exactly 15 high-difficulty, realistic, scenario-based Multiple Choice questions in English for the RGBC Authorized Signatory (AS) Examination.

All questions, scenarios, options, and rationales MUST BE IN ENGLISH.

Syllabus Focus for this batch (Questions {start_id} to {start_id + 14}):
{syllabus}

Do NOT repeat these recently tested scenarios:
{past_topics}

Return STRICT JSON ONLY (no markdown formatting, no ```json):
{{
  "questions": [
    {{
      "id": {start_id},
      "scenario": "A 2-3 sentence realistic site dilemma in English...",
      "options": [
        "A. First plausible option in English",
        "B. Second plausible option in English",
        "C. Third plausible option in English",
        "D. Fourth plausible option in English"
      ],
      "correctIndex": 1,
      "statutoryRef": "Exact statutory section/regulation code (e.g. BO Section 9(5)(b))",
      "rationale": "Clear legal rationale in English explaining the statutory reason."
    }}
  ]
}}
"""
    return call_gemini_with_retry(api_key, prompt)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("CRITICAL ERROR: GEMINI_API_KEY environment variable is missing!")
        return

    hk_now = get_hong_kong_time()
    hour = hk_now.hour
    date_str = hk_now.strftime("%Y-%m-%d")
    
    if 8 <= hour < 18:
        session_label = f"Morning Simulation Paper ({date_str} 08:00 HKT)"
    else:
        session_label = f"Evening Simulation Paper ({date_str} 18:00 HKT)"

    past_topics = load_history_summary()

    print(f"Starting Generation for {session_label}...")
    batch_1 = generate_batch(api_key, past_topics, batch_num=1, start_id=1)
    
    time.sleep(3)  # 緩衝保護

    batch_2 = generate_batch(api_key, past_topics, batch_num=2, start_id=16)

    all_questions = []
    for idx, q in enumerate(batch_1 + batch_2):
        q["id"] = idx + 1
        all_questions.append(q)

    quiz_data = {
        "session_title": session_label,
        "updated_at": hk_now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(all_questions),
        "questions": all_questions
    }

    with open("current_quiz.json", "w", encoding="utf-8") as f:
        json.dump(quiz_data, f, ensure_ascii=False, indent=2)

    append_to_history(all_questions)
    print(f"Completed! 30 English questions successfully written into current_quiz.json.")

if __name__ == "__main__":
    main()
