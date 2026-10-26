import os
import sys
from pathlib import Path

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import time
from sqlmodel import Session, select
from app.db import engine
from app.models import Application
from app.pipeline.run import run_pipeline

def run_benchmark():
    with Session(engine) as session:
        apps = session.exec(select(Application).order_by(Application.id)).all()
        
        stages = ["extract", "quality", "checks", "rules", "forensics", "verify", "entities", "risk"]
        app_results = []
        stage_totals = {s: 0.0 for s in stages}
        
        wall_clock_start = time.perf_counter()
        
        for app in apps:
            res = run_pipeline(app.id, session)
            st = res.get("stage_times", {})
            for s in stages:
                stage_totals[s] += st.get(s, 0.0)
            app_results.append({
                "inst": app.institution_id,
                "times": st,
                "total": res.get("total_time", 0.0),
                "risk": res.get("risk_band")
            })
            
        wall_clock_total = time.perf_counter() - wall_clock_start
        
        print("\n### Full Re-run Timing Table (Per-Stage Breakdown)\n")
        header = f"| Application | " + " | ".join(f"{s.capitalize()} (s)" for s in stages) + " | Total (s) | Risk Band |"
        sep = "|:---|:" + ":|:".join("-" * max(len(s) + 4, 7) for s in stages) + ":|:---:|:---:|"
        print(header)
        print(sep)
        
        for r in app_results:
            row_vals = [f"{r['times'].get(s, 0.0):.3f}" for s in stages]
            print(f"| **{r['inst']}** | " + " | ".join(row_vals) + f" | **{r['total']:.3f}** | {r['risk']} |")
            
        total_row = [f"{stage_totals[s]:.3f}" for s in stages]
        total_sum = sum(stage_totals.values())
        print(f"| **TOTAL** | " + " | ".join(total_row) + f" | **{total_sum:.3f}** | - |")
        print(f"\n**Wall Clock Total:** {wall_clock_total:.3f} s\n")

if __name__ == "__main__":
    run_benchmark()
