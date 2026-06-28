import json
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "committee_iterations"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_iteration(prompt_id: str, committee_results: dict):
    """序列化儲存委員會審查軌跡"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"{prompt_id}_{timestamp}.json"
    
    data = {
        "timestamp": timestamp,
        "prompt_id": prompt_id,
        "results": committee_results
    }
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(log_file)
