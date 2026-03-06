"""Mindra workflow orchestration client.

Wraps the Mindra REST API for triggering workflows, streaming SSE events,
and handling human-in-the-loop approvals.

API docs: https://docs.mindra.co/docs/api-reference
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

import httpx

from src.config import MINDRA_API_KEY, MINDRA_WORKFLOW_SLUG

logger = logging.getLogger("gtmagent.mindra")

MINDRA_BASE = "https://api.mindra.co"


@dataclass
class MindraEvent:
    """A single event from a Mindra workflow execution stream."""
    event_type: str  # chunk | tool_executing | tool_result | approval_request | done
    data: dict = field(default_factory=dict)


@dataclass
class MindraExecution:
    """Result of triggering a Mindra workflow."""
    execution_id: str
    status: str
    workflow_slug: str
    workflow_name: str
    stream_url: str
    created_at: str
    error: str = ""


def is_available() -> bool:
    return bool(MINDRA_API_KEY)


async def run_workflow(
    task: str,
    metadata: dict | None = None,
    workflow_slug: str = "",
) -> MindraExecution:
    """Trigger a Mindra workflow. Returns execution metadata with a stream URL."""
    slug = workflow_slug or MINDRA_WORKFLOW_SLUG
    url = f"{MINDRA_BASE}/v1/workflows/{slug}/run"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={
                "x-api-key": MINDRA_API_KEY,
                "Content-Type": "application/json",
            },
            json={"task": task, "metadata": metadata or {}},
        )

        if resp.status_code != 200:
            logger.error(f"[Mindra] run_workflow failed: {resp.status_code} {resp.text[:300]}")
            return MindraExecution(
                execution_id="",
                status="error",
                workflow_slug=slug,
                workflow_name="",
                stream_url="",
                created_at="",
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        data = resp.json()
        logger.info(f"[Mindra] Workflow started: {data.get('execution_id')}")
        return MindraExecution(
            execution_id=data.get("execution_id", ""),
            status=data.get("status", "running"),
            workflow_slug=data.get("workflow_slug", slug),
            workflow_name=data.get("workflow_name", ""),
            stream_url=data.get("stream_url", ""),
            created_at=data.get("created_at", ""),
        )


async def stream_events(execution_id: str) -> AsyncGenerator[MindraEvent, None]:
    """Connect to the SSE stream for a running execution and yield events."""
    url = f"{MINDRA_BASE}/api/v1/workflows/execute/{execution_id}/stream"

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async with client.stream(
            "GET", url, headers={"x-api-key": MINDRA_API_KEY}
        ) as resp:
            current_event = ""
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                    except (json.JSONDecodeError, ValueError):
                        data = {"raw": line[6:]}
                    yield MindraEvent(event_type=current_event or "unknown", data=data)
                    current_event = ""


async def approve(execution_id: str, approval_id: str, reason: str = "") -> bool:
    """Approve a pending tool execution."""
    url = f"{MINDRA_BASE}/v1/workflows/execute/{execution_id}/approve/{approval_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={"x-api-key": MINDRA_API_KEY, "Content-Type": "application/json"},
            json={"reason": reason or "Auto-approved by GTMAgent"},
        )
        ok = resp.status_code in (200, 204)
        if not ok:
            logger.warning(f"[Mindra] approve failed: {resp.status_code}")
        return ok


async def reject(execution_id: str, approval_id: str, reason: str = "") -> bool:
    """Reject a pending tool execution."""
    url = f"{MINDRA_BASE}/v1/workflows/execute/{execution_id}/reject/{approval_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={"x-api-key": MINDRA_API_KEY, "Content-Type": "application/json"},
            json={"reason": reason or "Rejected by GTMAgent budget policy"},
        )
        ok = resp.status_code in (200, 204)
        if not ok:
            logger.warning(f"[Mindra] reject failed: {resp.status_code}")
        return ok


MINDRA_GTM_AGENTS = {
    "web_search": {
        "name": "Web Search",
        "task_template": (
            "Research the market for: {goal}\n"
            "Find: competitors, market size, trends, pricing models, key players, recent funding rounds.\n"
            "Use web search to gather current data. Be specific and data-driven. "
            "Return structured findings with sources."
        ),
    },
    "linkedin": {
        "name": "LinkedIn",
        "task_template": (
            "Find LinkedIn intelligence for building: {goal}\n"
            "Search for: relevant connections in my network, industry leaders posting about this topic, "
            "potential partners or collaborators, companies hiring for similar roles, "
            "recent posts and articles about this market.\n"
            "Focus on actionable GTM contacts and partnership opportunities."
        ),
    },
    "google": {
        "name": "Google Workspace",
        "task_template": (
            "Search Google Workspace for context related to: {goal}\n"
            "Check emails, calendar events, documents, and sheets for any prior work, "
            "contacts, meetings, proposals, or research related to this business area.\n"
            "Summarize relevant findings that could accelerate go-to-market."
        ),
    },
    "github": {
        "name": "GitHub",
        "task_template": (
            "Find GitHub resources for building: {goal}\n"
            "Search for: relevant open-source tools, popular repositories, technical frameworks, "
            "API integrations, developer communities, and code examples.\n"
            "Focus on tools that could accelerate building this business. "
            "Include star counts and recent activity where available."
        ),
    },
    "content": {
        "name": "Content Creator",
        "task_template": (
            "Create go-to-market content for: {goal}\n"
            "Draft: (1) elevator pitch (2-3 sentences), "
            "(2) landing page headline + subheadline, "
            "(3) 3 LinkedIn post ideas with hooks, "
            "(4) key messaging pillars and value propositions.\n"
            "Make it compelling, specific, and ready to publish."
        ),
    },
}


async def run_parallel_tasks(
    goal: str,
    metadata: dict | None = None,
    timeout_seconds: float = 90.0,
) -> dict[str, dict]:
    """Run 5 focused Mindra agent tasks in parallel for comprehensive GTM intelligence.

    Each task targets a different connected agent (Web Search, LinkedIn, Google, GitHub,
    Content Creator) with a focused prompt derived from the user's business goal.
    Returns a dict keyed by agent_id with their individual results.
    """
    if not is_available():
        return {aid: {"status": "unavailable", "error": "Mindra API key not configured", "final_answer": ""}
                for aid in MINDRA_GTM_AGENTS}

    base_meta = metadata or {}
    coros = {}
    for agent_id, config in MINDRA_GTM_AGENTS.items():
        task_text = config["task_template"].format(goal=goal)
        coros[agent_id] = run_and_collect(
            task=task_text,
            metadata={**base_meta, "agent_focus": agent_id, "agent_name": config["name"], "goal": goal},
            auto_approve=True,
            timeout_seconds=timeout_seconds,
        )

    results = {}
    gathered = await asyncio.gather(*coros.values(), return_exceptions=True)
    for agent_id, result in zip(coros.keys(), gathered):
        if isinstance(result, Exception):
            logger.warning(f"[Mindra] Parallel task {agent_id} failed: {result}")
            results[agent_id] = {"status": "error", "error": str(result), "final_answer": ""}
        else:
            results[agent_id] = result

    succeeded = sum(1 for r in results.values() if r.get("status") == "completed")
    logger.info(f"[Mindra] Parallel tasks complete: {succeeded}/{len(results)} succeeded")
    return results


async def run_and_collect(
    task: str,
    metadata: dict | None = None,
    workflow_slug: str = "",
    auto_approve: bool = True,
    timeout_seconds: float = 120.0,
) -> dict:
    """Run a workflow and collect all events into a single result dict.

    Returns a dict with keys: execution_id, status, events, chunks (assembled text),
    tool_results, final_answer, approvals_handled, error.
    """
    result: dict = {
        "orchestrator": "mindra",
        "execution_id": "",
        "status": "pending",
        "events": [],
        "chunks": "",
        "tool_executions": [],
        "tool_results": [],
        "final_answer": "",
        "approvals_handled": 0,
        "error": "",
    }

    execution = await run_workflow(task, metadata, workflow_slug)
    if execution.error:
        result["status"] = "error"
        result["error"] = execution.error
        return result

    result["execution_id"] = execution.execution_id
    result["status"] = "running"
    result["workflow_name"] = execution.workflow_name

    try:
        async with asyncio.timeout(timeout_seconds):
            async for event in stream_events(execution.execution_id):
                result["events"].append({
                    "type": event.event_type,
                    "data": event.data,
                })

                if event.event_type == "chunk":
                    result["chunks"] += event.data.get("content", "")

                elif event.event_type == "tool_executing":
                    result["tool_executions"].append({
                        "tool": event.data.get("tool_name", ""),
                        "input": event.data.get("tool_input", {}),
                    })

                elif event.event_type == "tool_result":
                    result["tool_results"].append({
                        "tool": event.data.get("tool_name", ""),
                        "result": event.data.get("result", ""),
                    })

                elif event.event_type == "approval_request" and auto_approve:
                    aid = event.data.get("approval_id", "")
                    if aid:
                        await approve(execution.execution_id, aid)
                        result["approvals_handled"] += 1

                elif event.event_type == "done":
                    result["status"] = event.data.get("status", "completed")
                    result["final_answer"] = event.data.get("final_answer", "")
                    break

    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Workflow did not complete within {timeout_seconds}s"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    if not result["final_answer"] and result["chunks"]:
        result["final_answer"] = result["chunks"]

    return result
