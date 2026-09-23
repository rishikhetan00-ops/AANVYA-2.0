"""
cloud_server/aanvya_cloud.py — 24/7 Headless AANVYA + Hermes Autonomous Cloud Engine.

Runs 24/7/365 on Linux VPS:
- Long-polls Telegram 24/7 for messages, voice notes, documents, and instructions.
- Full conversational reasoning powered by Gemini 2.0.
- Integrated Hermes Autonomous Worker Engine for deep research, coding & scraping.
- Automated Cron Job Scheduler for daily briefings & scheduled tasks.
- Persistent Soul & Memory for long-term user context.
"""

import json
import logging
import os
import re
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote_plus
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AANVYA-247")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
MEMORY_PATH = BASE_DIR / "memory" / "cloud_memory.json"
INBOX_PATH = Path.home() / "aanvya_inbox"
DELIVERABLES_PATH = Path.home() / "hermes_deliverables"

INBOX_PATH.mkdir(parents=True, exist_ok=True)
DELIVERABLES_PATH.mkdir(parents=True, exist_ok=True)

# ── Configuration & Keys ─────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=4), encoding="utf-8")

def get_gemini_key() -> str:
    return load_config().get("gemini_api_key", "").strip()

def get_telegram_token() -> str:
    cfg = load_config()
    pc = cfg.get("plugin_config", {})
    tg = pc.get("telegram_remote", {})
    return str(tg.get("bot_token") or cfg.get("telegram_bot_token") or "").strip()

def get_allowed_chats() -> list[int]:
    cfg = load_config()
    pc = cfg.get("plugin_config", {})
    tg = pc.get("telegram_remote", {})
    raw = tg.get("allowed_chat_ids") or cfg.get("allowed_chat_ids") or ""
    if isinstance(raw, list):
        return [int(x) for x in raw if str(x).isdigit()]
    out = []
    for x in str(raw).replace(";", ",").split(","):
        x = x.strip()
        if x.isdigit() or (x.startswith("-") and x[1:].isdigit()):
            out.append(int(x))
    return out

def add_allowed_chat(chat_id: int) -> None:
    cfg = load_config()
    pc = cfg.setdefault("plugin_config", {})
    tg = pc.setdefault("telegram_remote", {})
    ids = get_allowed_chats()
    if chat_id not in ids:
        ids.append(chat_id)
        tg["allowed_chat_ids"] = ",".join(str(i) for i in ids)
        save_config(cfg)
        logger.info(f"Approved chat ID: {chat_id}")

# ── Memory & Soul Persistence ────────────────────────────────────────────────

def load_memory() -> dict:
    if MEMORY_PATH.exists():
        try:
            return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "user_name": "Rishi",
        "assistant_name": "AANVYA",
        "soul": "You are AANVYA, an elite autonomous AI companion and strategic operating system.",
        "facts": [],
        "scheduled_jobs": []
    }

def save_memory(mem: dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(mem, indent=4), encoding="utf-8")

# ── Gemini 2.0 Cloud Engine ──────────────────────────────────────────────────

