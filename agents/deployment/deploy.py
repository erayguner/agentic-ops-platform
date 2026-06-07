"""deployment/deploy.py — deploy AOP agents to Vertex AI Agent Engine.

Each agent is deployed as a Vertex AI Agent Engine "Deployment" (reasoning
engine) via the Vertex AI SDK (`vertexai.agent_engines.create`). This wires the
deploy mechanism; it is **dry-run by default** and only calls the billable
Preview API when `--execute` is passed.

Usage:
    # Show the plan (no API calls, no cost):
    python deployment/deploy.py --agent orchestrator --project ops-agents-prod \
        --region us-central1 --env prod

    # Actually deploy (billable, Preview API):
    python deployment/deploy.py --agent orchestrator --project ops-agents-prod \
        --region us-central1 --env prod --execute \
        --staging-bucket gs://ops-agents-prod-agent-staging

PREREQUISITES (see docs/deployment/AGENT-DEPLOY.md):
  1. The agent builder must be implemented — `build_<agent>()` in
     aop_<agent>/agent.py currently raises NotImplementedError (skeleton ADK
     graph). Deploy fails fast until the WorkflowAgent graph is wired.
  2. **Region must support Agent Engine.** Agent Engine is region-limited and
     does NOT include europe-west2; use a supported region (e.g. us-central1 /
     europe-west1) — confirm against the Vertex AI generative-AI locations docs.
  3. A staging GCS bucket (`--staging-bucket`) is required by the SDK to upload
     the packaged agent.
  4. The per-agent service account (sa-<agent>) must exist (created by the
     Terraform agent module).

Alternative (Terraform path): pre-build each agent package and set
`google_vertex_ai_reasoning_engine.package_pickle_gcs_uri` on the
`terraform/modules/agents/_base` module instead of using this SDK path.

Confirm the `vertexai.agent_engines.create()` signature against the installed
google-cloud-aiplatform / google-adk 2.1.x version before first use.
"""

from __future__ import annotations

import argparse
import importlib
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

# Regions that do NOT support Agent Engine (non-exhaustive guard for the most
# likely mistake here — the platform's default europe-west2).
_AGENT_ENGINE_UNSUPPORTED_REGIONS = {"europe-west2"}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy AOP agents to Vertex AI Agent Engine (dry-run by default).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--agent", choices=list(AGENT_REGISTRY), required=True, help="Agent to deploy.")
    parser.add_argument("--project", required=True, help="Target GCP project id.")
    parser.add_argument(
        "--region",
        default="us-central1",
        help="GCP region for Agent Engine (must support it; NOT europe-west2).",
    )
    parser.add_argument("--env", choices=["dev", "prod"], default="dev", help="Deployment environment.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually deploy via the billable Preview API. Omit for a dry run (default).",
    )
    parser.add_argument(
        "--staging-bucket",
        default="",
        help="gs:// bucket the SDK uses to stage the packaged agent (required with --execute).",
    )
    return parser.parse_args(argv)


def _reasoning_engine_resource_name(project: str, region: str, agent: str) -> str:
    return f"projects/{project}/locations/{region}/reasoningEngines/{agent}-agent"


def _print_plan(args: argparse.Namespace, spec: dict[str, str], resource_name: str, sa_email: str) -> None:
    print(f"[AOP Deploy] agent={args.agent!r} env={args.env!r} region={args.region!r}")
    print(f"  description : {spec['description']}")
    print(f"  builder     : {spec['builder']}")
    print(f"  service_acct: {sa_email}")
    print(f"  resource    : {resource_name}")
    print(f"  staging     : {args.staging_bucket or '<unset — required for --execute>'}")
    print(f"  mode        : {'EXECUTE (billable)' if args.execute else 'DRY RUN'}")


def _deploy_live(args: argparse.Namespace, spec: dict[str, str], sa_email: str) -> int:
    """Package and deploy the agent to Vertex AI Agent Engine (billable, Preview).

    Confirm the agent_engines.create() signature against the installed
    google-cloud-aiplatform version before relying on this.
    """
    import vertexai
    from aop_common.config import AopSettings
    from vertexai import agent_engines

    vertexai.init(project=args.project, location=args.region, staging_bucket=args.staging_bucket)

    settings = AopSettings(project=args.project, region=args.region, environment=args.env)
    module_name, builder_name = spec["builder"].split(":")
    builder = getattr(importlib.import_module(module_name), builder_name)

    # Raises NotImplementedError until the ADK WorkflowAgent graph is wired —
    # that is the prerequisite for a real deploy (see module docstring).
    agent_instance = builder(settings)

    remote_agent = agent_engines.create(
        agent_engine=agent_instance,
        requirements=["google-adk==2.1.*"],
        extra_packages=["aop_common", spec["package"]],
        display_name=f"{args.agent}-agent",
        description=spec["description"],
        service_account=sa_email,
    )
    print(f"Deployed: {remote_agent.resource_name}")
    print(f"Expected: {_reasoning_engine_resource_name(args.project, args.region, args.agent)}")
    return 0


def deploy(args: argparse.Namespace) -> int:
    spec = AGENT_REGISTRY[args.agent]
    resource_name = _reasoning_engine_resource_name(args.project, args.region, args.agent)
    sa_email = f"{spec['sa']}@{args.project}.iam.gserviceaccount.com"

    _print_plan(args, spec, resource_name, sa_email)
    print()

    if args.region in _AGENT_ENGINE_UNSUPPORTED_REGIONS:
        print(
            f"ERROR: region {args.region!r} does not support Vertex AI Agent Engine. "
            "Use a supported region (e.g. us-central1 / europe-west1).",
            file=sys.stderr,
        )
        return 2

    if not args.execute:
        print("[DRY RUN] Re-run with --execute --staging-bucket gs://... to deploy.")
        return 0

    if not args.staging_bucket:
        print("ERROR: --staging-bucket is required with --execute.", file=sys.stderr)
        return 2

    return _deploy_live(args, spec, sa_email)


def main(argv: list[str] | None = None) -> None:
    sys.exit(deploy(_parse_args(argv)))


if __name__ == "__main__":
    main()
