"""AgentAudit Dashboard — chat interface + stats sidebar."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

dashboard_app = FastAPI(title="AgentAudit Dashboard")
dashboard_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentAudit</title>
<style>
:root { --bg: #000; --fg: #fff; --dim: #555; --dim2: #333; --border: #1a1a1a; --green: #34d058; --orange: #e3b341; --red: #f85149; --input-bg: #0a0a0a; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  background: var(--bg); color: var(--fg);
  line-height: 1.5; font-size: 13px;
  -webkit-font-smoothing: antialiased;
  height: 100vh; overflow: hidden;
}

.shell { display: grid; grid-template-columns: 1fr 320px; grid-template-rows: 48px 1fr; height: 100vh; }

header {
  grid-column: 1 / -1;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}
header h1 { font-size: 13px; font-weight: 400; letter-spacing: 0.15em; text-transform: uppercase; }
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
  padding: 10px 14px; border-radius: 6px; font-size: 13px;
  line-height: 1.6; white-space: pre-wrap; word-break: break-word;
}
.msg.user .msg-bubble { background: #111; border: 1px solid var(--border); }
.msg.assistant .msg-bubble { background: transparent; border: 1px solid var(--border); }

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

.chat-input-area {
  padding: 16px 24px; border-top: 1px solid var(--border);
  display: flex; gap: 10px; align-items: center;
}
#chat-input {
  flex: 1; background: var(--input-bg); border: 1px solid var(--border);
  color: var(--fg); font-family: inherit; font-size: 13px;
  padding: 10px 14px; border-radius: 6px; outline: none;
  resize: none; min-height: 20px; max-height: 120px;
}
#chat-input:focus { border-color: var(--dim); }
#chat-input::placeholder { color: var(--dim2); }
#send-btn {
  background: var(--fg); color: var(--bg); border: none;
  font-family: inherit; font-size: 11px; letter-spacing: 0.08em;
  text-transform: uppercase; padding: 10px 16px; border-radius: 6px;
  cursor: pointer; font-weight: 500; white-space: nowrap;
}
#send-btn:hover { opacity: 0.85; }
#send-btn:disabled { opacity: 0.3; cursor: default; }

/* ---- Stats sidebar ---- */
.stats-panel { overflow-y: auto; padding: 20px 20px; }
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
.orch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 6px; }

/* ---- Flow view nodes ---- */
@keyframes flowIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes drawLine { to { stroke-dashoffset: 0; } }
.flow-node {
  border: 1px solid var(--border); border-radius: 5px;
  padding: 8px 12px; background: #060606; display: inline-block;
  font-size: 11px; position: relative; min-width: 100px; text-align: center;
  transition: border-color 0.3s;
}
.flow-node.goal { border-color: var(--orange); background: #120a00; min-width: 200px; font-size: 13px; font-weight: 500; }
.flow-node.search { border-color: #334; background: #05050a; }
.flow-node.candidate { border-color: var(--border); min-width: 120px; }
.flow-node.buy { border-color: var(--green); background: #040d04; }
.flow-node.skip { border-color: var(--red); background: #0d0404; opacity: 0.7; }
.flow-node.zeroclick { border-color: #1a3a1a; background: #050f05; }
.flow-node.apify { border-color: #1a1a3a; background: #05050f; }
.flow-reveal { opacity: 0; animation: flowIn 0.45s ease both; }
.flow-row { display: flex; gap: 12px; justify-content: center; margin-bottom: 32px; flex-wrap: wrap; }
.flow-label { font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--dim); margin-bottom: 3px; }
.flow-score { font-size: 16px; font-weight: 300; margin: 2px 0; }
.flow-connector { width: 1px; height: 24px; background: var(--border); margin: 0 auto -8px; }
.flow-line-row { display: flex; justify-content: center; margin-bottom: -8px; position: relative; }
.flow-tx-hash { font-size: 9px; color: var(--dim2); margin-top: 3px; }
/* Inline ZeroClick callouts */
.zc-inline { border-left: 2px solid #1a3a1a; padding: 5px 8px; margin: 5px 0; font-size: 10px; background: #050f05; border-radius: 0 3px 3px 0; }
.zc-inline-label { font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: #2a5a2a; margin-bottom: 2px; }
.agent-box {
  border: 1px solid var(--border); border-radius: 4px;
  padding: 8px 10px; font-size: 10px; position: relative;
  transition: border-color 0.3s;
}
.agent-box.running { border-color: var(--orange); }
.agent-box.done    { border-color: var(--green); }
.agent-box.failed  { border-color: var(--red); }
.agent-box.idle    { border-color: var(--border); }
.agent-box-name { font-weight: 500; color: var(--fg); margin-bottom: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.agent-box-status { color: var(--dim); font-size: 9px; letter-spacing: 0.06em; }
.agent-box-score { position: absolute; top: 7px; right: 8px; font-size: 11px; font-weight: 300; }
.agent-pulse { width: 5px; height: 5px; border-radius: 50%; display: inline-block; margin-right: 4px; vertical-align: middle; }
.agent-pulse.running { background: var(--orange); animation: pulse 1s infinite; }
.agent-pulse.done    { background: var(--green); }
.agent-pulse.failed  { background: var(--red); }
.agent-pulse.idle    { background: var(--dim2); }

.welcome { color: var(--dim); font-size: 12px; line-height: 1.8; padding: 40px 0; }
.welcome strong { color: var(--fg); font-weight: 500; }
</style>
</head>
<body>
<div class="shell">
  <header>
    <h1>AgentAudit</h1>
    <div class="header-right">
      <div class="svc-status" title="Seller endpoint status"><span class="dot" id="dot-seller"></span><span id="st-seller">seller</span></div>
      <div class="svc-status" title="Buyer agent status"><span class="dot" id="dot-buyer"></span><span id="st-buyer">buyer</span></div>
      <div style="width:1px;height:16px;background:var(--border);margin:0 4px"></div>
      <div class="svc-status" id="tool-openai-wrap" title="OpenAI GPT-4o-mini — quality scoring LLM"><span class="dot" id="dot-openai"></span><span style="font-size:10px">OpenAI</span><span id="tool-openai-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-exa-wrap" title="Exa — web crawl and ground-truth scoring"><span class="dot" id="dot-exa"></span><span style="font-size:10px">Exa</span><span id="tool-exa-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-nvm-wrap" title="Nevermined x402 — payment infrastructure"><span class="dot" id="dot-nvm"></span><span style="font-size:10px">Nevermined</span><span id="tool-nvm-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-zc-wrap" title="ZeroClick native ads — live"><span class="dot" id="dot-zc"></span><span style="font-size:10px">ZeroClick</span><span id="tool-zc-status" style="font-size:9px;color:var(--green);margin-left:3px">live</span></div>
      <div class="svc-status" id="tool-apify-wrap" title="Apify Store — web scrapers and AI actors marketplace"><span class="dot up" id="dot-apify"></span><span style="font-size:10px">Apify</span><span id="tool-apify-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div style="width:1px;height:16px;background:var(--border);margin:0 4px"></div>
      <div style="display:flex;gap:4px">
        <button id="btn-chat" onclick="showView('chat')" style="font-size:10px;font-family:inherit;background:var(--fg);border:1px solid var(--fg);color:var(--bg);padding:3px 10px;border-radius:3px;cursor:pointer;letter-spacing:0.05em">Chat</button>
        <button id="btn-flow" onclick="showView('flow')" style="font-size:10px;font-family:inherit;background:transparent;border:1px solid var(--dim2);color:var(--dim);padding:3px 10px;border-radius:3px;cursor:pointer;letter-spacing:0.05em">Flow</button>
      </div>
    </div>
  </header>

  <!-- Main content area — single grid cell shared by Chat and Flow views -->
  <div style="grid-column:1;grid-row:2;position:relative;overflow:hidden">

    <!-- Flow View (hidden by default) -->
    <div id="view-flow" style="display:none;position:absolute;inset:0;overflow-y:auto;padding:24px 32px;background:var(--bg)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
        <div style="font-size:10px;color:var(--dim);letter-spacing:0.1em;text-transform:uppercase">Workflow — last strategy run</div>
        <div id="flow-key-status" style="font-size:9px;color:var(--dim2);letter-spacing:0.05em"></div>
      </div>
      <div id="flow-canvas" style="position:relative;min-height:500px;font-size:11px">
        <div style="color:var(--dim2);padding:40px 0">Run a strategy in Chat to see the workflow here.</div>
      </div>
    </div>

    <!-- Chat View -->
    <div id="view-chat" class="chat-panel" style="position:absolute;inset:0">
    <div class="chat-messages" id="messages">
      <div class="welcome">
        <strong>AgentAudit</strong> — Autonomous Business Intelligence<br><br>
        Describe a business goal and I will search the marketplace, evaluate options, purchase the best services via Nevermined, and return a strategy.<br><br>
        Try asking:<br>
        &bull; I want to build a fintech AI assistant<br>
        &bull; Research the AI agent market for investment<br>
        &bull; Find the best social monitoring agent<br>
        &bull; audit https://some-endpoint.com<br>
        &bull; what services are available in the marketplace<br>
      </div>
    </div>
    <div class="chat-input-area">
      <input id="chat-input" placeholder="Ask AgentAudit..." autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    </div><!-- end view-chat -->
  </div><!-- end content-area wrapper -->

  <div class="stats-panel">

    <div class="section-label">Live Orchestration <span style="font-size:9px;color:var(--dim)">· agents running now</span></div>
    <div class="orch-grid" id="orch-grid">
        <div class="agent-box idle" id="orch-exa"       ><div class="agent-box-name">Exa Research</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-apify"      ><div class="agent-box-name">Apify Store</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-openai"     ><div class="agent-box-name">OpenAI Audit</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-nevermined" ><div class="agent-box-name">Nevermined</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-trinity"    ><div class="agent-box-name" style="color:var(--green)">▲ Trinity: Nexus</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-social"     ><div class="agent-box-name" style="color:var(--green)">▲ Trinity: Social</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
    </div>
    <div class="divider"></div>

    <div class="section-label">Purchases <span style="font-size:9px;color:var(--dim);letter-spacing:0">· Nevermined order_plan</span></div>
    <div class="stat-row"><span class="stat-key">total</span><span class="stat-val" id="ts">0</span></div>
    <div class="stat-row"><span class="stat-key">credits spent</span><span class="stat-val" id="ds">0</span></div>
    <div class="stat-row"><span class="stat-key">wallet</span><span class="stat-val" id="nvm-balance">&mdash;</span></div>
    <div id="txs-buyer" style="margin-top:6px"><div class="empty">no purchases yet</div></div>
    <div class="divider"></div>

    <div class="section-label">Seller <span style="font-size:9px;color:var(--dim);letter-spacing:0">· incoming</span></div>
    <div class="stat-row"><span class="stat-key">credits earned</span><span class="stat-val" id="rev">0</span></div>
    <div class="stat-row"><span class="stat-key">buyers</span><span class="stat-val" id="ub">0</span></div>
    <div style="font-size:10px;color:var(--dim2);margin-top:4px;padding-bottom:4px" id="seller-activity">no activity yet</div>
    <div class="divider"></div>

    <div class="section-label">ZeroClick <span style="font-size:9px;letter-spacing:0" id="tool-zc-status" style="color:var(--green)">live</span></div>
    <div id="zc-live-ad" style="display:none;border:1px solid #1a3a1a;border-radius:4px;padding:10px 12px;margin-bottom:8px;background:#050f05">
      <div style="font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:var(--green);margin-bottom:5px">◉ Sponsored — ZeroClick Native</div>
      <div id="zc-ad-title" style="font-size:12px;font-weight:bold;margin-bottom:4px;line-height:1.4"></div>
      <div id="zc-ad-msg" style="font-size:10px;color:var(--dim);line-height:1.5;margin-bottom:8px"></div>
      <a id="zc-ad-cta" href="#" target="_blank" rel="noopener" style="font-size:10px;color:var(--green);text-decoration:none;letter-spacing:0.05em;border:1px solid #1a3a1a;padding:3px 8px;border-radius:2px" onclick="trackZcClick(this)"></a>
    </div>
    <div class="stat-row"><span class="stat-key">impressions</span><span class="stat-val" id="zc-imp">0</span></div>
    <div class="stat-row"><span class="stat-key">conversions</span><span class="stat-val" id="zc-conv">0</span></div>
  </div>
</div>

<script>
const S='', B='';
const msgs = document.getElementById('messages');
const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
let sending = false;
let lastStrategyData = null; // store last strategy result for flow view

function showView(v) {
  const chat = document.getElementById('view-chat');
  const flow = document.getElementById('view-flow');
  const btnChat = document.getElementById('btn-chat');
  const btnFlow = document.getElementById('btn-flow');
  if (v === 'flow') {
    chat.style.display = 'none';
    flow.style.display = 'block';
    flow.style.zIndex = '1';
    btnFlow.style.background = 'var(--fg)';
    btnFlow.style.color = 'var(--bg)';
    btnFlow.style.borderColor = 'var(--fg)';
    btnChat.style.background = 'transparent';
    btnChat.style.color = 'var(--dim)';
    btnChat.style.borderColor = 'var(--dim2)';
    // Refresh key status then render
    _loadKeyStatus().then(() => {
      try { renderFlowView(lastStrategyData); }
      catch(err) {
        const cv = document.getElementById('flow-canvas');
        if (cv) cv.innerHTML = '<div style="color:var(--red);padding:20px">Flow render error: ' + err.message + '</div>';
      }
    });
  } else {
    flow.style.display = 'none';
    chat.style.display = 'flex';
    btnChat.style.background = 'var(--fg)';
    btnChat.style.color = 'var(--bg)';
    btnChat.style.borderColor = 'var(--fg)';
    btnFlow.style.background = 'transparent';
    btnFlow.style.color = 'var(--dim)';
    btnFlow.style.borderColor = 'var(--dim2)';
  }
}

// ─── Flow View — live animated node-link graph ──────────────────────────────
let _keyStatus = {};
async function _loadKeyStatus() {
  try {
    _keyStatus = await fetch(B+'/api/keys-status').then(r=>r.json());
    const el = document.getElementById('flow-key-status');
    if (el) {
      const parts = [
        'openai', 'exa', 'zeroclick', 'nvm', 'apify'
      ].map(k => {
        const ok = _keyStatus[k];
        return '<span style="color:' + (ok?'var(--green)':'var(--red)') + '">' + k + '</span>';
      });
      el.innerHTML = 'Keys: ' + parts.join(' · ');
    }
  } catch(e) {}
}
_loadKeyStatus();

// Shared HTML-escape used by flow view helpers
const e = s => { const d = document.createElement('div'); d.textContent = String(s||''); return d.innerHTML; };

function _fNode(id, type, content, extraStyle) {
  return '<div class="flow-node ' + type + '" id="fn-' + id + '" style="' + (extraStyle||'') + '">' + content + '</div>';
}

// Tiny ZeroClick inline callout reusing strategy ad data
function _zcInline(ad, context) {
  if (!ad) return '';
  return '<div class="zc-inline"><div class="zc-inline-label">◉ ZeroClick sponsored</div>' +
    '<span style="color:var(--dim)">' + e(ad.sponsor||'') + ' — </span>' +
    '<a href="' + e(ad.click_url||'#') + '" target="_blank" style="color:#3a7a3a;text-decoration:none">' + e((ad.title||'').substring(0,55)) + '</a>' +
    (context ? '<span style="color:var(--dim2);font-size:9px"> · '+e(context)+'</span>' : '') +
    '</div>';
}

function renderFlowView(data) {
  const canvas = document.getElementById('flow-canvas');
  if (!data) {
    canvas.innerHTML = '<div style="color:var(--dim2);padding:40px 0">Run a strategy in Chat to see the workflow here.</div>';
    return;
  }
  const scored = data.audit_scores || [];
  const apify = data.apify_actors || [];
  const exa = data.exa_research || {};
  const exaHighlights = exa.highlights || [];
  const exaSearch = exa.search_context || [];
  const allMkt = data.all_marketplace_results || data.candidates || [];
  const purchases = (data.purchases||[]).filter(p => p.purchased);
  const roi = data.roi_analysis || {};
  const caps = data.goal_capabilities || [];
  const trinityPlan = data.trinity_plan || [];
  const ad = data.zeroclick_ad || null;

  // Animation delay counter — each section appears progressively
  let _delay = 0;
  function nextDelay(step) { const d = _delay; _delay += step; return d; }

  let connections = []; // [{from, to, color, delay}]

  // Helper: wrap section in a .flow-reveal div with animation delay
  function reveal(html, delayMs) {
    return '<div class="flow-reveal" style="animation-delay:' + delayMs + 'ms">' + html + '</div>';
  }

  let sections = []; // [{html, delay}]
  function sec(html) { const d = _delay; sections.push({html, d}); }

  // ── Row 0: Goal ─────────────────────────────────────────────────────────────
  sec('<div style="display:flex;justify-content:center;margin-bottom:40px">' +
    _fNode('goal', 'goal',
      '<div class="flow-label">Business Goal</div><div>' + e(data.goal||'') + '</div>' +
      (caps.length ? '<div style="margin-top:5px;font-size:10px;color:var(--dim)">needs: ' + caps.map(e).join(' · ') + '</div>' : '') +
      '<div style="margin-top:6px;font-size:9px;color:#4a4a4a">↓ searching marketplace · Exa · Apify in parallel</div>'
    ) + '</div>');
  nextDelay(200);

  // ── Row 1: Three search branches (appear together, simulate parallel) ────────
  const exaOk = exaHighlights.length > 0 || exaSearch.length > 0;
  const exaStatus = exaOk ? (exaHighlights.length + exaSearch.length) + ' insights'
    : (_keyStatus.exa ? 'key active — run strategy' : 'no key — add EXA_API_KEY');

  let branchHtml = '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:8px">';

  // — Marketplace column —
  branchHtml += '<div>';
  branchHtml += _fNode('mkt', 'search',
    '<div class="flow-label" style="color:#5577ff">Marketplace Search</div>' +
    '<div class="flow-score">' + allMkt.length + '</div>' +
    '<div style="color:var(--dim);font-size:10px">agents discovered</div>');
  connections.push({from:'goal', to:'mkt', color:'#2244aa', delay: 300});
  allMkt.slice(0,4).forEach((m, i) => {
    const mid = 'mkt-'+i;
    const sc = scored.find(s => s.team === m.team);
    const scv = sc ? sc.overall_score : null;
    const col = scv === null ? 'var(--dim)' : (scv >= 0.6 ? 'var(--green)' : scv >= 0.4 ? 'var(--orange)' : 'var(--red)');
    branchHtml += '<div style="height:10px;width:1px;background:#223;margin:2px auto"></div>';
    branchHtml += _fNode(mid, scv !== null ? 'candidate' : '',
      '<div style="font-weight:500;font-size:11px">' + e(m.team) + '</div>' +
      (scv !== null
        ? '<div style="color:'+col+';font-size:10px">' + scv.toFixed(2) + ' · ' + (sc.roi_decision||'') + '</div>' +
          (sc.avg_latency_ms ? '<div style="font-size:9px;color:var(--dim2)">'+sc.avg_latency_ms.toFixed(0)+'ms latency</div>' : '')
        : '<div style="color:var(--dim2);font-size:9px">' + e(m.category||m.price||'') + '</div>'),
      scv !== null ? 'border-color:'+col : '');
    connections.push({from:'mkt', to:mid, color:'#223', delay: 350 + i*80});
  });
  // ZeroClick inline after marketplace — natural market suggestion
  if (ad) branchHtml += _zcInline(ad, 'market alternative');
  branchHtml += '</div>';

  // — Exa Research column —
  branchHtml += '<div>';
  branchHtml += _fNode('exa', 'search',
    '<div class="flow-label" style="color:#ff8833">Exa Web Research</div>' +
    '<div class="flow-score">' + (exaOk ? exaHighlights.length : '—') + '</div>' +
    '<div style="color:var(--dim);font-size:10px">' + exaStatus + '</div>');
  connections.push({from:'goal', to:'exa', color:'#5a3300', delay: 300});
  exaHighlights.slice(0,3).forEach((h, i) => {
    const hid = 'exa-h'+i;
    branchHtml += '<div style="height:10px;width:1px;background:#443300;margin:2px auto"></div>';
    branchHtml += _fNode(hid, 'search',
      '<div style="color:var(--dim);font-size:10px;line-height:1.4;text-align:left">' + e(String(h).substring(0,85)) + '</div>',
      'border-color:#443300;background:#080500;min-width:unset;text-align:left');
    connections.push({from:'exa', to:hid, color:'#443300', delay: 400 + i*80});
  });
  // Exa search context links
  exaSearch.slice(0,2).forEach((r, i) => {
    const sid = 'exa-s'+i;
    branchHtml += '<div style="height:10px;width:1px;background:#443300;margin:2px auto"></div>';
    branchHtml += _fNode(sid, 'search',
      '<div style="font-weight:500;font-size:10px;text-align:left">' + e((r.title||'').substring(0,45)) + '</div>' +
      '<div style="color:var(--dim2);font-size:9px;text-align:left">' + e((r.url||'').replace('https://','').substring(0,40)) + '</div>',
      'border-color:#332200;background:#060400;min-width:unset');
    connections.push({from:'exa', to:sid, color:'#332200', delay: 450 + i*80});
  });
  if (data.competitive_analysis) {
    branchHtml += '<div style="height:10px;width:1px;background:#443300;margin:2px auto"></div>';
    branchHtml += _fNode('exa-comp', 'search',
      '<div class="flow-label" style="color:#ff8833">Comparative Analysis</div>' +
      '<div style="color:var(--dim);font-size:10px;line-height:1.5;text-align:left">' + e(data.competitive_analysis.substring(0,160)) + '</div>',
      'border-color:#554400;background:#080500;text-align:left');
    connections.push({from:'exa', to:'exa-comp', color:'#554400', delay: 520});
    // ZeroClick inline after competitive analysis — "sponsored alternative"
    if (ad) branchHtml += _zcInline(ad, 'competitive alternative');
  }
  branchHtml += '</div>';

  // — Apify column —
  branchHtml += '<div>';
  branchHtml += _fNode('apify', 'apify',
    '<div class="flow-label" style="color:#6644ff">Apify Store</div>' +
    '<div class="flow-score">' + apify.length + '</div>' +
    '<div style="color:var(--dim);font-size:10px">' + (apify.length ? 'automation actors' : (_keyStatus.apify ? 'no results' : 'no key')) + '</div>');
  connections.push({from:'goal', to:'apify', color:'#331166', delay: 300});
  apify.slice(0,4).forEach((a, i) => {
    const aid = 'apify-'+i;
    const url = a.url || a.apify_url || '';
    branchHtml += '<div style="height:10px;width:1px;background:#221133;margin:2px auto"></div>';
    branchHtml += _fNode(aid, 'apify',
      '<div style="font-weight:500;font-size:10px;text-align:left">' + e(a.name||'Actor') + '</div>' +
      '<div style="color:var(--dim);font-size:9px;margin:2px 0;text-align:left">' + e((a.description||'').substring(0,50)) + '</div>' +
      (url ? '<a href="'+e(url)+'" target="_blank" style="font-size:9px;color:#6644ff;text-decoration:none">open in Apify →</a>' : ''),
      'border-color:#221133;background:#040309;min-width:unset');
    connections.push({from:'apify', to:aid, color:'#221133', delay: 360 + i*80});
  });
  branchHtml += '</div>';

  branchHtml += '</div>'; // end grid
  sec(branchHtml);
  nextDelay(150);

  // ── Row 2: Audit convergence ─────────────────────────────────────────────────
  if (scored.length > 0) {
    let auditHtml = '<div style="margin:16px 0 8px;text-align:center"><div style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:var(--dim);border-top:1px solid var(--border);padding-top:20px;display:inline-block;padding:20px 30px 0">Audit — real HTTP probes + OpenAI scoring</div></div>';
    auditHtml += '<div style="display:flex;gap:12px;justify-content:center;margin-bottom:12px;flex-wrap:wrap">';
    scored.forEach((s, i) => {
      const sc = s.overall_score || 0;
      const col = sc >= 0.6 ? 'var(--green)' : sc >= 0.4 ? 'var(--orange)' : 'var(--red)';
      const sid = 'aud-'+i;
      connections.push({from: 'mkt-'+Math.min(i, allMkt.length-1), to: sid, color: col==='var(--green)'?'#0a2a0a':'#2a1a00', delay: 600+i*80});
      auditHtml += _fNode(sid, 'candidate',
        '<div style="font-weight:500;font-size:11px">' + e(s.team||'') + '</div>' +
        '<div style="color:'+col+';font-size:18px;font-weight:300;margin:3px 0">' + sc.toFixed(2) + '</div>' +
        '<div style="color:'+col+';font-size:9px;letter-spacing:0.06em">' + (s.roi_decision||s.recommendation||'') + '</div>' +
        (s.avg_latency_ms ? '<div style="font-size:9px;color:var(--dim2);margin-top:2px">'+s.avg_latency_ms.toFixed(0)+'ms · quality '+(s.quality_score||0).toFixed(2)+(s.quality_score===0.5?' (est)':'')+' · price '+(s.price_score||0).toFixed(2)+'</div>' : ''),
        'border-color:'+col+';min-width:130px');
    });
    auditHtml += '</div>';
    sec(auditHtml);
    nextDelay(120);
  }

  // ── Row 3: Purchases ─────────────────────────────────────────────────────────
  if (purchases.length > 0) {
    let buyHtml = '<div style="margin:8px 0;text-align:center"><div style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:var(--green);display:inline-block;padding:0 20px">↓ Nevermined order_plan — blockchain transactions</div></div>';
    buyHtml += '<div style="display:flex;gap:12px;justify-content:center;margin-bottom:16px;flex-wrap:wrap">';
    purchases.forEach((p, i) => {
      const tx = (p.tx_hash||'').substring(0,14);
      const pid = 'buy-'+i;
      connections.push({from:'aud-'+Math.min(i, scored.length-1), to:pid, color:'#0a2a0a', delay:750+i*80});
      buyHtml += _fNode(pid, 'buy',
        '<div class="flow-label">' + e(p.team||'') +
          (p.repeat_purchase ? ' <span style="color:var(--orange)">REPEAT</span>' : ' <span style="color:var(--green)">NEW</span>') + '</div>' +
        '<div style="color:var(--green);font-weight:500;font-size:14px;margin:4px 0">order_plan ✓</div>' +
        '<div style="color:var(--dim);font-size:9px">roi: ' + e(p.roi_decision||'BUY') + '</div>' +
        (tx ? '<div class="flow-tx-hash">tx: ' + e(tx) + '…</div>' : ''));
    });
    buyHtml += '</div>';
    sec(buyHtml);
    nextDelay(120);
  }

  // ── ZeroClick main node (after purchases — "what to do next") ────────────────
  if (ad) {
    let zcHtml = '<div style="display:flex;justify-content:center;margin:12px 0 24px">';
    const adId = 'zc-main';
    if (purchases.length > 0) connections.push({from:'buy-0', to:adId, color:'#1a3a1a', delay:900});
    zcHtml += _fNode(adId, 'zeroclick',
      '<div class="flow-label" style="color:var(--green)">◉ ZeroClick — AI-native contextual recommendation</div>' +
      '<div style="display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;margin-top:6px">' +
        '<div>' +
          '<div style="font-weight:500;margin-bottom:3px;text-align:left">' + e(ad.title||ad.sponsor||'') + '</div>' +
          '<div style="color:var(--dim);font-size:10px;line-height:1.4;text-align:left">' + e((ad.message||'').substring(0,130)) + '</div>' +
        '</div>' +
        '<a href="' + e(ad.click_url||'#') + '" target="_blank" style="font-size:10px;color:var(--green);text-decoration:none;border:1px solid #1a3a1a;padding:5px 10px;border-radius:3px;white-space:nowrap">' + e(ad.cta||'Learn more') + ' →</a>' +
      '</div>',
      'min-width:440px;text-align:left');
    zcHtml += '</div>';
    sec(zcHtml);
    nextDelay(120);
  }

  // ── Trinity Business Plan ────────────────────────────────────────────────────
  if (trinityPlan.length > 0) {
    let tHtml = '<div style="border-top:1px solid #1a3a1a;padding-top:24px;margin-bottom:8px;text-align:center">';
    tHtml += '<div style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:var(--green);margin-bottom:12px">▲ AbilityAI Trinity — autonomous agent fleet generated for your goal</div>';
    tHtml += '<div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">';
    const tmplColors = {cornelius:'#334499', ruby:'#993344', outbound:'#449933', webmaster:'#996633'};
    trinityPlan.forEach((ag, i) => {
      const col = tmplColors[(ag.template||'').toLowerCase()] || '#444466';
      tHtml += '<div class="flow-reveal" style="animation-delay:' + (nextDelay(100)) + 'ms;border:1px solid '+col+';border-radius:5px;padding:10px 14px;background:#050508;min-width:135px;max-width:165px">';
      tHtml += '<div style="font-size:8px;letter-spacing:0.06em;text-transform:uppercase;color:'+col+';margin-bottom:4px">' + e(ag.template||'agent') + '</div>';
      tHtml += '<div style="font-weight:500;font-size:12px;margin-bottom:3px">' + e(ag.name||'') + '</div>';
      tHtml += '<div style="font-size:10px;color:var(--dim);margin-bottom:5px">' + e(ag.role||'') + '</div>';
      tHtml += '<div style="font-size:10px;color:var(--dim2);line-height:1.4">' + e((ag.task||'').substring(0,65)) + '</div>';
      tHtml += '<div style="margin-top:6px"><span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--green);vertical-align:middle"></span><span style="font-size:9px;color:var(--green);margin-left:4px">ready to deploy</span></div>';
      tHtml += '</div>';
    });
    tHtml += '</div></div>';
    sec(tHtml);
  }

  // ROI summary
  if (roi.roi_rationale) {
    let rHtml = '<div style="border:1px solid var(--border);border-radius:5px;padding:10px 14px;font-size:11px;margin:12px 0">';
    rHtml += '<div style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;color:var(--dim);margin-bottom:4px">ROI Summary</div>';
    rHtml += '<div style="color:var(--dim)">' + e(roi.roi_rationale) + '</div>';
    if (roi.teams_purchased_from && roi.teams_purchased_from.length) {
      rHtml += '<div style="margin-top:4px;color:var(--green);font-size:10px">Purchased from: ' + roi.teams_purchased_from.map(e).join(', ') + '</div>';
    }
    rHtml += '</div>';
    sec(rHtml);
  }

  // ── Render with staggered animation ─────────────────────────────────────────
  let fullHtml = '<svg id="flow-svg" style="position:absolute;top:0;left:0;pointer-events:none;overflow:visible"></svg>';
  sections.forEach(({html, d}) => {
    fullHtml += '<div class="flow-reveal" style="animation-delay:' + d + 'ms">' + html + '</div>';
  });
  canvas.innerHTML = fullHtml;

  // ── Draw animated SVG connection lines after DOM settles ─────────────────────
  requestAnimationFrame(() => setTimeout(() => {
    const svg = document.getElementById('flow-svg');
    if (!svg) return;
    svg.setAttribute('width', canvas.scrollWidth);
    svg.setAttribute('height', canvas.scrollHeight);
    svg.style.width = canvas.scrollWidth + 'px';
    svg.style.height = canvas.scrollHeight + 'px';
    const cR = canvas.getBoundingClientRect();

    connections.forEach(({from, to, color, delay: lineDelay}) => {
      const fEl = document.getElementById('fn-'+from);
      const tEl = document.getElementById('fn-'+to);
      if (!fEl || !tEl) return;
      const fR = fEl.getBoundingClientRect();
      const tR = tEl.getBoundingClientRect();
      const x1 = fR.left + fR.width/2 - cR.left;
      const y1 = fR.bottom - cR.top;
      const x2 = tR.left + tR.width/2 - cR.left;
      const y2 = tR.top - cR.top;
      const dy = Math.abs(y2 - y1);
      const d = `M${x1},${y1} C${x1},${y1+dy*0.45} ${x2},${y2-dy*0.45} ${x2},${y2}`;
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', d);
      p.setAttribute('fill', 'none');
      p.setAttribute('stroke', color || 'var(--border)');
      p.setAttribute('stroke-width', '1');
      p.setAttribute('opacity', '0.6');
      svg.appendChild(p);
      // Animate the line drawing
      const len = p.getTotalLength();
      p.style.strokeDasharray = len;
      p.style.strokeDashoffset = len;
      p.style.transition = `stroke-dashoffset 0.5s ease ${(lineDelay||300)}ms`;
      requestAnimationFrame(() => requestAnimationFrame(() => { p.style.strokeDashoffset = '0'; }));
    });
  }, 100));
}

async function get(u) {
  try { const r = await fetch(u); return r.ok ? r.json() : null; }
  catch { return null; }
}

function setDot(id, up) {
  const el = document.getElementById(id);
  el.classList.remove('up','down');
  el.classList.add(up ? 'up' : 'down');
}

function scrollDown() { msgs.scrollTop = msgs.scrollHeight; }

function addMsg(role, html) {
  const w = msgs.querySelector('.welcome');
  if (w) w.remove();
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.innerHTML = '<div class="msg-bubble">' + html + '</div>';
  msgs.appendChild(d);
  scrollDown();
  return d;
}

function toolLabel(name, args) {
  switch(name) {
    case 'execute_business_strategy':
      return {
        icon: '[strategy]',
        label: 'Autonomous business strategy',
        detail: args.goal ? 'goal: ' + args.goal.substring(0, 60) : '',
        sub: 'Exa research -> marketplace search -> audit top picks -> Nevermined purchase -> synthesize'
      };
    case 'search_marketplace':
      return {
        icon: '[search]',
        label: 'Nevermined Discovery API',
        detail: args.query ? 'query: "' + args.query + '"' : 'fetching all sellers',
        sub: 'GET nevermined.ai/hackathon/register/api/discover'
      };
    case 'analyze_url':
      return {
        icon: '[crawl]',
        label: 'Exa web crawl',
        detail: args.url ? args.url.substring(0, 60) : '',
        sub: 'POST api.exa.ai/contents + /search'
      };
    case 'audit_service':
      return {
        icon: '[audit]',
        label: 'Quality audit — OpenAI + Exa',
        detail: args.endpoint_url ? args.endpoint_url.substring(0, 55) : '',
        sub: 'latency probe · GPT-4o-mini quality score · Exa ground truth'
      };
    case 'compare_services':
      return {
        icon: '[compare]',
        label: 'Side-by-side comparison',
        detail: '',
        sub: (args.endpoint_url_1||'').substring(0,30) + ' vs ' + (args.endpoint_url_2||'').substring(0,30)
      };
    case 'buy_service':
      return {
        icon: '[buy]',
        label: 'Nevermined x402 purchase',
        detail: args.endpoint_url ? args.endpoint_url.replace(/https?:[/][/]/,'').substring(0, 50) : '',
        sub: 'Step 1: probe → 402 + plan_id  ·  Step 2: subscribe  ·  Step 3: token  ·  Step 4: pay'
      };
    case 'search_apify':
      return {
        icon: '[apify]',
        label: 'Apify Store marketplace search',
        detail: args.query ? 'query: "' + args.query + '"' : '',
        sub: 'apify.com/store — AI actors, scrapers, web agents'
      };
    case 'query_onchain':
      return {
        icon: '[chain]',
        label: 'On-chain subgraph — Base Sepolia',
        detail: args.data_type || '',
        sub: 'Nevermined ERC-1155 credit contract'
      };
    default:
      return { icon: '[tool]', label: name, detail: '', sub: '' };
  }
}

function addToolUse(name, args) {
  const t = toolLabel(name, args);
  const d = document.createElement('div');
  d.className = 'msg-tool';
  d.id = 'tool-' + Date.now();
  d.innerHTML =
    '<div style="display:flex;align-items:flex-start;gap:6px">' +
      '<span class="tool-dot"></span>' +
      '<div style="flex:1">' +
        '<div><span style="color:var(--fg);font-weight:500">' + t.icon + ' ' + t.label + '</span>' +
          (t.detail ? '<span style="color:var(--dim);margin-left:6px">' + escHtml(t.detail) + '</span>' : '') +
        '</div>' +
        (t.sub ? '<div class="tool-sub" style="color:var(--dim2);font-size:10px;margin-top:1px">' + escHtml(t.sub) + '</div>' : '<div class="tool-sub" style="display:none"></div>') +
      '</div>' +
    '</div>';
  msgs.appendChild(d);
  scrollDown();
  return d.id;
}

function markToolDone(toolElId, result) {
  const el = document.getElementById(toolElId);
  if (!el) return;
  const dot = el.querySelector('.tool-dot');
  if (dot) dot.classList.add('done');
  // If it's a buy_service result, update sub text with outcome
  if (result && typeof result === 'object' && 'purchased' in result) {
    const subEl = el.querySelector('.tool-sub');
    if (subEl) {
      if (result.purchased) {
        subEl.innerHTML = '<span style="color:var(--green)">✓ purchased — 1 credit deducted via Nevermined x402</span>';
      } else if (result.status === 402) {
        subEl.innerHTML = '<span style="color:var(--orange)">needs plan purchase — <a href="' + (result.purchase_url||'https://nevermined.app') + '" target="_blank" style="color:var(--orange)">buy plan →</a></span>';
      } else if (result.status >= 500) {
        subEl.innerHTML = '<span style="color:var(--red)">vendor offline (' + result.status + ') — tried with retry</span>';
      } else if (result.called) {
        subEl.innerHTML = '<span style="color:var(--dim)">responded (no payment required)</span>';
      } else {
        subEl.innerHTML = '<span style="color:var(--red)">failed: ' + escHtml((result.error||'unknown').substring(0,60)) + '</span>';
      }
    }
  }
}

function scoreBarCls(v) { return v >= 0.7 ? 'high' : v >= 0.45 ? 'mid' : 'low'; }

function renderAuditCard(data) {
  if (!data || typeof data !== 'object') return '';
  const score = data.overall_score;
  if (score === undefined) return '';
  const rec = data.recommendation || '';
  const scores = data.scores || {};
  const details = data.details || {};
  let html = '<div class="audit-card">';
  html += '<div class="audit-card-header"><span class="audit-card-title">' + escHtml(data.endpoint_url || '') + '</span><span class="audit-card-score">' + score.toFixed(2) + '</span></div>';
  html += '<div class="audit-card-rec"><span class="rec-dot ' + rec + '"></span>' + rec + '</div>';
  for (const [k, v] of Object.entries(scores)) {
    const pct = (v * 100).toFixed(0);
    html += '<div class="score-row"><span>' + k + '</span><div class="score-bar-track"><div class="score-bar-fill ' + scoreBarCls(v) + '" style="width:' + pct + '%"></div></div><span>' + v.toFixed(2) + '</span></div>';
  }
  if (data.reasoning) html += '<div style="margin-top:8px;color:var(--dim);font-size:11px;line-height:1.5">' + escHtml(data.reasoning) + '</div>';
  html += '</div>';
  // Append ZeroClick ad if the audit result includes one
  if (data.ad) html += renderAdCard(data.ad, score);
  return html;
}

function renderAdCard(ad, score) {
  if (!ad) return '';
  const sponsor = ad.sponsor || 'ZeroClick.ai';
  const title = ad.title || sponsor;
  const msg = (ad.message || '').substring(0, 180);
  const cta = ad.cta || 'Learn more';
  const url = ad.click_url || 'https://zeroclick.ai';
  const scoreStr = score && score > 0 ? ' · ' + (score * 100).toFixed(0) + '% audit score' : '';
  let html = '<div class="zc-ad-card">';
  html += '<div class="zc-ad-header">';
  html += '<span class="zc-ad-label">◉ ZeroClick Sponsored</span>';
  html += '<span class="zc-ad-score-badge">' + escHtml(sponsor) + scoreStr + '</span>';
  html += '</div>';
  html += '<div class="zc-ad-title">' + escHtml(title) + '</div>';
  if (msg) html += '<div class="zc-ad-msg">' + escHtml(msg) + '</div>';
  html += '<a class="zc-ad-cta" href="' + escHtml(url) + '" target="_blank" rel="noopener">' + escHtml(cta) + ' →</a>';
  html += '</div>';
  return html;
}

// ── Live Orchestration Panel (TrinityOS-style) ──────────────────────────────
// renderOrchestration: update the 4 permanent tool boxes with final results
function renderOrchestration(data) {
  if (!data) return;

  // Exa: only mark done if there are actual exa highlights
  const exaData = data.exa_research || {};
  const hasExa = exaData.highlights && exaData.highlights.length > 0;
  orchSetAgent('exa', hasExa ? 'done' : 'idle', hasExa ? 'highlights found' : 'no key — skipped');

  // Apify
  const nApify = (data.apify_actors || []).length;
  orchSetAgent('apify', nApify > 0 ? 'done' : 'idle', nApify > 0 ? nApify + ' actors' : 'no results');

  // OpenAI audit
  const nAudited = (data.audit_scores || []).filter(s => !s.error).length;
  orchSetAgent('openai', nAudited > 0 ? 'done' : 'idle', nAudited + ' audited');

  // Nevermined
  const purchases = data.purchases || data.agents || [];
  const nBought = purchases.filter(p => p.purchased).length;
  const nFailed = purchases.filter(p => !p.purchased && p.error);
  const nvmStatus = nBought > 0 ? 'done' : (nFailed.length > 0 ? 'failed' : 'idle');
  const nvmMsg = nBought > 0 ? nBought + ' purchased' : (nFailed.length > 0 ? nFailed.length + ' failed' : 'no purchases');
  orchSetAgent('nevermined', nvmStatus, nvmMsg);

  // Trinity: Nexus = Full Stack Agents, Social = TrinityAgents
  const nexusPurchase = purchases.find(p => (p.team||'').toLowerCase().includes('full stack') || (p.team||'').toLowerCase().includes('nexus'));
  const socialPurchase = purchases.find(p => (p.team||'').toLowerCase().includes('trinity') || (p.team||'').toLowerCase().includes('social'));
  if (nexusPurchase) {
    orchSetAgent('trinity', nexusPurchase.purchased ? 'done' : 'failed', nexusPurchase.purchased ? 'purchased ✓' : 'failed');
  } else { orchSetAgent('trinity', 'idle', 'standby'); }
  if (socialPurchase) {
    orchSetAgent('social', socialPurchase.purchased ? 'done' : 'failed', socialPurchase.purchased ? 'purchased ✓' : 'failed');
  } else { orchSetAgent('social', 'idle', 'standby'); }

  // Update buyer transactions sidebar
  const txBuyer = document.getElementById('txs-buyer');
  if (txBuyer && purchases.length > 0) {
    const boughtTxs = purchases.filter(p => p.purchased);
    if (boughtTxs.length > 0) {
      const items = boughtTxs.map(p => {
        const label = (p.team || p.vendor || '').substring(0, 22);
        const isRepeat = p.repeat_purchase;
        const tx = (p.tx_hash || '').substring(0, 10);
        const badge = isRepeat ? '<span style="font-size:9px;color:var(--orange);margin-left:3px">REPEAT</span>' : '<span style="font-size:9px;color:var(--green);margin-left:3px">NEW</span>';
        return '<div class="tx-item"><div class="tx-top"><span class="tx-endpoint">' + escHtml(label) + badge + '</span>' +
          '<span class="tx-credits" style="color:var(--green)">order_plan ✓</span></div>' +
          '<div class="tx-meta">nvm blockchain' + (tx ? ' · tx:' + escHtml(tx) + '…' : '') + ' · ' + new Date().toLocaleTimeString() + '</div></div>';
      });
      txBuyer.innerHTML = items.join('');
    }
  }
}

const ORCH_IDS = {exa:'orch-exa', apify:'orch-apify', openai:'orch-openai', nevermined:'orch-nevermined', trinity:'orch-trinity', social:'orch-social'};

function orchSetAgent(id, status, msg) {
  const boxId = ORCH_IDS[id] || ('orch-agent-' + id);
  let box = document.getElementById(boxId);
  if (!box) return;
  box.className = 'agent-box ' + status;
  const nameEl = box.querySelector('.agent-box-name');
  const stEl   = box.querySelector('.agent-box-status');
  if (stEl) stEl.innerHTML = '<span class="agent-pulse ' + status + '"></span>' + escHtml((msg||'').substring(0,22));
  // score styling on done
  const scoreEl = box.querySelector('.agent-box-score');
  if (scoreEl && status === 'done') scoreEl.style.color = 'var(--green)';
  if (scoreEl && status === 'failed') scoreEl.style.color = 'var(--red)';
}

function orchSetRunning() {
  ['exa','apify','openai','nevermined','trinity','social'].forEach(id => {
    orchSetAgent(id, 'running', 'queued');
  });
}

// Map endpoint URLs to orchestration box IDs for live updates
function orchIdFromEndpoint(ep) {
  if (!ep) return null;
  if (ep.includes('abilityai')) return 'trinity';
  if (ep.includes('exa') || ep.includes('ai.exa')) return 'exa';
  return 'nevermined';
}

function renderStrategyCard(data) {
  if (!data || !data.goal) return '';
  let html = '<div class="audit-card" style="margin-top:10px">';
  html += '<div class="audit-card-header"><span class="audit-card-title">Strategy: ' + escHtml(data.goal) + '</span>';
  html += '<span style="font-size:10px;color:var(--dim)">' + (data.credits_spent||0) + ' cr spent</span></div>';

  // Steps pipeline
  const stepLabels = {exa_research:'Exa research',marketplace_search:'Marketplace search',audit_candidates:'Candidate audit',purchase_services:'Nevermined purchase'};
  const steps = data.steps || [];
  if (steps.length) {
    html += '<div style="display:flex;gap:4px;margin:8px 0;flex-wrap:wrap">';
    steps.forEach((s,i) => {
      html += '<span style="font-size:9px;background:var(--border);padding:2px 6px;border-radius:2px;color:var(--dim)">' + (stepLabels[s]||s) + (i<steps.length-1?' →':'') + '</span>';
    });
    html += '</div>';
  }

  // Exa research highlights
  const exa = data.exa_research || {};
  if (exa.highlights && exa.highlights.length) {
    html += '<div style="margin:6px 0;font-size:10px;color:var(--dim)"><span style="color:var(--fg)">Exa research:</span><br>';
    exa.highlights.slice(0,2).forEach(h => {
      html += '· ' + escHtml((h||'').substring(0,120)) + '<br>';
    });
    html += '</div>';
  }

  // Audit scores — with explanation of what each sub-score means
  const scores = data.audit_scores || [];
  if (scores.length) {
    html += '<div style="margin:6px 0;font-size:11px">';
    html += '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">';
    html += '<span style="color:var(--fg)">Audit scores</span>';
    html += '<span style="font-size:9px;color:var(--dim2)" title="quality=OpenAI content assessment (0.5 default if 402-gated), latency=real HTTP probe, price=plan cost vs market rate, consistency=response variance">quality · latency · price — real measurements</span>';
    html += '</div>';
    scores.forEach(s => {
      const sc = s.overall_score || 0;
      const cls = sc >= 0.7 ? 'var(--green)' : sc >= 0.45 ? 'var(--orange)' : 'var(--red)';
      const rel = s.error ? '— error' : sc.toFixed(2) + ' · ' + (s.recommendation||'');
      const q = s.quality_score; const l = s.latency_score; const p = s.price_score; const c = s.consistency_score;
      const latMs = s.avg_latency_ms ? s.avg_latency_ms.toFixed(0)+'ms' : null;
      html += '<div style="margin-top:6px;border-left:2px solid '+cls+';padding-left:8px">';
      html += '<div style="display:flex;justify-content:space-between"><span style="color:var(--dim)">' + escHtml(s.team||s.endpoint||'') + '</span><span style="color:'+cls+'">' + rel + '</span></div>';
      if (q !== undefined || l !== undefined) {
        html += '<div style="font-size:9px;color:var(--dim2);margin-top:2px">';
        if (q !== undefined) html += 'quality ' + q.toFixed(2) + (q === 0.5 ? ' (estimated — endpoint is paid)' : '') + '  ';
        if (l !== undefined) html += 'latency ' + l.toFixed(2) + (latMs ? ' ('+latMs+')' : '') + '  ';
        if (p !== undefined) html += 'price ' + p.toFixed(2) + '  ';
        if (c !== undefined) html += 'consistency ' + c.toFixed(2);
        html += '</div>';
      }
      html += '</div>';
    });
    html += '</div>';
  }

  // Purchases — order_plan() blockchain transactions
  const purchases = data.purchases || [];
  const bought = purchases.filter(p => p.purchased);
  const failed = purchases.filter(p => !p.purchased && !p.skipped && p.error);
  const skipped = purchases.filter(p => p.skipped);

  if (bought.length) {
    html += '<div style="margin:6px 0;font-size:11px;border:1px solid var(--green);border-radius:4px;padding:8px 10px">';
    html += '<div style="color:var(--green);font-size:10px;letter-spacing:0.06em;margin-bottom:6px">NVM TRANSACTIONS — ' + bought.length + ' plan(s) purchased</div>';
    bought.forEach(p => {
      const isRepeat = p.repeat_purchase;
      const badge = isRepeat ? '<span style="font-size:9px;color:var(--orange);margin-left:5px">REPEAT</span>' : '<span style="font-size:9px;color:var(--green);margin-left:5px">NEW</span>';
      const tx = (p.tx_hash||'').substring(0,16);
      html += '<div style="margin-top:4px;display:flex;justify-content:space-between;align-items:center">';
      html += '<span>' + escHtml(p.team||p.vendor||'') + badge + '</span>';
      html += '<span style="color:var(--green);font-size:10px">order_plan ✓</span>';
      html += '</div>';
      if (tx) html += '<div style="font-size:9px;color:var(--dim2);margin-top:1px;padding-left:8px">txHash: ' + escHtml(tx) + '… · score: ' + (p.audit_score||0).toFixed(2) + ' · roi: ' + escHtml(p.roi_decision||'BUY') + '</div>';
    });
    html += '</div>';
  }

  if (failed.length) {
    html += '<div style="margin:6px 0;font-size:10px">';
    html += '<span style="color:var(--orange)">Failed (' + failed.length + '):</span><br>';
    failed.forEach(p => {
      html += '<div style="color:var(--dim);margin-top:2px">· ' + escHtml(p.team||'') + ' — <span style="color:var(--red)">' + escHtml((p.error||'').substring(0,80)) + '</span></div>';
    });
    html += '</div>';
  }

  if (skipped.length) {
    html += '<div style="margin:4px 0;font-size:10px;color:var(--dim2)">Skipped (low ROI score): ' + skipped.map(p => escHtml(p.team||'')).join(', ') + '</div>';
  }

  // ROI summary
  const roi = data.roi_analysis || {};
  if (roi.decision || roi.roi_rationale) {
    const cls = (roi.decision||'').includes('BUY') ? 'var(--green)' : 'var(--orange)';
    html += '<div style="margin-top:8px;font-size:11px;border-top:1px solid var(--border);padding-top:6px">';
    if (roi.decision) html += 'ROI decision: <span style="color:'+cls+'">' + escHtml(roi.decision) + '</span>';
    if (roi.teams_purchased_from && roi.teams_purchased_from.length) {
      html += '<div style="margin-top:3px;font-size:10px;color:var(--dim)">Teams: ' + roi.teams_purchased_from.map(t => escHtml(t)).join(', ') + '</div>';
    }
    if (roi.roi_rationale) {
      html += '<div style="margin-top:3px;font-size:10px;color:var(--dim2)">' + escHtml(roi.roi_rationale.substring(0,200)) + '</div>';
    }
    html += '</div>';
  }

  html += '</div>';
  return html;
}

function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function formatMarkdown(text) {
  let h = escHtml(text);
  h = h.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
  h = h.replace(/`([^`]+)`/g, '<code style="background:#111;padding:1px 4px;border-radius:3px">$1</code>');
  return h;
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || sending) return;
  sending = true;
  btn.disabled = true;
  input.value = '';

  addMsg('user', escHtml(text));

  let assistantEl = null;
  let assistantText = '';
  let lastToolId = null;
  let lastStepEl = null;
  let auditCards = '';

  try {
    const resp = await fetch(B + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    });

    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += dec.decode(value, { stream: true });

      const lines = buffer.split('\\n');
      buffer = lines.pop();

      let eventType = '';
      let eventData = '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          eventData = line.slice(6);
          try {
            const d = JSON.parse(eventData);

            if (eventType === 'tool_use') {
              if (lastToolId) markToolDone(lastToolId);
              lastToolId = addToolUse(d.tool, d.args || {});
              lastStepEl = null;
              // Orchestration grid updates
              if (d.tool === 'execute_business_strategy' || d.tool === 'parallel_agents') {
                orchSetRunning();
              } else if (d.tool === 'buy_service') {
                // Highlight the relevant orch box when a direct purchase fires
                const orchId = orchIdFromEndpoint((d.args||{}).endpoint_url || '');
                if (orchId) orchSetAgent(orchId, 'running', 'purchasing…');
                orchSetAgent('nevermined', 'running', 'x402 flow…');
              } else if (d.tool === 'search_marketplace') {
                orchSetAgent('exa', 'running', 'searching…');
              }
            }
            else if (eventType === 'tool_step') {
              if (d.agent_init) {
                d.agent_init.forEach(a => orchSetAgent(a.id, 'idle', 'queued'));
              } else if (d.agent) {
                orchSetAgent(d.agent, d.status || 'running', d.msg || d.status);
              } else if (d.message) {
                const el = lastToolId ? document.getElementById(lastToolId) : null;
                if (el) {
                  if (!el.stepList) {
                    const sl = document.createElement('div');
                    sl.style.cssText = 'margin-top:4px;padding-left:16px;font-size:10px;color:var(--dim2);line-height:1.6';
                    el.appendChild(sl);
                    el.stepList = sl;
                  }
                  el.stepList.innerHTML += '<div>- ' + escHtml(d.message) + '</div>';
                }
              }
              scrollDown();
            }
            else if (eventType === 'zeroclick_ad') {
              // Only update sidebar — ad card in chat is rendered once via tool_result
              const ad = d.ad;
              if (ad) {
                document.getElementById('zc-live-ad').style.display = 'block';
                document.getElementById('zc-ad-title').textContent = ad.title || ad.sponsor || 'ZeroClick';
                document.getElementById('zc-ad-msg').textContent = (ad.message || '').substring(0, 120);
                const cta = document.getElementById('zc-ad-cta');
                cta.textContent = (ad.cta || 'Learn more') + ' →';
                cta.href = ad.click_url || 'https://zeroclick.ai';
                cta.dataset.offerId = ad.id || '';
              }
              refreshStats();
            }
            else if (eventType === 'tool_result') {
              const r = d.result;
              // Pass result to markToolDone so buy cards show outcome
              if (lastToolId) markToolDone(lastToolId, r && typeof r === 'object' ? r : null);
              // For individual buy_service: update orch boxes + txs list
              if (d.tool === 'buy_service' && r && typeof r === 'object') {
                const orchId = orchIdFromEndpoint(r.endpoint || r.target || '');
                if (orchId) orchSetAgent(orchId, r.purchased ? 'done' : 'failed', r.purchased ? 'purchased ✓' : (r.status||'fail'));
                orchSetAgent('nevermined', r.purchased ? 'done' : (r.status === 402 ? 'idle' : 'failed'), r.purchased ? (r.purchased > 0 ? '1 bought' : 'open') : (r.status||'fail'));
                // Update transactions sidebar
                if (r.purchased || r.called) {
                  const txBuyer = document.getElementById('txs-buyer');
                  if (txBuyer) {
                    const prev = txBuyer.querySelector('.empty');
                    if (prev) prev.remove();
                    const item = document.createElement('div');
                    item.className = 'tx-item';
                    const ep = r.endpoint || r.target || '';
                    const label = ep.replace(/https?:[/][/]/,'').substring(0, 30);
                    const col = r.purchased ? 'var(--green)' : 'var(--orange)';
                    const badge = r.purchased ? '-1 cr' : 'open';
                    item.innerHTML = '<div class="tx-top"><span class="tx-endpoint">' + escHtml(label) + '</span><span class="tx-credits" style="color:'+col+'">' + badge + '</span></div>' +
                      '<div class="tx-meta">' + (r.payment_method||'attempted') + ' · ' + new Date().toLocaleTimeString() + '</div>';
                    txBuyer.insertBefore(item, txBuyer.firstChild);
                  }
                }
              }
              // Also search_marketplace: update exa orch box
              if (d.tool === 'search_marketplace') {
                const n = Array.isArray(r) ? r.length : (r && r.results ? r.results.length : 0);
                orchSetAgent('exa', 'done', (n||'?') + ' sellers found');
              }
              lastToolId = null;
              if (r && typeof r === 'object' && r.overall_score !== undefined) {
                auditCards += renderAuditCard(r);
              }
              if (r && typeof r === 'object' && r.endpoint_1) {
                auditCards += renderAuditCard(r.endpoint_1);
                auditCards += renderAuditCard(r.endpoint_2);
                if (r.recommendation) {
                  auditCards += '<div style="margin-top:8px;font-size:12px;color:var(--dim)">' + escHtml(r.recommendation) + '</div>';
                }
              }
              // Business strategy result card + live orchestration update
              if (r && typeof r === 'object' && r.goal && r.steps) {
                lastStrategyData = r; // save for flow view
                auditCards += renderStrategyCard(r);
                renderOrchestration(r);
                // ZeroClick ad — render once in chat, update sidebar
                if (r.zeroclick_ad) {
                  const ad = r.zeroclick_ad;
                  auditCards += renderAdCard(ad, r.roi_analysis && r.roi_analysis.top_score || 0);
                  document.getElementById('zc-live-ad').style.display = 'block';
                  document.getElementById('zc-ad-title').textContent = ad.title || ad.sponsor || 'ZeroClick';
                  document.getElementById('zc-ad-msg').textContent = (ad.message || '').substring(0, 120);
                  const cta = document.getElementById('zc-ad-cta');
                  cta.textContent = (ad.cta || 'Learn more') + ' →';
                  cta.href = ad.click_url || 'https://zeroclick.ai';
                  cta.dataset.offerId = ad.id || '';
                }
              }
              // Parallel agents result
              if (r && typeof r === 'object' && r.orchestration === 'parallel') {
                renderOrchestration(r);
                if (r.synthesis) {
                  auditCards += '<div style="border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-top:8px;font-size:12px"><div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:var(--dim);margin-bottom:8px">Synthesis — ' + (r.agents || []).length + ' agents</div>' + escHtml(r.synthesis) + '</div>';
                }
              }
            }
            else if (eventType === 'token') {
              assistantText += d.text || '';
            }
            else if (eventType === 'done') {
              // done
            }
          } catch(e) {}
          eventType = '';
          eventData = '';
        }
      }
    }
  } catch(e) {
    assistantText = 'Connection error — is the buyer running on port 8000?';
  }

  if (lastToolId) markToolDone(lastToolId);

  if (assistantText || auditCards) {
    const el = addMsg('assistant', formatMarkdown(assistantText) + auditCards);
  }

  sending = false;
  btn.disabled = false;
  input.focus();
  refreshStats();
}

input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
btn.addEventListener('click', sendMessage);

function trackZcClick(el) {
  const offerId = el.dataset.offerId;
  if (offerId) fetch(S + '/zeroclick/click?offer_id=' + encodeURIComponent(offerId), {method:'POST'}).catch(()=>{});
}

async function refreshStats() {
  const [stats, b, credits] = await Promise.all([get(S+'/stats'), get(B+'/api/status'), get(S+'/credits')]);
  const s = stats ? stats.seller : null;
  const by = stats ? stats.buyer : null;

  // NVM credit balance
  if (credits && credits.plans) {
    const planKeys = Object.keys(credits.plans);
    if (planKeys.length > 0) {
      const first = credits.plans[planKeys[0]];
      const bal = first.balance != null ? first.balance : '?';
      const sub = first.is_subscriber ? '✓' : '✗';
      document.getElementById('nvm-balance').textContent = bal + ' cr ' + sub;
    }
  }

  setDot('dot-seller', !!s);
  document.getElementById('st-seller').textContent = s ? 'seller' : 'seller offline';
  setDot('dot-buyer', !!b);
  document.getElementById('st-buyer').textContent = b ? 'buyer' : 'buyer offline';

  // Sponsor tool indicators
  const tools = stats ? (stats.tools || {}) : {};
  const toolDotMap = {openai:'dot-openai', exa:'dot-exa', nevermined:'dot-nvm', zeroclick:'dot-zc', apify:'dot-apify'};
  const toolCountMap = {openai:'tool-openai-count', exa:'tool-exa-count', nevermined:'tool-nvm-count', apify:'tool-apify-count'};
  Object.entries(toolDotMap).forEach(([t, dotId]) => {
    const info = tools[t] || {};
    const st = info.status || 'unknown';
    const dot = document.getElementById(dotId);
    if (dot) {
      dot.className = 'dot';
      if (st === 'active' || st === 'ok') dot.classList.add('up');
      else if (st === 'error') dot.classList.add('down');
      // pending/unknown stays grey
    }
    const countId = toolCountMap[t];
    if (countId) {
      const countEl = document.getElementById(countId);
      if (countEl) {
        if (info.calls > 0) {
          countEl.textContent = info.calls + 'x';
          countEl.style.display = '';
        } else {
          countEl.style.display = 'none';
        }
      }
    }
  });
  // ZeroClick: show live/pending status text
  const zcInfo = tools['zeroclick'] || {};
  const zcStatusEl = document.getElementById('tool-zc-status');
  if (zcStatusEl) {
    if (zcInfo.status === 'active' || zcInfo.status === 'ok') {
      zcStatusEl.textContent = zcInfo.calls > 0 ? zcInfo.calls + 'x' : 'live';
      zcStatusEl.style.color = 'var(--green)';
    } else {
      zcStatusEl.textContent = 'pending approval';
      zcStatusEl.style.color = 'var(--orange)';
    }
  }

  // ZeroClick — data lives in /stats (seller analytics module)
  const zc = stats ? stats.zeroclick : null;
  if (zc) {
    document.getElementById('zc-served').textContent = zc.ads_served || 0;
    document.getElementById('zc-imp').textContent = zc.impressions || 0;
    document.getElementById('zc-conv').textContent = zc.conversions || 0;
    const rate = zc.impressions > 0 ? ((zc.conversions / zc.impressions) * 100).toFixed(1) + '%' : '\\u2014';
    document.getElementById('zc-rate').textContent = rate;
    document.getElementById('zc-rev').textContent = (zc.revenue_driven || 0) + ' cr';
    const feed = (zc.recent || []).filter(e => e.type !== 'served').slice(0, 6);
    document.getElementById('zc-feed').innerHTML = feed.length
      ? feed.map(e => {
          if (e.type === 'conversion') {
            return '<div><span style="color:var(--green)">✓ conv</span> <span style="color:var(--dim)">' + escHtml(e.sponsor || '') + '</span> <span style="color:var(--green)">+' + (e.credits||1) + 'cr</span></div>';
          }
          return '<div><span style="color:var(--orange)">◉ imp</span> <span style="color:var(--dim)">' + escHtml((e.sponsor||'').substring(0,20)) + '</span></div>';
        }).join('')
      : '<span style="color:var(--dim2)">no ads yet</span>';
  }

  if (s) {
    document.getElementById('rev').textContent = s.total_revenue_credits || 0;
    document.getElementById('a').textContent = s.total_audits || 0;
    document.getElementById('c').textContent = s.total_compares || 0;
    document.getElementById('m').textContent = s.total_monitors || 0;
    document.getElementById('ub').textContent = s.unique_buyers || 0;

    const txs = (s.transactions || []).slice(0, 8);
    document.getElementById('txs').innerHTML = txs.length
      ? txs.map(t => {
          const method = t.payment_method === 'nevermined_x402' ? '\\u2714 nvm' : (t.payment_method === 'direct_fallback' ? '\\u2015 local' : t.payment_method);
          const cls = t.payment_method === 'nevermined_x402' ? 'var(--green)' : 'var(--orange)';
          return '<div class="tx-item"><div class="tx-top"><span class="tx-endpoint">' + t.endpoint + '</span><span class="tx-credits" style="color:'+cls+'">+' + t.credits + '</span></div><div class="tx-meta">' + t.caller + ' · ' + method + ' · ' + new Date(t.timestamp).toLocaleTimeString() + '</div></div>';
        }).join('')
      : '<div class="empty">none yet</div>';
  }

  // Buyer side
  const buyerData = by || (b ? b : null);
  if (buyerData) {
    document.getElementById('ds').textContent = buyerData.total_spent_credits || (b && b.budget ? b.budget.daily_spent : 0) || 0;
    document.getElementById('ts').textContent = buyerData.total_purchases || 0;

    // Buyer purchase history feed
    const ph = (by && by.purchase_history) || [];
    const txBuyer = document.getElementById('txs-buyer');
    if (txBuyer && ph.length > 0) {
      txBuyer.innerHTML = ph.slice(-5).reverse().map(p => {
        const ok = p.payment_method === 'nevermined_x402';
        const col = ok ? 'var(--green)' : 'var(--orange)';
        return '<div class="tx-item"><div class="tx-top"><span class="tx-endpoint">' + escHtml((p.vendor||'').substring(0,22)) + '</span><span class="tx-credits" style="color:'+col+'">-' + (p.credits||1) + ' cr</span></div>' +
          '<div class="tx-meta">' + (ok ? 'nvm x402' : 'local') + ' · ' + (p.score ? p.score.toFixed(2) : '') + ' · ' + new Date(p.timestamp||Date.now()).toLocaleTimeString() + '</div></div>';
      }).join('');
    }

    // ROI decisions
    const roi = (by && by.roi_decisions) || {};
    const roiEl = document.getElementById('roi');
    if (roiEl) {
      roiEl.innerHTML = Object.entries(roi).filter(([,v])=>v>0).map(([k,v]) => {
        const cls = k==='BUY'||k==='STRONG_BUY' ? 'var(--green)' : k==='AVOID' ? 'var(--red)' : 'var(--orange)';
        return '<span style="color:'+cls+';margin-right:8px">'+k+' '+v+'</span>';
      }).join('') || '<span style="color:var(--dim)">none yet</span>';
    }

  }

  // Seller section — compact
  if (s) {
    document.getElementById('rev').textContent = s.credits_earned || 0;
    const sa = document.getElementById('seller-activity');
    if (sa) {
      const parts = [];
      if (s.audits > 0)      parts.push('audits: ' + s.audits);
      if (s.comparisons > 0) parts.push('compare: ' + s.comparisons);
      if (s.monitors > 0)    parts.push('monitor: ' + s.monitors);
      if (s.unique_buyers > 0) parts.push('buyers: ' + s.unique_buyers);
      sa.textContent = parts.length ? parts.join(' · ') : 'no activity yet';
      sa.style.color = parts.length ? 'var(--fg)' : 'var(--dim2)';
    }
  }
}


async function triggerBuyerLoop() {
  const btn = document.getElementById('run-now-btn');
  btn.textContent = 'running...';
  btn.disabled = true;
  try {
    const r = await fetch(B + '/api/run-now', {method: 'POST'});
    const d = await r.json().catch(() => ({}));
    btn.textContent = d.status === 'ok' ? 'done' : 'error';
  } catch {
    btn.textContent = 'error';
  }
  setTimeout(() => { btn.textContent = 'run loop'; btn.disabled = false; }, 3000);
}

refreshStats();
setInterval(refreshStats, 5000);
input.focus();
</script>
</body></html>
"""


@dashboard_app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


def main():
    uvicorn.run(dashboard_app, host="0.0.0.0", port=9090)


if __name__ == "__main__":
    main()
