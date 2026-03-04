"""
NEXUS AGENT ORCHESTRATOR - Gemini Version
Usage: python run_all_agents.py [all|pricing|fraud|vacancy]
"""
import sys, time
from datetime import datetime

def run_all():
    print("\n"+"="*55)
    print("  NEXUS AGENTIC AI — NIGHTLY RUN (Gemini)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    print("\n[1/3] Pricing Intelligence Agent...")
    try:
        from pricing_agent import run_pricing_agent; run_pricing_agent()
        print("  SUCCESS")
    except Exception as e: print(f"  FAILED: {e}")
    time.sleep(2)

    print("\n[2/3] Fraud Detection Agent...")
    try:
        from fraud_agent import run_fraud_agent; run_fraud_agent()
        print("  SUCCESS")
    except Exception as e: print(f"  FAILED: {e}")
    time.sleep(2)

    print("\n[3/3] Vacancy Monitor Agent...")
    try:
        from vacancy_agent import run_vacancy_agent; run_vacancy_agent()
        print("  SUCCESS")
    except Exception as e: print(f"  FAILED: {e}")

    print("\n  ALL AGENTS COMPLETE!")

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv)>1 else "all"
    if arg=="pricing":
        from pricing_agent import run_pricing_agent; run_pricing_agent()
    elif arg=="fraud":
        from fraud_agent import run_fraud_agent; run_fraud_agent()
    elif arg=="vacancy":
        from vacancy_agent import run_vacancy_agent; run_vacancy_agent()
    else:
        run_all()
