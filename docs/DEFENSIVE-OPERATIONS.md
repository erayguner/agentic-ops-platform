# Defensive Operations — Agentic Operations Platform

Securing the agents you deploy is half the work. The other half is running
security operations fast enough to contend with attackers who are themselves
AI-accelerated: exploits land within hours of a patch, and an agentic adversary
can probe hundreds of systems in the time a human reviews one alert. This
runbook is AOP's **Part V** — defensive operations at the speed of autonomous
threats.

> **Source framework:** Anthropic, *Zero Trust for AI Agents* (2026), Part V.
> **Conformance:** `AGENT_GOVERNANCE_FRAMEWORK v1.1`; cross-referenced from
> [`GOVERNANCE-MAPPING.md`](./GOVERNANCE-MAPPING.md) (§15 Incident response, §9
> Observability) and [`DESIGN-REVIEW.md`](./DESIGN-REVIEW.md) Part 15.
> **Design test (applies to every control here):** *does this make the attack
> impossible, or just tedious?* Friction controls (rate limits, extra hops) buy
> time but do not stop a determined agentic attacker — prefer controls that
> remove a capability over controls that throttle it.

The principle that governs defensive automation: **automate the bookkeeping,
not the decisions.** Move humans off evidence collection, enrichment,
correlation and write-ups; keep them on the containment calls, the disclosure
calls, and the customer-comms calls. Human decision speed during an incident
must never be rate-limited on evidence gathering.

---

## 1. Put a model at the front of the alert queue

Every inbound signal gets an automated first-pass investigation before a human
sees it. AOP implements this as the **triage pass** in
[`agents/aop_common/triage.py`](../agents/aop_common/triage.py): each
`OpsSignal` produces a `TriageDisposition` — `auto_close`, `suppress_duplicate`,
`investigate`, or `escalate` — with a rationale and a recommended domain. The
triage agent has **read-only** scope; it routes, it does not act. Containment
still flows through the Action Broker approval gate.

**Rollout recipe (do not automate the whole queue at once):**

1. Pick one noisy rule with a known-high false-positive rate.
2. Wire the triage classifier into that rule's stream with **read-only** access
   to the underlying data (`TriageQueue(classifier=...)`).
3. Measure agreement against a human reviewer for **two weeks**
   (`aop_alert_triage_total` vs the reviewer's disposition).
4. If the agreement rate is tolerable, expand to the next rule.

Fail-safe: the model-backed classifier defaults to `escalate` under
uncertainty. The classifier is a skeleton until `ModelFactory`
([`agents/aop_common/models.py`](../agents/aop_common/models.py)) is wired; the
dwell/coverage stamping and structured emission are live.

---

## 2. Measure what matters — dwell time and coverage

Instrument these two metrics before investing anywhere else; they are where
AI-assisted automation has the most leverage and they matter most as exploit
windows shorten.

| Metric | Definition | Where it lives | Target |
|---|---|---|---|
| **Dwell time** | Seconds from anomaly occurrence to first-pass triage | `aop_alert_dwell_seconds` (distribution, `terraform/modules/observability/main.tf`) | p95 **< 1 h for critical** |
| **Coverage** | Fraction of alerts routed for human investigation vs total | `aop_alert_triage_total` labelled by `routed_to_human` | Tracked on the Platform Overview dashboard |
| **Detection speed alert** | p95 critical dwell breaches the 1 h target | `detection_dwell_p95` alert policy → Slack + Pub/Sub | Fires at > 3600 s |

Standing questions for the security team (from the brief): *would we know within
an hour if an agent went rogue? Can the team take time off without worrying
about undetected agent misbehaviour?* If either answer is uncertain, the
foundational controls need more work.

---

## 3. Map detection coverage against MITRE ATT&CK

Knowing which techniques you can detect — and which you can't — is more useful
than a general goal to "improve detection". Prioritise **lateral movement** and
**credential access**: these are where AI-accelerated attackers get the most
leverage from a compromised agent identity.

| ATT&CK area | AOP detection surface | Status |
|---|---|---|
| Credential Access (T1552 unsecured creds, T1528 token theft) | No exported SA keys (WIF); per-action-class short-lived impersonation (`services/action-broker/impersonation.py`); `gitleaks` + `secret-scan.yml` | Partial — runtime token-anomaly detection is a gap |
| Lateral Movement / pivot (T1550 alt-auth material) | Per-agent identity + explicit `run.invoker` allow-list; broker ingress `INTERNAL_LOAD_BALANCER`; VPC-SC perimeter (`terraform/modules/governance/`) | Partial — east-west call anomaly baselines are a gap |
| Privilege Escalation (T1078 valid accounts) | Custom roles ⊂ predefined; Principal Access Boundary; `aop_policy_denial_count` metric | Implemented (static) — per-principal budgets are a gap |
| Defense Evasion (T1562 impair defences) | Immutable BigQuery audit; SCC v2 + Model Armor floor settings; ConfigChange auditing | Partial — hash-chained/signed audit is a gap |
| Collection / Exfiltration (T1041) | Egress denied by default (VPC-SC); output redaction (`services/slack-notifier/redaction.py`); memory injection screen (`aop_common/memory.py`) | Partial |
| Impact (T1485/T1489) | Single write chokepoint + tiered approval; auto-rollback on post-condition failure (`services/action-broker/broker.py`) | Implemented (write side) |

**Atomic Red Team — one-afternoon coverage check.** Atomic Red Team is an
open-source library of small, safe tests mapped to ATT&CK techniques. Run a
handful targeting the **credential access** and **lateral movement** rows above,
then check which ones your existing logging actually detected. The output is a
concrete coverage map — repeat quarterly and after any detection change.

---

## 4. Session-level kill-switch

**Today:** the Slack `Reject` button halts a *pending* action chain — the
broker receives `ops.actions.approved` carrying `decision: rejected`
([`services/slack-notifier/interactivity.py`](../services/slack-notifier/interactivity.py)).
This is action-level, not session-level.

**Target (gap, tracked in GOVERNANCE-MAPPING §19 / ASI10):** a session-level
halt that denies **all in-flight tool calls for a session in < 1 minute**.
Design:

1. A `kill_session(correlation_id)` control on the Action Broker that adds the
   session to a deny set checked at the top of `propose_action`.
2. Broadcast the halt on `ops.signals` so specialist agents stop emitting.
3. Revoke the session's short-lived impersonation tokens (they expire in ≤ 1 h;
   revocation closes the residual window).
