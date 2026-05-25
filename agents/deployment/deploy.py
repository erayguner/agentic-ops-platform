"""deployment/deploy.py — CLI skeleton for deploying AOP agents to Agent Engine.

Each agent is deployed as a google_vertex_ai_reasoning_engine ("Deployment")
on Vertex AI Agent Engine. This script wraps the deployment call shape.

Usage:
    python deployment/deploy.py --agent orchestrator --project ops-agents-prod \
        --region europe-west2 --env prod

This is a SKELETON — it prints the would-deploy statement and shows the
ADK deployment call shape without invoking it.

ADK 2.0 API — confirm vertexai.agent_engines.create() / .deploy() signature
against adk.dev/2.0/ release notes and the google-adk 2.0.x changelog.
"""

from __future__ import annotations

import argparse
import sys

# --------------------------------------------------------------------------- #
# Canonical agent → package mapping
# --------------------------------------------------------------------------- #

AGENT_REGISTRY: dict[str, dict[str, str]] = {
    "orchestrator": {
        "package": "aop_orchestrator",
        "builder": "aop_orchestrator.agent:build_orchestrator",
        "sa": "sa-orchestrator",
        "description": "Ops Orchestrator — duty-manager hub, workflow runtime",
    },
    "sre": {
        "package": "aop_sre",
        "builder": "aop_sre.agent:build_sre_agent",
        "sa": "sa-sre",
        "description": "SRE Agent — reliability, latency, SLO burn, regressions",
    },
    "devsecops": {
        "package": "aop_devsecops",
        "builder": "aop_devsecops.agent:build_devsecops_agent",
        "sa": "sa-devsecops",
        "description": "DevSecOps Agent — SCC findings, IAM drift, key exposure",
    },
    "platform": {
        "package": "aop_platform",
        "builder": "aop_platform.agent:build_platform_agent",
        "sa": "sa-platform",
        "description": "Platform Engineering Agent — drift, IaC state, hygiene",
    },
    "finops": {
        "package": "aop_finops",
        "builder": "aop_finops.agent:build_finops_agent",
        "sa": "sa-finops",
        "description": "FinOps Agent — cost anomalies, rightsizing, budget burn",
    },
}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy AOP agents to Vertex AI Agent Engine (skeleton CLI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--agent",
        choices=list(AGENT_REGISTRY),
        required=True,
        help="Agent to deploy.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Target GCP project id (e.g., ops-agents-prod).",
    )
    parser.add_argument(
        "--region",
        default="europe-west2",
        help="GCP region for Agent Engine deployment.",
    )
    parser.add_argument(
        "--env",
        choices=["dev", "prod"],
        default="dev",
        help="Deployment environment.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print would-deploy statement without invoking the API (default: True).",
    )
    return parser.parse_args(argv)


def _reasoning_engine_resource_name(project: str, region: str, agent: str) -> str:
    """Return the expected resource name for the ReasoningEngine."""
    return (
        f"projects/{project}/locations/{region}"
        f"/reasoningEngines/{agent}-agent"
    )


def deploy(args: argparse.Namespace) -> int:
    """Skeleton deploy entry point.

    Prints the would-deploy statement and shows the ADK 2.0 deployment
    call shape. Returns 0 on success.

    ADK 2.0 API — confirm vertexai.agent_engines.create() call shape
    against adk.dev/2.0/ release notes.
    """
    spec = AGENT_REGISTRY[args.agent]
    resource_name = _reasoning_engine_resource_name(args.project, args.region, args.agent)
    sa_email = f"{spec['sa']}@{args.project}.iam.gserviceaccount.com"

    print(f"[AOP Deploy] agent={args.agent!r} env={args.env!r}")
    print(f"  description : {spec['description']}")
    print(f"  builder     : {spec['builder']}")
    print(f"  service_acct: {sa_email}")
    print(f"  resource    : {resource_name}")
    print()

    if args.dry_run:
        print("[DRY RUN] Would execute:")
        print()
        print(
            f"    import vertexai\n"
            f"    from {spec['package']}.agent import {spec['builder'].split(':')[1]} as builder\n"
            f"    from aop_common.config import AopSettings\n"
            f"\n"
            f"    vertexai.init(project={args.project!r}, location={args.region!r})\n"
            f"    settings = AopSettings(\n"
            f"        project={args.project!r},\n"
            f"        region={args.region!r},\n"
            f"        environment={args.env!r},\n"
            f"        # ... remaining env vars from Secret Manager\n"
            f"    )\n"
            f"    agent_instance = builder(settings)\n"
            f"\n"
            f"    # ADK 2.0 API — confirm vertexai.agent_engines.create() signature\n"
            f"    # against adk.dev/2.0/ release notes\n"
            f"    remote_agent = vertexai.agent_engines.create(\n"
            f"        agent_engine=agent_instance,\n"
            f"        requirements=[\n"
            f"            'google-adk==2.0.*',\n"
            f"            'aop-agents @ file:///app',\n"
            f"        ],\n"
            f"        display_name={args.agent!r},\n"
            f"        description={spec['description']!r},\n"
            f"        # service_account={sa_email!r},\n"
            f"        # encryption_spec_key_name='<cmek-key>',  # prod only\n"
            f"    )\n"
            f"    print('Deployed:', remote_agent.resource_name)\n"
            f"    # Expected: {resource_name}\n"
        )
        return 0

    # Non-dry-run is also skeletal — raise until wired
    raise NotImplementedError(
        "Non-dry-run deployment is not implemented in this skeleton. "
        "Set --dry-run (default) or wire vertexai.agent_engines.create() call."
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    sys.exit(deploy(args))


if __name__ == "__main__":
    main()
