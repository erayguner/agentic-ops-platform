# GCP Cost Estimate — AOP

Region basis **europe-west2** (London, Cloud Run Tier-1) + EU multi-region for
GCS/BigQuery. Prices in USD (GCP's billing baseline; this project's billing
account is **GBP** — convert ≈×0.79). Sourced from official
`cloud.google.com/<svc>/pricing` pages, **as of 2026-06-06**. Re-validate the
two big drivers (Agent Engine runtime + Gemini tokens) in the Pricing
Calculator before committing budget — Google's pricing pages are JS-rendered and
were partially fetch-truncated during research.

## The one thing that matters

**Cost is ~entirely Gemini token usage, which only accrues when agents run.**
The supporting platform with agents gated (what this validation deploys) is
essentially free-tier.

| Scenario | ≈ USD/mo | Driver |
|----------|---------|--------|
| **Infrastructure only** (agents gated, Cloud Run scale-to-zero) — *this deploy* | **$1–3** | KMS keys ($0.18, only with bootstrap), Secret Manager (~$0.12–0.30), Artifact Registry/GCS (~$0.06). No Gemini cost. |
| **Dev, agents active, light** (5 agents × ~50 calls/day, Gemini 2.5 Flash) | **~$58** ($65 w/ Model Armor) | ~95% Gemini Flash tokens ($55.50); Agent Engine compute within free tier |
| **Prod posture** (Cloud Run min-instances=1, heavier) | **~$175–185** | tokens + $6.48 Cloud Run idle + log retention |
| **Heavy** | **~$690** | Gemini 2.5 Pro (4× Flash) + custom-metric ingestion (~$90) + Model Armor |

## Unit prices (selected; full set researched)

| Service | Dimension | Unit (USD) | Free tier |
|---------|-----------|-----------|-----------|
| Vertex AI Agent Engine | vCPU-hr / GiB-hr | $0.0864 / $0.0090 | 50 vCPU-hr + 100 GiB-hr/mo |
| Gemini 2.5 Flash | in / out per 1M tok | $0.30 / $2.50 | none (Vertex) |
| Gemini 2.5 Pro | in / out per 1M tok | $1.25 / $10.00 | none |
| Cloud Run (Tier 1) | vCPU-s / GiB-s / req | $0.000024 / $0.0000025 / $0.40-1M | 180k vCPU-s, 360k GiB-s, 2M req |
| Cloud Run min-instances=1 (idle, CPU-throttled) | per 512 MiB svc | ~$3.24/mo | — |
| Pub/Sub | per TiB | $40 | first 10 GiB/mo |
| Cloud KMS | active key version | $0.06/mo | — |
| Artifact Registry | storage | $0.10/GB-mo | 0.5 GB |
| Cloud Logging | ingestion | $0.50/GiB | 50 GiB/mo |
| BigQuery | storage / query | $0.02/GB-mo / $6.25/TiB | 10 GB + 1 TiB/mo |
| Cloud Monitoring | custom metric ingest / uptime | $0.258/MiB / $0.30-1k | system metrics free; 1M uptime/mo; dashboards/alerts/Slack free |
| Secret Manager | active version / access | $0.06/mo / $0.03-10k | 6 versions + 10k ops/mo |
| Cloud Build | default pool | $0.006/build-min | 120 build-min/day |
| GCS (EU multi-region) | storage | $0.026/GB-mo | — |
| Model Armor | per 1M tokens | $0.10 | 2M tokens/mo |
| Security Command Center | n/a | **org-only — excluded** | — |

Sources: cloud.google.com/{vertex-ai,run,pubsub,kms,artifact-registry,
stackdriver,bigquery,secret-manager,build,storage}/pricing;
cloud.google.com/security/products/model-armor;
cloud.google.com/security-command-center/pricing.

## Assumptions & free-tier notes

- Cloud Run **scale-to-zero** in dev → $0 idle. Prod min-instances=1 with CPU
  **throttled** (default) ≈ $6.48/mo for both services; **avoid** CPU
  always-allocated (~$137/mo for two idle services).
- Agent Engine compute is fully absorbed by its free tier at dev volume.
- New-account $300 credit not modelled. SCC excluded (no org).

## Actual cost of THIS validation run

Resources existed ~30 minutes (deploy ≈21:14 UTC → destroy ≈21:43 UTC) with
Cloud Run at scale-to-zero, **no agents/tokens**, 2 short Cloud Build runs
(free tier), tiny Pub/Sub/BQ/logging. **Effective cost: a few pence (≈ $0).**
No KMS (bootstrap not applied). The GBP 20/mo budget alert was in place.

## Top cost controls

1. **Govern Gemini tokens** (90%+ of every scenario): default to 2.5 Flash, gate
   Pro behind explicit need, use context caching ($0.03 vs $0.30/1M input), cap
   `max_output_tokens` (output is 8.3× input on Flash), set a budget alert.
2. **Cloud Run:** scale-to-zero in dev; prod min-instances=1 **CPU-throttled**,
   not always-allocated.
3. **Watch the silent escalators:** Cloud Monitoring custom-metric cardinality
   ($0.258/MiB) and Cloud Logging volume — add Log Router exclusions; route
   audit logs to BigQuery (cheaper long-term) rather than Logging retention.
   Note: the current `_AllLogs` audit sink (governance) routes **everything** to
   BigQuery — add a filter to control volume at real usage.
