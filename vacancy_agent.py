"""NEXUS VACANCY MONITOR AGENT - Gemini Version"""
import os, json, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL","https://cvdriqyibnmazwnigfhu.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY   = os.getenv("GEMINI_KEY")

SBH = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=representation"}

def sb_get(t):
    r=requests.get(f"{SUPABASE_URL}/rest/v1/{t}?order=created_at.desc&limit=300",headers=SBH); r.raise_for_status(); return r.json()
def sb_patch(t,rid,u):
    r=requests.patch(f"{SUPABASE_URL}/rest/v1/{t}?id=eq.{rid}",headers=SBH,json=u); r.raise_for_status()
def sb_insert(t,rec):
    r=requests.post(f"{SUPABASE_URL}/rest/v1/{t}",headers=SBH,json=rec); r.raise_for_status(); d=r.json(); return d[0] if isinstance(d,list) else d
def log(action,status,details=""):
    try: sb_insert("agent_logs",{"agent":"Vacancy Monitor","action":action,"status":status,"details":details,"created_at":datetime.utcnow().isoformat()})
    except: pass

def ask_gemini(prompt):
    r=requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        params={"key":GEMINI_KEY},json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"maxOutputTokens":200}})
    r.raise_for_status(); return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def generate_nudge(pg, days):
    """Gemini writes a unique Hinglish WhatsApp message for this PG owner."""
    prompt = f"""Write a WhatsApp message in Hinglish (Hindi+English mix) to a PG owner in Indore.
Their PG "{pg.get('name')}" in {pg.get('area')} at Rs.{pg.get('rent')}/month has been vacant {days} days.
Under 80 words. Warm and helpful tone. Suggest 1 action. 1-2 emojis. Sound like a friend."""
    try: return ask_gemini(prompt)
    except: return f"Hi! Aapka {pg.get('name','PG')} {days} din se vacant hai. Price thoda adjust karo ya nayi photo add karo — jaldi tenant milega! nexus-indore.netlify.app 🏠"

def run_vacancy_agent():
    print("\n"+"="*55)
    print("  NEXUS VACANCY MONITOR AGENT (Gemini)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)
    if not SUPABASE_KEY or not GEMINI_KEY: print("ERROR: Set keys in .env"); return

    listings = sb_get("pg_listings")
    now = datetime.utcnow()
    stale_30, stale_60, active = [], [], []

    for pg in listings:
        try:
            dt=datetime.fromisoformat(pg.get("created_at","").replace("Z",""))
            days=(now-dt).days
            if days>=60: stale_60.append((pg,days))
            elif days>=30: stale_30.append((pg,days))
            else: active.append(pg)
        except: active.append(pg)

    print(f"\nActive: {len(active)} | Stale 30d: {len(stale_30)} | Stale 60d: {len(stale_60)}")

    # Auto-pause 60+ day listings
    for pg,days in stale_60:
        try:
            sb_patch("pg_listings",pg["id"],{"status":"paused","paused_reason":f"Auto-paused: {days} days vacant"})
            log(f"Auto-paused: {pg.get('name')}","warning",f"{days} days")
            print(f"  PAUSED: {pg.get('name')} ({days} days)")
        except Exception as e: print(f"  [ERR] {e}")

    # Generate nudge messages for 30-59 day stale
    nudged = 0
    for pg,days in stale_30:
        print(f"\n  Generating nudge for: {pg.get('name')} ({days} days)...")
        msg = generate_nudge(pg, days)
        print(f"  MESSAGE: {msg[:80]}...")
        # Save the generated message to Supabase for manual sending or Twilio
        try:
            sb_patch("pg_listings",pg["id"],{
                "last_nudge_at": now.isoformat(),
                "nudge_count": (pg.get("nudge_count") or 0)+1
            })
            log(f"Nudge generated: {pg.get('name')}","success",msg[:200])
            nudged+=1
        except Exception as e: print(f"  [ERR] {e}")

    summary=f"{len(listings)} checked. {len(stale_60)} paused. {nudged} nudge messages generated."
    log("Full vacancy scan","success",summary)
    print(f"\n  DONE! {summary}")
    print("  Nudge messages saved to agent_logs — send manually via WhatsApp or add Twilio later.")

if __name__ == "__main__":
    run_vacancy_agent()
