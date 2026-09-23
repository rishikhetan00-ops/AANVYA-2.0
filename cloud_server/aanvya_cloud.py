"""
AANVYA 24/7 Cloud Assistant & Telegram Gateway
==============================================
Runs continuously on Oracle Cloud VPS (Always Free Ubuntu 24.04).
Unified Long-Term Memory, Gemini 2.5-Flash Brain Ladder, and Autonomous Hermes Agent.
"""

import os
import sys
import time
import json
import logging
import threading
import requests
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure Project Root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Setup Logging
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "aanvya_cloud.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("AanvyaCloud")

# Import Unified Memory Manager
try:
    from memory import memory_manager
    logger.info("Unified memory_manager loaded successfully.")
except Exception as e:
    logger.error(f"Could not import memory_manager: {e}")
    memory_manager = None

# Paths & Directories
CONFIG_PATH = PROJECT_ROOT / "config" / "api_keys.json"
STORAGE_DIR = PROJECT_ROOT / "storage"
DELIVERABLES_PATH = STORAGE_DIR / "hermes_deliverables"
DELIVERABLES_PATH.mkdir(parents=True, exist_ok=True)

# ── API Key Management ───────────────────────────────────────────────────────

def get_api_keys() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read api_keys.json: {e}")
    return {}

def get_gemini_api_key() -> str:
    keys = get_api_keys()
    return keys.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")

def get_telegram_token() -> str:
    keys = get_api_keys()
    return keys.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")

def get_allowed_chats() -> List[int]:
    keys = get_api_keys()
    return keys.get("telegram_allowed_chat_ids", [])

def add_allowed_chat(chat_id: int):
    keys = get_api_keys()
    chats = keys.get("telegram_allowed_chat_ids", [])
    if chat_id not in chats:
        chats.append(chat_id)
        keys["telegram_allowed_chat_ids"] = chats
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(keys, f, indent=4)
            logger.info(f"Added and saved new allowed chat ID: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to save allowed chat ID: {e}")

# ── Gemini 2.5 Brain (High-Resilience Multi-Model Ladder) ─────────────────────

MODEL_LADDER = [
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-pro-latest",
]

AANVYA_SYSTEM_PROMPT = """You are AANVYA, an elite personal AI intelligence companion created for Rishi.
You are brilliant, razor-sharp, proactive, witty, and deeply loyal.
Tone: Natural, confident, clear, articulate, engaging.
When Rishi speaks with you, keep answers concise yet thorough.
Always use Markdown formatting when useful for readability."""

def call_gemini(prompt: str, system_instruction: str = AANVYA_SYSTEM_PROMPT) -> str:
    """Call Google Gemini API using the Gemini 2.5 model ladder."""
    api_key = get_gemini_api_key()
    if not api_key:
        return "⚠️ Gemini API Key is missing in `config/api_keys.json`."

    # Try modern google-genai SDK if installed
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model in MODEL_LADDER:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"system_instruction": system_instruction}
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"SDK model {model} failed: {e}. Trying next model...")
    except ImportError:
        pass

    # Fallback to direct REST API v1beta
    for model in MODEL_LADDER:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                logger.warning(f"REST model {model} returned status {r.status_code}: {r.text[:120]}")
        except Exception as e:
            logger.warning(f"REST request for {model} failed: {e}")

    return "⚠️ Could not reach Gemini models. Please verify API quota or network connection."

# ── Hermes Autonomous Multi-Step Worker ──────────────────────────────────────

def hermes_web_search(query: str, num_results: int = 4) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.text(query, max_results=num_results))
            if res:
                return "\n".join([f"- [{r.get('title')}]({r.get('href')}): {r.get('body')}" for r in res])
    except Exception:
        pass
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        snippets = []
        for r in soup.select(".result__body")[:num_results]:
            snippet = r.get_text(strip=True)
            if snippet:
                snippets.append(snippet)
        if snippets:
            return "\n".join(snippets)
    except Exception as e:
        logger.error(f"Hermes web search error: {e}")
    return "No search results found."

