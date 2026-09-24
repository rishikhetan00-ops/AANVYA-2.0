# Autonomous Social Media Post & Creative Asset Generator for Aanvya & Hermes
import os
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    from core.image_engine import generate_flux_image
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.image_engine import generate_flux_image

def generate_full_social_post(user_request: str, output_dir: Path) -> Dict[str, Any]:
    """
    Intelligently analyzes any post/flyer/poster request:
    1. Extracts headline, date, location, theme, and visual style.
    2. Constructs a high-impact FLUX 1.1 Pro prompt with exact typography quotes.
    3. Generates the visual graphic/poster.
    4. Composes ready-to-publish viral social media captions with emojis and hashtags.
    """
    from core import gemini
    
    analysis_prompt = f"""You are an elite Creative Director and Social Media Marketer.
The user wants to create a visual post / poster:
USER REQUEST: "{user_request}"

Output a strict JSON object with these fields:
1. "visual_prompt": A highly specific, professional prompt for FLUX 1.1 Pro. If it's a poster/flyer, include bold typography text in quotes like "EVENT TITLE" and "DATE/LOCATION", specify color palette, lighting, composition, and style.
2. "headline": Short punchy title for the post.
3. "caption": A high-converting, engaging Instagram/LinkedIn/Twitter caption with emojis, event details, call to action.
4. "hashtags": 5-10 relevant trending hashtags.

Respond ONLY with valid JSON, nothing else."""

    try:
        resp = gemini.call(analysis_prompt, tier=gemini.SMART, timeout_ms=25000)
        raw_text = getattr(resp, "text", None) or str(resp or "")
        clean_json = re.search(r"\{[\s\S]*\}", raw_text)
        if clean_json:
            data = json.loads(clean_json.group(0))
        else:
            data = {
                "visual_prompt": f"A modern professional graphic design poster for {user_request}, bold typography, vibrant lighting, 8k resolution",
                "headline": "Upcoming Event",
                "caption": f"Exciting event announcement: {user_request}! Don't miss out. Mark your calendars!",
                "hashtags": "#Event #Live #Announcement"
            }
    except Exception as e:
        data = {
            "visual_prompt": f"A modern professional graphic design poster for {user_request}, bold typography, vibrant lighting, 8k resolution",
            "headline": "Special Announcement",
            "caption": f"{user_request}\n\nJoin us for an unforgettable experience!",
            "hashtags": "#Live #Event"
        }

    # Generate Image
    img_filename = f"Post_{int(time.time())}.jpg"
    img_path = output_dir / img_filename
    
    flux_prompt = data.get("visual_prompt", user_request)
    saved_img = generate_flux_image(flux_prompt, str(img_path))
    
    return {
        "success": bool(saved_img and Path(saved_img).exists()),
        "image_path": str(img_path) if saved_img else None,
        "headline": data.get("headline", ""),
        "caption": data.get("caption", ""),
        "hashtags": data.get("hashtags", ""),
        "visual_prompt": flux_prompt
    }
