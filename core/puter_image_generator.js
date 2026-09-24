const { init } = require('@heyputer/puter.js/src/init.cjs');
const fs = require('fs');
const path = require('path');

async function generate(prompt, outputPath, model = 'flux-schnell') {
  try {
    const candidates = [
      path.resolve(__dirname, '../config/api_keys.json'),
      path.resolve('config/api_keys.json'),
      path.resolve('/home/ubuntu/Mark-LIV/config/api_keys.json')
    ];
    let token = process.env.PUTER_AUTH_TOKEN;
    if (!token) {
      for (const p of candidates) {
        if (fs.existsSync(p)) {
          try {
            const d = JSON.parse(fs.readFileSync(p, 'utf-8'));
            if (d.puter_auth_token) {
              token = d.puter_auth_token;
              break;
            }
          } catch(e) {}
        }
      }
    }

    if (!token) {
      console.error(JSON.stringify({ success: false, error: 'No puter_auth_token found' }));
      process.exit(1);
    }

    const puter = init(token);
    const res = await puter.ai.txt2img(prompt, { model });
    const imgUrl = res && res.src ? res.src : (typeof res === 'string' ? res : null);
    if (!imgUrl) {
      console.error(JSON.stringify({ success: false, error: 'No image URL in response' }));
      process.exit(1);
    }

    const resp = await fetch(imgUrl);
    if (!resp.ok) {
      console.error(JSON.stringify({ success: false, error: 'Failed to download image HTTP ' + resp.status }));
      process.exit(1);
    }

    const arrayBuffer = await resp.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    
    const resolvedOut = path.resolve(outputPath);
    fs.mkdirSync(path.dirname(resolvedOut), { recursive: true });
    fs.writeFileSync(resolvedOut, buffer);

    console.log(JSON.stringify({ success: true, path: resolvedOut, size: buffer.length }));
  } catch (err) {
    console.error(JSON.stringify({ success: false, error: err.message || String(err) }));
    process.exit(1);
  }
}

const args = process.argv.slice(2);
const prompt = args[0] || 'A realistic 35mm photograph of a coffee cup';
const out = args[1] || 'output.jpg';
const model = args[2] || 'flux-schnell';

generate(prompt, out, model);
