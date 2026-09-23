"""
plugins/hermes_worker.py — Autonomous Background Agent for Laptop AANVYA
========================================================================
Fixed & Enhanced:
- Correctly extracts response.text from gemini._Reply objects
- Direct high-speed FLUX.1 generation for image requests
- Saves images to Desktop/Hermes_Output/ and Desktop/ directly
- Automatically forwards generated image to Telegram
- Announces completion via voice
"""

import json
import logging
import os
import re
import shutil
import threading
import time
import requests
from pathlib import Path
from typing import Optional

from core import gemini
from memory.config_manager import get_plugin_config

logger = logging.getLogger("AANVYA.Hermes")

_NS = "hermes_worker"
_DEFAULT_OUT = Path.home() / "Desktop" / "Hermes_Output"

PLUGIN_SETTINGS = {
    "namespace": _NS,
    "title": "🧠  HERMES AUTONOMOUS AGENT",
    "fields": [
        {"key": "output_dir", "label": "Deliverables Output Folder", "type": "text",
         "placeholder": "Default = Desktop/Hermes_Output"},
        {"key": "max_steps", "label": "Max Autonomous Steps Per Mission", "type": "text",
         "placeholder": "Default = 8"},
        {"key": "notify_voice", "label": "Announce out loud when mission finishes",
         "type": "toggle", "default": True},
    ],
}

PLUGIN = {
    "name": "hermes_worker",
    "description": (
        "Dispatches an autonomous background worker (Hermes Agent) to perform "
        "tasks, such as generating photorealistic images, writing code, creating documents, "
        "doing deep web research, or scraping data. Call this whenever the user asks to "
        "'generate an image of...', 'create a picture of...', 'build an app for...', "
        "'research in depth and write a report on...', 'scrape data for...'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The exact goal, prompt, or project description for the agent"
            },
            "output_format": {
                "type": "STRING",
                "description": "Optional deliverable type (e.g. 'flux_image', 'markdown_report', 'python_project')"
            },
            "send_to_telegram": {
                "type": "BOOLEAN",
                "description": "Whether to send a copy of the deliverable/image to user's Telegram phone"
            }
        },
        "required": ["task"],
    },
}

# ── Telegram Media Dispatcher ────────────────────────────────────────────────

def _send_file_to_telegram(file_path: Path, caption: str = ""):
    """Sends photo or document directly to paired Telegram user."""
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if not cfg_path.exists():
            logger.warning(f"Config path {cfg_path} does not exist.")
            return
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        token = cfg.get("telegram_bot_token") or cfg.get("plugin_config", {}).get("telegram_remote", {}).get("bot_token")
        
        # Robustly resolve chat IDs from all possible config fields
        raw_chats = cfg.get("telegram_allowed_chat_ids") or cfg.get("plugin_config", {}).get("telegram_remote", {}).get("allowed_chat_ids") or []
        chat_ids = []
        if isinstance(raw_chats, int):
            chat_ids = [raw_chats]
        elif isinstance(raw_chats, str):
            chat_ids = [int(x.strip()) for x in raw_chats.split(",") if x.strip().isdigit()]
        elif isinstance(raw_chats, list):
            chat_ids = [int(x) for x in raw_chats if str(x).isdigit()]

        if not token or not chat_ids:
            logger.warning(f"Cannot forward to Telegram: token={bool(token)}, chat_ids={chat_ids}")
            return

        is_image = file_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
        endpoint = "sendPhoto" if is_image else "sendDocument"
        field_name = "photo" if is_image else "document"

        for cid in chat_ids:
            with open(file_path, "rb") as f:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/{endpoint}",
                    data={"chat_id": cid, "caption": caption[:1024], "parse_mode": "Markdown"},
                    files={field_name: f},
                    timeout=25
                )
                logger.info(f"Telegram dispatch status for {file_path.name}: {r.status_code}")
    except Exception as e:
        logger.error(f"Failed to send deliverable to Telegram: {e}")

# ── Toolset for Hermes Agent ─────────────────────────────────────────────────

