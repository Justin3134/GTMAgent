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
.orch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
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
      <button id="run-now-btn" style="font-size:10px;font-family:inherit;background:transparent;border:1px solid var(--dim2);color:var(--dim);padding:3px 8px;border-radius:3px;cursor:pointer;letter-spacing:0.05em" title="Manually trigger the autonomous buyer loop" onclick="triggerBuyerLoop()">run loop</button>
    </div>
  </header>

  <div class="chat-panel">
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
  </div>

  <div class="stats-panel">

    <div class="section-label">Live Orchestration <span style="font-size:9px;color:var(--dim)">· agents running now</span></div>
    <div class="orch-grid" id="orch-grid">
      <div class="agent-box idle" id="orch-exa"        style="grid-column:1"><div class="agent-box-name">Exa Research</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-apify"       style="grid-column:2"><div class="agent-box-name">Apify Store</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-openai"      style="grid-column:1"><div class="agent-box-name">OpenAI Audit</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-nevermined"  style="grid-column:2"><div class="agent-box-name">Nevermined x402</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-trinity"     style="grid-column:1"><div class="agent-box-name" style="color:var(--green)">▲ AbilityAI Trinity</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
    </div>
    <div class="divider"></div>

    <div class="section-label">Buyer <span style="font-size:9px;color:var(--dim);letter-spacing:0">· outgoing purchases</span></div>
    <div class="stat-row"><span class="stat-key">purchased</span><span class="stat-val" id="ts">0</span></div>
    <div class="stat-row"><span class="stat-key">credits spent</span><span class="stat-val" id="ds">0</span></div>
    <div class="stat-row"><span class="stat-key">nvm balance</span><span class="stat-val" id="nvm-balance">&mdash;</span></div>
    <div id="txs-buyer" style="margin-top:6px"><div class="empty">no purchases yet</div></div>
    <div class="divider"></div>

    <div class="section-label">Transactions <span style="font-size:9px;color:var(--dim);letter-spacing:0">· verified on-chain</span></div>
    <div id="txs"><div class="empty">none yet</div></div>
    <div class="divider"></div>

    <div class="section-label">ROI Decisions</div>
    <div id="roi" style="padding:4px 0;font-size:11px"><span style="color:var(--dim)">none yet</span></div>
    <div class="divider"></div>

    <div class="section-label">ZeroClick <span style="font-size:9px;color:var(--green);letter-spacing:0">● live</span></div>
    <div id="zc-live-ad" style="display:none;border:1px solid var(--border);border-radius:4px;padding:10px 12px;margin-bottom:8px;background:rgba(0,255,100,0.03)">
      <div style="font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:var(--dim);margin-bottom:5px">◉ ZeroClick Sponsored</div>
      <div id="zc-ad-title" style="font-size:12px;font-weight:bold;margin-bottom:4px"></div>
      <div id="zc-ad-msg" style="font-size:11px;color:var(--dim);line-height:1.5;margin-bottom:8px"></div>
      <a id="zc-ad-cta" href="#" target="_blank" rel="noopener" style="font-size:10px;color:var(--green);text-decoration:none;letter-spacing:0.05em" onclick="trackZcClick(this)"></a>
    </div>
    <div class="stat-row"><span class="stat-key">ads served</span><span class="stat-val" id="zc-served">0</span></div>
    <div class="stat-row"><span class="stat-key">impressions</span><span class="stat-val" id="zc-imp">0</span></div>
    <div class="stat-row"><span class="stat-key">conversions</span><span class="stat-val" id="zc-conv">0</span></div>
    <div class="stat-row"><span class="stat-key">revenue driven</span><span class="stat-val" id="zc-rev">0</span></div>
    <div class="divider"></div>

    <div class="section-label">Vendors</div>
    <div id="vbs"><div class="empty">no vendors</div></div>
    <div class="divider"></div>

    <div class="section-label">Coverage</div>
    <div class="stat-row"><span class="stat-key">endpoints tracked</span><span class="stat-val" id="ep">0</span></div>
    <div class="stat-row"><span class="stat-key">audit records</span><span class="stat-val" id="ar">0</span></div>
    <div class="divider"></div>

    <div class="section-label">On-Chain <span style="font-size:9px;color:var(--dim);letter-spacing:0">(Base Sepolia)</span></div>
    <div class="stat-row"><span class="stat-key">total mints</span><span class="stat-val" id="ch-mints">&mdash;</span></div>
    <div class="stat-row"><span class="stat-key">total burns</span><span class="stat-val" id="ch-burns">&mdash;</span></div>
    <div class="stat-row"><span class="stat-key">credits minted</span><span class="stat-val" id="ch-cminted">&mdash;</span></div>
    <div class="stat-row"><span class="stat-key">credits burned</span><span class="stat-val" id="ch-cburned">&mdash;</span></div>
    <div class="stat-row"><span class="stat-key">USDC volume</span><span class="stat-val" id="ch-usdc">&mdash;</span></div>
    <div class="stat-row"><span class="stat-key">agreements</span><span class="stat-val" id="ch-agreements">&mdash;</span></div>
    <div style="margin-top:10px;font-size:10px;color:var(--dim);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">Plan burns (recent)</div>
    <div id="ch-burns-feed" style="font-size:10px;line-height:1.7"><span style="color:var(--dim2)">loading...</span></div>
    <div style="margin-top:10px;font-size:10px;color:var(--dim);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px">Daily activity</div>
    <div id="ch-daily-feed" style="font-size:10px;line-height:1.7"><span style="color:var(--dim2)">loading...</span></div>
  </div>
