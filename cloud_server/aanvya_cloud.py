"""
AANVYA 24/7 Cloud Assistant & Business Automation Engine (2-Way Synced)
=======================================================================
Runs continuously on Oracle Cloud Always Free Ubuntu VPS.
Features:
- Gemini Flash 3.x / Flash-Latest Brain Ladder
- Instant Telegram Document Dispatch (`sendDocument`)
- Auto-Delivery of Hermes Deliverables (HTML, Python, Images, Reports)
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

try:
    from core.business_audit_engine import audit_engine
    from core.pitch_generator import pitch_generator
    logger.info("360 Business Audit Engine & Pitch Generator loaded successfully.")
except Exception as e:
    logger.error(f"Could not import business_audit_engine: {e}")
    audit_engine = None
    pitch_generator = None

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
Tone: Natural, articulate, confident, encouraging, concise, direct and action-oriented."""

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
            "parse_mode": parse_mode
        }
        try:
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code != 200:
                payload.pop("parse_mode", None)
                requests.post(url, json=payload, timeout=25)
        except Exception as e:
            logger.error(f"Failed to send telegram message chunk: {e}")

def send_telegram_photo(token: str, chat_id: int, photo_path: Path, caption: str = "") -> bool:
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"}
            r = requests.post(url, data=data, files=files, timeout=35)
            if r.status_code != 200:
                f.seek(0)
                r = requests.post(url, data={"chat_id": chat_id, "caption": caption[:1024]}, files={"photo": f}, timeout=35)
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

def send_telegram_document(token: str, chat_id: int, doc_path: Path, caption: str = "") -> bool:
    """Sends a document/file attachment directly to the user's Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(doc_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": chat_id, "caption": caption[:1024], "parse_mode": "Markdown"}
            r = requests.post(url, data=data, files=files, timeout=45)
            if r.status_code != 200:
                f.seek(0)
                r = requests.post(url, data={"chat_id": chat_id, "caption": caption[:1024]}, files={"document": f}, timeout=45)
            return r.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send telegram document: {e}")
        return False

# ── Hermes Autonomous Agent Engine ───────────────────────────────────────────

def hermes_web_search(query: str) -> str:
    """Live web search tool for Hermes using DuckDuckGo HTML parser."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', r.text, re.DOTALL)
            clean = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:4]]
            return "\n\n".join(clean) if clean else "No search results found."
    except Exception as e:
        return f"Search error: {e}"
    return "Search failed."