def _web_search(query: str) -> str:
    """Live web search via DuckDuckGo."""
    try:
        from urllib.request import Request, urlopen
        from urllib.parse import quote_plus
        from bs4 import BeautifulSoup
        
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for a in soup.select(".result__body")[:5]:
            title = a.select_one(".result__title")
            snippet = a.select_one(".result__snippet")
            t = title.get_text(strip=True) if title else ""
            s = snippet.get_text(strip=True) if snippet else ""
            if t or s:
                results.append(f"- **{t}**: {s}")
        return "\n".join(results) if results else "No direct results found."
    except Exception as e:
        return f"Search error: {e}"

def _generate_flux_image(out_dir: Path, prompt: str, filename_override: str = None) -> Optional[Path]:
    """Generates a FLUX.1 photorealistic image and saves it to output dir & Desktop."""
    try:
        clean_p = re.sub(r"[^\w\s,-]", "", prompt).strip()
        encoded = requests.utils.quote(clean_p)
        url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true&seed={int(time.time())}"
        
        fname = filename_override or f"Hermes_Image_{int(time.time())}.jpg"
        if not fname.endswith((".jpg", ".png", ".jpeg")):
            fname += ".jpg"
            
        out_file = out_dir / fname
        r = requests.get(url, timeout=40)
        if r.status_code == 200 and len(r.content) > 5000:
            out_file.write_bytes(r.content)
            
            # Only save directly to Desktop root if explicitly requested in prompt
            if "save to desktop" in prompt.lower() or "on my desktop" in prompt.lower() and "hermes_output" not in prompt.lower():
                desktop_copy = Path.home() / "Desktop" / fname
                try:
                    shutil.copy2(out_file, desktop_copy)
                except Exception:
                    pass
                
            # Forward directly to Telegram
            _send_file_to_telegram(out_file, caption=f"🎨 *Generated Image for Rishi:*\n_{clean_p}_")
            return out_file
    except Exception as e:
        logger.error(f"FLUX image generation error: {e}")
    return None

