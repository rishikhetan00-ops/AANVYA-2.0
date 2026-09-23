"""
Hermes Autonomous Agent Worker Plugin for AANVYA (Desktop Engine)
==================================================================
Runs real-world tasks in background threads on Windows laptop.
- Fast Path for FLUX.1 Images (Auto-saved to Desktop/Hermes_Output & Telegram synced)
- Fast Path for 21st.dev / Aceternity 3D Single-File Websites (Auto-saved to index.html & Auto-opened in Brave)
- Full Bash / Terminal Execution & Web Search Tools
- Zero Speculative Planning (Direct Code & Deliverable Generation)
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
import requests
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# Core Gemini & Memory
from core import gemini

logger = logging.getLogger("HermesWorker")
_NS = "hermes_worker"

# Output directory on Desktop
_DESKTOP = Path(os.environ.get("USERPROFILE", "C:\\Users\\BIT")) / "Desktop"
_DEFAULT_OUT = _DESKTOP / "Hermes_Output"
_DEFAULT_OUT.mkdir(parents=True, exist_ok=True)

HERMES_SYSTEM_PROMPT = """You are HERMES, an elite autonomous software engineer, 21st.dev designer & intelligence operator for AANVYA.
You have full access to tools and execute missions directly with working code and real-world deliverables.

CRITICAL LAWS FOR WEBSITES & DELIVERABLES:
1. 🚀 DIRECT IMMEDIATE ACTION (ZERO SPECULATIVE PLANNING):
   • When asked to build a website, landing page, app, or tool, DO NOT waste time creating planning documents, spec outlines, or markdown brainstorms.
   • IMMEDIATELY generate the complete, working, production code via `WRITE_FILE: index.html ||| <full complete code>`.

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

Available Tools:
1. `BASH: <windows/powershell command>` — Execute terminal commands, run python scripts, test code
2. `SEARCH: <query>` — Search live web for data, news, docs, pricing
3. `WRITE_FILE: <filename> ||| <content>` — Write code, scripts, or self-contained HTML landing pages
4. `IMAGE: <prompt>` — Generate photorealistic FLUX.1 image
5. `ACTION: FINISH: <summary>` — Conclude mission when deliverables are saved

Format:
THOUGHT: <your reasoning>
ACTION: <tool call>"""

def get_plugin_config(namespace: str) -> Dict[str, Any]:
    return {}

def _get_api_keys() -> Dict[str, Any]:
    try:
        keys_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        if keys_path.exists():
            with open(keys_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _send_telegram_photo(photo_path: Path, caption: str = ""):
    keys = _get_api_keys()
    bot_token = keys.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_ids = keys.get("telegram_allowed_chat_ids", [])
    if not chat_ids and keys.get("telegram_chat_id"):
        chat_ids = [keys.get("telegram_chat_id")]
    if not chat_ids:
        chat_ids = [936014573]

    if not bot_token:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    for cid in chat_ids:
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": cid, "caption": caption[:1024]}
                requests.post(url, data=data, files=files, timeout=25)
        except Exception:
            pass

def _send_telegram_document(doc_path: Path, caption: str = ""):
    keys = _get_api_keys()
    bot_token = keys.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_ids = keys.get("telegram_allowed_chat_ids", [])
    if not chat_ids and keys.get("telegram_chat_id"):
        chat_ids = [keys.get("telegram_chat_id")]
    if not chat_ids:
        chat_ids = [936014573]

    if not bot_token:
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    for cid in chat_ids:
        try:
            with open(doc_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": cid, "caption": caption[:1024]}
                requests.post(url, data=data, files=files, timeout=35)
        except Exception:
            pass

def _generate_flux_image(out_dir: Path, prompt: str) -> Optional[Path]:
    clean_p = re.sub(r"[^\w\s,-]", "", prompt).strip()
    encoded = requests.utils.quote(clean_p)
    url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true&seed={int(time.time())}"
    
    out_file = out_dir / f"Hermes_FLUX_{int(time.time())}.jpg"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code == 200 and len(r.content) > 5000:
            out_file.write_bytes(r.content)
            _send_telegram_photo(out_file, caption=f"🎨 *Hermes FLUX Render:* {clean_p[:100]}")
            return out_file
    except Exception as e:
        logger.error(f"FLUX generation error: {e}")
    return None

def _open_file_in_browser(file_path: Path):
    """Opens an HTML file directly in the user's Brave or default browser."""
    brave_paths = [
        Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe"
    ]
    brave_bin = next((p for p in brave_paths if p.exists()), None)
    try:
        if brave_bin:
            subprocess.Popen([str(brave_bin), f"file:///{file_path.resolve()}"])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", str(file_path.resolve())])
    except Exception as e:
        logger.error(f"Could not open browser: {e}")

def _run_hermes_mission(task: str, output_format: str, player, out_dir: Path, max_steps: int, notify: bool):
    """Executes the Hermes execution loop on Laptop."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if player:
            try:
                player.write_log(f"HERMES: Initialized mission — '{task[:60]}...'")
            except Exception:
                pass

        # ── Fast Path 1: Image Request ───────────────────────────────────────
        is_image_req = any(k in task.lower() for k in ["image", "photo", "picture", "draw", "render", "wallpaper", "logo", "illustration"])
        if is_image_req or output_format == "flux_image":
            if player:
                try:
                    player.write_log(f"HERMES: Rendering FLUX.1 image for: '{task[:50]}'...")
                except Exception:
                    pass
            
            img_file = _generate_flux_image(out_dir, task)
            if img_file:
                if player:
                    try:
                        player.write_log(f"HERMES: Image saved to {img_file.name}")
                        if notify:
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Rishi, aapki image ready hai. Desktop aur Telegram par bhej di hai.")
                    except Exception:
                        pass
                return

        # ── Fast Path 2: Website / Landing Page Direct Builder ───────────────
        is_web_req = any(k in task.lower() for k in ["website", "landing page", "web page", "web site", "portfolio", "site for", "make a site", "build a site", "create a site", "html", "glyph portal", "21st.dev"])
        if is_web_req or output_format == "html":
            if player:
                try:
                    player.write_log(f"HERMES: Building 21st.dev single-file website for '{task[:50]}'...")
                except Exception:
                    pass
            
            web_prompt = f"""{HERMES_SYSTEM_PROMPT}