def run_hermes_mission(task: str, chat_id: int, bot_token: str):
    """Executes a multi-step autonomous agent mission with clean single-file delivery."""
    send_telegram_text(bot_token, chat_id, f"🚀 *Hermes Autonomous Agent Dispatched*\n\n*Mission:* {task}\n_Executing with live Linux terminal & web search..._")
    
    system_prompt = """You are Hermes, an elite autonomous software engineer, researcher & 21st.dev design master working for AANVYA.
You have full access to a live Linux VPS terminal and tools to independently execute missions.

CRITICAL LAWS FOR WEBSITES & DELIVERABLES:
1. 🚀 DIRECT IMMEDIATE ACTION (ZERO SPECULATIVE PLANNING):
   • When asked to build a website, landing page, app, or tool, DO NOT waste time creating planning documents, spec outlines, or markdown brainstorms.
   • IMMEDIATELY generate the complete, working, production code in your very first step via `WRITE_FILE: index.html ||| <full complete code>`.

2. 📱 FULL MOBILE RESPONSIVENESS & TOUCH OPTIMIZATION:
   • Every page must be flawlessly responsive on Mobile (375px–430px), Tablet (768px), and Desktop (1200px+).
   • Responsive Typography: Use fluid scaling (`text-4xl sm:text-6xl md:text-8xl lg:text-9xl`) or `clamp()`.
   • Responsive Grid: Use `grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8`.
   • Mobile Navigation: Include a working mobile hamburger toggle with backdrop blur overlay.
   • Touch Targets: All interactive buttons and inputs must have `min-height: 44px` with proper padding.
   • Always include `<meta name="viewport" content="width=device-width, initial-scale=1.0">` and `overflow-x-hidden` on body.

3. 🚫 ZERO JSX IN RAW HTML (PURE STATIC HTML LAW):
   • NEVER write React/JSX syntax inside `.html` files (e.g. NEVER do `{[ {img:...} ].map(...)}` in HTML body).
   • Write clean, complete, static semantic HTML tags.

4. ⚡ ZERO DEAD JAVASCRIPT / ZERO PLACEHOLDER SCRIPTS:
   • NEVER write comments like `// GSAP animations would be initialized here`.
   • Every imported library (Three.js, GSAP, Lucide, Canvas) MUST have complete, working, interactive JavaScript code.
   • Always call `lucide.createIcons()` on page load.
   • Implement active cursor spotlight physics (`--mouse-x`, `--mouse-y`) or smooth 3D tilt calculations.

5. 🚫 ZERO PLACEHOLDER BOXES:
   • NEVER use empty gray rectangles (`bg-zinc-800`, `bg-gray-800`).
   • ALWAYS embed real, high-resolution Unsplash photography with `auto=format&fit=crop&w=1200&q=80`.

6. 🎨 21st.dev THEME TAXONOMY:
   • Glyph Portal: Scroll-driven typography hero that opens/steps into full-bleed project case studies on scroll (using SVG clip-path / canvas / GSAP ScrollTrigger).
   • 3D Spotlight Bento: Dark glassmorphic bento cards with cursor-following radial spotlight reflections and 3D layer pop-outs (`transform-style: preserve-3d; translateZ(35px)`).
   • Three.js Interactive Hero: Orbiting particle starfields, rotating wireframe monoliths, or geometric meshes that respond to mouse move.
   • Editorial Parallax: Rich photography cards with category filtering, floating badges, and smooth inquiry drawers.

7. 📦 DELIVERABLE FORMAT:
   • For websites, ALWAYS create a COMPLETE, 250+ LINE, 100% SELF-CONTAINED `index.html` with Tailwind CDN, Google Fonts, Lucide icons, Three.js, and GSAP.
   • Output via `WRITE_FILE: index.html ||| <full complete html>`.

Available Actions (choose ONE per step):
1. `BASH: <linux command>` — Execute terminal commands, run python scripts, pip install libraries, test code
2. `SEARCH: <query>` — Search live web for data, news, docs, pricing
3. `WRITE_FILE: <filename>|||<content>` — Write code, scripts, self-contained HTML landing pages, or reports
4. `IMAGE: <prompt>` — Generate photorealistic FLUX.1 image
5. `ACTION: FINISH <summary>` — When your mission is 100% complete and deliverables are ready.

Format:
THOUGHT: <your reasoning>
ACTION: <action string>"""

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
            
            # Send ONLY the single final deliverable file (e.g. index.html), NO spam
            if deliverables:
                primary = next((f for f in reversed(deliverables) if f.name.endswith(".html")), deliverables[-1])
                if primary.exists():
                    send_telegram_document(bot_token, chat_id, primary, caption=f"📁 *Final Deliverable:* `{primary.name}`")
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
                if fpath not in deliverables:
                    deliverables.append(fpath)
                history.append(f"STEP_{step}: Wrote {fname}")
                send_telegram_text(bot_token, chat_id, f"📝 *Hermes Progress:* Generated `{fname}`")
                continue
                
        if "SEARCH:" in resp:
            m = re.search(r"SEARCH:\s*(.+)", resp)
            if m:
                q = m.group(1).split("\n")[0].strip()
                res = hermes_web_search(q)
                history.append(f"STEP_{step}: Searched '{q}'\nRESULTS:\n{res}")
                continue
                
        if step == max_steps or len(resp) > 200:
            if not deliverables:
                report_path = DELIVERABLES_PATH / f"Hermes_Report_{int(time.time())}.md"
                report_path.write_text(resp, encoding="utf-8")
                deliverables.append(report_path)
            
            summary = resp[:1500]
            send_telegram_text(bot_token, chat_id, f"✅ *Hermes Finished Mission*\n\n{summary}")
            if deliverables:
                primary = next((f for f in reversed(deliverables) if f.name.endswith(".html")), deliverables[-1])
                if primary.exists():
                    send_telegram_document(bot_token, chat_id, primary, caption=f"📁 *Final Deliverable:* `{primary.name}`")
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

