#!/usr/bin/env node
/**
 * Self-contained installer for the "Dousea Darts" (douseadarts) custom game
 * on a Dartsnut PixelDart Raspberry Pi.
 *
 * Usage:
 *   node deploy_douseadarts.js [host]
 *   (default host: 172.16.102.254)
 */

const fs = require("fs");
const path = require("path");

const HOST = process.argv[2] || "172.16.102.254";
const WS_URL = `ws://${HOST}:9251/ws`;
const MCP_URL = `http://${HOST}:9252/mcp`;
const GAME_DIR = __dirname;

const backendMeta = JSON.parse(
  fs.readFileSync(path.join(GAME_DIR, ".dartsnut_backend.json"), "utf8")
);
const confJson = JSON.parse(
  fs.readFileSync(path.join(GAME_DIR, "conf.json"), "utf8")
);

const pyFiles = [
  "game_modes.py",
  "dartboard.py",
  "scoreboard.py",
  "game_state.py",
  "state_renderer.py",
  "game.py",
  "main.py",
];

const piInstallerScript = `import base64, io, json, os, shutil, sys
os.chdir("/home/rpi/dartsnut_rpi")
sys.path.insert(0, "/home/rpi/dartsnut_rpi")

app_root = "/home/rpi/dartsnut_rpi/apps/douseadarts"
src_root = "/home/rpi/dartsnut_rpi/apps/01dartgame"

# 1. Copy Micro5.ttf and sound/ assets from 01dartgame
if os.path.isfile(os.path.join(src_root, "Micro5.ttf")):
    shutil.copy2(os.path.join(src_root, "Micro5.ttf"), os.path.join(app_root, "Micro5.ttf"))

src_sound = os.path.join(src_root, "sound")
dst_sound = os.path.join(app_root, "sound")
if os.path.isdir(src_sound):
    os.makedirs(dst_sound, exist_ok=True)
    for fn in os.listdir(src_sound):
        s_file = os.path.join(src_sound, fn)
        if os.path.isfile(s_file):
            shutil.copy2(s_file, os.path.join(dst_sound, fn))

# 2. Generate 128x128 Basement Arcade preview image for preview_cache and conf.json
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (128, 128), (8, 0, 18))
draw = ImageDraw.Draw(img)

for y in range(128):
    r = int(52 * (1 - y / 127.0) + 6 * (y / 127.0))
    b = int(96 * (1 - y / 127.0) + 16 * (y / 127.0))
    draw.line([(0, y), (127, y)], fill=(r, 0, b))
for y in range(0, 128, 3):
    draw.line([(0, y), (127, y)], fill=(3, 0, 8))

draw.rectangle([0, 0, 127, 127], outline=(255, 43, 214), width=1)
draw.rectangle([2, 2, 125, 125], outline=(0, 240, 255), width=1)
for bx in range(4, 124, 8):
    col = (255, 230, 0) if (bx // 8) % 2 == 0 else (255, 43, 214)
    draw.rectangle([bx, 0, bx + 1, 1], fill=col)
    draw.rectangle([bx, 126, bx + 1, 127], fill=col)

cx, cy = 64, 86
draw.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=(22, 4, 46), outline=(255, 43, 214), width=2)
draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(12, 2, 26), outline=(0, 240, 255), width=2)
draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(57, 255, 20))
draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(255, 230, 0))

font_path = os.path.join(app_root, "Micro5.ttf")
try:
    f_big = ImageFont.truetype(font_path, 26)
    f_med = ImageFont.truetype(font_path, 20)
    f_sm = ImageFont.truetype(font_path, 13)
except Exception:
    f_big = ImageFont.load_default()
    f_med = ImageFont.load_default()
    f_sm = ImageFont.load_default()

def center_text(y, text, font, fill, shadow=(0, 0, 0)):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (128 - w) // 2
    draw.text((x + 1, y + 1), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)

center_text(8, "DOUSEA", f_big, (255, 43, 214), (60, 0, 50))
center_text(27, "DARTS", f_med, (0, 240, 255), (0, 55, 75))
center_text(44, "BASEMENT ARCADE", f_sm, (255, 230, 0), (0, 0, 0))

cache_dir = os.path.expanduser("~/.dartsnut/preview_cache")
os.makedirs(cache_dir, exist_ok=True)
img_path = os.path.join(cache_dir, "douseadarts.png")
meta_path = os.path.join(cache_dir, "douseadarts.meta.json")
img.save(img_path, format="PNG")
with open(meta_path, "w", encoding="utf-8") as mf:
    json.dump({"etag": "custom-v1", "last_modified": "Sun, 25 Oct 2026 00:00:00 GMT", "fetch_time": 9999999999.0}, mf)

buf = io.BytesIO()
img.save(buf, format="PNG")
b64_png = base64.b64encode(buf.getvalue()).decode("ascii")
conf_file = os.path.join(app_root, "conf.json")
with open(conf_file, "r", encoding="utf-8") as cf:
    cdata = json.load(cf)
cdata["preview"] = [b64_png]
with open(conf_file, "w", encoding="utf-8") as cf:
    json.dump(cdata, cf, indent=2)

# 3. Prepare .venv and .dartsnut_stamp using firmware's ensure_app_venv
from core.app_env import ensure_app_venv, app_venv_ready
venv_ok = ensure_app_venv("douseadarts", force=True)
venv_ready = app_venv_ready("douseadarts")

# 4. Safeguard remote_device_config.py so Cloud Sync never deletes local custom games (where download_url is empty)
rdc_path = "/home/rpi/dartsnut_rpi/runtime/remote_device_config.py"
with open(rdc_path, "r", encoding="utf-8") as rf:
    rdc_src = rf.read()

patched_rdc = False
target_line = "        for game_id in sorted(local_ids - remote_ids):\\n"
guard_block = "        for game_id in sorted(local_ids - remote_ids):\\n            if not resolve_app_metadata(game_id).get(\\"download_url\\"):\\n                continue\\n"
if "if not resolve_app_metadata(game_id).get(\\"download_url\\"):" not in rdc_src and target_line in rdc_src:
    rdc_src = rdc_src.replace(target_line, guard_block, 1)
    with open(rdc_path, "w", encoding="utf-8") as rf:
        rf.write(rdc_src)
    patched_rdc = True

with open("/tmp/douseadarts_install_result.json", "w", encoding="utf-8") as out_f:
    json.dump({"venv_ok": venv_ok, "venv_ready": venv_ready, "preview_saved": os.path.isfile(img_path), "patched_rdc": patched_rdc}, out_f)
`;

