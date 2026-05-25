# Security Policy

This project conforms to **`AGENT_GOVERNANCE_FRAMEWORK v1.1`**
([`docs/AGENT_GOVERNANCE_FRAMEWORK.md`](./docs/AGENT_GOVERNANCE_FRAMEWORK.md)).
This `SECURITY.md` is the disclosure-policy surface; the operational
controls live in:

- **§12 Security** — threat model, secret hygiene, supply-chain,
  signed artifacts, boundary hardening, managed threat detection,
  red-teaming.
- **§15 Incident response** — incident definition, runbook structure,
  forensic guarantees, blameless culture.
- **[`docs/GOVERNANCE-MAPPING.md`](./docs/GOVERNANCE-MAPPING.md)** —
  the per-control attestation for §12 and §15 against this codebase.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.** Report them privately via GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on this repository.

You should expect:
- Acknowledgement of receipt within **5 business days**.
- A more substantive response within **10 business days**.
- A coordinated disclosure window of 30–90 days depending on severity and remediation complexity.

## In scope

This repository is a **reference scaffold and design review** — there is no deployed service to attack here. Vulnerability reports are nevertheless welcomed for:

- **Insecure defaults in Terraform modules** — for example, overly permissive IAM bindings, missing CMEK on a sensitive resource, missing `deletion_policy = "PREVENT"` on a production-critical resource, missing `auth_token_wo` for a secret-bearing notification channel, or a default that would produce a public-Internet attack surface on apply.
- **Insecure defaults in the agent / service skeletons** — for example, missing Slack request-signature verification, weak ID-token verification on MCP endpoints, secrets logged at INFO level, or a `LIVE_MODE` guard that fails open.
- **Documentation that could mislead a deployer into an unsafe configuration** — for example, a recommendation that contradicts the principles in `docs/DESIGN-REVIEW.md` Part 5 / Part 8.
- **Residual sanitisation leaks** — if you find any real-looking GCP project ID, project number, billing-account ID, email, OAuth token, API key, SA key, KMS key path, GCS bucket name, secret name, workflow name, or internal product code name in this repository, please report it under this policy.

## Out of scope

- Issues that already require an attacker to hold direct privileges in the deployer's GCP organisation or CI identity.
- Theoretical vulnerabilities in third-party dependencies that have not produced a CVE; please report those to the relevant upstream project.
- Findings that depend on the deployer ignoring the explicit "skeleton — not a working deployment" guidance.

## Hardening checklist for deployers

A deployer should at minimum:

1. Bind WIF for CI; never create `google_service_account_key` resources or commit JSON SA keys.
2. Enable Org Policy `iam.disableServiceAccountKeyCreation` at folder/org scope.
3. Set `LIVE_MODE` and `LIVE_SLACK_ENABLED` only after end-to-end smoke tests in `dev`.
4. Enable Security Command Center v2 and the Model Armor floor settings before introducing any agent action class beyond Tier 1.
5. Review `docs/DESIGN-REVIEW.md` Part 8 (Security, Compliance, Resilience, Failure-Handling, Escalation) before promoting any action class to Tier 2+ in prod.