def handle_lead_pipeline_async(niche: str, city: str, chat_id: int, token: str):
    """Audits businesses across multiple service vectors, ranks opportunities, builds top prototype, and delivers pitch."""
    try:
        if not audit_engine:
            send_telegram_text(token, chat_id, "⚠️ Audit Engine module not available.")
            return

        results = audit_engine.search_and_audit_businesses(niche, city, limit=3)
        if not results:
            send_telegram_text(token, chat_id, f"ℹ️ No qualified businesses found for *{niche} in {city}*.")
            return

        lines = [f"🎯 *Top Audited Deal Flow: {niche} in {city}*\n"]
        for i, res in enumerate(results, 1):
            top = res["top_opportunity"]
            lines.append(
                f"*{i}. {res['name']}*\n"
                f"• *Website:* {res.get('website') or '❌ No Active Site'}\n"
                f"• *Winning Offer:* 🏆 `{top['service_title']}`\n"
                f"• *Conversion Probability:* `{top['conversion_probability']}%`\n"
                f"• *Revenue Leak:* _{top['pain_point']}_\n"
                f"• *Recommended Prototype:* `{top['prototype_to_build']}`\n"
            )
        send_telegram_text(token, chat_id, "\n".join(lines))

        # Build prototype and pitch for #1 top prospect
        top_lead = results[0]
        top_op = top_lead["top_opportunity"]
        b_name = top_lead["name"]
        proto_target = top_op["prototype_to_build"]

        send_telegram_text(token, chat_id, f"🚀 *Hermes is now autonomously building the customized prototype for #{1}: {b_name}*...\n_Solution: {proto_target}_")

        mission_task = f"Build a complete, working, self-contained single-file HTML deliverable for {b_name} ({niche} in {city}). Specifically build: {proto_target}."
        run_hermes_mission(mission_task, chat_id, token)

        if pitch_generator:
            pitch_pkg = pitch_generator.generate_pitch_package(top_lead, demo_url="[ATTACHED_PROTOTYPE]")
            pitch_msg = (
                f"✉️ *Ready-to-Send High-Converting Pitch Package for {b_name}*\n\n"
                f"📋 *Cold Email Copy:*\n"
                f"*Subject:* `{pitch_pkg['email_subject']}`\n\n"
                f"```\n{pitch_pkg['email_body']}\n```\n\n"
                f"📱 *WhatsApp Short Hook:*\n"
                f"```\n{pitch_pkg['whatsapp_pitch']}\n```\n\n"
                f"📸 *Instagram / LinkedIn DM:*\n"
                f"```\n{pitch_pkg['dm_pitch']}\n```"
            )
            send_telegram_text(token, chat_id, pitch_msg)
            record_shared_activity("lead_deal_flow", f"Deal: {b_name[:40]}", f"360 Audit & Pitch for {b_name} ({top_op['service_title']})")
    except Exception as err:
        logger.error(f"Lead pipeline async error: {err}")
        send_telegram_text(token, chat_id, f"⚠️ Lead pipeline error: {err}")


# ── Background Cron Scheduler ────────────────────────────────────────────────

def run_background_cron_loop():
    """Runs periodic cron jobs independently in the background (08:30 morning briefings, etc.)."""
    logger.info("Background Cron Scheduler active.")
    last_briefing_date = None
    
    while True:
        try:
            now = datetime.datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            
            # 08:30 AM Daily Morning Briefing
            if now.hour == 8 and now.minute >= 30 and last_briefing_date != today_str:
                last_briefing_date = today_str
                allowed = get_allowed_chats()
                token = get_telegram_token()
                if allowed and token:
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    
                    prompt = (
                        "Provide a crisp, energetic morning briefing for Rishi covering key highlights, "
                        "motivation, agency monetization focus, and high-margin action items.\n\n"
                        f"{mem_context}"
                    )
                    briefing = call_gemini(prompt, system_instruction="You are AANVYA, an elite personal intelligence companion.")
                    for cid in allowed:
                        send_telegram_text(token, cid, f"🌅 *Autonomous Morning Briefing*\n\n{briefing}")
                        record_shared_activity("daily_briefing", "Morning Briefing", briefing[:400])
            
            time.sleep(30)
        except Exception as e:
            logger.error(f"Cron loop error: {e}")
            time.sleep(60)

# ── Telegram Polling Engine ──────────────────────────────────────────────────

