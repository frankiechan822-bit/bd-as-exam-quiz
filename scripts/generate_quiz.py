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
    model_name = "gemini-3.8-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(1, max_retries + 1):
        try:
            log(f"Calling Google Gemini API (Attempt {attempt}/{max_retries})...")
            # 設置嚴格逾時：連線 10 秒，讀取 60 秒
            response = requests.post(url, json=payload, timeout=(10, 60))
            
            if response.status_code in [429, 503]:
                wait_sec = attempt * 5
                log(f"Server busy [{response.status_code}]. Waiting {wait_sec}s...")
                time.sleep(wait_sec)
                continue

            if response.status_code == 200:
                result = response.json()
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                log("Received response successfully.")
                return json.loads(raw_text).get("questions", [])
            else:
                log(f"HTTP Error {response.status_code}: {response.text}")
                time.sleep(3)

        except requests.exceptions.Timeout:
            log(f"Timeout on attempt {attempt}, retrying...")
            time.sleep(3)
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(3)

    raise Exception("Failed after maximum retries.")

def generate_batch(api_key, past_topics, batch_num, start_id):
    if batch_num == 1:
        syllabus = "Cap. 123 (s.9, s.14, s.17, s.21, s.23, s.40) & Forms BA8, BA10, BA12, BA13, BA14, BA14A, MWCS."
    else:
        syllabus = "B(A)R (Reg. 10, 11, 26, 27), PNRC 4, PNRC 14, PNRC 38, PNRC 52, SSPS Code (TCP streams)."

    prompt = f"""
You are an examiner for the HK Buildings Department RGBC Authorized Signatory MC exam (under PNRC 38 Appendix P).
Generate exactly 15 scenario-based Multiple Choice questions in English for questions {start_id} to {start_id + 14}.

Syllabus Focus:
{syllabus}

Do not repeat:
{past_topics}

Format: Return strictly a JSON object with a 'questions' array. No markdown code blocks.
{{
  "questions": [
    {{
      "id": {start_id},
      "scenario": "A 2-sentence site dilemma in English...",
      "options": [
        "A. First plausible option",
        "B. Second plausible option",
        "C. Third plausible option",
        "D. Fourth plausible option"
      ],
      "correctIndex": 1,
      "statutoryRef": "BO Section 9(5)(b)",
      "rationale": "Legal rationale in English."
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
    session_label = f"Morning Paper ({date_str} 08:00 HKT)" if 8 <= hk_now.hour < 18 else f"Evening Paper ({date_str} 18:00 HKT)"

    log(f"Starting generation for {session_label}...")
    past_topics = load_history_summary()

    log("Generating Batch 1 (Questions 1-15)...")
    batch_1 = generate_batch(api_key, past_topics, batch_num=1, start_id=1)
    
    time.sleep(2)

    log("Generating Batch 2 (Questions 16-30)...")
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
    log("Done! 30 questions saved to current_quiz.json.")

if __name__ == "__main__":
    main()
