"""
AANVYA 24/7 Cloud Assistant & Business Automation Engine (2-Way Synced)
=======================================================================
Runs continuously on Oracle Cloud Always Free Ubuntu VPS.
Features:
- Gemini Flash 3.x / Flash-Latest Brain Ladder
- FLUX.1 Photorealistic AI Image Generation (`/image`)
- Microsoft Edge-TTS Voice Note Replies (`/voice`, `/voicemode`)
- Autonomous Background Cron Scheduler (Daily briefings, Market trends)
- Hermes Autonomous Agent (`/hermes <mission>`)
- Autonomous Business Monetization Idea Engine (`/ideas`, `/venture`)
- 2-Way Real-Time Synchronization with Laptop AANVYA (`shared_activity.json`)
"""

import os
import sys
import time
import json
import logging
import threading
import asyncio
import requests
import re
import shutil
import datetime
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
MEDIA_DIR = STORAGE_DIR / "cloud_media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
SHARED_ACTIVITY_FILE = PROJECT_ROOT / "memory" / "shared_activity.json"

# ── Activity Ledger for 2-Way Laptop Synchronization ─────────────────────────

def record_shared_activity(activity_type: str, title: str, summary: str, source: str = "telegram_cloud", files: List[str] = None):
    """Records an activity or deliverable on the cloud so the laptop receives it on sync."""
    try:
        data = {"last_sync": "", "activities": [], "unseen_on_laptop": []}
        if SHARED_ACTIVITY_FILE.exists():
            try:
                data = json.loads(SHARED_ACTIVITY_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        entry = {
            "id": f"act_{int(time.time() * 1000)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "type": activity_type,
            "title": title,
            "summary": summary[:1200],
            "deliverable_files": files or []
        }
        
        if "activities" not in data:
            data["activities"] = []
        if "unseen_on_laptop" not in data:
            data["unseen_on_laptop"] = []
            
        data["activities"].insert(0, entry)
        data["activities"] = data["activities"][:50]
        data["unseen_on_laptop"].append(entry)
        data["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        SHARED_ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        SHARED_ACTIVITY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Recorded shared activity: [{activity_type}] {title}")
    except Exception as e:
        logger.error(f"Failed to record shared activity: {e}")

# ── Configuration & Keys ─────────────────────────────────────────────────────

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
            logger.info(f"Added and saved allowed chat ID: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to save allowed chat ID: {e}")

VOICE_MODE_ENABLED = False

# ── Gemini Brain Ladder ──────────────────────────────────────────────────────

MODEL_LADDER = [
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-pro-latest",
]

AANVYA_SYSTEM_PROMPT = """You are AANVYA, an elite, ultra-competent AI intelligence companion and business automation engine created for Rishi.
You are brilliant, loyal, razor-sharp, proactive, witty, and strategic.
You operate across Cloud (Telegram) and Desktop (Laptop) with unified continuous memory.
Tone: Natural, articulate, confident, encouraging, concise yet thorough."""

def call_gemini(prompt: str, system_instruction: str = AANVYA_SYSTEM_PROMPT) -> str:
    """Call Google Gemini API using the Gemini 3.x/Flash-Latest model ladder."""
    api_key = get_gemini_api_key()
    if not api_key:
        return "⚠️ Gemini API Key is missing in `config/api_keys.json`."

    for model in MODEL_LADDER:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        try:
            r = requests.post(url, json=payload, timeout=35)
            if r.status_code == 200:
                data = r.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
            else:
                logger.warning(f"Model {model} status {r.status_code}. Trying fallback...")
        except Exception as e:
            logger.warning(f"Request for {model} failed: {e}")

    return "⚠️ Could not reach Gemini models. Please check network/quota."

# ── FLUX.1 Photorealistic AI Image Generator ─────────────────────────────────

def generate_flux_image(prompt: str, filename_prefix: str = "flux") -> Optional[Path]:
    """Generates a photorealistic AI image using FLUX.1 engine."""
    clean_prompt = re.sub(r"[^\w\s,-]", "", prompt).strip()
    encoded = requests.utils.quote(clean_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true&seed={int(time.time())}"
    
    out_file = MEDIA_DIR / f"{filename_prefix}_{int(time.time())}.jpg"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code == 200 and len(r.content) > 5000:
            out_file.write_bytes(r.content)
            record_shared_activity("image_generation", f"Image: {clean_prompt[:50]}", f"Generated FLUX image for: {clean_prompt}", files=[out_file.name])
            return out_file
    except Exception as e:
        logger.error(f"FLUX image generation error: {e}")
    return None

# ── Microsoft Edge-TTS Voice Audio Notes ────────────────────────────────────

async def _synthesize_voice_async(text: str, out_path: Path, voice: str = "en-IN-NeerjaNeural"):
    import edge_tts
    clean_text = re.sub(r"[*_`#~>-]", "", text).strip()
    communicate = edge_tts.Communicate(clean_text[:800], voice)
    await communicate.save(str(out_path))

def generate_voice_note(text: str, language: str = "en") -> Optional[Path]:
    """Synthesizes high-definition voice audio note."""
    voice = "hi-IN-SwaraNeural" if language == "hi" or any("\u0900" <= c <= "\u097F" for c in text) else "en-IN-NeerjaNeural"
    out_file = MEDIA_DIR / f"voice_{int(time.time())}.ogg"
    try:
        asyncio.run(_synthesize_voice_async(text, out_file, voice=voice))
        if out_file.exists() and out_file.stat().st_size > 1000:
            return out_file
    except Exception as e:
        logger.error(f"Edge-TTS synthesis error: {e}")
    return None

# ── Telegram Protocol & Media Dispatch ───────────────────────────────────────

def send_telegram_text(token: str, chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    """Sends text message to Telegram, automatically converting headers and chunking long messages."""
    if not text:
        return

    # Convert markdown headers '### Title' into '*Title*' for clean Telegram rendering
    formatted_text = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)
    
    # Split into chunks under 3800 characters if message is large
    chunks = []
    if len(formatted_text) <= 3800:
        chunks = [formatted_text]
    else:
        parts = formatted_text.split("\n\n")
        current_chunk = ""
        for p in parts:
            if len(current_chunk) + len(p) + 2 < 3800:
                current_chunk += (("\n\n" if current_chunk else "") + p)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = p
        if current_chunk:
            chunks.append(current_chunk)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in chunks:
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        try:
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code >= 400:
                payload["parse_mode"] = ""
                requests.post(url, json=payload, timeout=20)
        except Exception as e:
            logger.error(f"Failed to send telegram message chunk: {e}")

def send_telegram_photo(token: str, chat_id: int, photo_path: Path, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"}
            r = requests.post(url, data=data, files=files, timeout=30)
            return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send telegram photo: {e}")
        return False

def send_telegram_voice(token: str, chat_id: int, audio_path: Path, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendVoice"
    try:
        with open(audio_path, "rb") as f:
            files = {"voice": f}
            data = {"chat_id": chat_id, "caption": caption[:1024]}
            r = requests.post(url, data=data, files=files, timeout=30)
            return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send telegram voice: {e}")
        return False

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
        f"• *Sync Bridge:* 🔄 2-Way Sync Active with Laptop\n"
        f"• *Uptime:* {hours}h {mins}m\n"
        f"• *RAM:* {mem_used} MB / {mem_total} MB ({((mem_used/max(mem_total,1))*100):.1f}%)\n"
        f"• *Storage:* {free // (1024**3)} GB free of {total // (1024**3)} GB\n"
        "• *Engines:* Gemini Flash 3.x + FLUX.1 + Edge-TTS + Hermes Autonomous Agent"
    )

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
    """Executes a multi-step autonomous agent mission with terminal execution in the background."""
    send_telegram_text(bot_token, chat_id, f"🚀 *Hermes Autonomous Agent Dispatched*\n\n*Mission:* {task}\n_Executing with live Linux terminal & web search..._")
    
    system_prompt = (
        "You are Hermes, an elite autonomous software engineer, researcher & business operator working for AANVYA.\n"
        "You have full access to a live Linux VPS terminal and tools to independently execute missions.\n\n"
        "Available Actions (choose ONE per step):\n"
        "1. `BASH: <linux command>` — Execute terminal commands, run python scripts, pip install libraries, test code\n"
        "2. `SEARCH: <query>` — Search live web for data, news, docs, pricing\n"
        "3. `WRITE_FILE: <filename>|||<content>` — Write code, scripts, HTML/CSS landing pages, or reports\n"
        "4. `IMAGE: <prompt>` — Generate photorealistic FLUX.1 image\n"
        "5. `ACTION: FINISH <summary>` — When your mission is 100% complete and deliverables are ready.\n\n"
        "Format:\n"
        "THOUGHT: <your reasoning>\n"
        "ACTION: <action string>"
    )
    
    history = [f"MISSION: {task}"]
    max_steps = 6
    deliverables = []
    
    for step in range(1, max_steps + 1):
        prompt = system_prompt + "\n\n" + "\n".join(history) + f"\n\nStep {step}/{max_steps}:"
        resp = call_gemini(prompt)
        
        if "ACTION: FINISH" in resp or "ACTION:FINISH" in resp:
            summary = resp.split("FINISH")[-1].strip(": \n")
            send_telegram_text(bot_token, chat_id, f"✅ *Hermes Mission Completed!*\n\n{summary}")
            record_shared_activity("hermes_mission", f"Hermes: {task[:50]}", summary, files=[p.name for p in deliverables])
            return
        
        if "BASH:" in resp:
            m = re.search(r"BASH:\s*(.+)", resp, re.DOTALL)
            if m:
                cmd = m.group(1).split("\n")[0].strip()
                import subprocess
                try:
                    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=str(DELIVERABLES_PATH))
                    out = (p.stdout + "\n" + p.stderr).strip()
                    if not out:
                        out = f"(Command completed with exit code {p.returncode})"
                    history.append(f"STEP_{step}: Executed bash '{cmd}'\nTERMINAL_OUTPUT:\n{out[:1500]}")
                    send_telegram_text(bot_token, chat_id, f"⚙️ *Hermes Ran Terminal Command:*\n`{cmd[:100]}`\n```\n{out[:400]}\n```")
                    continue
                except Exception as e:
                    history.append(f"STEP_{step}: Bash error: {e}")
                    continue

        if "IMAGE:" in resp:
            m = re.search(r"IMAGE:\s*(.+)", resp)
            if m:
                img_prompt = m.group(1).split("\n")[0].strip()
                img_path = generate_flux_image(img_prompt)
                if img_path:
                    send_telegram_photo(bot_token, chat_id, img_path, caption=f"🎨 *Hermes Generated Image:* {img_prompt[:100]}")
                    history.append(f"STEP_{step}: Generated image for '{img_prompt}'")
                    continue

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
                send_telegram_text(bot_token, chat_id, f"📝 *Hermes Created Deliverable:* `{fname}`")
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
            send_telegram_text(bot_token, chat_id, f"✅ *Hermes Finished Mission*\n\n{resp[:3000]}")
            record_shared_activity("hermes_mission", f"Hermes: {task[:50]}", resp[:1000], files=[p.name for p in deliverables])
            break

# ── Autonomous Business & Moneymaking Idea Generator ─────────────────────────

def generate_business_ventures(focus_area: str = "AI Automation & Lead Generation") -> str:
    """Generates lucrative, actionable, high-margin business ideas that AANVYA and Hermes can automate."""
    prompt = f"""Generate 3 highly lucrative, ultra-practical AI Automation Business models specifically tailored for Rishi (AI Agency Founder).
For each business idea:
1. 💡 **Business Concept & Monetization** (What service is sold and typical pricing, e.g. $500 - $3,000/mo)
2. 🤖 **How AANVYA & Hermes Automate It 100%** (Lead scraping from Google Maps, instant tailored demo website creation, automated outreach)
3. 🚀 **Immediate Action Step to Start Right Now** (The exact prompt to dispatch Hermes to build the first batch of client leads or prototype)

Keep it razor-sharp, realistic, high-margin, and inspiring. Focus area: {focus_area}"""
    
    ideas = call_gemini(prompt, system_instruction="You are AANVYA, an elite business strategist and AI agency architect.")
    record_shared_activity("business_ideas", f"Ideas: {focus_area[:40]}", ideas[:1000])
    return ideas

# ── Background Cron Scheduler ────────────────────────────────────────────────

def run_cron_scheduler():
    """Autonomous background scheduler for daily briefings and intelligence tasks."""
    token = get_telegram_token()
    if not token:
        return
    
    logger.info("Autonomous Cron Scheduler thread active.")
    last_briefing_date = None
    
    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            allowed_chats = get_allowed_chats()
            
            # Daily Morning Briefing at 08:30 AM
            if now.hour == 8 and now.minute == 30 and last_briefing_date != today_str:
                last_briefing_date = today_str
                for cid in allowed_chats:
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    
                    prompt = f"Deliver an inspiring, high-energy morning briefing for Rishi covering global tech highlights, agency monetization goals, and a sharp mindset tip.\n\n{mem_context}"
                    briefing = call_gemini(prompt)
                    send_telegram_text(token, cid, f"🌅 *Scheduled Morning Intelligence Briefing*\n\n{briefing}")
                    record_shared_activity("daily_briefing", "Morning Briefing", briefing[:400])
            
            time.sleep(45)
        except Exception as e:
            logger.error(f"Cron scheduler error: {e}")
            time.sleep(60)

# ── Telegram Long Polling Loop ───────────────────────────────────────────────

def run_telegram_loop():
    global VOICE_MODE_ENABLED
    token = get_telegram_token()
    if not token:
        logger.error("No Telegram Bot Token found in config/api_keys.json!")
        return

    logger.info("Starting 24/7 Telegram Engine (Gemini 3.x + FLUX.1 + Voice + Cron + 2-Way Sync)...")
    offset = None
    
    # Start Cron Scheduler in background thread
    cron_thread = threading.Thread(target=run_cron_scheduler, daemon=True, name="CronScheduler")
    cron_thread.start()
    
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
                    send_telegram_text(token, chat_id, f"🎉 *Phone Paired Successfully!*\nWelcome {from_user}! I am *AANVYA*, your 24/7 Cloud Assistant with FLUX.1 Image Gen, Voice Notes & 2-Way Laptop Sync.\n\nType `/help` to see all capabilities!")
                
                # ── Commands ────────────────────────────────────────────────
                if text == "/start" or text == "/help":
                    help_text = (
                        "🤖 *AANVYA 24/7 Cloud Intelligence & Business Engine*\n\n"
                        "• Text me anything for instant answers\n"
                        "• `/image <prompt>` — 🎨 Generate photorealistic FLUX.1 AI images\n"
                        "• `/voice <text>` — 🎙️ Get an instant spoken voice audio note\n"
                        "• `/voicemode` — 🔊 Toggle automatic voice notes ON/OFF\n"
                        "• `/ideas` — 💡 Generate automated AI Agency business ventures\n"
                        "• `/hermes <task>` — 🚀 Dispatch Hermes Autonomous Agent\n"
                        "• `/brief` — 🌅 Run your personalized daily morning briefing\n"
                        "• `/memory` — 🧠 View stored long-term memory & founder goals\n"
                        "• `/remember <fact>` — 📌 Store a permanent fact into memory\n"
                        "• `/sys` — 🖥️ Live VPS Hardware, Uptime & Sync Telemetry\n\n"
                        "💡 *Examples:*\n"
                        "- _'/image Futuristic cybernetic supercar on a rainy Tokyo street'_\n"
                        "- _'/ideas High ticket b2b lead automation'_\n"
                        "- _'/hermes Scrape top 5 dental clinics in Frankfurt and write a website pitch'_"
                    )
                    send_telegram_text(token, chat_id, help_text)
                    continue
                
                if text == "/sys":
                    send_telegram_text(token, chat_id, get_system_stats())
                    continue
                
                if text == "/voicemode":
                    VOICE_MODE_ENABLED = not VOICE_MODE_ENABLED
                    status = "🔊 ON (I will send audio voice notes with text)" if VOICE_MODE_ENABLED else "🔇 OFF (Text only)"
                    send_telegram_text(token, chat_id, f"Voice Mode is now *{status}*.")
                    continue
                
                if text.startswith("/voice "):
                    v_text = text.replace("/voice ", "").strip()
                    if v_text:
                        send_telegram_text(token, chat_id, "🎙️ _Recording voice note..._")
                        audio = generate_voice_note(v_text)
                        if audio:
                            send_telegram_voice(token, chat_id, audio, caption=v_text[:100])
                        else:
                            send_telegram_text(token, chat_id, "⚠️ Voice synthesis failed.")
                    continue

                if text.startswith("/image "):
                    img_prompt = text.replace("/image ", "").strip()
                    if img_prompt:
                        send_telegram_text(token, chat_id, f"🎨 *Generating FLUX.1 Image:*\n_{img_prompt}_\n_Rendering high-definition visual..._")
                        img_path = generate_flux_image(img_prompt)
                        if img_path:
                            send_telegram_photo(token, chat_id, img_path, caption=f"✨ *FLUX.1 Render:* {img_prompt}")
                        else:
                            send_telegram_text(token, chat_id, "⚠️ Image generation failed. Please try again.")
                    continue
                
                if text == "/ideas" or text.startswith("/ideas ") or text == "/venture":
                    focus = text.replace("/ideas", "").replace("/venture", "").strip() or "AI Agency Automation & Lead Generation"
                    send_telegram_text(token, chat_id, f"💡 *Generating High-Margin Automated Business Models for Rishi...*\n_Analyzing market opportunities in: {focus}_")
                    ideas = generate_business_ventures(focus)
                    send_telegram_text(token, chat_id, ideas)
                    continue
                
                if text == "/memory":
                    if memory_manager:
                        entries = memory_manager.all_entries_for_ui()
                        if not entries:
                            send_telegram_text(token, chat_id, "🧠 *Memory is currently empty.* Use `/remember <fact>` to store personal notes!")
                        else:
                            lines = ["🧠 *AANVYA Unified Long-Term Memory:*"]
                            for e in entries[:15]:
                                lines.append(f"• *{e['category'].title()} ({e['key']}):* {e['value']}")
                            send_telegram_text(token, chat_id, "\n".join(lines))
                    else:
                        send_telegram_text(token, chat_id, "🧠 Memory manager module not available.")
                    continue
                
                if text.startswith("/remember "):
                    fact = text.replace("/remember ", "").strip()
                    if fact:
                        if memory_manager:
                            memory_manager.remember("user_note", fact, category="notes")
                            send_telegram_text(token, chat_id, f"🧠 *Remembered:* {fact}")
                            record_shared_activity("memory_update", f"Remembered: {fact[:40]}", fact)
                        else:
                            send_telegram_text(token, chat_id, "🧠 Memory manager module not active.")
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
                    prompt = f"Provide a crisp, energetic morning briefing for Rishi covering key highlights, motivation, and agency monetization focus.\n\n{mem_context}"
                    reply = call_gemini(prompt, system_instruction="You are AANVYA, an elite personal intelligence companion.")
                    send_telegram_text(token, chat_id, f"🌅 *Morning Intelligence Briefing*\n\n{reply}")
                    record_shared_activity("daily_briefing", "Morning Briefing", reply[:400])
                    if VOICE_MODE_ENABLED:
                        audio = generate_voice_note(reply)
                        if audio:
                            send_telegram_voice(token, chat_id, audio)
                    continue
                
                # ── General Conversational & Agentic Triggers ────────────────
                if text:
                    if any(text.lower().startswith(k) for k in ["generate an image of", "create an image of", "draw a picture of", "make an image of", "image of "]):
                        clean_p = re.sub(r"^(generate an image of|create an image of|draw a picture of|make an image of|image of)\s*", "", text, flags=re.IGNORECASE)
                        send_telegram_text(token, chat_id, f"🎨 *Generating FLUX.1 Image:*\n_{clean_p}_\n_Rendering high-definition visual..._")
                        img_path = generate_flux_image(clean_p)
                        if img_path:
                            send_telegram_photo(token, chat_id, img_path, caption=f"✨ *FLUX.1 Render:* {clean_p}")
                        else:
                            send_telegram_text(token, chat_id, "⚠️ Image generation failed.")
                        continue
                    
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    
                    if any(k in text.lower() for k in ["research in depth", "build an app", "create a project", "scrape", "autonomous task"]):
                        send_telegram_text(token, chat_id, "🤖 *Dispatching Hermes Autonomous Agent for deep execution...*")
                        t = threading.Thread(target=run_hermes_mission, args=(text, chat_id, token), daemon=True)
                        t.start()
                        continue
                    
                    full_prompt = f"{mem_context}\n\nUser Query: {text}" if mem_context else text
                    reply = call_gemini(full_prompt)
                    send_telegram_text(token, chat_id, reply)
                    record_shared_activity("conversation", f"Chat: {text[:40]}", reply[:400])
                    
                    if VOICE_MODE_ENABLED:
                        audio = generate_voice_note(reply)
                        if audio:
                            send_telegram_voice(token, chat_id, audio)
                    
        except requests.exceptions.ReadTimeout:
            continue
        except requests.exceptions.ConnectionError:
            time.sleep(5)
            continue
        except Exception as e:
            logger.error(f"Error in telegram loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    logger.info("=== Starting AANVYA 24/7 Cloud Assistant & Business Engine (2-Way Synced) ===")
    run_telegram_loop()
