"""GTMAgent Dashboard — chat interface + stats sidebar."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import html

dashboard_app = FastAPI(title="GTMAgent Dashboard")
dashboard_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GTMAgent</title>
<style>
:root { --bg: #0a0a0a; --fg: #eee; --dim: #666; --dim2: #3a3a3a; --border: #1c1c1c; --green: #34d058; --orange: #e3b341; --red: #f85149; --input-bg: #111; --accent: #6ecbf5; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, 'Inter', 'Segoe UI', 'Roboto', sans-serif;
  background: var(--bg); color: var(--fg);
  line-height: 1.5; font-size: 13px;
  -webkit-font-smoothing: antialiased;
  height: 100vh; overflow: hidden;
}

.shell { display: grid; grid-template-columns: 1fr 300px; grid-template-rows: 52px 1fr; height: 100vh; }

header {
  grid-column: 1 / -1;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
  background: linear-gradient(180deg, #111 0%, var(--bg) 100%);
}
header h1 { font-size: 14px; font-weight: 600; letter-spacing: 0.08em; color: var(--accent); }
.header-right { display: flex; gap: 16px; align-items: center; }
.svc-status { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--dim); }
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--dim2); flex-shrink: 0; }
.dot.up { background: var(--green); }
.dot.down { background: var(--red); }

/* ---- Chat panel ---- */
.chat-panel { display: flex; flex-direction: column; border-right: 1px solid var(--border); overflow: hidden; }
.chat-messages { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: var(--dim2); border-radius: 2px; }

.msg { max-width: 85%; }
.msg.user { align-self: flex-end; }
.msg.assistant { align-self: flex-start; }
.msg-bubble {
  padding: 12px 16px; border-radius: 12px; font-size: 13px;
  line-height: 1.7; white-space: pre-wrap; word-break: break-word;
}
.msg.user .msg-bubble { background: #1a1a2a; border: 1px solid #252540; border-radius: 12px 12px 4px 12px; }
.msg.assistant .msg-bubble { background: #141414; border: 1px solid var(--border); border-radius: 12px 12px 12px 4px; }

.msg-tool {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; color: var(--dim); padding: 6px 0;
}
.tool-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--orange); flex-shrink: 0; animation: pulse 1.5s infinite; }
.tool-dot.done { background: var(--green); animation: none; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

.audit-card {
  border: 1px solid var(--border); border-radius: 6px;
  padding: 12px 14px; margin-top: 8px; font-size: 12px;
}
.audit-card-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.audit-card-title { font-weight: 500; }
.audit-card-score { font-size: 18px; font-weight: 300; }
.audit-card-rec { font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; display: flex; align-items: center; gap: 5px; margin-bottom: 8px; }
.rec-dot { width: 5px; height: 5px; border-radius: 50%; }
.rec-dot.STRONG_BUY, .rec-dot.BUY { background: var(--green); }
.rec-dot.CAUTIOUS, .rec-dot.WATCH { background: var(--orange); }
.rec-dot.AVOID { background: var(--red); }
.score-row { display: flex; justify-content: space-between; padding: 3px 0; color: var(--dim); font-size: 11px; }
.score-bar-track { flex: 1; height: 2px; background: var(--border); margin: 0 10px; align-self: center; position: relative; }
.score-bar-fill { height: 100%; }
.score-bar-fill.high { background: var(--green); }
.score-bar-fill.mid { background: var(--orange); }
.score-bar-fill.low { background: var(--red); }

.zc-ad-card {
  border: 1px solid #1a3a1a; border-radius: 6px;
  padding: 12px 14px; margin-top: 8px; font-size: 12px;
  background: #050f05;
}
.zc-ad-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.zc-ad-label { font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--green); }
.zc-ad-score-badge { font-size: 9px; color: var(--dim); }
.zc-ad-title { font-weight: 500; font-size: 13px; margin-bottom: 6px; line-height: 1.4; }
.zc-ad-msg { color: var(--dim); font-size: 11px; line-height: 1.5; margin-bottom: 10px; }
.zc-ad-cta {
  display: inline-block; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
  background: #0a1e0a; border: 1px solid #1a3a1a; color: var(--green);
  padding: 4px 10px; border-radius: 3px; text-decoration: none; font-family: inherit; cursor: pointer;
}
.zc-ad-cta:hover { background: #142814; }

/* ZeroClick Toggle Switch */
.zc-toggle-wrap { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.zc-toggle-label { font-size: 9px; color: var(--dim); }
.zc-toggle { position: relative; width: 28px; height: 16px; cursor: pointer; }
.zc-toggle input { display: none; }
.zc-toggle-track {
  position: absolute; inset: 0; border-radius: 8px;
  background: #1a1a1a; border: 1px solid var(--border); transition: background 0.2s, border-color 0.2s;
}
.zc-toggle input:checked + .zc-toggle-track { background: #0a2a0a; border-color: var(--green); }
.zc-toggle-thumb {
  position: absolute; top: 2px; left: 2px; width: 12px; height: 12px;
  border-radius: 50%; background: var(--dim); transition: transform 0.2s, background 0.2s;
}
.zc-toggle input:checked ~ .zc-toggle-thumb { transform: translateX(12px); background: var(--green); }

/* ZeroClick Ad Gate Overlay */
#zc-gate-overlay {
  display: none;
  position: absolute; inset: 0; z-index: 90;
  background: rgba(0,0,0,0.92);
  backdrop-filter: blur(8px);
  flex-direction: column; align-items: center; justify-content: center;
  padding: 32px;
}
#zc-gate-overlay.active { display: flex; }
.zc-gate-card {
  max-width: 440px; width: 100%;
  border: 1px solid #1a4a1a; border-radius: 12px;
  background: #060e06; padding: 32px 28px; text-align: center;
  box-shadow: 0 0 60px rgba(52,208,88,0.08);
}
.zc-gate-badge {
  font-size: 9px; letter-spacing: 0.15em; text-transform: uppercase;
  color: var(--green); margin-bottom: 16px; display: inline-block;
}
.zc-gate-title {
  font-size: 20px; font-weight: 500; line-height: 1.4; margin-bottom: 12px;
}
.zc-gate-msg {
  font-size: 12px; color: var(--dim); line-height: 1.6; margin-bottom: 24px;
}
.zc-gate-cta {
  display: inline-block; font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase;
  background: var(--green); color: #000; font-weight: 700;
  padding: 12px 36px; border-radius: 6px; text-decoration: none;
  font-family: inherit; cursor: pointer; border: none;
  transition: background 0.15s, transform 0.1s;
}
.zc-gate-cta:hover { background: #45e06a; transform: scale(1.03); }
.zc-gate-hint {
  font-size: 11px; color: var(--fg); margin-top: 18px; letter-spacing: 0.04em;
  font-weight: 500;
}
.zc-gate-sponsor {
  font-size: 9px; color: #2a5a2a; margin-top: 10px;
}

.chat-input-area {
  padding: 16px 24px; border-top: 1px solid var(--border);
  display: flex; gap: 10px; align-items: center;
  background: linear-gradient(0deg, #0e0e0e 0%, transparent 100%);
}
#chat-input {
  flex: 1; background: var(--input-bg); border: 1px solid var(--border);
  color: var(--fg); font-family: inherit; font-size: 13px;
  padding: 12px 16px; border-radius: 10px; outline: none;
  resize: none; min-height: 20px; max-height: 120px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
#chat-input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(110,203,245,0.1); }
#chat-input::placeholder { color: var(--dim2); }
#send-btn {
  background: var(--accent); color: #000; border: none;
  font-family: inherit; font-size: 11px; letter-spacing: 0.06em;
  text-transform: uppercase; padding: 12px 20px; border-radius: 10px;
  cursor: pointer; font-weight: 600; white-space: nowrap;
  transition: background 0.15s, transform 0.1s;
}
#send-btn:hover { background: #8dd7f8; transform: scale(1.02); }
#send-btn:disabled { opacity: 0.3; cursor: default; transform: none; }

/* ---- Stats sidebar ---- */
.stats-panel { overflow-y: auto; padding: 16px 16px; background: #0d0d0d; border-left: 1px solid var(--border); }
.stats-panel::-webkit-scrollbar { width: 4px; }
.stats-panel::-webkit-scrollbar-thumb { background: var(--dim2); border-radius: 2px; }

.section-label {
  font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--dim); margin-bottom: 12px; margin-top: 20px;
}
.section-label:first-child { margin-top: 0; }

.metric { margin-bottom: 16px; }
.metric-value { font-size: 28px; font-weight: 300; letter-spacing: -0.02em; line-height: 1; }
.metric-label { font-size: 11px; color: var(--dim); margin-top: 3px; }

.stat-row {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 4px 0; border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.stat-row:last-child { border-bottom: none; }
.stat-key { color: var(--dim); }
.stat-val { font-weight: 500; }

.divider { height: 1px; background: var(--border); margin: 16px 0; }

.tx-item { padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 12px; }
.tx-item:last-child { border-bottom: none; }
.tx-top { display: flex; justify-content: space-between; }
.tx-endpoint { font-weight: 500; }
.tx-credits { color: var(--dim); }
.tx-meta { color: var(--dim); font-size: 10px; margin-top: 1px; }

.vendor-row { display: flex; align-items: center; padding: 4px 0; gap: 8px; font-size: 11px; }
.vendor-name { flex: 1; color: var(--dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vendor-bar { flex: 1.5; height: 2px; background: var(--border); }
.vendor-fill { height: 100%; background: var(--fg); transition: width 0.4s ease; }
.vendor-amt { width: 32px; text-align: right; }

.empty { color: var(--dim2); font-size: 11px; padding: 8px 0; }

/* ---- Live orchestration grid (TrinityOS-style) ---- */
.orch-