import os
import re
import json
import random
import requests
from datetime import datetime, timezone

JSON_DB_FILE = "scholarships.json"
API_KEY_FILE = "api_key.txt"

TARGET_HUNT_POOL = [
    ("Switzerland", "ETH Zurich Excellence & Swiss Government Scholarship", "Master's / PhD", "Computer Science & Engineering"),
    ("Singapore", "SINGA & ASEAN/NTU Science & Engineering Scholarship", "Class 12 UG / PhD", "Computer Science & AI"),
    ("Australia", "Australia Awards & Melbourne International Undergraduate Scholarship", "Class 12 UG / Master's", "All Fields"),
    ("Italy", "Invest Your Talent in Italy & DSU Regional Need-Based Scholarship", "Class 12 UG / Master's", "Engineering & Business"),
    ("France", "Eiffel Excellence Scholarship & Emile-Boutmy Scholarship", "Master's / PhD", "Engineering, CS & Law"),
    ("Ireland", "Government of Ireland International Education Scholarship (GOI-IES)", "Master's / PhD", "All Fields"),
    ("New Zealand", "Manaaki New Zealand Government Scholarship", "Undergraduate / Master's", "Science & Technology"),
    ("Sweden", "Swedish Institute (SI) Global Professionals Scholarship", "Master's Degree", "Computer Science & Sustainability"),
    ("Netherlands", "NL Scholarship & TU Delft Justus & Louise van Effen Excellence", "Master's Degree", "Engineering & CS"),
    ("Hungary", "Stipendium Hungaricum Government Scholarship", "Class 12 UG / Master's / PhD", "Computer Science, Medicine & Engineering"),
    ("UAE", "Khalifa University & NYU Abu Dhabi Full Financial Support", "Class 12 UG / Master's / PhD", "AI, Robotics & Engineering"),
    ("Taiwan", "Taiwan ICDF & MOE Government Scholarship", "Class 12 UG / Master's / PhD", "Semiconductors, CS & Engineering")
]

def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GEMMA_API_KEY", "").strip()
    if not key and os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r", encoding="utf-8") as f:
            key = f.read().strip()
    return key

def load_existing_db():
    if os.path.exists(JSON_DB_FILE):
        try:
            with open(JSON_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": "", "scholarships": []}

def discover_working_models(api_key):
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        res = requests.get(url, timeout=15).json()
        models = [
            m["name"].replace("models/", "")
            for m in res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        priority = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemma-3-27b-it"]
        ordered = [p for p in priority if p in models] + [m for m in models if "gemini" in m or "gemma" in m]
        return ordered or priority
    except Exception:
        return ["gemini-3.5-flash", "gemini-2.5-flash", "gemma-3-27b-it"]

def generate_scholarship_entry(api_key, models, country, sch_name, level_label, field_label):
    prompt = f"""
    Generate ONLY a valid JSON object (no markdown code blocks) for the foreign scholarship: "{sch_name}" in {country}.
    Use this exact JSON schema:
    {{
      "id": "{re.sub(r'[^a-z0-9]+', '-', sch_name.lower()).strip('-')}",
      "title": "{sch_name}",
      "university": "Top Partner Universities in {country}",
      "logoTitle": "{country} Scholar",
      "logoIcon": "fa-building-columns",
      "logoColor": "text-indigo-700",
      "country": "{country}",
      "flag": "🌍",
      "badge": "Fully Funded",
      "badgeColor": "bg-[#10b981]",
      "fundingType": "Fully Funded",
      "deadline": "Exact typical application month/date in 2026/2027",
      "bestDate": "Recommended window to submit form (e.g. 3 weeks before deadline)",
      "levels": ["Class 12 / High School", "Undergraduate", "Master's Degree", "PhD / Research"],
      "forLabel": "{level_label}",
      "fields": ["ALL", "Computer Science", "Engineering", "Science", "Medicine", "Business"],
      "benefitsShort": "Full Tuition + Monthly Stipend + Travel",
      "benefitsFull": "Complete financial details including tuition waiver, monthly living stipend in local currency, accommodation, and flights.",
      "image": "https://images.unsplash.com/photo-1541339907198-e08756dedf3f?auto=format&fit=crop&w=800&q=80",
      "eligibility": ["Criterion 1", "Criterion 2", "Criterion 3"],
      "docs": ["Document 1", "Document 2", "Document 3", "Document 4", "Document 5"],
      "steps": ["Step 1", "Step 2", "Step 3", "Step 4"],
      "tip": "Practical insider tip for Indian students to get selected",
      "link": "Official portal URL"
    }}
    """
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for mdl in models[:4]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, timeout=35).json()
            text = res["candidates"][0]["content"]["parts"][0]["text"]
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                return json.loads(m.group(0))
        except Exception:
            continue
    return None

def main():
    api_key = get_api_key()
    if not api_key:
        print("❌ GEMINI_API_KEY not found!")
        return

    db = load_existing_db()
    existing_ids = {s.get("id") for s in db.get("scholarships", [])}
    models = discover_working_models(api_key)

    missing_targets = [
        t for t in TARGET_HUNT_POOL
        if re.sub(r"[^a-z0-9]+", "-", t[1].lower()).strip("-") not in existing_ids
    ]
    if not missing_targets:
        missing_targets = random.sample(TARGET_HUNT_POOL, k=2)

    added = 0
    for country, sch_name, level_label, field_label in missing_targets[:3]:
        item = generate_scholarship_entry(api_key, models, country, sch_name, level_label, field_label)
        if item and item.get("id") not in existing_ids:
            db["scholarships"].append(item)
            existing_ids.add(item["id"])
            added += 1
            print(f"✅ AI Discovered & Added: {item['title']} ({country})")

    db["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(JSON_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    print(f"🏆 Done! Added {added} new scholarships. Total in scholarships.json: {len(db['scholarships'])}")

if __name__ == "__main__":
    main()
