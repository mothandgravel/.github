// Local-only recording utility. Run: node capture-preview.mjs
// Proxies the maritime study on :3015 to :3016 and adds a canvas recorder.
// Records the actual canvas, with no generated frames or simulated telemetry.
import http from 'node:http';

const recorder = String.raw`
const panel = document.createElement('aside');
panel.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:10000;background:#101c22;padding:12px;color:#eee;border:1px solid #c6b894;font:12px monospace';
const button = document.createElement('button');
button.textContent = 'Record 20 seconds';
const status = document.createElement('span');
status.style.marginLeft = '10px';
panel.append(button, status); document.body.append(panel);
button.onclick = () => {
  const canvas = [...document.querySelectorAll('canvas')].filter(c => c.clientWidth && c.clientHeight).sort((a,b) => b.clientWidth*b.clientHeight-a.clientWidth*a.clientHeight)[0];
  if (!canvas) { status.textContent = 'No visible canvas'; return; }
  const stream = canvas.captureStream(30);
  const mimeType = ['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(t => MediaRecorder.isTypeSupported(t));
  const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8000000 });
  const chunks = []; let timer;
  recorder.ondataavailable = e => { if(e.data.size) chunks.push(e.data); };
  recorder.onerror = () => { status.textContent = 'Recording failed'; button.disabled = false; clearInterval(timer); stream.getTracks().forEach(t=>t.stop()); };
  recorder.onstop = () => {
    clearInterval(timer); stream.getTracks().forEach(t=>t.stop());
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob(chunks, {type:mimeType}));
    link.download = 'maritime-canvas-' + new Date().toISOString().replace(/[:.]/g,'-') + '.webm';
    link.textContent = 'Download recording';
    status.replaceChildren(link); button.disabled = false;
  };
  button.disabled = true; const start = Date.now(); recorder.start(1000);
  status.textContent = 'Recording 0 / 20 s';
  timer = setInterval(() => { const elapsed = (Date.now()-start)/1000; status.textContent = 'Recording ' + Math.floor(elapsed) + ' / 20 s'; if(elapsed>=20) recorder.stop(); }, 250);
};`;

http.createServer(async (request, response) => {
  try {
    const path = new URL(request.url, 'http://127.0.0.1:3016').pathname;
    if (path === '/capture-recorder.js') {
      response.writeHead(200, {'Content-Type':'text/javascript'}); response.end(recorder); return;
    }
    const upstream = await fetch('http://127.0.0.1:3015' + request.url);
    const headers = {'Content-Type':upstream.headers.get('content-type') || 'application/octet-stream', 'Cache-Control':'no-store'};
    response.writeHead(upstream.status, headers);
    if (path === '/') response.end((await upstream.text()).replace('</body>','<script type="module" src="/capture-recorder.js"></script></body>'));
    else response.end(Buffer.from(await upstream.arrayBuffer()));
  } catch { response.writeHead(502); response.end('Start the maritime study on port 3015 first.'); }
}).listen(3016, '127.0.0.1', () => console.log('Canvas recording preview: http://127.0.0.1:3016/'));
