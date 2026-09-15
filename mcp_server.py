"""MCP server for Acme Approvals. Claude Code connects to this over stdio.

Every tool calls the running app's REST API on localhost, so whatever the agent
does shows up in the browser UI within two seconds. Run via .mcp.json, or:
    python mcp_server.py
"""
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

BASE = os.environ.get("ACME_URL", "http://127.0.0.1:8080")
HEADERS = {"X-Actor": "prospect-agent"}
if os.environ.get("ACME_API_KEY"):
    HEADERS["X-API-Key"] = os.environ["ACME_API_KEY"]

mcp = FastMCP("acme-approvals", instructions=(
    "Acme Approvals is an approval-workflow product. Use these tools to inspect "
    "and change workflows and requests. Amounts are USD."))


def call(method: str, path: str, **kw):
    r = httpx.request(method, BASE + path, headers=HEADERS, timeout=10, **kw)
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"{r.status_code}: {detail}")
    return r.json()


@mcp.tool()
def list_workflows() -> list:
    """List every approval workflow with its approver, threshold, notify setting and active state."""
    return call("GET", "/api/workflows")


@mcp.tool()
def create_workflow(name: str, approver: str, threshold: float = 1000, notify_requester: bool = True) -> dict:
    """Create a new approval workflow. threshold is the USD amount above which approval is required."""
    return call("POST", "/api/workflows", json={
        "name": name, "approver": approver, "threshold": threshold, "notify_requester": notify_requester})


@mcp.tool()
def set_threshold(workflow_id: int, threshold: float) -> dict:
    """Change the USD amount above which a workflow requires approval."""
    return call("PATCH", f"/api/workflows/{workflow_id}", json={"threshold": threshold})


@mcp.tool()
def set_approver(workflow_id: int, approver: str) -> dict:
    """Change who approves requests in a workflow."""
    return call("PATCH", f"/api/workflows/{workflow_id}", json={"approver": approver})


@mcp.tool()
def set_notify_requester(workflow_id: int, enabled: bool) -> dict:
    """Turn 'notify requester on decision' on or off for a workflow."""
    return call("PATCH", f"/api/workflows/{workflow_id}", json={"notify_requester": enabled})


@mcp.tool()
def set_workflow_active(workflow_id: int, active: bool) -> dict:
    """Pause (active=false) or resume (active=true) a workflow."""
    return call("PATCH", f"/api/workflows/{workflow_id}", json={"active": active})


@mcp.tool()
def list_requests(status: Optional[str] = None, workflow_id: Optional[int] = None) -> list:
    """List approval requests. status may be pending, approved or rejected."""
    params = {k: v for k, v in {"status": status, "workflow_id": workflow_id}.items() if v is not None}
    return call("GET", "/api/requests", params=params)


@mcp.tool()
def create_request(workflow_id: int, requester: str, description: str, amount: float) -> dict:
    """Submit a new request into a workflow."""
    return call("POST", "/api/requests", json={
        "workflow_id": workflow_id, "requester": requester, "description": description, "amount": amount})


@mcp.tool()
def decide_request(request_id: int, decision: str) -> dict:
    """Approve or reject a request. decision is 'approved' or 'rejected'."""
    return call("POST", f"/api/requests/{request_id}/decision", json={"status": decision})


@mcp.tool()
def recent_activity(limit: int = 10) -> list:
    """Show the most recent changes made in Acme Approvals and who made them."""
    return call("GET", "/api/activity", params={"limit": limit})


if __name__ == "__main__":
    mcp.run()