USER REQUEST: {task}

TASK: Build a complete, production-ready, self-contained `index.html` file right now.
Do NOT write any planning markdown, outline, or conversational explanation.
Respond ONLY with the complete HTML code starting with `WRITE_FILE: index.html ||| <!DOCTYPE html>`."""

            try:
                resp = gemini.call(web_prompt, tier=gemini.FAST, timeout_ms=45000)
                resp_text = getattr(resp, "text", None) or str(resp or "").strip()
            except Exception as e:
                resp_text = ""

            html_content = ""
            if "WRITE_FILE:" in resp_text:
                m = re.search(r"WRITE_FILE:\s*([^|\n]+)\|\|\|(.*)", resp_text, re.DOTALL)
                if m:
                    html_content = m.group(2).strip()
            elif "<!DOCTYPE html>" in resp_text or "<html" in resp_text:
                html_content = resp_text

            if html_content:
                html_content = re.sub(r"^```[a-zA-Z]*\n?", "", html_content)
                html_content = re.sub(r"\n?```$", "", html_content)
                
                index_file = out_dir / "index.html"
                index_file.write_text(html_content, encoding="utf-8")
                
                # Auto open in Brave browser
                _open_file_in_browser(index_file)
                
                # Auto forward to Telegram
                _send_telegram_document(index_file, caption=f"🚀 *Hermes Generated Website:* {task[:60]}")
                
                if player:
                    try:
                        player.write_log(f"HERMES: Generated index.html and opened in browser!")
                        if notify:
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Rishi, landing page ready ho gayi hai. Maine ise Brave browser me open kar diya hai.")
                    except Exception:
                        pass
                
                try:
                    from core.cloud_sync import record_activity
                    record_activity("web_generation", f"Website: {task[:40]}", "Generated single-file 21st.dev website and opened in browser.", files=["index.html"])
                except Exception:
                    pass
                return

        # ── General Multi-Step Autonomous Mission Loop ───────────────────────
        history = [
            f"MISSION: {task}\nDELIVERABLE TARGET: {output_format or 'Production code / deliverable'}"
        ]

        deliverables = []

        for step in range(1, max_steps + 1):
            prompt = HERMES_SYSTEM_PROMPT + "\n\n" + "\n".join(history) + f"\n\nTurn {step}/{max_steps}:"
            
            try:
                response = gemini.call(prompt, tier=gemini.FAST, timeout_ms=35000)
                resp_text = getattr(response, "text", None) or str(response or "").strip()
            except Exception as e:
                resp_text = f"THOUGHT: API error {e}.\nACTION: FINISH: Mission concluded."

            if "ACTION: FINISH" in resp_text or "ACTION:FINISH" in resp_text:
                summary = resp_text.split("FINISH")[-1].strip(": \n")
                if player:
                    try:
                        player.write_log(f"HERMES: Mission Completed! {summary[:80]}")
                        if notify:
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Rishi, Hermes has completed your mission.")
                    except Exception:
                        pass
                
                if deliverables:
                    primary = next((f for f in reversed(deliverables) if f.name.endswith(".html")), deliverables[-1])
                    if primary.exists() and primary.name.endswith(".html"):
                        _open_file_in_browser(primary)
                    _send_telegram_document(primary, caption=f"📁 *Final Deliverable:* `{primary.name}`")
                
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

            # Parse WRITE_FILE action
            if "WRITE_FILE:" in resp_text:
                match = re.search(r"WRITE_FILE:\s*([^|\n]+)\|\|\|(.*)", resp_text, re.DOTALL)
                if match:
                    fname = match.group(1).strip()
                    content = match.group(2).strip()
                    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                    fpath = out_dir / fname
                    fpath.write_text(content, encoding="utf-8")
                    if fpath not in deliverables:
                        deliverables.append(fpath)
                    history.append(f"HERMES_STEP_{step}: Wrote {fname}")
                    if player:
                        player.write_log(f"HERMES: Created deliverable `{fname}`")
                    continue

            # If it reached end of steps or raw output
            if step == max_steps or len(resp_text) > 200:
                # If output contains html code, save as index.html
                if "<!DOCTYPE html>" in resp_text or "<html" in resp_text:
                    clean_html = re.sub(r"^```[a-zA-Z]*\n?", "", resp_text)
                    clean_html = re.sub(r"\n?```$", "", clean_html)
                    idx_file = out_dir / "index.html"
                    idx_file.write_text(clean_html, encoding="utf-8")
                    deliverables.append(idx_file)
                    _open_file_in_browser(idx_file)
                else:
                    report_file = out_dir / f"Hermes_Output_{int(time.time())}.md"
                    report_file.write_text(resp_text, encoding="utf-8")
                    deliverables.append(report_file)

                if player:
                    player.write_log(f"HERMES: Mission Finished.")
                    if notify:
                        say_fn = getattr(player, "request_say", None)
                        if callable(say_fn):
                            say_fn("Rishi, Hermes has finished your task and saved the files to your desktop.")
                break

    except Exception as e:
        logger.error(f"Hermes mission error: {e}")
        if player:
            player.write_log(f"HERMES ERROR: {e}")

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Dispatches Hermes Agent in a dedicated background worker thread on Laptop.
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
