#!/usr/bin/env node
// Deterministic MP4 of any web/canvas game: headless Chrome over the DevTools protocol, no npm deps (Node >= 22
// for the global WebSocket). A VIRTUAL CLOCK replaces requestAnimationFrame / performance.now / Date.now before any
// page script runs: each output frame advances it by 1000/fps*speed ms, runs the queued rAF callbacks, screenshots
// (jpeg) and pipes the frame to ffmpeg (libx264). Footage is smooth and identical per seed however slowly headless
// Chrome rasterises - a slow frame only makes the capture take longer.
//
//   node record_web.mjs --url dist/index.html?seed=3 --out run.mp4 --events run.jsonl \
//     --ready-js 'document.title === "ready"' \
//     --probe-js '({scene: game.scene, key: game.chapter, hp: game.hp, events: (window.__ev||[]).splice(0)})' \
//     --end-js 's && s.scene === "victory"' --tail 4 --speed 2
//
// Flags: --url (http(s)/file URL or a local path) --out x.mp4 --fps 30 --speed 1 --speeds 1,3,3 (speed per probe
//   `key`, 1-based; overrides --speed) --seconds 600 (cap, video time) --tail 4 (video seconds kept after --end-js
//   turns true) --width 1280 --height 720 --quality 82 (jpeg) --events out.jsonl --watch scene,key (probe fields
//   whose changes become events) --sample-every 1 (video seconds between full state samples)
// --ready-js  page expression; recording starts once it is truthy (default: document.readyState === "complete").
// --probe-js  page expression returning a small JSON state, evaluated after every frame. Its `events` array (if any)
//             is logged with t in VIDEO seconds; `key` selects the --speeds entry.
// --end-js    expression over `s` (the last probe state) and the page globals; truthy ends the run after --tail.
// env: CHROME, FFMPEG (else PATH / standard install paths / python imageio_ffmpeg). Exits 1 without writing a
// video when Chrome, ffmpeg or the page is missing.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// ---- pure helpers ------------------------------------------------------------------------------------------------
const NUM = new Set(['fps', 'speed', 'width', 'height', 'seconds', 'tail', 'quality', 'sample-every']);
export function parseArgs(argv) {
  const o = { fps: 30, speed: 1, width: 1280, height: 720, seconds: 600, tail: 4, quality: 82, 'sample-every': 1,
    watch: 'scene,key', 'ready-js': 'document.readyState === "complete"' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const k = a.slice(2);
    const v = argv[i + 1];
    if (v === undefined || v.startsWith('--')) { o[k] = true; continue; }
    o[k] = NUM.has(k) ? Number(v) : v;
    i++;
  }
  if (typeof o.speeds === 'string') o.speeds = o.speeds.split(',').map(Number);
  o.watch = String(o.watch).split(',').filter(Boolean);
  return o;
}
/** Game ms one output frame advances. */
export const stepMs = (fps, speed) => (1000 / fps) * speed;
export const speedFor = (o, key) => (o.speeds ? (o.speeds[Math.max(0, (key || 1) - 1)] ?? o.speeds.at(-1)) : o.speed);
export const timecode = (sec) => {
  const s = Math.max(0, sec);
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${(s % 60).toFixed(2).padStart(5, '0')}`;
};
/** Changes to watched probe fields between two samples, as event records. */
export function diffState(prev, s, watch) {
  if (!s) return [];
  return watch.filter((f) => s[f] !== undefined && (!prev || prev[f] !== s[f]))
    .map((f) => ({ type: 'change', field: f, from: prev ? prev[f] : null, to: s[f] }));
}
export const toUrl = (u) => (/^[a-z][a-z0-9+.-]+:\/\//i.test(u) ? u
  : pathToFileURL(resolve(u.split('?')[0])).href + (u.includes('?') ? u.slice(u.indexOf('?')) : ''));

// The virtual clock, injected before any page script runs.
export const CLOCK = `(() => {
  let now = 0, id = 0, q = [];
  const t0 = Date.now();
  performance.now = () => now;
  Date.now = () => t0 + Math.floor(now);
  window.requestAnimationFrame = (cb) => { q.push([++id, cb]); return id; };
  window.cancelAnimationFrame = (i) => { q = q.filter((x) => x[0] !== i); };
  window.__vclock = { advance(ms) { now += ms; const run = q; q = []; for (const [, cb] of run) { try { cb(now); } catch (e) { console.error(e); } } return now; } };
})();`;

// ---- tool discovery ----------------------------------------------------------------------------------------------
const runs = (cmd, args) => { try { return spawnSync(cmd, args, { stdio: 'ignore' }).status === 0; } catch { return false; } };
export function findFfmpeg() {
  if (process.env.FFMPEG) return existsSync(process.env.FFMPEG) ? process.env.FFMPEG : null;
  if (runs('ffmpeg', ['-version'])) return 'ffmpeg';
  for (const py of ['python3', 'python']) {
    try {
      const r = spawnSync(py, ['-c', 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())'], { encoding: 'utf8' });
      const p = r.status === 0 && r.stdout.trim();
      if (p && existsSync(p)) return p;
    } catch { /* next */ }
  }
  return null;
}
export function findChrome() {
  if (process.env.CHROME) return existsSync(process.env.CHROME) ? process.env.CHROME : null;
  const pf = [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
  const paths = [...pf.map((d) => join(d, 'Google/Chrome/Application/chrome.exe')),
    ...pf.map((d) => join(d, 'Microsoft/Edge/Application/msedge.exe')),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium',
    '/usr/bin/chromium-browser', '/snap/bin/chromium'];
  return paths.find((p) => existsSync(p)) ?? null;
}

// ---- recorder core -----------------------------------------------------------------------------------------------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdp(chrome, W, H) {
  const profile = mkdtempSync(join(tmpdir(), 'rec_'));
  const proc = spawn(chrome, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, `--window-size=${W},${H}`, '--force-device-scale-factor=1', '--allow-file-access-from-files',
    '--mute-audio', '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
  const portFile = join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 150 && !existsSync(portFile); i++) await sleep(100);
  if (!existsSync(portFile)) { proc.kill(); throw new Error(`Chrome did not open a DevTools port: ${chrome}`); }
  const port = readFileSync(portFile, 'utf8').split('\n')[0].trim();
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((x) => x.type === 'page');
    if (!target) await sleep(100);
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const pending = new Map();
  const errors = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method === 'Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
    else if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push(msg.params.args.map((a) => a.value ?? a.description).join(' '));
  };
  const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evaluate = async (expression) => {
    const r = (await send('Runtime.evaluate', { expression, returnByValue: true })).result;
    if (r?.exceptionDetails) throw new Error(`page expression threw: ${expression.slice(0, 80)}: ${r.exceptionDetails.exception?.description || r.exceptionDetails.text}`);
    return r?.result?.value;
  };
  const close = async () => { ws.close(); proc.kill(); await sleep(300); try { rmSync(profile, { recursive: true, force: true }); } catch { /* held */ } };
  return { send, evaluate, close, errors };
}

export async function record(o) {
  if (!o.url) throw new Error('--url is required');
  if (typeof WebSocket === 'undefined') throw new Error('needs Node >= 22 (global WebSocket)');
  const url = toUrl(o.url);
  if (url.startsWith('file:') && !existsSync(fileURLToPath(url.split('?')[0]))) throw new Error(`missing page ${url}: build first`);
  const chrome = findChrome();
  if (!chrome) throw new Error('no Chrome: set CHROME to a Chrome/Chromium/Edge binary');
  const ffmpeg = findFfmpeg();
  if (!ffmpeg) throw new Error('no ffmpeg: set FFMPEG, put ffmpeg on PATH, or pip install imageio-ffmpeg');
  const out = resolve(o.out || 'record.mp4');
  mkdirSync(dirname(out), { recursive: true });
  const c = await cdp(chrome, o.width, o.height);
  let ff = null, ffDone = Promise.resolve(0);
  const events = [];
  try {
    await c.send('Page.enable');
    await c.send('Runtime.enable');
    await c.send('Emulation.setDeviceMetricsOverride', { width: o.width, height: o.height, deviceScaleFactor: 1, mobile: false });
    await c.send('Page.addScriptToEvaluateOnNewDocument', { source: CLOCK });
    await c.send('Page.navigate', { url });
    for (let t0 = Date.now(); !(await c.evaluate(o['ready-js']).catch(() => false)); ) {
      if (Date.now() - t0 > 60000) throw new Error(`page never became ready (--ready-js ${o['ready-js']})`);
      await sleep(50);
    }
    // ffmpeg starts only once the page is up, so a failed launch leaves no half-written video behind.
    ff = spawn(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(o.fps), '-c:v', 'mjpeg', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    ffDone = new Promise((r) => ff.on('close', r));
    const probe = typeof o['probe-js'] === 'string' ? o['probe-js'] : null;
    const endJs = typeof o['end-js'] === 'string' ? o['end-js'] : null;
    const sampleFrames = Math.max(1, Math.round(o['sample-every'] * o.fps));
    let prev = null, endAt = Infinity, frame = 0, gameMs = 0;
    const maxFrames = Math.round(o.seconds * o.fps);
    const wall = Date.now();
    while (frame < maxFrames && frame < endAt) {
      gameMs = await c.evaluate(`window.__vclock.advance(${stepMs(o.fps, speedFor(o, prev?.key))})`);
      const s = probe ? await c.evaluate(probe) : null;
      const vt = +(frame / o.fps).toFixed(3);
      for (const e of [...diffState(prev, s, o.watch), ...(s?.events ?? [])]) events.push({ t: vt, tc: timecode(vt), ...e });
      if (s && frame % sampleFrames === 0) events.push({ t: vt, tc: timecode(vt), type: 'sample', game_s: +(gameMs / 1000).toFixed(3), ...s, events: undefined });
      if (endAt === Infinity && endJs && await c.evaluate(`((s) => (${endJs}))(${JSON.stringify(s)})`)) {
        endAt = frame + 1 + Math.round(o.tail * o.fps);
        events.push({ t: vt, tc: timecode(vt), type: 'end' });
      }
      prev = s;
      const shot = await c.send('Page.captureScreenshot', { format: 'jpeg', quality: o.quality, optimizeForSpeed: true });
      if (!ff.stdin.write(Buffer.from(shot.result.data, 'base64'))) await new Promise((r) => ff.stdin.once('drain', r));
      frame++;
      if (frame % (o.fps * 30) === 0) console.log(`video ${timecode(vt)}  game ${(gameMs / 1000).toFixed(0)}s  wall ${((Date.now() - wall) / 1000).toFixed(0)}s`);
    }
    console.log(`${frame} frames = ${timecode(frame / o.fps)} video, ${(gameMs / 1000).toFixed(2)}s game, ${((Date.now() - wall) / 1000).toFixed(0)}s wall, ended by ${endAt === Infinity ? '--seconds cap' : '--end-js'}`);
    for (const e of c.errors.slice(0, 10)) console.log('  page error: ' + e);
  } finally {
    if (ff) ff.stdin.end();
    const code = await ffDone;
    await c.close();
    if (o.events) writeFileSync(resolve(o.events), events.map((e) => JSON.stringify(e)).join('\n') + '\n');
    if (code) throw new Error(`ffmpeg exited ${code}`);
  }
  return { out, events };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  record(parseArgs(process.argv.slice(2))).catch((e) => { console.error('FAIL: ' + (e?.message || e)); process.exit(1); });
}
