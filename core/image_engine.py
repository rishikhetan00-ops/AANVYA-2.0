# Core High-Fidelity Photorealistic Image Engine (FLUX 1.1 Pro via Puter.js)
import os
import json
import subprocess
import re
from pathlib import Path
from typing import Optional

def enhance_realism_prompt(raw_prompt: str) -> str:
    cleaned = raw_prompt.strip()
    
    # If the user asks for a poster, graphic, event flyer, or specific scene, don't force 'portrait of a person'
    if any(k in cleaned.lower() for k in ['poster', 'flyer', 'banner', 'event', 'dance', 'concert', 'car', 'landscape', 'building', 'interior', 'logo']):
        return f'{cleaned}, highly detailed, professional visual design, cinematic lighting, 8k resolution'
    
    if any(k in cleaned.lower() for k in ['f/1.', '35mm', '85mm', 'bokeh', 'skin texture', 'photograph', 'hasselblad']):
        return cleaned
    
    return f'Authentic cinematic photograph of {cleaned}, natural lighting, professional photography, highly detailed, photorealistic, 8k resolution'

def generate_flux_image(prompt: str, output_path: str, model: str = 'flux-1.1-pro') -> Optional[str]:
    final_prompt = enhance_realism_prompt(prompt)
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    
    script_path = Path(__file__).parent / 'puter_image_generator.js'
    if not script_path.exists():
        script_path = Path('core/puter_image_generator.js').resolve()
    
    cmd = ['node', str(script_path), final_prompt, str(out_p), model]
    
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and out_p.exists() and out_p.stat().st_size > 1000:
            return str(out_p)
        else:
            print(f'[ImageEngine] Generation error: {proc.stderr} {proc.stdout}')
            return None
    except Exception as e:
        print(f'[ImageEngine] Exception: {e}')
        return None
