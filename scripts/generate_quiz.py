import os
import json
import requests
import time
import sys
from datetime import datetime, timezone, timedelta

def log(msg):
    print(msg, flush=True)

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
    model_name = "gemini-2.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            log(f"Calling Google Gemini API (Attempt {attempt}/{max_retries})...")
            response = requests.post(url, json=payload, timeout=(15, 100))
            
            if response.status_code in [429, 503]:
                wait_sec = attempt * 5
                log(f"Server busy [{response.status_code}]. Waiting {wait_sec}s...")
                time.sleep(wait_sec)
                continue

            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                log("Batch generated successfully.")
                return json.loads(raw_text).get("questions", [])
            else:
                log(f"HTTP Error {response.status_code}: {response.text}")
                time.sleep(4)

        except requests.exceptions.Timeout:
            log(f"Timeout on attempt {attempt}, retrying...")
            time.sleep(4)
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(4)

    raise Exception("Failed after maximum retries.")

def generate_batch(api_key, past_topics, batch_num, start_id):
    if batch_num == 1:
        syllabus = """
1. Buildings Ordinance (Cap. 123) Core Duties, Powers & Criminal Liabilities:
   - Section 9(5)(a)-(c): Continuous supervision, mandatory written notice to BA of material divergence/defects, fitness of materials.
   - Section 14(1) & Section 17: Consent validity, proof drilling conditions.
   - Section 20(1) & (2): Deemed revocation of consent if works not commenced within 3 months OR if commenced are suspended for 3 months; renewal application via Form BA9.
   - Section 21: Occupation Permit statutory grounds for refusal.
   - Section 23 (Cease Works Order), Section 24 (Demolition of unauthorized building works), Section 24A (Closure Order).
   - Criminal offenses: Section 40(1AA) false representation, Section 40(2A) material divergence, Section 40(2B) injury/damage.
   - Section 13: Disciplinary board powers (fines, deregistration; no custodial sentencing).
"""
    elif batch_num == 2:
        syllabus = """
2. Specified Forms & Minor Works Control System (MWCS):
   - Form BA8 (Appointment of RGBC/RSC).
   - Form BA9 (Application for Renewal of Consent under BO Section 20).
   - Form BA10 (Notice of commencement under B(A)R Reg. 20, min 7 days prior).
   - Form BA12, BA13 (Application for OP), BA14 (RGBC practical completion certificate), BA14A (Specialist completion).
   - MWCS (Cap. 123N): Class I, II, III prescribed criteria; Forms MW01 through MW06.
"""
    else:
        syllabus = """
3. Subsidiary Regulations (Active Clauses Only) & Practice Notes:
   - Building (Administration) Regulations (Cap. 123A):
     * Reg. 10: Approved plans and documents to be kept on site.
     * Reg. 11: Duty of contractor to retain test records and supervisory logs for >= 12 months.
     * Reg. 20: Minimum 7 days' prior notice for commencement (Form BA10).
     * Reg. 26: Continuous supervision obligations.
     * Reg. 34: Endorsement of renewed consent under Section 20 on the notice of consent.
     * CRITICAL: Do NOT cite repealed provisions (e.g. Reg. 21, Reg. 27, Reg. 32A).
   - Building (Planning) Regulations: Part IX temporary structures, MOE clear widths.
   - Practice Notes:
     * PNRC 4: Hoardings and covered walkways (clear headroom >= 2.5m, clear width >= 1.1m).
     * PNRC 14: Railway Protection Zone (Alert 20mm trigger).
     * PNRC 38: AS qualification, sole AS resignation (mandatory immediate stop work).
     * PNAP APP-55 / PNRC 52: Minor Amendments boundaries.
     * SSPS Code: Contractor Stream TCP grades (T1 to T5), logbook entries, prohibition on cross-stream concurrent appointments.
"""

    prompt = f"""
You are an expert Chief Building Surveyor and examiner for the HK Buildings Department RGBC Authorized Signatory Examination (under PNRC 38 Appendix P).
Generate exactly 10 high-difficulty, realistic, scenario-based Multiple Choice questions in English for questions {start_id} to {start_id + 9}.

STRICT STATUTORY ACCURACY RULES:
1. ONLY cite active, non-repealed provisions from the Hong Kong Buildings Ordinance (Cap. 123) and subsidiary regulations.
2. DO NOT cite repealed regulations (e.g., B(A)R Regulation 27 is repealed; suspension/revocation is governed by BO Section 20(1) [3 months] and renewal by BO Section 20(2) / B(A)R Reg. 34 / Form BA9).
3. Commencement notice is B(A)R Reg. 20(1) (Form BA10, min 7 days).
4. All questions, scenarios, options, and rationales MUST BE IN ENGLISH.

Syllabus Focus for this batch:
{syllabus}

Do not duplicate these past scenarios:
{past_topics}

Format: Return strictly a raw JSON object with a 'questions' array. No markdown code blocks.
{{
  "questions": [
    {{
      "id": {start_id},
      "scenario": "A 2-3 sentence realistic site dilemma in English...",
      "options": [
        "A. First plausible option",
        "B. Second plausible option",
        "C. Third plausible option",
        "D. Fourth plausible option"
      ],
      "correctIndex": 1,
      "statutoryRef": "Exact verified statutory clause (e.g., BO Section 20(1) & Form BA9)",
      "rationale": "Precise legal explanation in English explaining why the answer is correct and why other options are statutory traps."
    }}
  ]
}}
"""
    return call_gemini_with_retry(api_key, prompt)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log("CRITICAL ERROR: GEMINI_API_KEY is missing!")
        sys.exit(1)

    hk_now = get_hong_kong_time()
    date_str = hk_now.strftime("%Y-%m-%d")
    session_label = f"Morning Simulation Paper ({date_str} 08:00 HKT)" if 8 <= hk_now.hour < 18 else f"Evening Simulation Paper ({date_str} 18:00 HKT)"

    log(f"Starting generation for {session_label}...")
    past_topics = load_history_summary()

    log("Generating Batch 1 (Questions 1-10)...")
    b1 = generate_batch(api_key, past_topics, batch_num=1, start_id=1)
    time.sleep(2)

    log("Generating Batch 2 (Questions 11-20)...")
    b2 = generate_batch(api_key, past_topics, batch_num=2, start_id=11)
    time.sleep(2)

    log("Generating Batch 3 (Questions 21-30)...")
    b3 = generate_batch(api_key, past_topics, batch_num=3, start_id=21)

    all_questions = []
    for idx, q in enumerate(b1 + b2 + b3):
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
    log(f"Done! Successfully generated {len(all_questions)} verified English questions into current_quiz.json.")

if __name__ == "__main__":
    main()
