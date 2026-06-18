# release-please runbook

This is an unstaged, local-only reference. It is intentionally **not** tracked
in git. If you decide later that it should live in the repo, move it into
`docs/` and commit it deliberately.

---

## 0. What release-please does, in one paragraph

release-please reads every commit on `main` since the last release tag, looks
at the **Conventional-Commit type** of each one, computes the next semver
version, and opens (or updates) a single PR titled
`chore(main): release X.Y.Z`. That PR contains the version bump, the
CHANGELOG diff, and any extra files configured for the bump. **Merging that
PR is what actually cuts the release** — it tags the merge commit `vX.Y.Z`
and creates a GitHub Release. Until you merge it, nothing is released.

You do **not** run anything manually. Your only job is to write
conventional commits and merge the release PR when you want to ship.

---

## 1. One-time prerequisites (do these once, then forget)

### 1.1. Enable the repo setting

This is the single most common failure. Without it, the release PR never
gets opened.

1. Open <https://github.com/erayguner/agentic-ops-platform/settings/actions>
2. Scroll to **Workflow permissions**
3. Tick **Allow GitHub Actions to create and approve pull requests**
4. Click **Save**

Symptom if you skip this: workflow fails with
`GitHub Actions is not permitted to create or approve pull requests`.

### 1.2. Confirm the manifest exists

```bash
cat .release-please-manifest.json
# expected: { ".": "0.2.0" }   (or whatever your current version is)
```

If the file is missing or empty, release-please will tag the very next
commit on `main` as `v0.1.0`.

### 1.3. Confirm CHANGELOG.md exists

```bash
ls CHANGELOG.md
```

If absent, release-please will create one on the first release PR. Either
way is fine.

### 1.4. Sanity-check the config

```bash
cat release-please-config.json | jq .
```

Should be valid JSON and contain a `packages.["."]` entry. The current
config also lists `terraform/FRAMEWORK.md` under `extra-files`, which means
release-please will rewrite a version string in that file at release time.

---

## 2. Conventional Commits cheat sheet

Every commit on `main` (i.e. every merged PR's commits, or every direct
push) **must** follow this shape:

```text
<type>(<optional scope>)<!>: <subject>

<optional body>

<optional footer>
```

### 2.1. What bumps what

| Commit looks like                 | Bump         | 0.2.0 → |
| --------------------------------- | ------------ | ------- |
| `fix: something broke`            | patch        | 0.2.1   |
| `fix(framework): something broke` | patch        | 0.2.1   |
| `perf: faster query`              | patch        | 0.2.1   |
| `revert: bad change`              | patch        | 0.2.1   |
| `feat: new agent type`            | minor        | 0.3.0   |
| `feat(agents): new agent type`    | minor        | 0.3.0   |
| `feat!: redesign API`             | minor in 0.x | 0.3.0   |
| `feat: x\n\nBREAKING CHANGE: y`   | minor in 0.x | 0.3.0   |
| `chore: bump deps`                | no bump      | 0.2.0   |
| `docs: fix typo`                  | no bump      | 0.2.0   |
| `ci: tweak pipeline`              | no bump      | 0.2.0   |
| `test: add coverage`              | no bump      | 0.2.0   |
| `refactor: rename helper`         | no bump      | 0.2.0   |
| `build: bump tool`                | no bump      | 0.2.0   |
| `style: format`                   | no bump      | 0.2.0   |

The **highest** applicable bump across all commits since the last release
wins — one `feat:` outranks ten `fix:`es.

### 2.2. Pre-major behaviour (you are here)

Your `release-please-config.json` sets:

- `"bump-minor-pre-major": true` — breaking changes bump **minor** (not
  major) while you are on `0.x`. You stay in `0.x` until you explicitly
  cut `1.0.0`.
- `"bump-patch-for-minor-pre-major": false` — `feat:` still bumps minor
  (not patch) while on `0.x`.

