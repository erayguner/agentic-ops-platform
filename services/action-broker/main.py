"""
Action Broker Cloud Run service.

Endpoints:
  POST /mcp/tools/list       — MCP Streamable HTTP: list available tools
  POST /mcp/tools/call       — MCP Streamable HTTP: invoke a tool
  POST /pubsub/approved      — Pub/Sub push: receive ActionApproval from Slack-notifier
  GET  /healthz              — liveness probe

Authentication:
  /mcp/*    — Google ID-token verification (caller must present a valid OIDC token)
  /pubsub/* — Pub/Sub push token (query param) OR signed request

Environment variables:
  LIVE_MODE           (default: false) — when false, executors raise NotImplementedError
  GCP_PROJECT_ID      — target project
  PUBSUB_PUSH_TOKEN   — shared secret on the push subscription URL
  OIDC_AUDIENCE       — expected `aud` of caller ID tokens (this service's URL).
                        REQUIRED in LIVE_MODE; tokens are rejected if it is unset.
  PORT                — injected by Cloud Run (default 8080)
"""

from __future__ import annotations

import base64
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from broker import Broker, BrokerError
from fastapi import FastAPI, HTTPException, Query, Request, Response
from idempotency import IdempotencyStore
from policy import PolicyEngine
from pydantic import ValidationError
from schemas import ActionApproval

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "ops-agents-dev")
PUBSUB_PUSH_TOKEN = os.environ.get("PUBSUB_PUSH_TOKEN", "")
# Expected audience of caller OIDC ID tokens (this Cloud Run service's URL).
# Without it, verify_oauth2_token skips the `aud` check and accepts ANY valid
# Google-signed token (confused-deputy / token-passthrough). Required in LIVE_MODE.
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")

_state: dict[str, Any] = {}

# ---------------------------------------------------------------------------
# MCP tool catalogue (Streamable HTTP — minimal)
# ---------------------------------------------------------------------------

_MCP_TOOLS = [
    {
        "name": "propose_action",
        "description": "Propose a governed action for policy evaluation and (if approved) execution.",
        "inputSchema": {
            "type": "object",
            "required": [
                "action_class",
                "target",
                "params",
                "requested_by",
                "correlation_id",
                "environment",
            ],
            "properties": {
                "action_class": {"type": "string"},
                "target": {"type": "object"},
                "params": {"type": "object"},
                "requested_by": {"type": "string"},
                "correlation_id": {"type": "string"},
                "environment": {"type": "string", "enum": ["dev", "prod"]},
            },
        },
    },
    {
        "name": "request_approval",
        "description": "Query the status of a pending approval request.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id"],
            "properties": {"action_id": {"type": "string"}},
        },
    },
    {
        "name": "execute",
        "description": "Directly execute a pre-approved action (for Tier-2 auto-approve bypass).",
        "inputSchema": {
            "type": "object",
            "required": ["action_id", "approval_token"],
            "properties": {
                "action_id": {"type": "string"},
                "approval_token": {"type": "string"},
            },
        },
    },
    {
        "name": "rollback",
        "description": "Roll back a previously executed action.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id"],
            "properties": {"action_id": {"type": "string"}},
        },
    },
    {
        "name": "status",
        "description": "Return the current status of an action by ID.",
        "inputSchema": {
            "type": "object",
            "required": ["action_id"],
            "properties": {"action_id": {"type": "string"}},
        },
    },
]


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    policy_engine = PolicyEngine.load()

    pubsub_client = None
    firestore_client = None
    if LIVE_MODE:
        from google.cloud import firestore, pubsub_v1  # type: ignore

        pubsub_client = pubsub_v1.PublisherClient()
        firestore_client = firestore.Client(project=GCP_PROJECT_ID)
        logger.info("Live Pub/Sub + Firestore clients initialised")
    else:
        logger.info("LIVE_MODE=false — stub Pub/Sub and Firestore; no real connections")

    idempotency_store = IdempotencyStore(firestore_client)
    broker = Broker(policy_engine, idempotency_store, pubsub_client)

    _state["broker"] = broker
    _state["pubsub"] = pubsub_client
    yield
    _state.clear()


