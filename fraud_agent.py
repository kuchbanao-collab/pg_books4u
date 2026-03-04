"""NEXUS FRAUD DETECTION AGENT - Gemini Version"""
import os, json, requests, re
from datetime import datetime, timedelta
from collections import defaultdict
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
    try: sb_insert("agent_logs",{"agent":"Fraud Detection","action":action,"status":status,"details":details,"created_at":datetime.utcnow().isoformat()})
    except: pass

def ask_gemini(prompt):
    r=requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        params={"key":GEMINI_KEY},json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"maxOutputTokens":300}})
    r.raise_for_status(); return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def ai_fraud_check(pg):
    prompt = f"""You are a fraud detection AI for a PG rental platform in Indore India.
Check this listing for fraud. Return ONLY JSON, no markdown.

Name: {pg.get('name','')} | Area: {pg.get('area','')} | Rent: Rs.{pg.get('rent',0)}
Description: {str(pg.get('description',''))[:200]}
Address: {str(pg.get('address',''))[:100]}

Common frauds: impossibly low price, vague address, demands advance payment, copied descriptions.

Return: {{"fraud_score":0-100,"verdict":"clean" or "suspicious" or "likely_fraud","reason":"<one sentence>"}}"""
    try:
        txt=ask_gemini(prompt).strip()
        if "```" in txt:
            txt=txt.split("```")[1]
            if txt.startswith("json"): txt=txt[4:]
        s,e=txt.find("{"),txt.rfind("}")+1
        return json.loads(txt[s:e]) if s>=0 and e>s else {"fraud_score":0,"verdict":"clean","reason":"parse error"}
    except: return {"fraud_score":0,"verdict":"clean","reason":"api error"}

def run_fraud_agent():
    print("\n"+"="*55)
    print("  NEXUS FRAUD DETECTION AGENT (Gemini)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)
    if not SUPABASE_KEY or not GEMINI_KEY: print("ERROR: Set keys in .env"); return

    listings = sb_get("pg_listings")
    print(f"\nScanning {len(listings)} listings...")
    flagged=0

    for i,pg in enumerate(listings):
        name=pg.get("name","?")
        print(f"  [{i+1}/{len(listings)}] {name}...", end=" ", flush=True)
        result=ai_fraud_check(pg)
        score=result.get("fraud_score",0)
        verdict=result.get("verdict","clean")
        print(f"→ Score: {score}/100 | {verdict}")
        try:
            sb_patch("pg_listings",pg["id"],{
                "fraud_score":score,"fraud_verdict":verdict,
                "fraud_reason":result.get("reason",""),
                "needs_review": score>=60 or verdict!="clean",
                "fraud_checked_at":datetime.utcnow().isoformat()
            })
            if score>=60 or verdict!="clean":
                flagged+=1
                log(f"Flagged: {name}","warning",f"Score {score}/100 — {result.get('reason','')}")
                print(f"  *** FLAGGED ***")
        except Exception as e: print(f"  [ERR] {e}")

    log("Full scan","success",f"Scanned {len(listings)}, flagged {flagged}")
    print(f"\n  DONE! Scanned: {len(listings)} | Flagged: {flagged} | Clean: {len(listings)-flagged}")

if __name__ == "__main__":
    run_fraud_agent()