Translation: until you decide to ship `1.0.0`, the worst that any single
commit can do is bump the **minor**.

### 2.3. Good commit examples

```text
fix(action-broker): handle empty Pub/Sub batch without 500
feat(agents): add Platform agent runtime wrapper
feat(framework)!: rename ops_audit_topic_id input

BREAKING CHANGE: existing callers must rename `audit_topic_id` to
`ops_audit_topic_id` in their tfvars.
docs: clarify staging variant in FRAMEWORK.md
chore: bump uvicorn to 0.48
ci(workflows): refresh action SHA pins
```

### 2.4. Bad commit examples (do not do these)

```text
update stuff                             # no type
Fixing the broker bug                    # capital F, no colon
feat:broker                              # missing space after colon
feature: add agent                       # "feature" is not a valid type
[broker] fix race                        # no conventional type at all
```

These commits get skipped by release-please's parser (you'll see
`commit could not be parsed` in the workflow log) — they neither bump the
version nor appear in the CHANGELOG. They are effectively invisible to
the release process.

Pre-commit / commitlint in this repo should catch most of these locally.

---

## 3. Day-to-day workflow

```text
        you                          release-please bot
         |                                    |
         |  git checkout -b feat/x            |
         |  ...code...                        |
         |  git commit -m "feat(x): y"        |
         |  git push + open PR                |
         |  merge PR to main                  |
         |--------------------------------->  |
         |                                    | runs on push to main
         |                                    | opens / updates
         |                                    | "chore(main): release 0.3.0" PR
         |                                    |
         |  review release PR's CHANGELOG     |
         |  merge release PR                  |
         |--------------------------------->  |
         |                                    | tags v0.3.0
         |                                    | creates GitHub Release
         |                                    | runs CHANGELOG side-effects
         |                                    |
         |    you are done                    |
```

Important: there is **only ever one open release PR at a time**. As you
merge more feature PRs, release-please **updates the same release PR** with
the new commits and (possibly) a higher version. Do not close it manually
unless you have a reason — it will just be re-opened on the next push.

---

## 4. Force-overrides (for when you do need to be specific)

### 4.1. Cut a specific version regardless of commits

Land any commit with this footer:

```text
fix(release): pin next version

Release-As: 0.2.12
```

The next release PR will use exactly `0.2.12`. Use this for backporting
or aligning with an external versioning scheme.

### 4.2. Cut 1.0.0

Two options.

Option A (recommended) — use Release-As in a commit:

```bash
git commit --allow-empty -m "chore: graduate to 1.0.0" -m "Release-As: 1.0.0"
git push
```

Option B — edit the manifest directly:

```bash
jq '."." = "0.9.999"' .release-please-manifest.json > /tmp/m && mv /tmp/m .release-please-manifest.json
# then any feat: commit bumps it to 1.0.0
```

After 1.0.0, breaking changes will bump major (2.0.0, 3.0.0, ...).

### 4.3. Skip release for a single change

- Use a non-bumping type: `chore:`, `docs:`, `ci:`, `style:`, `test:`,
  `refactor:`, `build:`.
- Or add `[skip-release]` anywhere in the commit body.

### 4.4. Hide a commit from the CHANGELOG

Use a type marked `"hidden": true` in `release-please-config.json`. Currently
hidden: `ci`, `chore`, `test`, `style`. They still trigger no bump.

---

## 5. Cutting your first patch release, end-to-end

Assume the manifest says `0.2.0` and you want to ship `0.2.1`.

```bash
# 1. branch + make a real fix
git checkout -b fix/example
echo "// bug fix" >> agents/orchestrator/main.py
git add agents/orchestrator/main.py
git commit -m "fix(orchestrator): handle null reasoning engine response"

# 2. push + open PR + merge it to main (via UI or gh)
git push -u origin fix/example
gh pr create --base main --title "fix(orchestrator): handle null response" --body "..."
gh pr merge --squash --delete-branch
```