def run_telegram_loop():
    token = get_telegram_token()
    if not token:
        logger.error("No Telegram Bot Token found in `config/api_keys.json`. Polling aborted.")
        return

    logger.info("Connecting to Telegram Bot API with Long Polling...")
    offset = None
    
    # Start Cron Scheduler Daemon
    cron_thread = threading.Thread(target=run_background_cron_loop, daemon=True)
    cron_thread.start()
    
    global VOICE_MODE_ENABLED
    
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
                        "- _'/hermes Build a luxury coffee shop landing page in 21st.dev style'_"
                    )
                    send_telegram_text(token, chat_id, help_text)
                    continue

                if text == "/voicemode":
                    VOICE_MODE_ENABLED = not VOICE_MODE_ENABLED
                    status = "🔊 ON" if VOICE_MODE_ENABLED else "🔇 OFF"
                    send_telegram_text(token, chat_id, f"Voice mode is now *{status}*.")
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
                
                if text.startswith("/leads") or text.startswith("/audit"):
                    raw_q = text.replace("/leads", "").replace("/audit", "").strip()
                    if not raw_q:
                        send_telegram_text(token, chat_id, "ℹ️ *Usage:* `/leads <niche> in <city>`\n_Example:_ `/leads Cosmetic Dentists in Zurich` or `/leads Luxury Interior Designers in London`")
                        continue

                    if " in " in raw_q:
                        niche_p, city_p = raw_q.split(" in ", 1)
                    elif "," in raw_q:
                        niche_p, city_p = raw_q.split(",", 1)
                    else:
                        niche_p, city_p = raw_q, "Zurich"

                    niche_p = niche_p.strip().title()
                    city_p = city_p.strip().title()

                    send_telegram_text(token, chat_id, f"🔍 *Initiating 360° Business Audit & Deal Flow Pipeline...*\n• *Target Niche:* {niche_p}\n• *Target City:* {city_p}\n_Scanning businesses, auditing digital infrastructure & scoring conversion probability..._")
                    threading.Thread(target=handle_lead_pipeline_async, args=(niche_p, city_p, chat_id, token), daemon=True).start()
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

                if text == "/sys":
                    try:
                        import psutil
                        cpu = psutil.cpu_percent()
                        ram = psutil.virtual_memory().percent
                        disk = psutil.disk_usage("/").percent
                        uptime_s = time.time() - psutil.boot_time()
                        uptime_str = str(datetime.timedelta(seconds=int(uptime_s)))
                        sys_msg = (
                            f"🖥️ *Oracle Cloud VPS Telemetry*\n\n"
                            f"• *CPU Utilization:* `{cpu}%`\n"
                            f"• *RAM Utilization:* `{ram}%`\n"
                            f"• *Disk Usage:* `{disk}%`\n"
                            f"• *System Uptime:* `{uptime_str}`\n"
                            f"• *Sync Status:* `Active & Polling`\n"
                            f"• *Deliverables Stored:* `{len(list(DELIVERABLES_PATH.glob('*')))} files`"
                        )
                        send_telegram_text(token, chat_id, sys_msg)
                    except Exception as e:
                        send_telegram_text(token, chat_id, f"🖥️ *VPS Status:* Online & Active (Telemetry error: {e})")
                    continue
                
                # ── Smart Intent Interceptor (Zero-Delay File Delivery & Action Execution) ──
                if text:
                    lower_text = text.lower().strip()
                    
                    # 1. User wants the generated file/document/code sent
                    send_file_keywords = [
                        "send me the file", "send the file", "send file", "send it", "send now",
                        "send to telegram", "send on telegram", "give me the file", "file bhejo",
                        "bhejo", "bhej do", "site bhejo", "send site", "send index.html",
                        "download file", "give me the code", "send code", "send html"
                    ]
                    
                    if lower_text in ["send", "send it", "send now", "send file", "bhejo", "bhej do"] or any(k in lower_text for k in send_file_keywords):
                        all_files = sorted(list(DELIVERABLES_PATH.glob("*")), key=lambda p: p.stat().st_mtime, reverse=True)
                        if all_files:
                            latest_file = all_files[0]
                            send_telegram_text(token, chat_id, f"📤 *Sending your latest deliverable:* `{latest_file.name}`...")
                            success = send_telegram_document(token, chat_id, latest_file, caption=f"🚀 *Deliverable:* `{latest_file.name}`")
                            if not success:
                                send_telegram_text(token, chat_id, "⚠️ Failed to send file. Please retry.")
                        else:
                            send_telegram_text(token, chat_id, "ℹ️ No recent deliverables found in cloud storage. Tell me what site or project you'd like Hermes to build!")
                        continue

                    # 2. Image generation natural language trigger
                    if any(lower_text.startswith(k) for k in ["generate an image of", "create an image of", "draw a picture of", "make an image of", "image of "]):
                        clean_p = re.sub(r"^(generate an image of|create an image of|draw a picture of|make an image of|image of)\s*", "", text, flags=re.IGNORECASE)
                        send_telegram_text(token, chat_id, f"🎨 *Generating FLUX.1 Image:*\n_{clean_p}_\n_Rendering high-definition visual..._")
                        img_path = generate_flux_image(clean_p)
                        if img_path:
                            send_telegram_photo(token, chat_id, img_path, caption=f"✨ *FLUX.1 Render:* {clean_p}")
                        else:
                            send_telegram_text(token, chat_id, "⚠️ Image generation failed.")
                        continue
                    
                    # 3. Autonomous coding / website building trigger
                    if any(k in lower_text for k in ["build a website", "build a landing page", "make a website", "make a site", "create a site", "build a site", "create a landing page", "build an app", "create an app", "scrape google maps"]):
                        t = threading.Thread(target=run_hermes_mission, args=(text, chat_id, token), daemon=True)
                        t.start()
                        continue
                    
                    # 4. Standard conversational query
                    mem_context = ""
                    if memory_manager:
                        mem = memory_manager.load_memory()
                        mem_context = memory_manager.format_memory_for_prompt(mem)
                    
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