app = FastAPI(title="aop-action-broker", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/healthz", status_code=200)
async def healthz() -> dict:
    return {"status": "ok", "live_mode": LIVE_MODE}


# ---------------------------------------------------------------------------
# ID-token verification helper
# ---------------------------------------------------------------------------


async def _verify_id_token(request: Request) -> str:
    """
    Verify the Google OIDC ID token in the Authorization header.
    Returns the email claim on success.  In dry-run mode skips verification.
    """
    if not LIVE_MODE:
        return "dry-run@local"
    if not OIDC_AUDIENCE:
        # Fail closed: a write-capable broker MUST bind tokens to its own audience.
        # Verifying without an audience accepts any valid Google-signed ID token.
        logger.error("OIDC_AUDIENCE is unset; refusing to verify tokens in LIVE_MODE")
        raise HTTPException(status_code=500, detail="Server misconfigured: OIDC_AUDIENCE unset")
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth_header.removeprefix("Bearer ")
    try:
        from google.auth.transport import requests as google_requests  # type: ignore
        from google.oauth2 import id_token as id_token_module  # type: ignore

        info = id_token_module.verify_oauth2_token(
            token, google_requests.Request(), audience=OIDC_AUDIENCE
        )
        return info.get("email", info.get("sub", "unknown"))
    except Exception as exc:
        logger.warning("ID token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid ID token") from exc


# ---------------------------------------------------------------------------
# MCP Streamable HTTP endpoints
# ---------------------------------------------------------------------------


@app.post("/mcp/tools/list")
async def mcp_tools_list(request: Request) -> dict:
    await _verify_id_token(request)
    return {"tools": _MCP_TOOLS}


@app.post("/mcp/tools/call")
async def mcp_tools_call(request: Request) -> dict:
    caller = await _verify_id_token(request)
    body = await request.json()
    tool_name: str = body.get("name", "")
    tool_input: dict = body.get("input", {})

    broker: Broker = _state["broker"]

    try:
        if tool_name == "propose_action":
            result = broker.propose_action(
                action_class=tool_input["action_class"],
                target=tool_input["target"],
                params=tool_input["params"],
                requested_by=tool_input.get("requested_by", caller),
                correlation_id=tool_input["correlation_id"],
                environment=tool_input["environment"],
            )
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        if tool_name == "request_approval":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"status": "not_implemented", "action_id": tool_input.get("action_id")}
                        ),
                    }
                ]
            }

        if tool_name in ("execute", "rollback", "status"):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"status": "not_implemented", "tool": tool_name}),
                    }
                ]
            }

    except BrokerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing input field: {exc}") from exc

    raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name!r}")


# ---------------------------------------------------------------------------
# Pub/Sub approved subscription handler
# ---------------------------------------------------------------------------


@app.post("/pubsub/approved", status_code=204)
async def pubsub_approved(
    request: Request,
    token: str = Query(default=""),
) -> Response:
    if PUBSUB_PUSH_TOKEN and token != PUBSUB_PUSH_TOKEN:
        logger.warning("Pub/Sub approved push: invalid token")
        raise HTTPException(status_code=401, detail="Invalid push token")

    body = await request.json()
    message = body.get("message", {})
    data_b64: str = message.get("data", "")

    try:
        raw = base64.b64decode(data_b64).decode()
        payload = json.loads(raw)
    except Exception as exc:
        logger.error("Failed to decode approved push: %s", exc)
        return Response(status_code=204)

    try:
        approval = ActionApproval(**payload)
    except ValidationError as exc:
        logger.error("ActionApproval validation failed: %s", exc)
        return Response(status_code=204)

    broker: Broker = _state["broker"]
    try:
        broker.on_approval(approval)
    except Exception as exc:
        logger.exception("on_approval failed: %s", exc)
        raise HTTPException(status_code=500, detail="Approval handling failed") from exc

    return Response(status_code=204)