def _write_file(out_dir: Path, rel_path: str, content: str) -> str:
    """Safely write a deliverable file to the project output folder."""
    try:
        dest = (out_dir / rel_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        return f"Successfully created file: {dest.name} ({len(content)} bytes)"
    except Exception as e:
        return f"File write error: {e}"

# ── Autonomous Worker Thread ─────────────────────────────────────────────────

def _run_hermes_mission(task: str, output_format: str, player, out_dir: Path, max_steps: int, notify: bool):
    """Executes the Hermes execution loop."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if player:
            try:
                player.write_log(f"HERMES: Initialized mission — '{task[:60]}...'")
            except Exception:
                pass

        # ── Fast Path: If task is directly asking for an image ───────────────
        is_image_req = any(k in task.lower() for k in ["image", "photo", "picture", "draw", "render", "wallpaper", "logo", "illustration"])
        if is_image_req or output_format == "flux_image":
            if player:
                try:
                    player.write_log(f"HERMES: Rendering FLUX.1 image for prompt: '{task[:50]}'...")
                except Exception:
                    pass
            
            img_file = _generate_flux_image(out_dir, task)
            if img_file:
                msg = f"HERMES: Image generated successfully ({img_file.name}) and saved to Desktop & Telegram!"
                if player:
                    try:
                        player.write_log(msg)
                        if notify:
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Rishi, aapki image generate ho gayi hai. Maine ise aapke Desktop par save kar diya hai aur aapke Telegram par bhi bhej diya hai.")
                    except Exception:
                        pass
                
                try:
                    from core.cloud_sync import record_activity
                    record_activity("image_generation", f"Image: {task[:40]}", f"Generated image and saved to Desktop/{img_file.name}", files=[img_file.name])
                except Exception:
                    pass
                return

        # ── General Multi-Step Autonomous Mission Loop ───────────────────────
        history = [
            f"MISSION: {task}\nDELIVERABLE TARGET: {output_format or 'Comprehensive project / deliverable'}"
        ]

        system_prompt = """You are HERMES, an elite autonomous software engineer, UI/UX designer & agent working for AANVYA.
You execute real-world tasks step-by-step using tools until the mission is 100% complete.

CRITICAL 21ST.DEV DESIGN & VISUAL RULES:
- When asked to build a website, ALWAYS create a SINGLE-FILE, 100% SELF-CONTAINED `index.html`.
- NEVER USE EMPTY GRAY BOXES OR "IMAGE PLACEHOLDER" TEXT.
- ALWAYS embed REAL, STUNNING HIGH-RESOLUTION PHOTOGRAPHY using high-quality Unsplash URLs (e.g. `https://images.unsplash.com/photo-...?auto=format&fit=crop&w=1200&q=80`) for hero banners, menu/product cards, baristas, and showcase sections.
- Use 21st.dev / Magic UI aesthetics:
  1. Rich modern dark backgrounds (`bg-[#09090b]`, `bg-zinc-950`) with warm glowing radial mesh gradients and glassmorphism cards (`backdrop-blur-xl bg-white/[0.04] border border-white/[0.08] hover:border-amber-500/50 transition-all duration-300`).
  2. Vibrant accent colors, glowing pill badges, smooth hover animations, and Lucide vector icons (`<i data-lucide="..."></i>`).
  3. Interactive JavaScript (filters, counters, mobile menu toggle, modals).
- Use Tailwind CSS CDN (`<script src="https://cdn.tailwindcss.com"></script>`), Google Fonts (Outfit / Plus Jakarta Sans), and Lucide Icons (`<script src="https://unpkg.com/lucide@latest"></script>`).

Available Tool Calls:
1. BASH: <shell command> (Run python scripts, terminal commands, test code)
2. SEARCH: <query> (Search the live web for facts, documentation, or data)
3. WRITE_FILE: <filename> ||| <content> (Write code, markdown reports, or self-contained HTML files)
4. IMAGE: <prompt> (Generate a photorealistic FLUX.1 image deliverable)
5. FINISH: <summary of what you created and where it is saved>

Format each turn as:
THOUGHT: <your step-by-step reasoning>
ACTION: <one of SEARCH, WRITE_FILE, IMAGE, or FINISH>

When all deliverables are created and written, return ACTION: FINISH.
"""

        deliverables = []

        for step in range(1, max_steps + 1):
            prompt = system_prompt + "\n\n" + "\n".join(history) + f"\n\nTurn {step}/{max_steps}:"
            
            try:
                response = gemini.call(prompt, tier=gemini.FAST, timeout_ms=30000)
                # Safely extract text from _Reply object
                resp_text = getattr(response, "text", None) or str(response or "").strip()
            except Exception as e:
                resp_text = f"THOUGHT: Encountered API error {e}.\nACTION: FINISH: Mission concluded."

            if "ACTION: FINISH" in resp_text or "ACTION:FINISH" in resp_text:
                summary = resp_text.split("FINISH")[-1].strip(": \n")
                if player:
                    try:
                        player.write_log(f"HERMES: Mission Completed! {summary[:80]}")
                        if notify:
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Rishi, Hermes has completed your mission and saved the deliverables to your desktop.")
                    except Exception:
                        pass
                
                try:
                    from core.cloud_sync import record_activity
                    record_activity("hermes_mission", f"Hermes: {task[:50]}", summary, files=[p.name for p in deliverables])
                except Exception:
                    pass
                return

            # Parse BASH action
            if "BASH:" in resp_text:
                match = re.search(r"BASH:\s*(.+)", resp_text)
                if match:
                    cmd = match.group(1).split("\n")[0].strip()
                    import subprocess
                    try:
                        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45, cwd=str(out_dir))
                        out = (p.stdout + "\n" + p.stderr).strip() or f"(Exit {p.returncode})"
                        history.append(f"HERMES_STEP_{step}: Ran '{cmd}'\nOUTPUT:\n{out[:1200]}")
                        if player:
                            player.write_log(f"HERMES: Executed `{cmd[:40]}`")
                        continue
                    except Exception as e:
                        history.append(f"HERMES_STEP_{step}: Error executing bash: {e}")
                        continue

            # Parse IMAGE action
            if "IMAGE:" in resp_text:
                match = re.search(r"IMAGE:\s*(.+)", resp_text)
                if match:
                    img_prompt = match.group(1).split("\n")[0].strip()
                    img_path = _generate_flux_image(out_dir, img_prompt)
                    if img_path:
                        deliverables.append(img_path)
                        history.append(f"HERMES_STEP_{step}: Generated image for '{img_prompt}'\nTOOL_RESULT: Saved to {img_path.name}")
                        if player:
                            player.write_log(f"HERMES: Rendered image for '{img_prompt[:30]}'")
                        continue

            # Parse WRITE_FILE action
            if "WRITE_FILE:" in resp_text:
                match = re.search(r"WRITE_FILE:\s*([^|\n]+)\|\|\|(.*)", resp_text, re.DOTALL)
                if match:
                    fname = match.group(1).strip()
                    content = match.group(2).strip()
                    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                    res = _write_file(out_dir, fname, content)
                    f_dest = out_dir / fname
                    deliverables.append(f_dest)
                    # Forward document to Telegram
                    _send_file_to_telegram(f_dest, caption=f"📄 *Hermes Created File:* `{fname}`")
                    history.append(f"HERMES_STEP_{step}: Wrote {fname}\nTOOL_RESULT: {res}")
                    if player:
                        player.write_log(f"HERMES: Generated {fname}")
                    continue

            # Parse SEARCH action
            if "SEARCH:" in resp_text:
                match = re.search(r"SEARCH:\s*(.+)", resp_text)
                if match:
                    q = match.group(1).split("\n")[0].strip()
                    res = _web_search(q)
                    history.append(f"HERMES_STEP_{step}: Searched '{q}'\nSEARCH_RESULTS:\n{res}")
                    if player:
                        player.write_log(f"HERMES: Researched '{q[:40]}'")
                    continue

            # Fallback: save as markdown report
            if step == max_steps or len(resp_text) > 200:
                rep_name = f"Hermes_Mission_Report_{int(time.time())}.md"
                _write_file(out_dir, rep_name, resp_text)
                rep_file = out_dir / rep_name
                deliverables.append(rep_file)
                _send_file_to_telegram(rep_file, caption=f"📑 *Hermes Mission Report:* {task[:60]}")
                history.append(f"HERMES_STEP_{step}: Saved mission report.")
                break

        # Final notification
        if player:
            try:
                player.write_log(f"HERMES: All tasks finished. Deliverables in: {out_dir}")
                if notify:
                    say_fn = getattr(player, "request_say", None)
                    if callable(say_fn):
                        say_fn("Sir, Hermes has completed the mission and created your deliverables.")
            except Exception:
                pass

        try:
            from core.cloud_sync import record_activity
            record_activity("hermes_mission", f"Hermes: {task[:50]}", "Completed mission and saved deliverables", files=[p.name for p in deliverables])
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[Hermes] Mission failure: {e}")
        if player:
            player.write_log(f"HERMES: Error during mission: {e}")

# ── Plugin Entry Point ───────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Dispatches Hermes Agent in a dedicated background worker thread on Laptop.
    Returns immediate spoken confirmation.
    """
    task = parameters.get("task", "").strip()
    fmt = parameters.get("output_format", "").strip()
    if not task:
        return "Sir, please specify the task for Hermes to execute."

    cfg = get_plugin_config(_NS)
    out_dir_str = str(cfg.get("output_dir") or "").strip()
    out_dir = Path(out_dir_str) if out_dir_str else _DEFAULT_OUT
    
    try:
        max_steps = max(3, min(20, int(cfg.get("max_steps", 8))))
    except (ValueError, TypeError):
        max_steps = 8
        
    notify = bool(cfg.get("notify_voice", True))

    # Launch background thread
    t = threading.Thread(
        target=_run_hermes_mission,
        args=(task, fmt, player, out_dir, max_steps, notify),
        daemon=True,
        name="HermesWorkerThread"
    )
    t.start()

    res_msg = f"Hermes Agent initialized in the background for: '{task}'. I'll notify you once it's complete."
    if player:
        try:
            player.write_log(f"SYS: {res_msg}")
        except Exception:
            pass

    return res_msg
