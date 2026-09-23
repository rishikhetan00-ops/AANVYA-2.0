"""
core/cloud_sync.py — Universal 2-Way Real-Time Synchronization Engine
====================================================================
Synchronizes memory, shared tasks, skills/plugins, and Hermes deliverables
between Desktop AANVYA and the 24/7 Oracle Cloud VPS in Frankfurt.
"""

import os
import sys
import json
import time
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("AANVYA.CloudSync")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
PLUGINS_DIR = PROJECT_ROOT / "plugins"
SHARED_ACTIVITY_FILE = MEMORY_DIR / "shared_activity.json"
LOCAL_DELIVERABLES_DIR = Path.home() / "Desktop" / "Hermes_Output"

# VPS Connection Details
VPS_USER = "ubuntu"
VPS_IP = "130.61.42.202"
SSH_KEY_PATH = Path.home() / "OneDrive" / "Desktop" / "ssh-key-2026-09-23.key"
REMOTE_PROJECT_ROOT = "/home/ubuntu/AANVYA-2.0"

_SYNC_INTERVAL_SECONDS = 30
_sync_thread = None
_stop_event = threading.Event()

# ── Activity Ledger Utilities ────────────────────────────────────────────────

def load_shared_activity() -> Dict[str, Any]:
    if SHARED_ACTIVITY_FILE.exists():
        try:
            return json.loads(SHARED_ACTIVITY_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read shared_activity.json: {e}")
    return {"last_sync": "", "activities": [], "unseen_on_laptop": []}

def save_shared_activity(data: Dict[str, Any]) -> None:
    try:
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        SHARED_ACTIVITY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save shared_activity.json: {e}")

def record_activity(activity_type: str, title: str, summary: str, source: str = "desktop_laptop", files: List[str] = None) -> None:
    """Records an action or conversation turn into the shared activity ledger."""
    data = load_shared_activity()
    entry = {
        "id": f"act_{int(time.time() * 1000)}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "type": activity_type,
        "title": title,
        "summary": summary[:1000],
        "deliverable_files": files or []
    }
    data["activities"].insert(0, entry)
    data["activities"] = data["activities"][:50]
    save_shared_activity(data)

def get_recent_cross_device_context(max_items: int = 5) -> str:
    """Returns a clean formatted context string of recent cross-device activity for LLM prompt injection."""
    data = load_shared_activity()
    acts = data.get("activities", [])
    if not acts:
        return ""
    
    lines = ["Recent Cross-Device Activity (Telegram Cloud & Desktop Sync):"]
    for a in acts[:max_items]:
        src = "📱 Telegram (Phone)" if "telegram" in a.get("source", "").lower() else "💻 Desktop (Laptop)"
        lines.append(f"- [{a.get('timestamp')}] ({src}) {a.get('type').upper()}: *{a.get('title')}* — {a.get('summary')[:200]}")
    
    return "\n".join(lines)

def get_unseen_missions_summary() -> Optional[str]:
    """Returns a greeting summary if there are newly completed cloud missions since the laptop was last opened."""
    data = load_shared_activity()
    unseen = data.get("unseen_on_laptop", [])
    if not unseen:
        return None
    
    titles = [u.get("title", "Background Mission") for u in unseen]
    data["unseen_on_laptop"] = []
    save_shared_activity(data)
    
    if len(titles) == 1:
        return f"While you were away on your phone, Hermes completed: '{titles[0]}'."
    return f"While you were away on your phone, Hermes completed {len(titles)} tasks: {', '.join(titles)}."

# ── Universal 2-Way Sync Engine (Memory, Plugins, Skills & Deliverables) ─────

def run_sync_cycle() -> bool:
    """Executes a full 2-way sync with the Oracle Cloud VPS."""
    if not SSH_KEY_PATH.exists():
        logger.warning(f"SSH Key not found at {SSH_KEY_PATH}. Skipping cloud sync.")
        return False

    try:
        LOCAL_DELIVERABLES_DIR.mkdir(parents=True, exist_ok=True)
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        key_str = str(SSH_KEY_PATH)

        # 1. Pull remote memory/shared_activity.json from VPS
        remote_act = f"{VPS_USER}@{VPS_IP}:{REMOTE_PROJECT_ROOT}/memory/shared_activity.json"
        local_act = str(SHARED_ACTIVITY_FILE)
        cmd_pull_act = [
            "scp", "-i", key_str, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            remote_act, local_act
        ]
        subprocess.run(cmd_pull_act, capture_output=True, text=True)
        
        # 2. Pull remote memory/long_term.json from VPS
        remote_mem = f"{VPS_USER}@{VPS_IP}:{REMOTE_PROJECT_ROOT}/memory/long_term.json"
        local_mem = str(MEMORY_DIR / "long_term.json")
        cmd_pull_mem = [
            "scp", "-i", key_str, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            remote_mem, local_mem
        ]
        subprocess.run(cmd_pull_mem, capture_output=True, text=True)

        # 3. 2-Way Plugin & Skill Sync: Push local plugins to VPS
        for p in PLUGINS_DIR.glob("*.py"):
            if p.name.startswith("__"):
                continue
            remote_dest = f"{VPS_USER}@{VPS_IP}:{REMOTE_PROJECT_ROOT}/plugins/{p.name}"
            cmd_push_plugin = [
                "scp", "-i", key_str, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                str(p), remote_dest
            ]
            subprocess.run(cmd_push_plugin, capture_output=True, text=True)

        # 4. Pull any newly generated Hermes deliverables from VPS to Desktop/Hermes_Output/
        remote_deliverables = f"{VPS_USER}@{VPS_IP}:{REMOTE_PROJECT_ROOT}/storage/hermes_deliverables/*"
        cmd_pull_files = [
            "scp", "-i", key_str, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            remote_deliverables, str(LOCAL_DELIVERABLES_DIR)
        ]
        subprocess.run(cmd_pull_files, capture_output=True, text=True)

        logger.info("Universal 2-Way Sync (Memory + Plugins + Deliverables) completed.")
        return True

    except Exception as e:
        logger.error(f"Sync cycle error: {e}")
        return False

# ── Background Daemon Thread ─────────────────────────────────────────────────

def _sync_loop():
    logger.info("CloudSync daemon active. 2-way auto-syncing memory, plugins, and skills every 30s...")
    while not _stop_event.is_set():
        run_sync_cycle()
        for _ in range(_SYNC_INTERVAL_SECONDS):
            if _stop_event.is_set():
                break
            time.sleep(1)

def start_cloud_sync_daemon():
    global _sync_thread
    if _sync_thread is None or not _sync_thread.is_alive():
        _stop_event.clear()
        _sync_thread = threading.Thread(target=_sync_loop, daemon=True, name="AanvyaCloudSync")
        _sync_thread.start()
        logger.info("CloudSync daemon successfully initialized.")

def stop_cloud_sync_daemon():
    _stop_event.set()
    if _sync_thread:
        _sync_thread.join(timeout=3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Universal 2-Way Sync...")
    res = run_sync_cycle()
    print("Result:", "SUCCESS" if res else "FAILED")