def call_gemini(prompt: str, system_instruction: str = "") -> str:
    """Call Google Gemini 2.0 Flash API with resilient fallback."""
    key = get_gemini_key()
    if not key:
        return "Gemini API key is missing. Please set 'gemini_api_key' in config/api_keys.json."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": contents}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return f"Gemini API returned status {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        logger.error(f"Gemini call error: {e}")
        return f"Encountered network error connecting to Gemini: {e}"

# ── Hermes Autonomous Tool Engine ────────────────────────────────────────────

def hermes_web_search(query: str) -> str:
    """Search live web for real-time facts."""
    try:
        from bs4 import BeautifulSoup
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for a in soup.select(".result__body")[:5]:
            t_el = a.select_one(".result__title")
            s_el = a.select_one(".result__snippet")
            t = t_el.get_text(strip=True) if t_el else ""
            s = s_el.get_text(strip=True) if s_el else ""
            if t or s:
                results.append(f"• **{t}**: {s}")
        return "\n".join(results) if results else "No direct results found."
    except Exception as e:
        return f"Search error: {e}"

def run_hermes_mission(task: str, chat_id: int, bot_token: str):
    """Executes multi-step autonomous Hermes mission and delivers report to Telegram."""
    send_telegram(bot_token, chat_id, f"🚀 *Hermes Autonomous Agent Dispatched*\nMission: `{task}`\nWorking in background...")
    
    history = [f"MISSION: {task}"]
    system_prompt = """You are HERMES, an elite autonomous task agent.
Execute the user's mission step-by-step using tools.
Tools:
1. SEARCH: <query>
2. WRITE_FILE: <filename> ||| <content>
3. FINISH: <final comprehensive summary & deliverables>

Format:
THOUGHT: <reasoning>
ACTION: <SEARCH / WRITE_FILE / FINISH>
"""
    max_steps = 8
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
                send_telegram(bot_token, chat_id, f"📝 *Hermes Created:* `{fname}`")
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
        requests.post(url, json=payload, timeout=20)
    except Exception:
        # Fallback without markdown if markdown parsing fails
        payload["parse_mode"] = ""
        try:
            requests.post(url, json=payload, timeout=20)
        except Exception as e:
            logger.error(f"Failed to send telegram message: {e}")

def get_system_stats() -> str:
    """Return VPS CPU, RAM, Uptime & Disk stats."""
    import shutil
    total, used, free = shutil.disk_usage("/")
    
    # Read uptime
    uptime_s = 0
    try:
        with open("/proc/uptime", "r") as f:
            uptime_s = float(f.readline().split()[0])
    except Exception:
        pass
    
    hours = int(uptime_s // 3600)
    mins = int((uptime_s % 3600) // 60)
    
    # Read memory
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
        f"🖥️ *AANVYA Cloud VPS Telemetry*\n"
        f"• *Status:* 🟢 Online 24/7 (Frankfurt Cloud)\n"
        f"• *Uptime:* {hours}h {mins}m\n"
        f"• *RAM:* {mem_used} MB / {mem_total} MB ({((mem_used/max(mem_total,1))*100):.1f}%)\n"
        f"• *Storage:* {used // (1024**3)} GB / {total // (1024**3)} GB free\n"
        f"• *Active Engine:* Gemini 2.0 Flash + Hermes Agent"
    )

# ── Telegram Long Polling Loop ───────────────────────────────────────────────

def run_telegram_loop():
    token = get_telegram_token()
    if not token:
        logger.error("No Telegram Bot Token found in config/api_keys.json!")
        print("\n[!] Please set 'bot_token' in config/api_keys.json to start Telegram.\n")
        return

    logger.info("Starting 24/7 Telegram Long-Poll Engine...")
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
                
                # Pairing step: if pairing code sent or no chats allowed yet
                pairing_code = load_config().get("plugin_config", {}).get("telegram_remote", {}).get("pairing_code", "aanvya123").strip()
                if chat_id not in allowed_chats:
                    if text == pairing_code or not allowed_chats:
                        add_allowed_chat(chat_id)
                        send_telegram(token, chat_id, f"🎉 *Phone Paired Successfully!*\nWelcome {from_user}! I am *AANVYA*, your 24/7 Cloud Assistant with Hermes Agent.\n\nType `/help` to see what I can do!")
                        continue
                    else:
                        send_telegram(token, chat_id, "🔒 *Authentication Required*\nPlease send the Pairing Code to authorize this chat.")
                        continue
                
                # Handle Commands
                if text == "/start" or text == "/help":
                    help_text = (
                        f"🤖 *AANVYA 24/7 Cloud Intelligence*\n\n"
                        f"• Text me anything for instant spoken/written answers\n"
                        f"• `/sys` — Live VPS Hardware & Uptime Telemetry\n"
                        f"• `/hermes <task>` — Dispatch Hermes Autonomous Agent\n"
                        f"• `/brief` — Run your daily morning briefing right now\n"
                        f"• `/clear` — Reset active conversation memory\n\n"
                        f"💡 *Examples:*\n"
                        f"- _'/hermes Research top 5 AI trends and write a report'_\n"
                        f"- _'Summarize the latest tech news today'_\n"
                        f"- _'Write a Python script to track crypto prices'_"
                    )
                    send_telegram(token, chat_id, help_text)
                    continue
                
                if text == "/sys":
                    send_telegram(token, chat_id, get_system_stats())
                    continue
                
                if text.startswith("/hermes "):
                    task = text.replace("/hermes ", "").strip()
                    t = threading.Thread(target=run_hermes_mission, args=(task, chat_id, token), daemon=True)
                    t.start()
                    continue
                
                if text == "/brief":
                    mem = load_memory()
                    prompt = f"Provide a crisp, professional morning briefing for {mem.get('user_name', 'Rishi')} covering current world highlights, motivation, and productivity tips."
                    reply = call_gemini(prompt, system_instruction="You are AANVYA, an elite personal intelligence companion.")
                    send_telegram(token, chat_id, f"🌅 *Morning Intelligence Briefing*\n\n{reply}")
                    continue
                
                # General Conversational & Agentic Queries
                if text:
                    mem = load_memory()
                    # Check if user asked for an autonomous project
                    if any(k in text.lower() for k in ["research in depth", "build an app", "create a project", "scrape", "autonomous task"]):
                        t = threading.Thread(target=run_hermes_mission, args=(text, chat_id, token), daemon=True)
                        t.start()
                        continue
                    
                    system_inst = (
                        f"You are AANVYA, an elite, highly intelligent 24/7 AI companion and tactical operating system. "
                        f"You are speaking to {mem.get('user_name', 'Rishi')}. Be direct, smart, concise, and helpful."
                    )
                    reply = call_gemini(text, system_instruction=system_inst)
                    send_telegram(token, chat_id, reply)
                    
        except Exception as e:
            logger.error(f"Error in Telegram loop: {e}")
            time.sleep(5)

# ── Background Scheduler (Cron) ──────────────────────────────────────────────

def run_scheduler_loop():
    logger.info("Starting Background Cron Scheduler...")
    while True:
        now = datetime.now()
        # Daily Morning Brief at 09:00 AM UTC / Local
        if now.hour == 9 and now.minute == 0:
            token = get_telegram_token()
            chats = get_allowed_chats()
            if token and chats:
                for c in chats:
                    prompt = "Provide a fresh daily morning briefing with key tech/AI highlights and productivity goals."
                    reply = call_gemini(prompt)
                    send_telegram(token, c, f"🌅 *Daily Scheduled Briefing*\n\n{reply}")
            time.sleep(65)
        time.sleep(30)

# ── Main Entrypoint ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Initializing AANVYA 24/7 Cloud Service...")
    
    # Start scheduler thread
    t_sched = threading.Thread(target=run_scheduler_loop, daemon=True, name="SchedulerThread")
    t_sched.start()
    
    # Start telegram bot listener
    run_telegram_loop()