Within ~60 seconds of the push to `main`, the **release-please** workflow
runs and opens a new PR:

```text
chore(main): release 0.2.1
```

Steps to ship it:

```bash
# 3. review what the release PR contains
gh pr view <release-pr-number> --web
# - confirm version is 0.2.1
# - confirm CHANGELOG.md got a "Bug Fixes" section
# - confirm .release-please-manifest.json bumped to 0.2.1

# 4. merge the release PR
gh pr merge <release-pr-number> --squash

# 5. verify the tag + release appeared
gh release view v0.2.1
```

Done. You shipped `0.2.1`.

To reach `0.2.12` from `0.2.0`, repeat this loop **12 times** with only
`fix:`/`perf:`/`revert:` commits between each release. The moment a `feat:`
or `!:` lands, the next release jumps to `0.3.0`.

---

## 6. Troubleshooting

### 6.1. "GitHub Actions is not permitted to create or approve pull requests"

You skipped section 1.1. Go enable the setting. No code change fixes this.

### 6.2. "commit could not be parsed" in the workflow log

Some merged commits don't follow Conventional Commits. They're silently
ignored. This is annoying but not fatal — release-please uses the commits
it can parse. To fix going forward, enforce commitlint in pre-commit (this
repo already does, on PR commits). For the existing bad commits in
history, you can either:

- Live with them (they just don't show up in CHANGELOG), or
- Rebase + reword them on `main` (only if no one else has pulled).

### 6.3. The release PR has the wrong version

Check the workflow run's "Building candidate release pull request" section.
The log shows every parsed commit and which bump it triggered. Common
causes:

- An unexpected `feat:` landed since the last release.
- A `Release-As: x.y.z` footer is in one of the commits.
- The manifest got hand-edited.

### 6.4. The release PR isn't being opened at all

In order of likelihood:

1. **Repo setting from section 1.1 is off.** Workflow log says
   `not permitted to create or approve pull requests`.
2. **No bumping commits since the last release.** All your commits are
   `chore:`/`docs:`/`ci:` etc. — release-please correctly does nothing.
3. **Workflow itself failed earlier.** Check
   <https://github.com/erayguner/agentic-ops-platform/actions/workflows/release-please.yml>.

### 6.5. I want to undo a release

```bash
# 1. delete the tag locally + remotely
git tag -d v0.2.1
git push --delete origin v0.2.1

# 2. delete the GitHub Release in the UI (Releases tab → Delete)
#    or:
gh release delete v0.2.1 --yes

# 3. reset the manifest if you want the next release to re-use 0.2.1
jq '."." = "0.2.0"' .release-please-manifest.json > /tmp/m && mv /tmp/m .release-please-manifest.json
git add .release-please-manifest.json
git commit -m "revert: manifest back to 0.2.0"
```

The CHANGELOG entry can be reverted in a follow-up commit, or just left in
place if the release was real and you only want to delete the tag.

### 6.6. release-please updated `terraform/FRAMEWORK.md` and I don't want that

It's listed in `release-please-config.json` under `extra-files`. Remove
that entry if you don't want version strings rewritten there. Make sure
`terraform/FRAMEWORK.md` actually has a `x-release-please-version` marker
where you want the version substituted; without one, release-please does
nothing to the file.

---

## 7. Where to look when something is weird

- Workflow runs: <https://github.com/erayguner/agentic-ops-platform/actions/workflows/release-please.yml>
- Open release PR: <https://github.com/erayguner/agentic-ops-platform/pulls?q=is%3Apr+is%3Aopen+head%3Arelease-please>
- Current manifest: `.release-please-manifest.json`
- Current config: `release-please-config.json`
- CHANGELOG: `CHANGELOG.md`
- Upstream docs: <https://github.com/googleapis/release-please>

---

## 8. The one-line summary

Write `fix:`, `feat:`, `feat!:` commits → push to main → review the
release PR the bot opens → merge it → done.