</div>

<script>
const S='', B='';
const msgs = document.getElementById('messages');
const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
let sending = false;

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

  // Count apify actors found
  const nApify = (data.apify_actors || []).length;
  orchSetAgent('exa',        'done',    'research done');
  orchSetAgent('apify',      'done',    nApify + ' actors');

  const nAudited = (data.audit_scores || []).filter(s => !s.error).length;
  orchSetAgent('openai', nAudited > 0 ? 'done' : 'idle', nAudited + ' audited');

  const purchases = data.purchases || data.agents || [];
  const nBought = purchases.filter(p => p.purchased).length;
  const nFailed = purchases.filter(p => !p.purchased && !p.skipped).length;
  orchSetAgent('nevermined', nBought > 0 ? 'done' : (nFailed > 0 ? 'failed' : 'idle'), nBought + ' bought');

  // Update Trinity + fiat-team boxes based on which vendors were purchased
  const trinityPurchase = purchases.find(p => (p.endpoint||p.team||'').includes('abilityai'));
  orchSetAgent('trinity', trinityPurchase ? (trinityPurchase.purchased ? 'done' : 'failed') : 'idle',
               trinityPurchase ? (trinityPurchase.purchased ? 'purchased ✓' : 'failed') : 'standby');

  // Update buyer purchase list with team labels
  const txBuyer = document.getElementById('txs-buyer');
  if (txBuyer && purchases.length > 0) {
    const bought = purchases.filter(p => p.purchased || p.called);
    if (bought.length > 0) {
      const items = bought.map(p => {
        const rawVendor = (p.endpoint || p.team || '');
        const isTrinity = rawVendor.includes('abilityai.dev');
        const label = isTrinity ? 'AbilityAI Trinity' : rawVendor.replace(/https?:[/][/]/,'').substring(0,20);
        const col = p.purchased ? 'var(--green)' : 'var(--orange)';
        const badge = isTrinity ? '<span style="font-size:9px;color:var(--green);margin-left:4px">▲ Trinity</span>' : '';
        return '<div class="tx-item"><div class="tx-top"><span class="tx-endpoint">' + escHtml(label) + badge + '</span>' +
          '<span class="tx-credits" style="color:'+col+'">' + (p.purchased ? '-1 cr' : 'open') + '</span></div>' +
          '<div class="tx-meta">' + (p.purchased ? 'nvm x402' : 'no payment') + ' · ' + new Date().toLocaleTimeString() + '</div></div>';
      });
      txBuyer.innerHTML = items.join('');
    }
  }
}

