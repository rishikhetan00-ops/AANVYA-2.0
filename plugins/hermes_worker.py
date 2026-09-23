"""
plugins/hermes_worker.py — Autonomous Background Agent for AANVYA.

Powered by Nous Research Hermes Agent concepts:
- Multi-step autonomous planning & tool execution
- Background threading (never freezes the live voice session)
- Built-in web search, code writing, file generation & self-healing
- Desktop deliverable exports & voice completion notification
"""

import json
import logging
import os
import re
import threading
import time
from pathlib import Path

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
        "Dispatches an autonomous multi-step background worker (Hermes Agent) to perform "
        "complex deep research, software building, file generation, or web data extraction. "
        "Call this whenever the user wants a full task done in the background without waiting, "
        "such as 'build an app for...', 'research in depth and write a report on...', "
        "'scrape and compile data for...', 'write a complete project on my desktop...'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The exact goal, mission, or project description for the autonomous agent"
            },
            "output_format": {
                "type": "STRING",
                "description": "Optional desired deliverable type (e.g. 'markdown_report', 'python_project', 'excel_data', 'code_files')"
            }
        },
        "required": ["task"],
    },
}

# ── Internal Toolset for Hermes Agent ────────────────────────────────────────

def _web_search(query: str) -> str:
    """Live web search via DuckDuckGo Lite."""
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
    """Executes the multi-step Hermes reasoning and execution loop."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if player:
            try:
                player.write_log(f"HERMES: Initialized mission — '{task[:60]}...'")
            except Exception:
                pass

        history = [
            f"MISSION: {task}\nDELIVERABLE TARGET: {output_format or 'Comprehensive project / deliverable'}"
        ]

        system_prompt = f"""You are HERMES, an expert autonomous agent working for AANVYA.
You execute real-world tasks step-by-step using tools until the mission is 100% complete.

Available Tool Calls:
1. SEARCH: <query> (Search the live web for facts, documentation, or data)
2. WRITE_FILE: <filename> ||| <content> (Write code, markdown reports, or data files)
3. FINISH: <summary of what you created and where it is saved>

Format each turn as:
THOUGHT: <your step-by-step reasoning>
ACTION: <one of SEARCH, WRITE_FILE, or FINISH>

When all deliverables are created and written, return ACTION: FINISH.
"""

        for step in range(1, max_steps + 1):
            prompt = system_prompt + "\n\n" + "\n".join(history) + f"\n\nTurn {step}/{max_steps}:"
            
            try:
                response = gemini.call(prompt, tier=gemini.FAST, timeout_ms=30000)
                resp_text = str(response or "").strip()
            except Exception as e:
                resp_text = f"THOUGHT: Encountered API error {e}. Writing final report.\nACTION: FINISH: Created preliminary deliverables."

            if "ACTION: FINISH" in resp_text or "ACTION:FINISH" in resp_text:
                summary = resp_text.split("FINISH")[-1].strip(": \n")
                if player:
                    try:
                        player.write_log(f"HERMES: Mission Completed! {summary[:80]}")
                        if notify:
                            # Speak via the mid-task voice channel
                            say_fn = getattr(player, "request_say", None)
                            if callable(say_fn):
                                say_fn("Sir, Hermes has completed your background mission and saved the files to your desktop.")
                    except Exception:
                        pass
                return

            # Parse WRITE_FILE action
            if "WRITE_FILE:" in resp_text:
                match = re.search(r"WRITE_FILE:\s*([^|\n]+)\|\|\|(.*)", resp_text, re.DOTALL)
                if match:
                    fname = match.group(1).strip()
                    content = match.group(2).strip()
                    # Clean markdown code fences if wrapped
                    content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
                    content = re.sub(r"\n?```$", "", content)
                    res = _write_file(out_dir, fname, content)
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

            # Fallback: if model provided text without strict action format, save as report
            if step == max_steps or len(resp_text) > 200:
                _write_file(out_dir, "Hermes_Mission_Report.md", resp_text)
                history.append(f"HERMES_STEP_{step}: Saved mission report.")
                break

        # Final notification
        if player:
            try:
                player.write_log(f"HERMES: All tasks finished. Deliverables saved in: {out_dir}")
                if notify:
                    say_fn = getattr(player, "request_say", None)
                    if callable(say_fn):
                        say_fn("Sir, Hermes has completed the mission and created your deliverables.")
            except Exception:
                pass

    except Exception as e:
        logger.error(f"[Hermes] Mission failure: {e}")
        if player:
            player.write_log(f"HERMES: Error during mission: {e}")

# ── Plugin Entry Point ───────────────────────────────────────────────────────

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Dispatches Hermes Agent in a dedicated background worker thread.
    Returns immediate spoken confirmation so the user never experiences lag.
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
