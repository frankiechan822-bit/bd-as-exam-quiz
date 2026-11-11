import json
import os
from datetime import datetime, timezone, timedelta

def get_hong_kong_time():
    # 香港時區 UTC+8
    hk_tz = timezone(timedelta(hours=8))
    return datetime.now(hk_tz)

def main():
    hk_now = get_hong_kong_time()
    hour = hk_now.hour
    date_str = hk_now.strftime("%Y-%m-%d")
    
    # 判斷是早卷 (08:00–17:59) 還是晚卷 (18:00–07:59)
    if 8 <= hour < 18:
        session_type = "MORNING"
        session_label = f"早晨衝刺卷 ({date_str} 08:00 發布)"
    else:
        session_type = "EVENING"
        session_label = f"傍晚強化卷 ({date_str} 18:00 發布)"

    # 讀取完整題庫
    bank_path = "questions_bank.json"
    if not os.path.exists(bank_path):
        print("Error: questions_bank.json not found!")
        return

    with open(bank_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 根據日期與早晚卷計算題目組（確保每日更換且不重複）
    pool = data.get("all_questions", [])
    if len(pool) < 30:
        print("Warning: Question pool has fewer than 30 questions.")
        selected = pool
    else:
        # 使用天數與時段作為 offset 抽題
        day_of_year = hk_now.timetuple().tm_yday
        offset = (day_of_year * 2 + (0 if session_type == "MORNING" else 1)) * 30
        
        selected = []
        for i in range(30):
            idx = (offset + i) % len(pool)
            selected.append(pool[idx])

    output_payload = {
        "updated_at": hk_now.strftime("%Y-%m-%d %H:%M:%S"),
        "session_type": session_type,
        "session_title": session_label,
        "total_questions": len(selected),
        "questions": selected
    }

    with open("current_quiz.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated {session_label} with {len(selected)} questions.")

if __name__ == "__main__":
    main()