const ORCH_IDS = {exa:'orch-exa', apify:'orch-apify', openai:'orch-openai', nevermined:'orch-nevermined', trinity:'orch-trinity'};

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
  ['exa','apify','openai','nevermined','trinity'].forEach(id => {
    orchSetAgent(id, 'idle', 'queued...');
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

  // Audit scores
  const scores = data.audit_scores || [];
  if (scores.length) {
    html += '<div style="margin:6px 0;font-size:11px"><span style="color:var(--fg)">Audited candidates:</span><br>';
    scores.forEach(s => {
      const sc = s.overall_score || 0;
      const cls = sc >= 0.7 ? 'var(--green)' : sc >= 0.45 ? 'var(--orange)' : 'var(--red)';
      const rel = s.error ? '— error' : sc.toFixed(2) + ' · ' + (s.recommendation||'');
      html += '<div style="display:flex;justify-content:space-between;margin-top:4px"><span style="color:var(--dim)">' + escHtml(s.team||s.endpoint||'') + '</span><span style="color:'+cls+'">' + rel + '</span></div>';
    });
    html += '</div>';
  }

  // Purchases
  const purchases = data.purchases || [];
  const bought = purchases.filter(p => p.purchased);
  if (bought.length) {
    html += '<div style="margin:6px 0;font-size:11px"><span style="color:var(--green)">✓ Purchased ' + bought.length + ' service(s):</span><br>';
    bought.forEach(p => {
      html += '<div style="margin-top:4px;color:var(--dim)">· ' + escHtml(p.team||p.vendor||p.endpoint||'') + ' <span style="color:var(--green)">−1 credit</span></div>';
      if (p.response) {
        const resp = typeof p.response === 'string' ? p.response : JSON.stringify(p.response).substring(0,200);
        html += '<div style="margin-top:2px;font-size:10px;color:var(--dim2);padding-left:10px">' + escHtml(resp.substring(0,180)) + '…</div>';
      }
    });
    html += '</div>';
  }

  // ROI
  const roi = data.roi_analysis || {};
  if (roi.decision) {
    const cls = roi.decision.includes('BUY') ? 'var(--green)' : 'var(--orange)';
    html += '<div style="margin-top:8px;font-size:11px;border-top:1px solid var(--border);padding-top:6px">';
    html += '<span style="color:var(--fg)">ROI decision: </span><span style="color:'+cls+'">' + escHtml(roi.decision) + '</span>';
    if (roi.top_pick) html += ' · top pick: <span style="color:var(--dim)">' + escHtml(roi.top_pick) + '</span>';
    html += '</div>';
  }

  // Plans that need browser checkout to unlock
  const needsPlan = (roi.needs_plan_purchase || []).filter(p => p.url);
  if (needsPlan.length) {
    html += '<div style="margin-top:8px;padding:8px 10px;border:1px solid var(--orange);border-radius:4px;font-size:11px">';
    html += '<div style="color:var(--orange);margin-bottom:6px;font-size:10px;letter-spacing:0.05em;text-transform:uppercase">Unlock paid plans (one-time)</div>';
    needsPlan.forEach(p => {
      html += '<div style="margin-top:4px">· <span style="color:var(--fg)">' + escHtml(p.team||'Team') + '</span> — ';
      html += '<a href="' + escHtml(p.url) + '" target="_blank" style="color:var(--orange);text-decoration:none">checkout → nevermined.app</a></div>';
    });
    html += '<div style="margin-top:6px;font-size:10px;color:var(--dim)">Log in as justin.07823@gmail.com · card: 4242 4242 4242 4242 · any expiry/CVC</div>';
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

    // Coverage
    const epEl = document.getElementById('ep'); if (epEl) epEl.textContent = b ? (b.services_tracked || 0) : 0;
    const arEl = document.getElementById('ar'); if (arEl) arEl.textContent = b ? (b.audit_history_count || 0) : 0;
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

async function refreshChain() {
  const chain = await get(S + '/chain');
  if (!chain) {
    document.getElementById('ch-burns-feed').innerHTML = '<span style="color:var(--red)">offline</span>';
    return;
  }
  const proto = chain.protocol || {};
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v != null ? v : '\u2014'; };
  set('ch-mints', proto.totalMints);
  set('ch-burns', proto.totalBurns);
  set('ch-cminted', proto.totalCreditsMinted);
  set('ch-cburned', proto.totalCreditsBurned);
  set('ch-usdc', proto.totalUSDCVolume != null ? '$' + proto.totalUSDCVolume : '\u2014');
  set('ch-agreements', proto.totalAgreements);

  // Recent plan burns
  const burnsFeed = document.getElementById('ch-burns-feed');
  const burns = chain.recent_burns || [];
  if (burns.length) {
    burnsFeed.innerHTML = burns.slice(0, 6).map(b => {
      const ts = b.blockTimestamp ? new Date(parseInt(b.blockTimestamp) * 1000).toLocaleTimeString() : '';
      const from = b.from ? b.from.substring(0, 8) + '\u2026' : '';
      return '<div><span style="color:var(--red)">\u2212' + b.amount + '</span> <span style="color:var(--dim)">' + from + (ts ? ' \xb7 ' + ts : '') + '</span></div>';
    }).join('');
  } else {
    burnsFeed.innerHTML = '<span style="color:var(--dim2)">none yet</span>';
  }

  // Daily stats
  const dailyFeed = document.getElementById('ch-daily-feed');
  const daily = chain.daily || [];
  if (daily.length) {
    dailyFeed.innerHTML = daily.slice(0, 5).map(d => {
      return '<div><span style="color:var(--dim)">' + d.date + '</span> <span style="color:var(--green)">\u2191' + (d.mintCount||0) + '</span> <span style="color:var(--red)">\u2193' + (d.burnCount||0) + '</span></div>';
    }).join('');
  } else {
    dailyFeed.innerHTML = '<span style="color:var(--dim2)">no daily data</span>';
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
refreshChain();
setInterval(refreshStats, 5000);
setInterval(refreshChain, 30000);
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
