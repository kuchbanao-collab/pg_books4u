"""
NEXUS PRICING INTELLIGENCE AGENT - Gemini Version
Free: 1500 requests/day, no credit card needed
Get key: aistudio.google.com
"""
import os, json, requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL","https://cvdriqyibnmazwnigfhu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY   = os.getenv("GEMINI_KEY")

INDORE_RATES = {
    "Vijay Nagar":    {"no_ac":(3500,4800),"ac":(5500,7200)},
    "AB Road":        {"no_ac":(4200,5800),"ac":(5500,6500)},
    "Scheme 54":      {"no_ac":(4500,6000),"ac":(6000,8000)},
    "Bhawarkuan":     {"no_ac":(3800,5000),"ac":(5000,5500)},
    "Super Corridor": {"no_ac":(6000,8000),"ac":(8000,12000)},
    "MR-10":          {"no_ac":(3000,4000),"ac":(4000,4500)},
    "Scheme 78":      {"no_ac":(4000,5500),"ac":(5500,7000)},
}

SBH = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def sb_get(t):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{t}?order=created_at.desc&limit=300",headers=SBH)
    r.raise_for_status(); return r.json()

def sb_patch(t,rid,u):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{t}?id=eq.{rid}",headers=SBH,json=u)
    r.raise_for_status()

def sb_insert(t,rec):
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{t}",headers=SBH,json=rec)
    r.raise_for_status(); d=r.json(); return d[0] if isinstance(d,list) else d

def log(action,status,details=""):
    try: sb_insert("agent_logs",{"agent":"Pricing Intelligence","action":action,"status":status,"details":details,"created_at":datetime.utcnow().isoformat()})
    except: pass

def ask_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    r = requests.post(url,params={"key":GEMINI_KEY},json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"maxOutputTokens":512}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def analyze_pg(pg):
    area = pg.get("area","Unknown")
    rent = pg.get("rent",0)
    fac  = pg.get("facilities",[])
    has_ac = any("AC" in str(f) or "ac" in str(f).lower() for f in (fac or []))
    rates = INDORE_RATES.get(area,{"no_ac":(3000,8000),"ac":(5000,10000)})
    lo,hi = rates["ac"] if has_ac else rates["no_ac"]

    prompt = f"""You are a PG rental pricing expert in Indore India.
Analyze this listing and return ONLY valid JSON — no markdown, no extra text.

PG: {pg.get('name')} | Area: {area} | Rent: Rs.{rent}/bed/month
Room: {pg.get('room_type','')} | Type: {pg.get('type','')}
Facilities: {', '.join(fac) if fac else 'None'} | Food: {pg.get('food','')}
Market range for {area}: Rs.{lo}-{hi}/month

Return exactly: {{"verdict":"fair" or "overpriced" or "underpriced","suggested_price":<integer>,"confidence":"high" or "medium" or "low","reason":"<one sentence>","action":"<what owner should do>"}}"""

    try:
        txt = ask_gemini(prompt).strip()
        if "```" in txt:
            txt = txt.split("```")[1]
            if txt.startswith("json"): txt = txt[4:]
        s,e = txt.find("{"), txt.rfind("}")+1
        return json.loads(txt[s:e]) if s>=0 and e>s else {"verdict":"unknown","suggested_price":rent,"confidence":"low","reason":"Parse error","action":"Manual review"}
    except Exception as ex:
        print(f"  [ERR] {ex}")
        return {"verdict":"unknown","suggested_price":rent,"confidence":"low","reason":str(ex)[:60],"action":"Manual review"}

def run_pricing_agent():
    print("\n"+"="*55)
    print("  NEXUS PRICING AGENT (Gemini — Free)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)
    if not SUPABASE_KEY: print("ERROR: Set SUPABASE_KEY in .env"); return
    if not GEMINI_KEY:   print("ERROR: Set GEMINI_KEY in .env"); return

    print("\nFetching listings from Supabase...")
    try:
        listings = sb_get("pg_listings")
        print(f"Found {len(listings)} listings")
    except Exception as e:
        print(f"FAILED: {e}"); log("Fetch failed","error",str(e)); return

    if not listings:
        print("No listings yet. Post some PGs first!"); return

    print(f"\nAnalyzing with Gemini AI...")
    counts = {"fair":0,"overpriced":0,"underpriced":0,"unknown":0}
    flagged = 0

    for i,pg in enumerate(listings):
        name,rent = pg.get("name","?"),pg.get("rent",0)
        print(f"  [{i+1}/{len(listings)}] {name} (Rs.{rent})...", end=" ", flush=True)
        a = analyze_pg(pg)
        v = a.get("verdict","unknown")
        counts[v] = counts.get(v,0)+1
        print(f"→ {v.upper()} | Suggested: Rs.{a.get('suggested_price',rent)}")

        updates = {
            "ai_verdict": a.get("verdict"),
            "ai_suggested_price": a.get("suggested_price"),
            "ai_price_reason": a.get("reason"),
            "ai_analyzed_at": datetime.utcnow().isoformat(),
            "ai_confidence": a.get("confidence"),
        }
        suggested = a.get("suggested_price",rent)
        if suggested and rent > suggested * 1.20:
            updates["needs_review"] = True
            flagged += 1
            print(f"  *** FLAGGED as overpriced ***")

        try:
            sb_patch("pg_listings", pg["id"], updates)
        except Exception as e:
            print(f"  [WRITE ERR] {e}")

    summary = f"Analyzed {len(listings)}: {counts['fair']} fair, {counts['overpriced']} overpriced, {counts['underpriced']} underpriced. {flagged} flagged."
    log(f"Scan complete — {len(listings)} PGs","success",summary)

    print("\n"+"="*55)
    print(f"  DONE! {len(listings)} listings analyzed")
    print(f"  Fair: {counts['fair']} | Overpriced: {counts['overpriced']} | Underpriced: {counts['underpriced']}")
    print(f"  Flagged for review: {flagged}")
    print("="*55)
    print("\nOpen Supabase Table Editor -> pg_listings to see ai_verdict column filled in!")

if __name__ == "__main__":
    run_pricing_agent()