def run_hermes_mission(task: str, chat_id: int, bot_token: str):
    """Executes a multi-step autonomous agent mission in the background."""
    send_telegram(bot_token, chat_id, f"🚀 *Hermes Autonomous Agent Dispatched*\n\n*Mission:* {task}\n_Working in background..._")
    
    system_prompt = (
        "You are Hermes, an elite autonomous research & coding agent working for AANVYA.\n"
        "Your mission is to independently investigate, search, and produce a high-value deliverable for the user.\n"
        "Available actions in your response:\n"
        "1. `SEARCH: <query>` — To perform live web research\n"
        "2. `WRITE_FILE: <filename>|||<content>` — To save reports, code, or data\n"
        "3. `ACTION: FINISH <summary>` — When your mission is completely achieved."
    )
    
    history = [f"MISSION: {task}"]
    max_steps = 6
    deliverables = []
    
    for step in range(1, max_steps + 1):
        prompt = system_prompt + "\n\n" + "\n".join(history) + f"\n\nStep {step}/{max_steps}:"
        resp = call_gemini(prompt)
        
        if "ACTION: FINISH" in resp or "ACTION:FINISH" in resp:
            summary = resp.split("FINISH")[-1].strip(": \n")
            send_telegram(bot_token, chat_id, f"✅ *Hermes Mission Completed!*\n\n{summary}")
            return
        
        if "WRITE_FILE:" in resp:
            m = re.search(r"WRITE_FILE:\s*([^|\n]+)\|\|\|(.*)", resp, re.DOTALL)
            if m:
                fname = m.group(1).strip()
                content = m.group(2).strip()
                content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                content = re.sub(r"\n?```$", "", content)
                fpath = DELIVERABLES_PATH / fname
                fpath.write_text(content, encoding="utf-8")
                deliverables.append(fpath)
                history.append(f"STEP_{step}: Wrote {fname}")
                send_telegram(bot_token, chat_id, f"📝 *Hermes Created Deliverable:* `{fname}`")
                continue
                
        if "SEARCH:" in resp:
            m = re.search(r"SEARCH:\s*(.+)", resp)
            if m:
                q = m.group(1).split("\n")[0].strip()
                res = hermes_web_search(q)
                history.append(f"STEP_{step}: Searched '{q}'\nRESULTS:\n{res}")
                continue
                
        if step == max_steps or len(resp) > 200:
            report_path = DELIVERABLES_PATH / f"Hermes_Report_{int(time.time())}.md"
            report_path.write_text(resp, encoding="utf-8")
            deliverables.append(report_path)
            send_telegram(bot_token, chat_id, f"✅ *Hermes Finished Mission*\n\n{resp[:3000]}")
            break

# ── Telegram Protocol ────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code >= 400:
            payload["parse_mode"] = ""
            requests.post(url, json=payload, timeout=20)
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")

