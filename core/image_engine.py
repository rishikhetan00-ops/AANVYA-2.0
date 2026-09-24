# Core High-Fidelity Photorealistic Image Engine (FLUX.1 via Puter.js)
import os
import json
import subprocess
from pathlib import Path
from typing import Optional

def enhance_realism_prompt(raw_prompt: str) -> str:
    cleaned = raw_prompt.strip()
    if any(k in cleaned.lower() for k in ['f/1.', '35mm', '85mm', 'bokeh', 'skin texture', 'photograph', 'hasselblad']):
        return cleaned
    
    return f'Authentic cinematic 35mm raw photograph of {cleaned}, natural morning window lighting, shot on Sony A7R V with 85mm f/1.4 GM lens, natural skin texture with subtle fine pores, photorealistic, shallow depth of field, 8k resolution'

def generate_flux_image(prompt: str, output_path: str, model: str = 'flux-1.1-pro') -> Optional[str]:
    prompt = enhance_realism_prompt(prompt)
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    
    script_path = Path(__file__).parent / 'puter_image_generator.js'
    if not script_path.exists():
        script_path = Path('core/puter_image_generator.js').resolve()
    
    cmd = ['node', str(script_path), prompt, str(out_p), model]
    
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
