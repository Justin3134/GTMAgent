"""GTMAgent Dashboard — chat interface + stats sidebar."""

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

dashboard_app = FastAPI(title="GTMAgent Dashboard")
dashboard_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GTMAgent</title>
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

/* ── Flow View ── */
@keyframes flowIn {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
.flow-reveal { opacity: 0; animation: flowIn 0.4s ease both; }

/* Section headers */
.flow-section { margin-bottom: 28px; }
.flow-section-label {
  font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--dim2); margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}
.flow-section-label::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.flow-section-label::before { content: ''; flex: 0; }

/* Goal card */
.flow-goal {
  border: 1px solid var(--orange); border-radius: 6px;
  padding: 16px 20px; background: #0d0800; text-align: center; margin-bottom: 28px;
}
.flow-goal-title { font-size: 15px; font-weight: 500; margin-bottom: 4px; }
.flow-goal-caps { font-size: 10px; color: var(--dim); margin-top: 6px; }
.flow-goal-phase { font-size: 9px; color: #5a4400; letter-spacing: 0.06em; margin-top: 8px; }

/* Research branch columns */
.flow-branches { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 28px; }
.flow-branch { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.flow-branch-header {
  padding: 8px 12px; font-size: 9px; letter-spacing: 0.1em;
  text-transform: uppercase; font-weight: 500; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
}
.flow-branch-body { padding: 8px 10px; }
.flow-branch.mkt   { border-color: #223366; } .flow-branch.mkt   .flow-branch-header { background: #050815; color: #5577ff; }
.flow-branch.exa   { border-color: #443300; } .flow-branch.exa   .flow-branch-header { background: #090500; color: #ff8833; }
.flow-branch.apify { border-color: #221144; } .flow-branch.apify .flow-branch-header { background: #060309; color: #8855ff; }

/* Cards inside branches */
.flow-card {
  border: 1px solid var(--border); border-radius: 4px; padding: 7px 9px;
  margin-bottom: 6px; font-size: 10px; background: #040404;
  transition: border-color 0.2s;
}
.flow-card:last-child { margin-bottom: 0; }
.flow-card.scored-buy  { border-color: #1a3a1a; background: #040804; }
.flow-card.scored-watch { border-color: #3a3000; background: #080700; }
.flow-card.scored-avoid { border-color: #3a1a1a; background: #080404; }
.flow-card .fc-name  { font-weight: 500; margin-bottom: 2px; }
.flow-card .fc-meta  { color: var(--dim2); font-size: 9px; }
.flow-card .fc-score { font-size: 13px; font-weight: 300; }
.flow-card .fc-link  { color: #5577ff; font-size: 9px; text-decoration: none; }
.flow-card .fc-link:hover { text-decoration: underline; }

/* ZeroClick inline */
.zc-inline { border-left: 2px solid #1a4a1a; padding: 5px 8px; margin: 6px 0; font-size: 10px; background: #040a04; border-radius: 0 3px 3px 0; }
.zc-inline-label { font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: #2a6a2a; margin-bottom: 2px; }

/* Competitive analysis table */
.comp-table { width: 100%; border-collapse: collapse; font-size: 10px; }
.comp-table th { text-align: left; color: var(--dim); font-weight: 400; padding: 4px 8px; border-bottom: 1px solid var(--border); font-size: 9px; letter-spacing: 0.06em; }
.comp-table td { padding: 6px 8px; border-bottom: 1px solid #111; vertical-align: top; }
.comp-table tr:last-child td { border-bottom: none; }
.comp-table tr:hover td { background: #0a0a0a; }

/* Audit decisions row */
.flow-audit-row { display: flex; gap: 10px; flex-wrap: wrap; }
.flow-audit-card {
  border: 1px solid var(--border); border-radius: 5px; padding: 10px 14px;
  flex: 1; min-width: 120px; text-align: center;
}
.flow-audit-card.buy   { border-color: var(--green); background: #030a03; }
.flow-audit-card.watch { border-color: var(--orange); background: #080600; }
.flow-audit-card.avoid { border-color: var(--red); background: #080303; }
.flow-audit-card .fac-team  { font-size: 10px; font-weight: 500; margin-bottom: 4px; }
.flow-audit-card .fac-score { font-size: 22px; font-weight: 300; line-height: 1; }
.flow-audit-card .fac-label { font-size: 9px; letter-spacing: 0.06em; margin-top: 2px; }
.flow-audit-card .fac-sub   { font-size: 9px; color: var(--dim2); margin-top: 4px; line-height: 1.5; }

/* Purchases */
.flow-purchase-row { display: flex; gap: 10px; flex-wrap: wrap; }
.flow-purchase-card {
  border: 1px solid var(--green); border-radius: 5px; padding: 10px 14px;
  background: #030a03; flex: 1; min-width: 130px;
}
.fpc-team  { font-size: 11px; font-weight: 500; margin-bottom: 3px; }
.fpc-tx    { font-size: 9px; color: var(--dim2); font-family: monospace; }
.fpc-badge { font-size: 8px; letter-spacing: 0.06em; padding: 1px 5px; border-radius: 2px; margin-left: 4px; }
.fpc-badge.new    { background: #0d2a0d; color: var(--green); }
.fpc-badge.repeat { background: #2a1f00; color: var(--orange); }

/* ZeroClick full card */
.flow-zc-card {
  border: 1px solid #1a4a1a; border-radius: 5px; padding: 12px 16px;
  background: #030a03; display: flex; justify-content: space-between; align-items: center; gap: 16px;
}
.flow-zc-badge { font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: #3a8a3a; margin-bottom: 4px; }

/* Trinity fleet */
.flow-trinity-grid { display: flex; gap: 10px; flex-wrap: wrap; }
.flow-trinity-card {
  border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px;
  flex: 1; min-width: 130px; max-width: 180px; cursor: pointer;
  transition: border-color 0.2s, background 0.2s; position: relative;
}
.flow-trinity-card:hover { background: #0a0a0a; }
.ftc-template { font-size: 8px; letter-spacing: 0.07em; text-transform: uppercase; margin-bottom: 3px; }
.ftc-name     { font-size: 13px; font-weight: 500; margin-bottom: 2px; }
.ftc-role     { font-size: 10px; color: var(--dim); margin-bottom: 5px; }
.ftc-task     { font-size: 9px; color: var(--dim2); line-height: 1.45; }
.ftc-status   { margin-top: 7px; font-size: 9px; display: flex; align-items: center; gap: 4px; }
.ftc-explore  { position: absolute; top: 8px; right: 8px; font-size: 8px; color: var(--dim2); }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.4} }
.dot-pulse { width: 5px; height: 5px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; display: inline-block; }

/* Trinity detail side-panel */
#trinity-panel {
  position: fixed; top: 0; right: -420px; width: 400px; height: 100vh;
  background: #090909; border-left: 1px solid var(--border);
  overflow-y: auto; padding: 24px 20px; z-index: 100;
  transition: right 0.3s ease;
}
#trinity-panel.open { right: 0; }
#trinity-panel-close { position: sticky; top: 0; float: right; background: transparent; border: 1px solid var(--border); color: var(--dim); cursor: pointer; padding: 3px 8px; border-radius: 3px; font-family: inherit; font-size: 11px; }

/* ── Pipeline Graph ── */
#flow-canvas { position: relative; }
.fg-wrap { max-width: 880px; margin: 0 auto; }

/* Goal box */
.fg-goal-box {
  margin: 0 auto;
  max-width: 440px;
  border: 1px solid var(--orange);
  border-radius: 6px;
  padding: 14px 20px;
  background: #080500;
  text-align: center;
  position: relative; z-index: 2;
}
.fg-goal-title { font-size: 17px; font-weight: 500; }
.fg-goal-sub { font-size: 9px; color: var(--orange); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 5px; }
.fg-goal-caps { font-size: 9px; color: var(--dim2); margin-top: 5px; }

/* Stage wrapper */
.fg-stage {
  border: 1px solid var(--border); border-radius: 6px;
  background: #040404; margin-top: 44px;
  position: relative; z-index: 2;
}
.fg-stage.green { border-color: #1a4a1a; }
.fg-stage-lbl {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--dim);
}
.fg-stage.green .fg-stage-lbl { border-color: #0d2a0d; color: var(--green); }
.fg-step-n {
  font-size: 8px; font-weight: 700; padding: 2px 5px;
  border-radius: 2px; background: #1a1a1a; color: var(--dim);
}
.fg-stage.green .fg-step-n { background: #0d2a0d; color: var(--green); }
.fg-stage-body { padding: 12px 14px; }

/* 3-column discover row (inside stage) */
.fg-branches { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
@media(max-width:600px) { .fg-branches { grid-template-columns: 1fr; } }
.fg-branch { border: 1px solid var(--border); border-radius: 4px; background: #050505; }
.fg-branch-hdr {
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 10px; border-bottom: 1px solid var(--border);
  font-size: 9px; text-transform: uppercase; letter-spacing: 0.07em;
}
.fg-branch-body { padding: 6px 8px; min-height: 60px; }
.fg-branch.mkt .fg-branch-hdr { color: #6688dd; }
.fg-branch.exa .fg-branch-hdr { color: #dd8833; }
.fg-branch.api .fg-branch-hdr { color: #8844cc; }
.fg-mini-card { border-left: 2px solid var(--border); padding: 3px 7px; margin-bottom: 4px; font-size: 10px; }
.fg-mini-card:hover { background: #0a0a0a; }
.fg-mini-name { font-weight: 500; }
.fg-mini-meta { font-size: 9px; color: var(--dim2); }

/* Audit chips */
.fg-audit-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.fg-chip {
  border: 1px solid var(--border); border-radius: 4px;
  padding: 8px 12px; min-width: 120px; background: #050505;
}
.fg-chip.buy  { border-color: #1a4a1a; }
.fg-chip.watch { border-color: #4a3a00; }
.fg-chip.avoid { border-color: #4a1a1a; }
.fg-chip-team  { font-size: 11px; font-weight: 500; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fg-chip-score { font-size: 22px; font-weight: 300; line-height: 1; }
.fg-chip-label { font-size: 8px; text-transform: uppercase; letter-spacing: 0.07em; margin-top: 2px; }
.fg-chip-sub   { font-size: 9px; color: var(--dim2); margin-top: 5px; line-height: 1.5; }

/* Trinity grid */
.fg-trinity-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); gap: 8px; }
.fg-ta {
  border-radius: 4px; padding: 10px 12px; cursor: pointer;
  transition: transform 0.12s;
}
.fg-ta:hover { transform: translateY(-2px); }
.fg-ta-role { font-size: 8px; text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 3px; }
.fg-ta-name { font-size: 12px; font-weight: 500; margin-bottom: 2px; }
.fg-ta-task { font-size: 9px; color: var(--dim); line-height: 1.4; margin-bottom: 5px; }
.fg-ta-out  { font-size: 9px; color: #3a6a3a; font-style: italic; border-left: 2px solid #1a3a1a; padding-left: 5px; margin-bottom: 5px; }
.fg-ta-foot { font-size: 9px; display: flex; align-items: center; gap: 4px; }

/* Execution output cards */
.fg-output-card {
  border: 1px solid #1a4a1a; border-radius: 5px;
  padding: 12px 14px; margin-bottom: 8px; background: #030a03;
}
.fg-output-hdr { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.fg-output-team { font-weight: 500; font-size: 13px; }
.fg-output-live { display: flex; align-items: center; gap: 4px; font-size: 8px; color: var(--green); text-transform: uppercase; letter-spacing: 0.07em; }
.fg-output-body { font-size: 10px; color: #ccc; line-height: 1.7; border-left: 2px solid #1a4a1a; padding-left: 10px; }
.fg-output-body ul, .fg-output-body ol { margin: 4px 0 4px 12px; padding: 0; }
.fg-synth-card {
  border-left: 3px solid var(--border); padding: 8px 12px;
  margin-bottom: 7px; background: #050505; border-radius: 0 4px 4px 0;
}
.fg-synth-title { font-size: 11px; font-weight: 500; margin-bottom: 5px; }
.fg-synth-body  { font-size: 10px; color: var(--dim); line-height: 1.7; }

/* SVG connector layer */
.fg-svg { position: absolute; top: 0; left: 0; width: 100%; pointer-events: none; overflow: visible; }

/* Next actions */
.fg-next { border: 1px solid var(--border); border-radius: 5px; padding: 12px 14px; margin-top: 12px; }
.fg-next-title { font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--dim); margin-bottom: 8px; }
.fg-next-btn {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border: 1px solid var(--border); border-radius: 3px; margin-bottom: 5px;
  cursor: pointer; font-size: 11px; background: transparent; color: var(--fg);
  font-family: inherit; width: 100%; text-align: left; transition: background 0.12s;
}
.fg-next-btn:hover { background: #0d0d0d; border-color: #444; }
.fg-next-btn:last-child { margin-bottom: 0; }

/* ── Business Dashboard ── */
.biz-header {
  border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px;
}
.biz-goal { font-size: 18px; font-weight: 500; margin-bottom: 4px; }
.biz-meta { font-size: 10px; color: var(--dim); display: flex; gap: 16px; }
.biz-meta span { display: flex; align-items: center; gap: 4px; }

.biz-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
@media(max-width:700px) { .biz-grid { grid-template-columns: 1fr; } }

.biz-agent-card {
  border: 1px solid var(--border); border-radius: 8px; padding: 16px;
  background: #060606; position: relative; overflow: hidden;
}
.biz-agent-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
}
.biz-agent-card.cornelius::before { background: #334499; }
.biz-agent-card.ruby::before      { background: #993344; }
.biz-agent-card.outbound::before  { background: #449933; }
.biz-agent-card.webmaster::before { background: #996633; }

.biz-agent-name { font-size: 14px; font-weight: 500; margin-bottom: 2px; }
.biz-agent-role { font-size: 9px; color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
.biz-agent-output {
  font-size: 11px; color: #ccc; line-height: 1.65; white-space: pre-wrap;
  border-left: 2px solid var(--border); padding-left: 10px;
}
.biz-agent-output.loading {
  color: var(--dim2); font-style: italic;
  animation: shimmerLoad 2s ease-in-out infinite;
}
@keyframes shimmerLoad {
  0%,100% { opacity: 1; border-left-color: var(--border); }
  50%     { opacity: 0.5; border-left-color: var(--orange); }
}
.biz-agent-output strong { color: var(--fg); font-weight: 500; }
.biz-agent-status { margin-top: 10px; font-size: 9px; display: flex; align-items: center; gap: 5px; }
.biz-agent-card.processing { animation: cardPulse 1.8s ease-in-out infinite; }
@keyframes cardPulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(100,200,100,0); }
  50%     { box-shadow: 0 0 12px 2px rgba(100,200,100,0.15); }
}
.biz-processing-label {
  font-size: 9px; color: var(--orange); text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 5px; display: flex; align-items: center; gap: 6px;
}
.biz-processing-label .spinner {
  width: 10px; height: 10px; border: 1.5px solid var(--border); border-top-color: var(--orange);
  border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }
.suggest-card {
  border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px;
  background: linear-gradient(160deg, #060608 0%, #0a0a10 100%);
  cursor: pointer; transition: border-color 0.2s, background 0.2s;
}
.suggest-card:hover { border-color: var(--dim); background: #0c0c14; }

.biz-txns { margin-bottom: 20px; }
.biz-txn-row {
  display: flex; align-items: center; gap: 12px; padding: 8px 12px;
  border: 1px solid #1a2a1a; border-radius: 5px; margin-bottom: 6px;
  background: #030a03; font-size: 10px;
}
.biz-txn-team { font-weight: 500; flex: 1; }
.biz-txn-hash { font-family: monospace; color: var(--dim2); font-size: 9px; }
.biz-txn-badge { font-size: 8px; padding: 2px 6px; border-radius: 2px; background: #0d2a0d; color: var(--green); }

.biz-next { border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px; margin-bottom: 20px; }
.biz-next-title { font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--dim); margin-bottom: 10px; }
.biz-next-action {
  display: flex; align-items: center; gap: 10px; padding: 8px 10px;
  border: 1px solid var(--border); border-radius: 4px; margin-bottom: 6px;
  cursor: pointer; font-size: 11px; background: transparent; color: var(--fg);
  font-family: inherit; width: 100%; text-align: left; transition: background 0.15s;
}
.biz-next-action:hover { background: #0a0a0a; }
.biz-next-action:last-child { margin-bottom: 0; }

/* Business Execution Results (in Flow) */
.exec-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.exec-card {
  border: 1px solid #1a2a1a; border-radius: 6px; padding: 14px 16px;
  background: linear-gradient(160deg, #050a05 0%, #060909 100%);
}
.exec-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.exec-card-team { font-weight: 500; font-size: 12px; }
.exec-card-badge { font-size: 8px; letter-spacing: 0.07em; text-transform: uppercase; padding: 2px 6px; border-radius: 2px; background: #0d2a0d; color: var(--green); }
.exec-card-content { font-size: 10px; color: var(--dim); line-height: 1.6; }
.exec-card-content b, .exec-card-content strong { color: #ccc; font-weight: 500; }

/* Apify run result */
.apify-run-card {
  border: 1px solid #221133; border-radius: 6px; padding: 14px 16px;
  background: linear-gradient(160deg, #040309 0%, #060408 100%);
}
.apify-run-item { border-left: 2px solid #441188; padding: 5px 8px; margin-bottom: 5px; font-size: 10px; }

/* Live status pulse on execution section */
@keyframes statusPulse { 0%,100%{background:#0d2a0d}50%{background:#0a200a} }
.exec-running { animation: statusPulse 2.5s ease infinite; }
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
    <h1>GTMAgent</h1>
    <div class="header-right">
      <div class="svc-status" title="Seller endpoint status"><span class="dot" id="dot-seller"></span><span id="st-seller">seller</span></div>
      <div class="svc-status" title="Buyer agent status"><span class="dot" id="dot-buyer"></span><span id="st-buyer">buyer</span></div>
      <div style="width:1px;height:16px;background:var(--border);margin:0 4px"></div>
      <div class="svc-status" id="tool-openai-wrap" title="OpenAI GPT-4o-mini — quality scoring LLM"><span class="dot" id="dot-openai"></span><span style="font-size:10px">OpenAI</span><span id="tool-openai-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-exa-wrap" title="Exa — web crawl and ground-truth scoring"><span class="dot" id="dot-exa"></span><span style="font-size:10px">Exa</span><span id="tool-exa-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-nvm-wrap" title="Nevermined x402 — payment infrastructure"><span class="dot" id="dot-nvm"></span><span style="font-size:10px">Nevermined</span><span id="tool-nvm-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-zc-wrap" title="ZeroClick native ads — live"><span class="dot" id="dot-zc"></span><span style="font-size:10px">ZeroClick</span><span id="tool-zc-status" style="font-size:9px;color:var(--green);margin-left:3px">live</span></div>
      <div class="svc-status" id="tool-apify-wrap" title="Apify Store — web scrapers and AI actors marketplace"><span class="dot up" id="dot-apify"></span><span style="font-size:10px">Apify</span><span id="tool-apify-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div class="svc-status" id="tool-mindra-wrap" title="Mindra — 5 parallel GTM agents (Web Search, LinkedIn, Google, GitHub, Content)"><span class="dot up" id="dot-mindra"></span><span style="font-size:10px">Mindra&times;5</span><span id="tool-mindra-count" style="font-size:9px;color:var(--dim);margin-left:3px;display:none"></span></div>
      <div style="width:1px;height:16px;background:var(--border);margin:0 4px"></div>
      <div style="display:flex;gap:4px">
        <button id="btn-chat" onclick="showView('chat')" style="font-size:10px;font-family:inherit;background:var(--fg);border:1px solid var(--fg);color:var(--bg);padding:3px 10px;border-radius:3px;cursor:pointer;letter-spacing:0.05em">Chat</button>
        <button id="btn-flow" onclick="showView('flow')" style="font-size:10px;font-family:inherit;background:transparent;border:1px solid var(--dim2);color:var(--dim);padding:3px 10px;border-radius:3px;cursor:pointer;letter-spacing:0.05em">Flow</button>
        <button id="btn-biz" onclick="showView('biz')" style="font-size:10px;font-family:inherit;background:transparent;border:1px solid var(--dim2);color:var(--dim);padding:3px 10px;border-radius:3px;cursor:pointer;letter-spacing:0.05em">Business</button>
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

    <!-- Business Dashboard View -->
    <div id="view-biz" style="display:none;position:absolute;inset:0;overflow-y:auto;padding:24px 32px;background:var(--bg)">
      <div id="biz-canvas">
        <div style="color:var(--dim2);padding:40px 0;text-align:center">Run a business strategy in Chat first.<br><br><span style="font-size:10px">Try: "I want to build a marketing agency"</span></div>
      </div>
    </div>

    <!-- ZeroClick Ad Gate Overlay (covers all views) -->
    <div id="zc-gate-overlay">
      <div class="zc-gate-card">
        <div class="zc-gate-badge">◉ ZeroClick Sponsored</div>
        <div class="zc-gate-title" id="zc-gate-title"></div>
        <div class="zc-gate-msg" id="zc-gate-msg"></div>
        <a class="zc-gate-cta" id="zc-gate-cta" href="#" target="_blank" rel="noopener">Learn more →</a>
        <div class="zc-gate-hint" id="zc-gate-hint">Click the link above to continue</div>
        <div class="zc-gate-sponsor" id="zc-gate-sponsor"></div>
      </div>
    </div>

    <!-- Chat View -->
    <div id="view-chat" class="chat-panel" style="position:absolute;inset:0">
    <div class="chat-messages" id="messages">
      <div class="welcome">
        <strong>GTMAgent</strong> — Autonomous Business Intelligence<br><br>
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
      <input id="chat-input" placeholder="Describe a business goal..." autocomplete="off" />
      <button id="send-btn">Send</button>
    </div>
    </div><!-- end view-chat -->
  </div><!-- end content-area wrapper -->

  <div class="stats-panel">

    <div class="section-label">Mindra GTM Agents <span style="font-size:9px;color:#6ecbf5">· 5 parallel</span></div>
    <div class="orch-grid" id="orch-grid-mindra" style="grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:4px;display:grid">
      <div class="agent-box idle" id="orch-mindra-web"     ><div class="agent-box-name" style="color:#6ecbf5;font-size:9px">&#x1F50D; Web Search</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-mindra-linkedin" ><div class="agent-box-name" style="color:#6ecbf5;font-size:9px">&#x25C8; LinkedIn</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-mindra-google"   ><div class="agent-box-name" style="color:#6ecbf5;font-size:9px">&#x25A3; Google</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-mindra-github"   ><div class="agent-box-name" style="color:#6ecbf5;font-size:9px">&#x2B22; GitHub</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-mindra-content"  ><div class="agent-box-name" style="color:#6ecbf5;font-size:9px">&#x270E; Content</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
    </div>
    <div style="height:4px"></div>
    <div class="section-label">Live Orchestration <span style="font-size:9px;color:var(--dim)">· marketplace agents</span></div>
    <div class="orch-grid" id="orch-grid">
      <div class="agent-box idle" id="orch-exa"        ><div class="agent-box-name">Exa Research</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-apify"      ><div class="agent-box-name">Apify Store</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-openai"     ><div class="agent-box-name">OpenAI Audit</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-nevermined" ><div class="agent-box-name">Nevermined</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-trinity"    ><div class="agent-box-name" style="color:var(--green)">&#x25B2; TrinityOS: Nexus</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
      <div class="agent-box idle" id="orch-social"     ><div class="agent-box-name" style="color:var(--green)">&#x25B2; TrinityOS: Social</div><div class="agent-box-status"><span class="agent-pulse idle"></span>standby</div></div>
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
    <div style="font-size:9px;color:var(--dim2);margin-bottom:6px">Ad gate active — every action requires ZeroClick</div>
    <div class="stat-row"><span class="stat-key">impressions</span><span class="stat-val" id="zc-imp">0</span></div>
    <div class="stat-row"><span class="stat-key">conversions</span><span class="stat-val" id="zc-conv">0</span></div>
    <div class="divider"></div>

    <div class="section-label">Mindra <span style="font-size:9px;letter-spacing:0;color:#6ecbf5" id="mindra-status">ready</span></div>
    <div style="font-size:9px;color:var(--dim2);margin-bottom:4px">5 parallel GTM agents</div>
    <div class="stat-row"><span class="stat-key">orchestrations</span><span class="stat-val" id="mindra-calls">0</span></div>
    <div class="stat-row"><span class="stat-key">agents succeeded</span><span class="stat-val" id="mindra-succeeded" style="color:#6ecbf5">0/5</span></div>
    <div class="stat-row"><span class="stat-key">self-healing</span><span class="stat-val" style="color:#6ecbf5">active</span></div>
    <div class="stat-row"><span class="stat-key">anomaly detection</span><span class="stat-val" style="color:#6ecbf5">active</span></div>
  </div>
</div>

<script>
const S='', B='';
const msgs = document.getElementById('messages');
const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
let sending = false;
let lastSentMessage = '';
let totalCreditsSpent = 0;
let lastStreamAd = null;
let adGateActive = false;


function retryLastMessage() {
  if (lastSentMessage && !sending) {
    input.value = lastSentMessage;
    sendMessage();
  }
}

let _gateResolve = null;
async function showAdGate(ad, hint, onDone) {
  adGateActive = true;
  if (!ad) {
    try {
      const resp = await fetch(B + '/api/zeroclick-ad');
      if (resp.ok) ad = await resp.json();
    } catch(e) {}
  }
  if (!ad) ad = {
    sponsor: 'ZeroClick.ai', title: 'ZeroClick — Native AI Ads',
    message: 'Contextual native ads for AI-native services.',
    cta: 'Learn about ZeroClick', click_url: 'https://zeroclick.ai'
  };

  const overlay = document.getElementById('zc-gate-overlay');
  document.getElementById('zc-gate-title').textContent = ad.title || ad.sponsor || 'ZeroClick';
  document.getElementById('zc-gate-msg').textContent = (ad.message || '').substring(0, 200);
  const ctaEl = document.getElementById('zc-gate-cta');
  ctaEl.textContent = (ad.cta || 'Learn more') + ' →';
  ctaEl.href = ad.click_url || 'https://zeroclick.ai';
  ctaEl.dataset.offerId = ad.id || '';
  document.getElementById('zc-gate-sponsor').textContent = 'Sponsored by ' + (ad.sponsor || 'ZeroClick.ai');
  document.getElementById('zc-gate-hint').textContent = hint || 'Click the link above to continue';

  overlay.classList.add('active');
  input.disabled = true;
  btn.disabled = true;

  ctaEl.addEventListener('click', function onGateClick() {
    ctaEl.removeEventListener('click', onGateClick);
    const offerId = ctaEl.dataset.offerId;
    if (offerId) fetch(S + '/zeroclick/click?offer_id=' + encodeURIComponent(offerId), {method:'POST'}).catch(()=>{});
    overlay.classList.remove('active');
    adGateActive = false;
    input.disabled = false;
    btn.disabled = false;
    input.focus();
    if (onDone) onDone();
  }, {once: true});
}

document.getElementById('zc-gate-overlay').addEventListener('click', e => e.stopPropagation());
document.addEventListener('keydown', e => { if (adGateActive && e.key === 'Escape') e.preventDefault(); });

let lastStrategyData = null;

function _doShowView(v) {
  const chat  = document.getElementById('view-chat');
  const flow  = document.getElementById('view-flow');
  const biz   = document.getElementById('view-biz');
  const btnChat = document.getElementById('btn-chat');
  const btnFlow = document.getElementById('btn-flow');
  const btnBiz  = document.getElementById('btn-biz');

  function applyStyle(b, active) {
    b.style.background   = active ? 'var(--fg)' : 'transparent';
    b.style.color        = active ? 'var(--bg)' : 'var(--dim)';
    b.style.borderColor  = active ? 'var(--fg)' : 'var(--dim2)';
  }

  chat.style.display = 'none';
  flow.style.display = 'none';
  biz.style.display  = 'none';
  applyStyle(btnChat, false);
  applyStyle(btnFlow, false);
  if (btnBiz) applyStyle(btnBiz, false);

  if (v === 'flow') {
    flow.style.display = 'block';
    flow.style.zIndex = '1';
    applyStyle(btnFlow, true);
    _loadKeyStatus().then(() => {
      try { renderFlowView(lastStrategyData); }
      catch(err) {
        const cv = document.getElementById('flow-canvas');
        if (cv) cv.innerHTML = '<div style="color:var(--red);padding:20px">Flow render error: ' + err.message + '</div>';
      }
    });
  } else if (v === 'biz') {
    biz.style.display = 'block';
    if (btnBiz) applyStyle(btnBiz, true);
    try { renderBizDashboard(lastStrategyData); }
    catch(err) {
      const cv = document.getElementById('biz-canvas');
      if (cv) cv.innerHTML = '<div style="color:var(--red);padding:20px">Biz render error: ' + err.message + '</div>';
    }
  } else {
    chat.style.display = 'flex';
    applyStyle(btnChat, true);
  }
}

function showView(v) {
  if (v === 'flow' || v === 'biz') {
    const label = v === 'flow' ? 'Flow view' : 'Business dashboard';
    showAdGate(null, 'Click to access ' + label, function() { _doShowView(v); });
  } else {
    _doShowView(v);
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
        'openai', 'exa', 'zeroclick', 'nvm', 'apify', 'mindra'
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

// ZeroClick inline badge
function _zcInline(ad, context) {
  if (!ad) return '';
  return '<div class="zc-inline"><div class="zc-inline-label">◉ ZeroClick sponsored</div>' +
    '<span style="color:var(--dim)">' + e(ad.sponsor||'') + ' — </span>' +
    '<a href="' + e(ad.click_url||'#') + '" target="_blank" style="color:#3a8a3a;text-decoration:none">' + e((ad.title||'').substring(0,60)) + '</a>' +
    (context ? ' <span style="color:var(--dim2);font-size:9px">· ' + e(context) + '</span>' : '') +
    '</div>';
}

// Section wrapper with animation delay
let _flowDelay = 0;
function _sec(html) {
  const d = _flowDelay;
  _flowDelay += 130;
  return '<div class="flow-section flow-reveal" style="animation-delay:' + d + 'ms">' + html + '</div>';
}
function _secLabel(txt) {
  return '<div class="flow-section-label">' + txt + '</div>';
}
function _arrow() {
  return '<div class="flow-arrow">↓</div>';
}

function renderFlowView(data) {
  const canvas = document.getElementById('flow-canvas');
  if (!data) {
    canvas.innerHTML = '<div style="color:var(--dim2);padding:60px 0;text-align:center;font-size:12px">Run a strategy in Chat to see the workflow graph here.<br><br><span style="font-size:10px;color:var(--dim2)">Try: "I want to start a marketing agency"</span></div>';
    return;
  }
  const scored  = (data.audit_scores || []).filter(s => s.team);
  const apify   = data.apify_actors || [];
  const exa     = data.exa_research || {};
  const exaComps = exa.competitors || [];
  const allMkt  = data.all_marketplace_results || data.candidates || [];
  const purchases = (data.purchases||[]).filter(p => p.purchased);
  const caps    = data.goal_capabilities || [];
  const ad      = data.zeroclick_ad || null;
  const mindraAgents = data.mindra_agents || {};
  const mindraGtm    = data.mindra_gtm_synthesis || '';
  const hasMindra    = Object.keys(mindraAgents).length > 0 || data.orchestrator === 'mindra';

  let html = '<div class="fg-wrap" style="position:relative">';

  // ── GOAL ──────────────────────────────────────────────────────────────────────
  html += '<div id="fgn-goal" class="fg-goal-box">';
  html += '<div class="fg-goal-sub">Goal</div>';
  html += '<div class="fg-goal-title">' + e(data.goal||'') + '</div>';
  if (caps.length) html += '<div class="fg-goal-caps">' + caps.slice(0,4).map(e).join(' · ') + '</div>';
  html += '</div>';

  // ── MINDRA GTM — 5 parallel agents ─────────────────────────────────────────
  if (hasMindra) {
    const mindraIds = {web_search:'Web Search', linkedin:'LinkedIn', google:'Google Workspace', github:'GitHub', content:'Content Creator'};
    const mindraSucc = Object.values(mindraAgents).filter(a => a.status === 'completed' && (a.answer||'').length > 0).length;
    const mindraTotal = Object.keys(mindraAgents).length || 5;
    html += '<div class="fg-stage" id="fgn-mindra" style="margin-top:44px;border-color:#1a3044">';
    html += '<div class="fg-stage-lbl"><span class="fg-step-n" style="background:#0a1a2a;color:#6ecbf5">M</span> Mindra GTM Agents — ' + mindraSucc + '/' + mindraTotal + ' succeeded</div>';
    html += '<div class="fg-stage-body">';
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px">';
    Object.entries(mindraIds).forEach(([mid, label]) => {
      const ma = mindraAgents[mid] || {};
      const ok = ma.status === 'completed' && (ma.answer||'').length > 0;
      const errored = ma.status === 'error' || ma.status === 'timeout' || ma.status === 'unavailable';
      const borderCol = ok ? '#1a4a1a' : errored ? '#4a1a1a' : '#1a3044';
      const statusCol = ok ? 'var(--green)' : errored ? 'var(--red)' : '#6ecbf5';
      const statusTxt = ok ? 'completed' : (ma.status || 'running');
      const tools = ma.tool_count || 0;
      html += '<div class="fg-mini-card" style="border-color:' + borderCol + '">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center">';
      html += '<div class="fg-mini-name" style="color:#6ecbf5">' + e(label) + '</div>';
      html += '<div style="font-size:9px;font-weight:500;color:' + statusCol + '">' + e(statusTxt) + '</div>';
      html += '</div>';
      if (ok && tools > 0) html += '<div class="fg-mini-meta">' + tools + ' tools · ' + (ma.answer||'').length + ' chars</div>';
      else if (ma.answer) html += '<div class="fg-mini-meta">' + e((ma.answer||'').substring(0,55)) + '</div>';
      html += '</div>';
    });
    html += '</div>';
    if (mindraGtm) {
      html += '<div style="margin-top:10px;padding:8px 10px;background:#050d14;border:1px solid #1a3044;border-radius:4px">';
      html += '<div style="font-size:8px;text-transform:uppercase;letter-spacing:0.08em;color:#6ecbf5;margin-bottom:4px">GTM Strategy Synthesis</div>';
      html += '<div style="font-size:10px;color:#bbb;line-height:1.5;white-space:pre-wrap">' + e(mindraGtm.substring(0, 600)) + '</div>';
      html += '</div>';
    }
    html += '</div></div>';
  }

  // ── DISCOVER — 3 parallel branches ───────────────────────────────────────────
  html += '<div style="margin-top:44px;position:relative;z-index:2" id="fgn-discover">';
  html += '<div style="font-size:8px;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim);text-align:center;margin-bottom:12px">01 · Discover — parallel search</div>';
  html += '<div class="fg-branches">';

  // Marketplace branch
  html += '<div class="fg-branch mkt" id="fgn-mkt">';
  html += '<div class="fg-branch-hdr"><span>Nevermined Marketplace</span><span style="font-size:9px;color:var(--dim)">' + allMkt.length + ' agents</span></div>';
  html += '<div class="fg-branch-body">';
  if (allMkt.length === 0) {
    html += '<div style="color:var(--dim2);font-size:10px;padding:6px 0">Searching...</div>';
  }
  allMkt.slice(0,5).forEach(m => {
    const sc  = scored.find(s => s.team === m.team);
    const scv = sc ? sc.overall_score : null;
    const bc  = scv === null ? 'var(--border)' : scv >= 0.6 ? '#1a4a1a' : scv >= 0.4 ? '#4a3a00' : '#4a1a1a';
    const tc  = scv === null ? 'var(--dim)' : scv >= 0.6 ? 'var(--green)' : scv >= 0.4 ? 'var(--orange)' : 'var(--red)';
    html += '<div class="fg-mini-card" style="border-color:' + bc + '">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center">';
    html += '<div class="fg-mini-name">' + e((m.team||'').substring(0,22)) + '</div>';
    if (scv !== null) html += '<div style="font-size:11px;font-weight:500;color:' + tc + '">' + scv.toFixed(2) + '</div>';
    html += '</div>';
    html += '<div class="fg-mini-meta">' + e((m.category||m.price||'').substring(0,30)) + '</div>';
    html += '</div>';
  });
  html += '</div></div>';

  // Exa competitive intelligence branch
  const exaLabel = exaComps.length > 0 ? 'Exa · competitive landscape' : 'Exa · competitive research';
  html += '<div class="fg-branch exa" id="fgn-exa">';
  html += '<div class="fg-branch-hdr"><span>' + exaLabel + '</span><span style="font-size:9px;color:var(--dim)">' + exaComps.length + ' tools</span></div>';
  html += '<div class="fg-branch-body">';
  if (exaComps.length === 0) {
    html += '<div style="color:var(--dim2);font-size:10px;padding:6px 0">No results — Exa key required</div>';
  }
  exaComps.forEach(comp => {
    const dom = comp.domain || comp.url.replace(/https?:\/\//,'').split('/')[0];
    html += '<div class="fg-mini-card" style="border-color:#332200">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center">';
    html += '<div class="fg-mini-name">' + e((comp.title||dom).substring(0,28)) + '</div>';
    html += '<a href="' + e(comp.url||'#') + '" target="_blank" style="font-size:9px;color:#dd8833;text-decoration:none;flex-shrink:0">→</a>';
    html += '</div>';
    if (comp.snippet) html += '<div class="fg-mini-meta">' + e(comp.snippet.substring(0,55)) + '…</div>';
    html += '</div>';
  });
  // ZeroClick ad inline — naturally placed in competitive analysis
  if (ad) {
    html += '<div style="border:1px dashed #1a3a1a;border-radius:3px;padding:5px 7px;margin-top:6px;background:#030a03">';
    html += '<div style="font-size:8px;color:var(--green);margin-bottom:2px">◉ ZeroClick — related tool</div>';
    html += '<a href="' + e(ad.click_url||'#') + '" target="_blank" style="font-size:10px;color:#ccc;text-decoration:none;font-weight:500" data-offer-id="' + e(ad.id||'') + '">' + e((ad.title||ad.sponsor||'').substring(0,40)) + ' →</a>';
    if (ad.message) html += '<div class="fg-mini-meta">' + e(ad.message.substring(0,50)) + '</div>';
    html += '</div>';
  }
  html += '</div></div>';

  // Apify Store branch
  html += '<div class="fg-branch api" id="fgn-apify">';
  html += '<div class="fg-branch-hdr"><span>Apify Store</span><span style="font-size:9px;color:var(--dim)">' + apify.length + ' actors</span></div>';
  html += '<div class="fg-branch-body">';
  if (apify.length === 0) {
    html += '<div style="color:var(--dim2);font-size:10px;padding:6px 0">No actors found</div>';
  }
  apify.slice(0,4).forEach(a => {
    const url = a.url || a.apify_url || '';
    html += '<div class="fg-mini-card" style="border-color:#221133">';
    html += '<div style="display:flex;justify-content:space-between;align-items:center">';
    html += '<div class="fg-mini-name">' + e((a.name||'').replace('Apify: ','').substring(0,22)) + '</div>';
    if (url) html += '<a href="' + e(url) + '" target="_blank" style="font-size:9px;color:#8844cc;text-decoration:none;flex-shrink:0">→</a>';
    html += '</div>';
    if (a.runs) html += '<div class="fg-mini-meta">' + Number(a.runs).toLocaleString() + ' runs</div>';
    else if (a.description) html += '<div class="fg-mini-meta">' + e((a.description||'').substring(0,45)) + '</div>';
    html += '</div>';
  });
  html += '</div></div>';

  html += '</div></div>'; // branches + discover wrapper

  // ── AUDIT ─────────────────────────────────────────────────────────────────────
  if (scored.length > 0) {
    html += '<div class="fg-stage" id="fgn-audit" style="margin-top:44px">';
    html += '<div class="fg-stage-lbl"><span class="fg-step-n">02</span> Audit — real HTTP probes · OpenAI scoring · weighted formula</div>';
    html += '<div class="fg-stage-body">';
    // Score formula legend
    html += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;font-size:9px;color:var(--dim)">';
    html += '<span style="color:#ccc;font-weight:500">Score formula:</span>';
    html += '<span>Quality <span style="color:#dd8833">40%</span></span>';
    html += '<span>Consistency <span style="color:#dd8833">25%</span></span>';
    html += '<span>Latency <span style="color:#dd8833">20%</span></span>';
    html += '<span>Price <span style="color:#dd8833">15%</span></span>';
    html += '</div>';
    html += '<div class="fg-audit-chips">';
    const sortedScored = scored.slice().sort((a,b) => (b.overall_score||0) - (a.overall_score||0));
    sortedScored.forEach(s => {
      const sc  = s.overall_score || 0;
      const cls = sc >= 0.65 ? 'buy' : sc >= 0.45 ? 'watch' : 'avoid';
      const col = sc >= 0.65 ? 'var(--green)' : sc >= 0.45 ? 'var(--orange)' : 'var(--red)';
      // Component scores
      const q  = s.quality_score != null ? s.quality_score : null;
      const cs = s.consistency_score != null ? s.consistency_score : null;
      const ls = s.latency_score != null ? s.latency_score : null;
      const ps = s.price_score != null ? s.price_score : null;
      const lat = s.avg_latency_ms ? Math.round(s.avg_latency_ms) + 'ms' : null;
      const qEst = (q === 0.5); // estimated quality flag
      // Bar width helper (percent of chip width)
      function bar(v, c) {
        const w = Math.round((v||0)*100);
        return '<div style="height:3px;background:#1a1a1a;border-radius:2px;margin-top:2px"><div style="width:'+w+'%;height:3px;background:'+c+';border-radius:2px"></div></div>';
      }
      html += '<div class="fg-chip ' + cls + '" style="min-width:150px">';
      html += '<div class="fg-chip-team">' + e((s.team||'').substring(0,20)) + '</div>';
      html += '<div style="display:flex;align-items:baseline;gap:6px;margin:4px 0">';
      html += '<div class="fg-chip-score" style="color:' + col + ';font-size:28px">' + sc.toFixed(2) + '</div>';
      html += '<div style="font-size:8px;color:' + col + ';text-transform:uppercase;letter-spacing:0.07em;font-weight:500">' + e(s.roi_decision||cls.toUpperCase()) + '</div>';
      html += '</div>';
      // Component breakdown rows
      if (q != null) {
        html += '<div style="font-size:9px;color:var(--dim);display:flex;justify-content:space-between"><span>Quality' + (qEst?' <span style="color:var(--dim2)">est.</span>':'') + '</span><span style="color:#ccc">' + q.toFixed(2) + '</span></div>';
        html += bar(q, '#4488cc');
      }
      if (cs != null) {
        html += '<div style="font-size:9px;color:var(--dim);display:flex;justify-content:space-between"><span>Consistency</span><span style="color:#ccc">' + cs.toFixed(2) + '</span></div>';
        html += bar(cs, '#8844cc');
      }
      if (ls != null) {
        html += '<div style="font-size:9px;color:var(--dim);display:flex;justify-content:space-between"><span>Latency' + (lat?' <span style="color:var(--dim2)">'+lat+'</span>':'') + '</span><span style="color:#ccc">' + ls.toFixed(2) + '</span></div>';
        html += bar(ls, '#44aa66');
      }
      if (ps != null) {
        html += '<div style="font-size:9px;color:var(--dim);display:flex;justify-content:space-between"><span>Price value</span><span style="color:#ccc">' + ps.toFixed(2) + '</span></div>';
        html += bar(ps, '#cc8833');
      }
      html += '</div>';
    });
    html += '</div>';
    html += '<div style="font-size:9px;color:var(--dim2);margin-top:10px">Quality <i>est.</i> = endpoint requires payment, tested availability only. Sorted best → worst.</div>';
    html += '</div></div>';
  }

  // ── PURCHASE ──────────────────────────────────────────────────────────────────
  if (purchases.length > 0) {
    html += '<div class="fg-stage green" id="fgn-purchase" style="margin-top:44px">';
    html += '<div class="fg-stage-lbl"><span class="fg-step-n" style="background:#0d2a0d;color:var(--green)">03</span> Purchase — Nevermined order_plan() · ' + purchases.length + ' blockchain tx</div>';
    html += '<div class="fg-stage-body">';
    purchases.forEach(p => {
      const tx    = (p.tx_hash||'').substring(0,20);
      const badge = p.repeat_purchase ? 'background:#2a2a00;color:var(--orange)' : 'background:#0d2a0d;color:var(--green)';
      const paid  = p.plan_price || (p.price_per_credit ? p.price_per_credit + ' cr/req' : null);
      html += '<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid #0a1a0a">';
      html += '<div style="color:var(--green);font-size:16px;flex-shrink:0;line-height:1.2;margin-top:1px">✓</div>';
      html += '<div style="flex:1">';
      html += '<div style="font-weight:500;font-size:13px">' + e(p.team||'') + '<span style="font-size:8px;padding:2px 5px;border-radius:2px;margin-left:6px;' + badge + '">' + (p.repeat_purchase?'REPEAT':'NEW') + '</span></div>';
      html += '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:9px;color:var(--dim);margin-top:3px">';
      html += '<span>' + e(p.roi_decision||'BUY') + '</span>';
      if (p.audit_score) html += '<span>score <span style="color:#ccc">' + (p.audit_score||0).toFixed(2) + '</span></span>';
      if (paid) html += '<span>paid <span style="color:var(--green)">' + e(paid) + '</span></span>';
      if (p.credits_purchased) html += '<span><span style="color:#ccc">' + p.credits_purchased + '</span> credits acquired</span>';
      html += '</div>';
      html += '</div>';
      if (tx) html += '<div style="font-family:monospace;font-size:9px;color:var(--dim2);flex-shrink:0;margin-top:3px">' + e(tx) + '…</div>';
      html += '</div>';
    });
    html += '<div style="font-size:9px;color:var(--dim2);margin-top:8px">Each tx = real Nevermined order_plan() on Base Sepolia. See agents running in the Business tab →</div>';
    html += '</div></div>';
  } else if (scored.length > 0) {
    html += '<div style="margin-top:44px;border:1px dashed var(--border);border-radius:6px;padding:12px 14px;text-align:center;color:var(--dim2);font-size:10px" id="fgn-purchase">No purchases yet — all scored agents failed payment or had insufficient budget.</div>';
  }

  html += '</div>'; // fg-wrap
  canvas.innerHTML = html;

  // Track ZeroClick click
  canvas.querySelectorAll('[data-offer-id]').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.dataset.offerId;
      if (id) fetch(S+'/zeroclick/click?offer_id='+encodeURIComponent(id),{method:'POST'}).catch(()=>{});
    });
  });
  requestAnimationFrame(() => _drawFlowLines(canvas));
}

function _drawFlowLines(canvas) {
  const old = canvas.querySelector('.fg-svg');
  if (old) old.remove();

  const cr = canvas.getBoundingClientRect();
  const h  = canvas.scrollHeight + 20;

  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class','fg-svg');
  svg.setAttribute('style','position:absolute;top:0;left:0;width:100%;height:'+h+'px;pointer-events:none;overflow:visible');

  function nr(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const st = canvas.scrollTop || 0;
    return {
      cx: r.left - cr.left + r.width/2,
      cy_top: r.top - cr.top + st,
      cy_bot: r.bottom - cr.top + st,
    };
  }

  function line(x1,y1,x2,y2,col,w) {
    const my = (y1+y2)/2;
    const p = document.createElementNS('http://www.w3.org/2000/svg','path');
    p.setAttribute('d','M'+x1+','+y1+' C'+x1+','+(y1+(my-y1)*0.75)+' '+x2+','+(y2-(my-y1)*0.75)+' '+x2+','+y2);
    p.setAttribute('stroke',col||'#2a2a2a');
    p.setAttribute('stroke-width',w||'1');
    p.setAttribute('fill','none');
    p.setAttribute('opacity','0.7');
    svg.appendChild(p);
  }

  const goal   = nr('fgn-goal');
  const mindra = nr('fgn-mindra');
  const disc   = nr('fgn-discover');
  const mkt    = nr('fgn-mkt');
  const exaN   = nr('fgn-exa');
  const api    = nr('fgn-apify');
  const audit  = nr('fgn-audit');
  const purch  = nr('fgn-purchase');

  // Goal → Mindra (if present)
  if (goal && mindra) line(goal.cx, goal.cy_bot, mindra.cx, mindra.cy_top, '#1a3044', 1.5);

  // Mindra → Discover columns (or Goal → Discover if no Mindra)
  const fanSrc = mindra || goal;
  if (fanSrc && mkt)   line(fanSrc.cx, fanSrc.cy_bot, mkt.cx,   mkt.cy_top,   '#553300', 1.5);
  if (fanSrc && exaN)  line(fanSrc.cx, fanSrc.cy_bot, exaN.cx,  exaN.cy_top,  '#553300', 1.5);
  if (fanSrc && api)   line(fanSrc.cx, fanSrc.cy_bot, api.cx,   api.cy_top,   '#553300', 1.5);

  // 3 columns → Audit (fan in)
  if (audit) {
    if (mkt)  line(mkt.cx,  mkt.cy_bot,  audit.cx, audit.cy_top, '#2a2a2a', 1);
    if (exaN) line(exaN.cx, exaN.cy_bot, audit.cx, audit.cy_top, '#2a2a2a', 1);
    if (api)  line(api.cx,  api.cy_bot,  audit.cx, audit.cy_top, '#2a2a2a', 1);
  } else if (purch && disc) {
    // If no audit, connect discover directly to purchase
    if (mkt)  line(mkt.cx,  mkt.cy_bot,  purch.cx, purch.cy_top, '#1a4a1a', 1);
    if (exaN) line(exaN.cx, exaN.cy_bot, purch.cx, purch.cy_top, '#1a4a1a', 1);
    if (api)  line(api.cx,  api.cy_bot,  purch.cx, purch.cy_top, '#1a4a1a', 1);
  }

  // Audit → Purchase
  if (audit && purch) line(audit.cx, audit.cy_bot, purch.cx, purch.cy_top, '#1a4a1a', 1.5);

  canvas.style.position = 'relative';
  canvas.insertBefore(svg, canvas.firstChild);
}

// ── Business Dashboard ────────────────────────────────────────────────────────
function renderBizDashboard(data) {
  const canvas = document.getElementById('biz-canvas');
  if (!data) {
    canvas.innerHTML = '<div style="color:var(--dim2);padding:60px 0;text-align:center;font-size:12px">Run a strategy in Chat first.<br><br><span style="font-size:10px">Try: "build a marketing agency"</span></div>';
    return;
  }
  const goal      = data.goal || '';
  const purchases = (data.purchases || []).filter(p => p.purchased);
  const realOuts  = (data.business_outputs || []).filter(b => b.status === 'ok' && (b.content||'').length > 20);
  const execSynth = data.execution_synthesis || '';
  const trinity   = data.trinity_plan || [];
  const trinityAgents = data.trinity_agents || [];
  const tmplColors = {cornelius:'#334499',ruby:'#993344',outbound:'#449933',webmaster:'#996633'};

  let html = '';

  // ── HEADER ──────────────────────────────────────────────────────────────────
  html += '<div style="border-bottom:1px solid var(--border);padding-bottom:12px;margin-bottom:18px">';
  html += '<div style="font-size:16px;font-weight:500;margin-bottom:4px">' + e(goal) + '</div>';
  html += '<div style="display:flex;gap:14px;font-size:9px;color:var(--dim);flex-wrap:wrap;text-transform:uppercase;letter-spacing:0.06em">';
  if (purchases.length) html += '<span style="color:var(--green)">✓ ' + purchases.length + ' purchased</span>';
  if (realOuts.length)  html += '<span style="color:var(--green);display:flex;align-items:center;gap:4px"><span class="dot-pulse"></span>' + realOuts.length + ' live response' + (realOuts.length>1?'s':'') + '</span>';
  else if (!purchases.length) html += '<span style="color:var(--dim2)">no agents yet — run a strategy in Chat</span>';
  html += '</div></div>';

  // ── PURCHASED AGENT CARDS ────────────────────────────────────────────────────
  if (purchases.length > 0) {
    // Build a lookup of ALL business_outputs by team (including failed attempts)
    const allOutputs = data.business_outputs || [];
    const outputByTeam = {};
    allOutputs.forEach(o => { if (o.team) outputByTeam[o.team] = o; });

    const anyLive = purchases.some(p => {
      const o = outputByTeam[p.team];
      return o && o.status === 'ok' && (o.content||'').length > 10;
    });
    const hdrColor = anyLive ? 'var(--green)' : 'var(--dim)';
    html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:' + hdrColor + ';margin-bottom:10px">Purchased agents — ' + purchases.length + ' acquired</div>';
    html += '<div class="biz-grid">';
    purchases.forEach((p, idx) => {
      const tx      = (p.tx_hash||'').substring(0,18);
      const out     = outputByTeam[p.team] || null;
      const hasLive = out && out.status === 'ok' && (out.content||'').length > 10;
      const hasFail = out && out.status !== 'ok';
      const isTrinity = (p.endpoint||'').includes('abilityai.dev');
      const tri     = trinity[idx] || {};
      const tplKey  = (tri.template||'').toLowerCase();
      const accentCol = hasLive ? (isTrinity ? 'var(--green)' : '#4488cc') : (tmplColors[tplKey] || '#334455');

      html += '<div class="biz-agent-card ' + (tplKey||'') + '" style="border-color:' + (hasLive ? '#1a4a1a' : '#1a1a2a') + '">';
      html += '<div style="height:2px;background:' + accentCol + ';border-radius:2px 2px 0 0;margin:-16px -16px 12px -16px"></div>';

      // Header
      html += '<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">';
      html += '<div>';
      html += '<div class="biz-agent-name">' + (isTrinity ? '▲ ' : '') + e(p.team||'') + '</div>';
      const epHost = (p.endpoint||'').replace('https://','').replace('http://','').split('/')[0];
      html += '<div class="biz-agent-role">' + (isTrinity ? 'TrinityOS · ' : '') + e(epHost.substring(0,28)) + '</div>';
      html += '</div>';
      const badge = p.repeat_purchase ? 'background:#2a2a00;color:var(--orange)' : 'background:#0d2a0d;color:var(--green)';
      html += '<span style="font-size:8px;padding:2px 6px;border-radius:2px;' + badge + '">' + (p.repeat_purchase?'REPEAT':'NEW') + '</span>';
      html += '</div>';

      // Output area — honest status, no fake spinners
      if (hasLive) {
        html += '<div style="font-size:9px;color:var(--green);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;display:flex;align-items:center;gap:4px"><span class="dot-pulse"></span>' + (isTrinity ? 'TrinityOS response' : 'Live response') + '</div>';
        html += '<div class="biz-agent-output">' + e((out.content||'').substring(0,500)).replace(/\\n/g,'<br>') + '</div>';
      } else if (hasFail) {
        // Show the real error — no fake spinner
        const errSt = (out.status||'');
        let errMsg = '';
        if (errSt.includes('402'))      errMsg = 'Endpoint returned 402 — needs fresh access token. Use "Run →" to re-try.';
        else if (errSt.includes('403')) errMsg = 'Payment token rejected (403) — scheme mismatch or facilitator error. Use "Run →" to retry.';
        else if (errSt.includes('500') || errSt.includes('502')) errMsg = 'Endpoint returned ' + errSt.replace('http_','') + ' — agent server may be temporarily down.';
        else if (errSt.includes('404')) errMsg = 'Endpoint 404 — this agent may have changed URLs.';
        else if (errSt === 'no_token')  errMsg = 'Could not obtain access token — check NVM_BUYER_API_KEY.';
        else if (errSt === 'skip')      errMsg = 'Not called — endpoint or plan_id missing.';
        else                            errMsg = 'Call failed: ' + errSt;
        html += '<div style="font-size:9px;color:var(--orange);margin-bottom:6px">' + e(errMsg) + '</div>';
        html += '<div style="font-size:9px;color:var(--dim2)">Use "Run →" below to query this agent directly.</div>';
      } else {
        // No call was attempted yet
        html += '<div style="font-size:9px;color:var(--dim2);margin-bottom:6px">Agent purchased — no auto-call attempted yet.</div>';
        html += '<div style="font-size:9px;color:var(--dim2)">Use "Run →" below to query it directly.</div>';
      }

      // NVM transaction line
      if (tx) {
        html += '<div style="font-size:9px;color:var(--dim2);margin-top:8px;display:flex;gap:8px;align-items:center;border-top:1px solid var(--border);padding-top:6px">';
        html += '<span style="color:var(--green)">✓ NVM tx</span>';
        html += '<span style="font-family:monospace">' + e(tx) + '…</span>';
        if (p.audit_score) html += '<span style="margin-left:auto;color:var(--dim)">score ' + p.audit_score.toFixed(2) + '</span>';
        html += '</div>';
      }

      // Query input — primary interaction
      html += '<div style="margin-top:10px;display:flex;gap:6px">';
      html += '<input type="text" placeholder="Ask this agent anything..." data-agent-idx="' + idx + '"'
        + ' style="flex:1;background:#0a0a0a;border:1px solid var(--border);border-radius:3px;padding:6px 8px;font-size:10px;font-family:inherit;color:var(--fg);outline:none" />';
      html += '<button data-agent-run="' + idx + '" style="background:transparent;border:1px solid ' + (hasLive?'var(--green)':'#4488cc') + ';color:' + (hasLive?'var(--green)':'#4488cc') + ';padding:6px 12px;border-radius:3px;font-size:9px;font-family:inherit;cursor:pointer;white-space:nowrap;font-weight:500">Run →</button>';
      html += '</div>';
      html += '<div class="biz-agent-response" id="biz-resp-' + idx + '" style="display:none;margin-top:8px;font-size:10px;color:#ccc;line-height:1.7;border-left:2px solid ' + accentCol + ';padding-left:8px;white-space:pre-wrap"></div>';

      html += '</div>'; // biz-agent-card
    });
    html += '</div><div style="height:16px"></div>';
  }

  // ── TRINITYOS AGENTS (called separately from purchases) ────────────────────
  const triResponded = trinityAgents.filter(t => t.status === 'ok' && (t.content||'').length > 10);
  if (triResponded.length > 0) {
    html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:var(--green);margin-bottom:10px">▲ TrinityOS Agent Intelligence</div>';
    html += '<div class="biz-grid">';
    triResponded.forEach(t => {
      html += '<div class="biz-agent-card" style="border-color:#1a3a1a">';
      html += '<div style="height:2px;background:var(--green);border-radius:2px 2px 0 0;margin:-16px -16px 12px -16px"></div>';
      html += '<div class="biz-agent-name">▲ ' + e(t.agent||'') + '</div>';
      html += '<div class="biz-agent-role">TrinityOS · ' + e((t.endpoint||'').replace('https://','').split('/')[0].substring(0,28)) + '</div>';
      html += '<div style="font-size:9px;color:var(--green);text-transform:uppercase;letter-spacing:0.06em;margin:8px 0 5px;display:flex;align-items:center;gap:4px"><span class="dot-pulse"></span>Live from TrinityOS</div>';
      html += '<div class="biz-agent-output">' + e((t.content||'').substring(0,500)).replace(/\\n/g,'<br>') + '</div>';
      html += '</div>';
    });
    html += '</div><div style="height:16px"></div>';
  }

  // ── EXECUTION SYNTHESIS ──────────────────────────────────────────────────────
  if (execSynth) {
    html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.08em;color:var(--dim);margin-bottom:10px">Strategy — synthesized from all agents</div>';
    const synthLinesB = execSynth.split('\\n').filter(l => l.trim().length > 0);
    const acols2 = ['#334499','#993344','#449933','#996633'];
    const synthSecsB = [];
    let curSecB = [];
    synthLinesB.forEach(ln => {
      if (/^(###|\\*\\*[A-Z]|\\d\\.\\s)/.test(ln) && curSecB.length > 0) { synthSecsB.push(curSecB.join(' ')); curSecB = []; }
      curSecB.push(ln);
    });
    if (curSecB.length > 0) synthSecsB.push(curSecB.join(' '));
    if (synthSecsB.length > 1) {
      synthSecsB.slice(0,4).forEach((sec, i) => {
        const rawH = sec.replace(/^(###\\s+|\\*\\*)/,'').split(/[:(]/)[0].replace(/\\*\\*/g,'').trim().substring(0,35);
        const body = sec.replace(/^[^:]+:/,'').replace(/\\*\\*/g,'').trim();
        const c = acols2[i % acols2.length];
        const tri = trinity[i];
        html += '<div class="fg-synth-card" style="border-color:' + c + ';margin-bottom:8px">';
        html += '<div class="fg-synth-title" style="color:#ccc">';
        if (tri) html += '<span style="font-size:8px;color:' + c + ';text-transform:uppercase;letter-spacing:0.06em;margin-right:6px">' + e(tri.template||'') + '</span>';
        html += e(rawH||('Section '+(i+1))) + '<span class="dot-pulse" style="background:' + c + ';margin-left:8px"></span></div>';
        html += '<div class="fg-synth-body">' + e(body.substring(0,500)) + '</div>';
        html += '</div>';
      });
    } else {
      html += '<div class="fg-synth-card"><div class="fg-synth-body">' + e(execSynth.substring(0,800)) + '</div></div>';
    }
  }

  if (!purchases.length && !execSynth) {
    html += '<div style="color:var(--dim2);font-size:11px;padding:20px 0;line-height:1.8">No agents purchased yet.<br>Go to <b style="color:var(--fg)">Chat</b> and describe a business goal — e.g. <i style="color:var(--dim)">"I want to build a marketing agency"</i>.<br>The agent will find, audit, and buy services from the marketplace on your behalf.</div>';
  }

  canvas.innerHTML = html;

  // Wire up the "Run →" buttons for direct agent queries
  canvas.querySelectorAll('[data-agent-run]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const idx = parseInt(btn.dataset.agentRun);
      const inp = canvas.querySelector('[data-agent-idx="' + idx + '"]');
      const resp = document.getElementById('biz-resp-' + idx);
      const query = inp ? inp.value.trim() : '';
      const p = (data.purchases||[]).filter(pp=>pp.purchased)[idx];
      if (!query || !p) return;

      resp.style.display = 'block';
      resp.textContent = 'Querying ' + (p.team||'agent') + '...';
      btn.disabled = true;

      try {
        const r = await fetch(B + '/api/chat', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({message: 'Query agent "' + (p.team||'') + '" with endpoint ' + (p.endpoint||'') + ': ' + query}),
        });
        if (!r.ok) { resp.textContent = 'Error ' + r.status; btn.disabled = false; return; }
        if (!r.body) { resp.textContent = 'No response'; btn.disabled = false; return; }

        resp.textContent = '';
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        let buf = '', text = '';
        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          buf += dec.decode(value, {stream:true});
          const lines = buf.split('\\n'); buf = lines.pop();
          let ev = '';
          for (const ln of lines) {
            if (ln.startsWith('event: ')) ev = ln.slice(7).trim();
            else if (ln.startsWith('data: ') && ev === 'token') {
              try { text += JSON.parse(ln.slice(6)).text||''; } catch(err){}
              resp.textContent = text;
            }
          }
        }
        if (!text) resp.textContent = 'No text response.';
      } catch(err) {
        resp.textContent = 'Error: ' + err.message;
      }
      btn.disabled = false;
    });
  });
}

function sendFromBiz(text) {
  showView('chat');
  const inp = document.getElementById('chat-input');
  if (inp) { inp.value = text; document.getElementById('send-btn').click(); }
}

// ── Trinity Agent Detail Panel ────────────────────────────────────────────────
function openTrinityPanel(idx) {
  const fleet = window._trinityFleet;
  if (!fleet) return;
  const ag = fleet.agents[idx];
  if (!ag) return;
  const col = {cornelius:'#334499', ruby:'#993344', outbound:'#449933', webmaster:'#996633'}[(ag.template||'').toLowerCase()] || '#444466';
  const apify = fleet.apify || [];

  let html = '';
  html += '<div style="margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid var(--border)">';
  html += '<div style="font-size:9px;letter-spacing:0.07em;text-transform:uppercase;color:' + col + ';margin-bottom:4px">' + e(ag.template||'agent') + ' · AbilityAI Trinity</div>';
  html += '<div style="font-size:18px;font-weight:500;margin-bottom:3px">' + e(ag.name||'') + '</div>';
  html += '<div style="color:var(--dim);font-size:12px">' + e(ag.role||'') + '</div>';
  html += '</div>';

  html += '<div style="font-size:10px;color:var(--dim);line-height:1.6;margin-bottom:8px">' + e(ag.task||'') + '</div>';
  if (ag.output_preview) {
    html += '<div style="border-left:2px solid #1a4a1a;padding:5px 10px;margin-bottom:12px;font-size:10px;color:#3a7a3a;font-style:italic">';
    html += e(ag.output_preview);
    html += '</div>';
  }

  // Goal context
  html += '<div style="border:1px solid var(--border);border-radius:4px;padding:8px 10px;margin-bottom:16px;font-size:10px">';
  html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.07em;color:var(--dim);margin-bottom:4px">Context</div>';
  html += '<div style="color:var(--dim2)">Goal: ' + e(fleet.goal||'') + '</div>';
  html += '</div>';

  // Playbook suggestions
  html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.07em;color:var(--dim);margin-bottom:8px">Suggested Playbooks</div>';
  const playbooks = {
    cornelius: ['Market research report', 'Competitor analysis', 'Industry trend analysis', 'Due diligence report'],
    ruby:      ['Blog post creation', 'Social media calendar', 'Email sequence', 'Product description copy'],
    outbound:  ['Lead generation', 'Cold outreach sequence', 'Sales pitch script', 'Follow-up automation'],
    webmaster: ['Landing page audit', 'SEO analysis', 'Site performance report', 'Content gap analysis'],
  };
  const pbs = playbooks[(ag.template||'').toLowerCase()] || ['Custom task execution', 'Data analysis', 'Report generation'];
  html += '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:16px">';
  pbs.forEach(pb => {
    html += '<span style="border:1px solid var(--border);border-radius:3px;padding:3px 8px;font-size:10px;color:var(--dim)">' + e(pb) + '</span>';
  });
  html += '</div>';

  // Related Apify actors
  if (apify.length > 0) {
    html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.07em;color:var(--dim);margin-bottom:8px">Related Automation Actors (Apify)</div>';
    apify.slice(0,4).forEach(a => {
      const url = a.url || a.apify_url || '';
      html += '<div style="border:1px solid #221133;border-radius:4px;padding:8px 10px;margin-bottom:6px;background:#040309">';
      html += '<div style="display:flex;justify-content:space-between;align-items:baseline">';
      html += '<div style="font-weight:500;font-size:11px">' + e((a.name||'Actor').substring(0,35)) + '</div>';
      if (url) html += '<a href="' + e(url) + '" target="_blank" style="font-size:9px;color:#8855ff;text-decoration:none">Open Apify →</a>';
      html += '</div>';
      html += '<div style="font-size:9px;color:var(--dim2);margin-top:2px">' + e((a.description||'').substring(0,80)) + '</div>';
      html += '</div>';
    });
  }

  // Deploy with Trinity
  html += '<div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">';
  html += '<div style="font-size:9px;text-transform:uppercase;letter-spacing:0.07em;color:var(--dim);margin-bottom:8px">Deploy with Trinity</div>';
  html += '<a href="https://us14.abilityai.dev" target="_blank" style="display:block;text-align:center;border:1px solid ' + col + ';border-radius:4px;padding:8px;font-size:11px;color:' + col + ';text-decoration:none">Launch ' + e(ag.name||ag.template||'Agent') + ' in Trinity →</a>';
  html += '</div>';

  (document.getElementById('trinity-panel-content')||{}).innerHTML = html;
  document.getElementById('trinity-panel').classList.add('open');
  document.getElementById('trinity-overlay').style.display = 'block';
}

function closeTrinityPanel() {
  document.getElementById('trinity-panel').classList.remove('open');
  document.getElementById('trinity-overlay').style.display = 'none';
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

  // Mindra GTM agents
  const mindraAgents = data.mindra_agents || {};
  const mindraIdMap = {web_search:'mindra-web', linkedin:'mindra-linkedin', google:'mindra-google', github:'mindra-github', content:'mindra-content'};
  let mindraOk = 0;
  if (Object.keys(mindraAgents).length > 0) {
    Object.entries(mindraIdMap).forEach(([mid, sseId]) => {
      const ma = mindraAgents[mid] || {};
      const ok = ma.status === 'completed' && (ma.answer||'').length > 0;
      if (ok) mindraOk++;
      const msg = ok ? (ma.tool_count||0)+' tools — '+(ma.answer||'').length+' chars'
                  : ma.status === 'error' ? ((ma.answer||'error').substring(0,20)||'failed')
                  : (ma.status||'unknown');
      orchSetAgent(sseId, ok ? 'done' : 'failed', msg);
    });
  } else if (data.orchestrator === 'mindra' || data.mindra_status) {
    Object.values(mindraIdMap).forEach(sseId => {
      orchSetAgent(sseId, 'failed', data.mindra_status || 'no result');
    });
  }
  window._mindraSucceeded = mindraOk;
  const mse = document.getElementById('mindra-succeeded');
  if (mse) mse.textContent = mindraOk + '/5';

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

const ORCH_IDS = {'mindra-web':'orch-mindra-web', 'mindra-linkedin':'orch-mindra-linkedin', 'mindra-google':'orch-mindra-google', 'mindra-github':'orch-mindra-github', 'mindra-content':'orch-mindra-content', exa:'orch-exa', apify:'orch-apify', openai:'orch-openai', nevermined:'orch-nevermined', trinity:'orch-trinity', social:'orch-social'};

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
  ['mindra-web','mindra-linkedin','mindra-google','mindra-github','mindra-content','exa','apify','openai','nevermined','trinity','social'].forEach(id => {
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
  const stepLabels = {mindra_parallel_agents:'Mindra GTM x5',exa_research:'Exa research',marketplace_search:'Marketplace search',audit_candidates:'Candidate audit',purchase_services:'Nevermined purchase'};
  const steps = data.steps || [];
  if (steps.length) {
    html += '<div style="display:flex;gap:4px;margin:8px 0;flex-wrap:wrap">';
    steps.forEach((s,i) => {
      html += '<span style="font-size:9px;background:var(--border);padding:2px 6px;border-radius:2px;color:var(--dim)">' + (stepLabels[s]||s) + (i<steps.length-1?' →':'') + '</span>';
    });
    html += '</div>';
  }

  // Mindra GTM agent results
  const mindraAgents = data.mindra_agents || {};
  const mindraKeys = Object.keys(mindraAgents);
  if (mindraKeys.length) {
    const mSucc = mindraKeys.filter(k => mindraAgents[k].status === 'completed').length;
    html += '<div style="margin:6px 0;font-size:10px;border:1px solid #1a2a3a;border-radius:4px;padding:8px 10px;background:#020a14">';
    html += '<div style="color:#6ecbf5;font-size:9px;letter-spacing:0.08em;margin-bottom:6px">MINDRA GTM AGENTS — ' + mSucc + '/' + mindraKeys.length + ' succeeded</div>';
    mindraKeys.forEach(k => {
      const a = mindraAgents[k];
      const ok = a.status === 'completed' && a.answer;
      const clr = ok ? '#6ecbf5' : 'var(--red)';
      html += '<div style="margin-top:4px;border-left:2px solid '+clr+';padding-left:8px">';
      html += '<div style="display:flex;justify-content:space-between"><span style="color:var(--dim)">' + escHtml(a.name||k) + '</span><span style="color:'+clr+';font-size:9px">' + (ok?'done':''+a.status) + '</span></div>';
      if (ok) html += '<div style="font-size:9px;color:var(--dim2);margin-top:2px;line-height:1.4">' + escHtml((a.answer||'').substring(0,150)) + '…</div>';
      html += '</div>';
    });
    html += '</div>';
  }
  // Mindra GTM synthesis
  if (data.mindra_gtm_synthesis) {
    html += '<div style="margin:6px 0;font-size:10px;color:var(--dim);border-left:2px solid #6ecbf5;padding-left:8px"><span style="color:#6ecbf5">Mindra GTM Strategy:</span><br>';
    html += escHtml(data.mindra_gtm_synthesis.substring(0,300)) + '…</div>';
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
  lastSentMessage = text;
  sending = true;
  btn.disabled = true;
  input.value = '';
  lastStreamAd = null;

  addMsg('user', escHtml(text));

  let assistantEl = null;
  let assistantText = '';
  let lastToolId = null;
  let lastStepEl = null;
  let auditCards = '';

  // Show a "thinking" placeholder while waiting for first token
  const thinkEl = addMsg('assistant', '<span style="color:var(--dim2);font-size:11px">thinking...</span>');

  try {
    const ctrl = new AbortController();
    // Strategy runs can take 60–90s; give 3 minutes before timing out
    const tOut = setTimeout(() => ctrl.abort(), 180000);

    const resp = await fetch(B + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
      signal: ctrl.signal,
    });

    clearTimeout(tOut);

    if (!resp.ok) {
      thinkEl.remove();
      assistantText = 'Server error ' + resp.status + '. Please try again.';
      throw new Error('http_' + resp.status);
    }
    if (!resp.body) {
      thinkEl.remove();
      assistantText = 'No response body from server.';
      throw new Error('no_body');
    }

    thinkEl.remove(); // Remove placeholder once stream starts

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
                window._mindraSucceeded = 0;
              } else if (d.agent) {
                orchSetAgent(d.agent, d.status || 'running', d.msg || d.status);
                if (d.agent && d.agent.startsWith('mindra-') && d.status === 'done') {
                  window._mindraSucceeded = (window._mindraSucceeded || 0) + 1;
                  const mse = document.getElementById('mindra-succeeded');
                  if (mse) mse.textContent = window._mindraSucceeded + '/5';
                }
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
              const ad = d.ad;
              if (ad && !adGateActive) {
                lastStreamAd = ad;
                showAdGate(ad, 'Click to continue chatting');
              }
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
                lastStrategyData = r;
                auditCards += renderStrategyCard(r);
                renderOrchestration(r);
                // Show "Business" tab button as active indicator after strategy completes
                const btnBiz = document.getElementById('btn-biz');
                if (btnBiz) {
                  btnBiz.style.borderColor = 'var(--green)';
                  btnBiz.style.color = 'var(--green)';
                  btnBiz.title = 'Business dashboard ready — click to see agents running';
                }
                // ZeroClick ad handled by the gate overlay
                if (r.zeroclick_ad && !adGateActive) {
                  showAdGate(r.zeroclick_ad, 'Click to continue chatting');
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
    if (thinkEl && thinkEl.parentNode) thinkEl.remove();
    const msg = (e && e.message) ? e.message : String(e);
    const retryBtn = '<div style="margin-top:8px"><button onclick="retryLastMessage()" style="font-family:inherit;font-size:10px;background:transparent;border:1px solid var(--border);color:var(--dim);padding:3px 10px;border-radius:3px;cursor:pointer">Retry</button></div>';
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('Load failed')) {
      assistantText = 'Network error — server may be restarting. Refresh the page or wait a moment, then retry.' + retryBtn;
    } else if (msg.includes('AbortError') || msg.includes('abort')) {
      assistantText = 'Request timed out. The strategy may have completed — check the Flow and Business tabs for results.' + retryBtn;
    } else if (msg.startsWith('http_')) {
      assistantText = 'Server returned ' + msg.slice(5) + '. Try again.' + retryBtn;
    } else {
      assistantText = 'Error: ' + msg + retryBtn;
    }
    console.error('[chat] stream error:', msg);
  }

  if (lastToolId) markToolDone(lastToolId);

  if (assistantText || auditCards) {
    const el = addMsg('assistant', formatMarkdown(assistantText) + auditCards);
  }

  sending = false;
  refreshStats();
  if (!adGateActive) {
    showAdGate(lastStreamAd, 'Click to continue chatting');
  }
  lastStreamAd = null;
}

input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!adGateActive) sendMessage(); } });
btn.addEventListener('click', () => { if (!adGateActive) sendMessage(); });

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
      (document.getElementById('nvm-balance')||{}).textContent = bal + ' cr ' + sub;
    }
  }

  setDot('dot-seller', !!s);
  (document.getElementById('st-seller')||{}).textContent = s ? 'seller' : 'seller offline';
  setDot('dot-buyer', !!b);
  (document.getElementById('st-buyer')||{}).textContent = b ? 'buyer' : 'buyer offline';

  // Sponsor tool indicators
  const tools = stats ? (stats.tools || {}) : {};
  const toolDotMap = {openai:'dot-openai', exa:'dot-exa', nevermined:'dot-nvm', zeroclick:'dot-zc', apify:'dot-apify', mindra:'dot-mindra'};
  const toolCountMap = {openai:'tool-openai-count', exa:'tool-exa-count', nevermined:'tool-nvm-count', apify:'tool-apify-count', mindra:'tool-mindra-count'};
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

  // Mindra sidebar stats
  const mindraInfo = tools['mindra'] || {};
  const mindraCallsEl = document.getElementById('mindra-calls');
  if (mindraCallsEl) mindraCallsEl.textContent = mindraInfo.calls || 0;
  const mindraStatusEl = document.getElementById('mindra-status');
  if (mindraStatusEl) {
    if (mindraInfo.status === 'active' || mindraInfo.calls > 0) {
      mindraStatusEl.textContent = 'active';
      mindraStatusEl.style.color = '#6ecbf5';
    } else {
      mindraStatusEl.textContent = 'ready';
    }
  }
  // Mindra per-agent succeeded count (updated from tool_step events in SSE handler)
  const mindraSuccEl = document.getElementById('mindra-succeeded');
  if (mindraSuccEl && window._mindraSucceeded !== undefined) {
    mindraSuccEl.textContent = window._mindraSucceeded + '/5';
  }

  // ZeroClick — data lives in /stats (seller analytics module)
  const zc = stats ? stats.zeroclick : null;
  if (zc) {
    (document.getElementById('zc-served')||{}).textContent = zc.ads_served || 0;
    (document.getElementById('zc-imp')||{}).textContent = zc.impressions || 0;
    (document.getElementById('zc-conv')||{}).textContent = zc.conversions || 0;
    const rate = zc.impressions > 0 ? ((zc.conversions / zc.impressions) * 100).toFixed(1) + '%' : '\\u2014';
    (document.getElementById('zc-rate')||{}).textContent = rate;
    (document.getElementById('zc-rev')||{}).textContent = (zc.revenue_driven || 0) + ' cr';
    const feed = (zc.recent || []).filter(e => e.type !== 'served').slice(0, 6);
    (document.getElementById('zc-feed')||{}).innerHTML = feed.length
      ? feed.map(e => {
          if (e.type === 'conversion') {
            return '<div><span style="color:var(--green)">✓ conv</span> <span style="color:var(--dim)">' + escHtml(e.sponsor || '') + '</span> <span style="color:var(--green)">+' + (e.credits||1) + 'cr</span></div>';
          }
          return '<div><span style="color:var(--orange)">◉ imp</span> <span style="color:var(--dim)">' + escHtml((e.sponsor||'').substring(0,20)) + '</span></div>';
        }).join('')
      : '<span style="color:var(--dim2)">no ads yet</span>';
  }

  if (s) {
    (document.getElementById('rev')||{}).textContent = s.total_revenue_credits || 0;
    (document.getElementById('a')||{}).textContent = s.total_audits || 0;
    (document.getElementById('c')||{}).textContent = s.total_compares || 0;
    (document.getElementById('m')||{}).textContent = s.total_monitors || 0;
    (document.getElementById('ub')||{}).textContent = s.unique_buyers || 0;

    const txs = (s.transactions || []).slice(0, 8);
    (document.getElementById('txs')||{}).innerHTML = txs.length
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
    (document.getElementById('ds')||{}).textContent = buyerData.total_spent_credits || (b && b.budget ? b.budget.daily_spent : 0) || 0;
    (document.getElementById('ts')||{}).textContent = buyerData.total_purchases || 0;

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
    (document.getElementById('rev')||{}).textContent = s.credits_earned || 0;
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
<!-- Trinity Agent Detail Panel -->
<div id="trinity-panel">
  <button id="trinity-panel-close" onclick="closeTrinityPanel()">close ×</button>
  <div id="trinity-panel-content"></div>
</div>
<div id="trinity-overlay" onclick="closeTrinityPanel()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:99"></div>
</body></html>
"""


@dashboard_app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML


def main():
    uvicorn.run(dashboard_app, host="0.0.0.0", port=9090)


if __name__ == "__main__":
    main()