4. Record a `phase="rollback"` audit event with `human_identity`.

Until wired, the emergency path is: reject the pending action, then demote the
relevant action class to Tier 0 (§7 below) to stop further writes.

---

## 5. Tabletop: five simultaneous incidents, not one

The standard tabletop assumes one critical CVE with a working exploit lands on a
Monday. Run the version where **five** land in the same week. AI-accelerated
offense means an order-of-magnitude increase in finding volume; a workflow built
around a spreadsheet and a weekly meeting will not keep up.

**Exercise script (run quarterly):**

1. Inject five concurrent `OpsSignal`s of `severity: critical` across different
   domains (sre, devsecops, platform, finops) in **dev**.
2. Verify triage routes/auto-closes each within the dwell target and that
   `aop_alert_dwell_seconds` reflects it.
3. Verify intake, triage, and remediation tracking scale — no single human is a
   serialisation point on evidence collection.
4. Exercise two approvals requiring a **2-approver quorum** concurrently.
5. Exercise one **session-level kill** (§4) and one **emergency change** (§6).
6. Record dwell p95 and coverage for the exercise; file gaps as roadmap items.

---

## 6. Emergency change procedures (decide in advance)

A two-week change-approval cycle for production patches is itself a security
risk. The same applies to emergency containment. **Decide in advance** who can
authorise each action, how fast they can be authorised, and what evidence is
required — then practise the authorisation path so it is not improvised during
an incident.

| Emergency action | Pre-authorised by | How | Evidence required |
|---|---|---|---|
| Take a service offline | Platform Owner **or** on-call SRE | Cloud Run revision → 0; or demote action class to Tier 0 | Correlation id + triage disposition |
| Rotate a credential | DevSecOps Reviewer | New Secret Manager version (`latest`); services pick it up without redeploy | Affected secret + reason |
| Block a network path | Platform Owner | Tighten VPC-SC / firewall (`terraform/modules/foundation/`, `governance/`) | Source/destination + signal |
| Demote an action class to Tier 0 | On-call SRE (single approver in emergency) | Set tier `0` in `services/action-broker/policy/action_classes.yaml`, apply | Action class + incident id |

All emergency changes are still **logged and audited** (`AuditRecord`) and
**reviewed after the fact** under the normal 2-reviewer rule in
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Emergency speed buys a relaxed
*pre*-approval, never a skipped *audit*.

---

## 7. Trust through verification for defensive agents

Agentic SOAR capabilities are powerful, and their blast radius can be
significant — apply the same Zero Trust posture to defensive automation that you
apply to any other agent:

- **Least privilege.** The triage agent is read-only; automated responses are
  scoped to specific action classes with bounds (`policy/action_classes.yaml`).
- **Verified integrity.** Defensive agents run in the same hardened runtime
  (`terraform/modules/agent-runtime/`) with per-agent identity.
- **Human in the loop on high impact.** Automated responses generate alerts for
  review; high-impact actions require approval even when automation recommends
  them (tier ≥ 3 routing).
- **Logged like any agent.** Defensive agent actions are logged, traced, and
  reviewed — the same audit stream, the same `correlation_id`.

Do not blindly trust defensive automation any more than you trust other
autonomous systems.

---

## Maintenance

Update this runbook in the same PR as any change that adds/removes a detection
surface, a kill-switch capability, or an emergency-change authorisation path.
The 2-reviewer rule in [`CONTRIBUTING.md`](../CONTRIBUTING.md) applies — this is
a project-level governance artefact. Open defensive-ops gaps are tracked in
[`GOVERNANCE-MAPPING.md`](./GOVERNANCE-MAPPING.md) §19 and
[`DESIGN-REVIEW.md`](./DESIGN-REVIEW.md) Part 10 (Roadmap).