function buildCommands() {
  const cmds = [
    { action: "create_directory", directory: "douseadarts" },
    {
      action: "send_file",
      file_name: "douseadarts/.dartsnut_backend.json",
      file_data: Buffer.from(JSON.stringify(backendMeta, null, 2), "utf8").toString("base64"),
    },
    {
      action: "send_file",
      file_name: "douseadarts/conf.json",
      file_data: Buffer.from(JSON.stringify(confJson, null, 2), "utf8").toString("base64"),
    },
  ];

  for (const fn of pyFiles) {
    const content = fs.readFileSync(path.join(GAME_DIR, fn));
    cmds.push({
      action: "send_file",
      file_name: `douseadarts/${fn}`,
      file_data: content.toString("base64"),
    });
  }

  cmds.push(
    {
      action: "sideload_upload",
      session_id: "install_douseadarts",
      app_id: "installer",
      relative_path: "main.py",
      file_data: Buffer.from(piInstallerScript, "utf8").toString("base64"),
    },
    {
      action: "sideload_start",
      session_id: "install_douseadarts",
      app_id: "installer",
      size: [128, 160],
      params: {},
    }
  );
  return cmds;
}

function runWsBatch(commands) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL);
    let idx = 0;
    ws.onerror = (err) => reject(err);
    ws.onopen = () => {
      ws.send(JSON.stringify({ ...commands[idx], req_id: idx + 1 }));
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.req_id !== idx + 1 && msg.req_id !== undefined) return;
      console.log(`Step ${idx + 1}/${commands.length} (${commands[idx].action}):`, msg.message || msg.error || "OK");
      idx++;
      if (idx < commands.length) {
        ws.send(JSON.stringify({ ...commands[idx], req_id: idx + 1 }));
      } else {
        ws.close();
        resolve();
      }
    };
  });
}

function readInstallResult() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL);
    ws.onerror = (err) => reject(err);
    ws.onopen = () => {
      ws.send(JSON.stringify({ action: "get_file", file_name: "../../../../tmp/douseadarts_install_result.json", req_id: 1 }));
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      ws.close();
      if (msg.file_data) {
        resolve(JSON.parse(Buffer.from(msg.file_data, "base64").toString("utf8")));
      } else {
        resolve(null);
      }
    };
  });
}

async function restartMainService() {
  const resp = await fetch(MCP_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/call",
      params: { name: "restart_main_service", arguments: {} },
    }),
  });
  return await resp.json();
}

(async () => {
  console.log(`Deploying Dousea Darts to ${HOST}...`);
  await runWsBatch(buildCommands());
  await new Promise((r) => setTimeout(r, 4000));
  const res = await readInstallResult();
  console.log("Install result:", res);
  if (res && res.patched_rdc) {
    console.log("remote_device_config.py was newly patched; restarting dartsnut_python.service and re-verifying...");
    await restartMainService();
    await new Promise((r) => setTimeout(r, 4000));
    await runWsBatch(buildCommands());
    await new Promise((r) => setTimeout(r, 4000));
    console.log("Re-verify result:", await readInstallResult());
  }
  console.log("Dousea Darts deployment complete!");
})();