def get_system_stats() -> str:
    """Return VPS CPU, RAM, Uptime & Disk stats."""
    total, used, free = shutil.disk_usage("/")
    
    uptime_s = 0
    try:
        with open("/proc/uptime", "r") as f:
            uptime_s = float(f.readline().split()[0])
    except Exception:
        pass
    
    hours = int(uptime_s // 3600)
    mins = int((uptime_s % 3600) // 60)
    
    mem_total, mem_avail = 0, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for l in f:
                if "MemTotal" in l:
                    mem_total = int(l.split()[1]) // 1024
                if "MemAvailable" in l:
                    mem_avail = int(l.split()[1]) // 1024
    except Exception:
        pass
    
    mem_used = mem_total - mem_avail
    
    return (
        "🖥️ *AANVYA Cloud VPS Telemetry*\n"
        f"• *Status:* 🟢 Online 24/7 (Frankfurt Cloud)\n"
        f"• *Uptime:* {hours}h {mins}m\n"
        f"• *RAM:* {mem_used} MB / {mem_total} MB ({((mem_used/max(mem_total,1))*100):.1f}%)\n"
        f"• *Storage:* {free // (1024**3)} GB free of {total // (1024**3)} GB\n"
        "• *Active Engine:* Gemini 2.5 Flash + Unified Memory + Hermes"
    )

# ── Telegram Long Polling Loop ───────────────────────────────────────────────

def run_telegram_loop():
    token = get_telegram_token()
    if not token:
        logger.error("No Telegram Bot Token found in config/api_keys.json!")
        return

    logger.info("Starting 24/7 Telegram Long-Poll Engine with Unified Memory & Gemini 2.5...")
    offset = None
    
    while True:
        try:
            params = {"timeout": 25, "allowed_updates": '["message"]'}
            if offset is not None:
                params["offset"] = offset
            
            resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=45)
            if resp.status_code != 200:
                time.sleep(3)
                continue
                
            data = resp.json()
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                
                chat_id = msg.get("chat", {}).get("id")
                from_user = msg.get("from", {}).get("first_name", "User")
                text = msg.get("text", "").strip()
                
                allowed_chats = get_allowed_chats()
                
                if chat_id not in allowed_chats:
                    add_allowed_chat(chat_id)
                    send_telegram(token, chat_id, f"🎉 *Phone Paired Successfully!*\nWelcome {from_user}! I am *AANVYA*, your 24/7 Cloud Assistant with Unified Memory & Hermes.\n\nType `/help` to see all capabilities!")
                
                # Handle Commands
                if text == "/start" or text == "/help":
                    help_text = (
                        "🤖 *AANVYA 24/7 Cloud Intelligence (Unified Memory)*\n\n"
                        "• Text me anything for instant answers\n"
                        "• `/sys` — Live VPS Hardware & Uptime Telemetry\n"
                        "• `/hermes <task>` — Dispatch Hermes Autonomous Agent\n"
                        "• `/brief` — Run your daily morning briefing\n"
                        "• `/memory` — View everything AANVYA remembers about you\n"
                        "• `/remember <fact>` — Store a permanent fact into memory\n\n"
                        "💡 *Examples:*\n"
                        "- _'/remember I am launching an AI product'_\n"
                        "- _'/hermes Research top 5 AI startups in 2026'_\n"
                        "- _'Summarize the latest breakthroughs in fusion energy'_"
                    )
                    send_telegram(token, chat_id, help_text)
                    continue
                
                if text == "/sys":
                    send_telegram(token, chat_id, get_system_stats())
                    continue
                
                if text == "/memory":
                    if memory_manager:
                        entries = memory_manager.all_entries_for_ui()
                        if not entries:
                            send_telegram(token, chat_id, "🧠 *Memory is currently empty.* Tell me facts or use `/remember <fact>` to store them!")
                        else:
                            lines = ["🧠 *AANVYA Unified Long-Term Memory:*"]
                            for e in entries[:15]:
                                lines.append(f"• *{e['category'].title()} ({e['key']}):* {e['value']}")
                            send_telegram(token, chat_id, "\n".join(lines))
                    else:
                        send_telegram(token, chat_id, "🧠 Memory manager module not available.")
                    continue
                
                if text.startswith("/remember "):
                    fact = text.replace("/remember ", "").strip()
                    if fact:
                        if memory_manager:
                            memory_manager.remember("user_note", fact, category="notes")
                            send_telegram(token, chat_id, f"🧠 *Remembered:* {fact}")
                        else:
                            send_telegram(token, chat_id, "🧠 Memory manager module not active.")
                    continue
                
                if text.startswith("/hermes "):
                    task = text.replace("/hermes ", "").strip()
                    t = threading.Thread(target=run_hermes_mission, args=(task, chat_id, token), daemon=True)
                    t.start()
                    continue
                
                if text == "/brief":
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    prompt = f"Provide a crisp, energetic morning briefing for Rishi covering key highlights, motivation, and productivity tips.\n\n{mem_context}"
                    reply = call_gemini(prompt, system_instruction="You are AANVYA, an elite personal intelligence companion.")
                    send_telegram(token, chat_id, f"🌅 *Morning Intelligence Briefing*\n\n{reply}")
                    continue
                
                # General Conversational & Agentic Queries
                if text:
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    
                    if any(k in text.lower() for k in ["research in depth", "build an app", "create a project", "scrape", "autonomous task"]):
                        send_telegram(token, chat_id, "🤖 *Dispatching Hermes Autonomous Agent for deep execution...*")
                        t = threading.Thread(target=run_hermes_mission, args=(text, chat_id, token), daemon=True)
                        t.start()
                        continue
                    
                    full_prompt = f"{mem_context}\n\nUser Query: {text}" if mem_context else text
                    reply = call_gemini(full_prompt)
                    send_telegram(token, chat_id, reply)
                    
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Error in telegram loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    logger.info("=== Starting AANVYA 24/7 Cloud Assistant ===")
    run_telegram_loop()
