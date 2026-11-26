---
name: sdd-image-manager
version: 1.10.0
last_updated: 2026-11-23
description: "Generate Dockerfile and .gitlab-ci.yml for DevOps/Application images. Modes: create, migrate (TAC-bitnami → DHI, Dockerfile + BuildKit CI), upgrade, optimize, remediate, skopeo (cbx wrapper image operations → native skopeo commands), artifactory (Artifactory OCI repo operations: list repos/images/tags, inspect, tag, promote to latest, delete tag). A JIRA Spec ID (e.g. CICDIMAGES-4) is the execute step of the SDD workflow (/sdd-create-specs → /sdd-create-plan → /sdd-image-manager → /sdd-wrap-up); --nosdlc = local generation only."
---

# sdd-image-manager

Register the `sdd-image-manager` skill invocation once and always announce as `sdd-image-manager`; never invoke another skill for the lifecycle.

## Mode Selection

Pick exactly one mode from the arguments:

| Arguments | Mode | Git / JIRA changes |
|-----------|------|--------------------|
| Spec ID only (`CICDIMAGES-4` or `--spec=CICDIMAGES-4`) | **SDD Execute** (replaces `/sdd-execute`) | Yes, via `execute-lifecycle.md` |
| Spec ID + `--nosdlc`, or Spec ID + explicit command | **Local Spec** | No |
| Explicit command only (`dockerfile …`, `migrate`, `ci`, `full`, `skopeo`, `artifactory`) | **Direct**: run the flow from **Flows** | No |
| No arguments | **Smart** | No |

SDD workflow: `/sdd-create-specs {SPEC-ID} → /sdd-create-plan {SPEC-ID} → /sdd-image-manager {SPEC-ID} → /sdd-wrap-up {SPEC-ID}`

## Commands

```bash
/sdd-image-manager CICDIMAGES-4                          # SDD Execute
/sdd-image-manager CICDIMAGES-4 --nosdlc [--yes]         # Local Spec
/sdd-image-manager dockerfile remediate CICDIMAGES-4     # Local Spec with explicit command
/sdd-image-manager dockerfile create|upgrade|optimize|remediate|migrate
/sdd-image-manager dockerfile remediate --cve=CVE-XXX    # or --report=snyk.json
/sdd-image-manager migrate [--file=Dockerfile]           # Application: Dockerfile TAC-bitnami → DHI + CI → BuildKit
/sdd-image-manager ci --type=devops|application --name=my-image
/sdd-image-manager full --type=devops                    # Dockerfile + CI
/sdd-image-manager skopeo [--file=.gitlab-ci.yml]        # cbx image operations → native skopeo commands
/sdd-image-manager artifactory repos|images|tags|inspect [--repo=…] [--image=…] [--tag=…]   # Artifactory OCI reads
/sdd-image-manager artifactory tag --new-tag=1.2.3 | promote [--target-tag=latest] | delete [--repo=…] [--image=…] [--tag=…]   # writes: plan + yes first
/sdd-image-manager                                       # Smart
```

| Param | Values | Description |
|-------|--------|-------------|
| `--type` | `devops`, `application` | DevOps = root, Application = non-root |
| `--name` | string | Image name (default: dir name) |
| `--file` | path | Target file path (`migrate`: Dockerfile to migrate, default `./Dockerfile`; `skopeo`: limit the scan to this file, default whole repo) |
| `--cve` | CVE ID | Fix specific vulnerability |
| `--report` | path | Snyk JSON report |
| `--spec` / positional | JIRA key (`^[A-Z][A-Z0-9_]+-\d+$`) | Spec ID |
| `--nosdlc` / `--no-sdlc` | flag | Local Spec instead of SDD Execute |
| `--yes` / `-y` | flag | Local Spec only: skip confirmation when R3 asked nothing (never applies to `artifactory`) |
| `--repo` / `--image` / `--tag` | Artifactory repo key, repo-relative image path, tag | `artifactory`: e.g. `cicd-1003184-oci-prd-local`, `trixie/pre-release/python-3.13`, `latest`; asked with a pick list when missing |
| `--new-tag` | tag | `artifactory tag`: version tag to add |
| `--target-repo` / `--target-image` / `--target-tag` | repo / image / tag | `artifactory promote`: defaults `--repo`, `--image`, `latest` |
| `--move` | flag | `artifactory promote`: remove the source tag after a verified copy |
| `--allow-prod` | flag | `artifactory`: allow changes under `trixie/cicd-images/` (second confirmation required) |
| `--app-id` | digits (default `1003184`) | `artifactory repos`: CMDB app ID used to filter repositories |

---

## Shared Rules (all modes)

### R1 — Templates

Determine the image type first (`--type` → R2 → **Type detection**; still unknown → ask per R3; `migrate` is always Application), then fetch before any generation the shared files plus **only** that type's Dockerfile template (and `execute-lifecycle.md` only in SDD Execute mode):

```powershell
$BASE  = "https://gitlab.dell.com/devops/devops-images/image-skills/image-sub-skills/-/raw/v1.1.0"
$TPL   = if ($type -eq "devops") { "devops-dockerfile-template.md" } else { "application-dockerfile-template.md" }
$FILES = if ($cmd -eq "artifactory") { "artifactory-oci.md","scripts/artifactory_oci.py" }
         elseif ($cmd -eq "skopeo") { "questions.md","gitlab-ci-templates.md","cbx-skopeo-migration.md" }
         elseif ($mode -eq "sdd-execute") { "questions.md","gitlab-ci-templates.md","vulnerability-remediation.md","execute-lifecycle.md",$TPL }
         else { "questions.md","gitlab-ci-templates.md","vulnerability-remediation.md",$TPL }
foreach ($f in $FILES) {
  $out = Join-Path $env:TEMP (Split-Path $f -Leaf)
  curl.exe -fsSL -k "$BASE/$f" -o $out
  if ($LASTEXITCODE -ne 0 -or ((Get-Content $out -TotalCount 1) -notmatch '^#')) {
    if (Test-Path "image-sub-skills/$f") { Copy-Item "image-sub-skills/$f" $out; Write-Warning "Using local image-sub-skills/$f" }
    else { throw "Template fetch failed: $f" }
  }
}
```

Every fetched file must start with a Markdown heading (`#`); anything else (404 / login page) is a failed fetch. Fallback: the workspace copy `image-sub-skills/<file>` (state it in the output). Neither available → STOP with `Template fetch failed: <file>` (see **Error Handling**). Never generate without the templates. `execute-lifecycle.md` is fetched only in SDD Execute Mode; Local Spec, Direct and Smart modes do not fetch it.

| Type | Dockerfile template |
|------|---------------------|
| Application (create, migrate, upgrade, optimize, remediate) | `application-dockerfile-template.md` |
| DevOps (create, upgrade, optimize, remediate) | `devops-dockerfile-template.md` |

A run that touches both types (e.g. several files in a Spec) fetches both templates.

`skopeo` is type-independent: skip type detection and fetch only `questions.md`, `gitlab-ci-templates.md` and `cbx-skopeo-migration.md` (`$FILES` above).

`artifactory` is type-independent: skip type detection and fetch only `artifactory-oci.md` and `scripts/artifactory_oci.py` (saved as `$env:TEMP/artifactory_oci.py`; line 1 is a `#` comment, so the same check applies).

### R2 — Requirement Mapping

Source: the JIRA Spec's summary, description, acceptance criteria, labels, components and comments (Local Spec), or `specs.md` + `plan.md` (SDD Execute). Later comments override earlier text; CLI arguments override everything.

| Field | Look for | Maps to |
|-------|----------|---------|
| Action | create / new image, upgrade / bump, optimize / reduce size, remediate / CVE / Snyk, migrate / convert / harden **+ Dockerfile, base image, bitnami, TAC or DHI**, pipeline / CI / build-container / kaniko / BuildKit (pipeline only), `cbx` / `cbx_wrapper` **+ skopeo or an image operation** (login, logout, pull, tag, push, inspect, delete, list-tags, sync), label `cbx-skopeo` | `dockerfile create` · `upgrade` · `optimize` · `remediate` · `migrate` (Dockerfile + CI) · `dockerfile migrate` (Dockerfile only, when explicitly limited) · `ci` · `full` · `skopeo` |
| Image type | devops, application, root / non-root, `cicd-1003184-oci-prd-local/trixie/pre-release` (or legacy `non-prod-devops`), DHI, bitnami | `--type` |
| Image name | image / repo name, component | `--name` |
| Language / runtime | Python, Go, Node.js, Java, .NET, PHP + versions | Q&A answers |
| Base image | Registry path, OS (Debian 12/13), FIPS | Must pass **Approved Registries** |
| Packages | Names + target versions | `upgrade` targets |
| CVEs | `CVE-\d{4}-\d+`, Snyk IDs | `--cve` (one or more) |
| Target files | Dockerfile / `.gitlab-ci.yml` paths | `--file` |
| Acceptance criteria | "Done when…", checklists | Final ✅ / ❌ checklist |

**Action priority** (first match wins; ask per R3 only if still ambiguous):

1. Label `cbx-skopeo`, or `cbx` / `cbx_wrapper` with skopeo or an image operation → `skopeo`, even when "migrate", "convert" or "image" also appear. `cbx build` / `build-image` / `push-image` / `build-push` also present → `skopeo` **+** `ci` (two rows, one R4 confirmation).
2. migrate / convert / harden + Dockerfile, base image, bitnami, TAC or DHI → `migrate` (or `dockerfile migrate` when explicitly limited). "image" alone does not trigger it.
3. list / show / inspect / tag / retag / promote / delete **+ Artifactory, OCI, registry, repo, tag or latest** (no Dockerfile / CI change requested) → `artifactory <op>` (Direct; map to the command per `artifactory-oci.md` → Commands).
4. All other actions as listed in the table.
### R3 — Gaps & Policy

- Ask only fields that are missing, ambiguous or conflicting (e.g. root + Application), grouped, using `questions.md`.
- Policy violation (unapproved registry, public base image, root for Application, non-FIPS): explain it, propose the nearest compliant option, wait. Never accept silently.
- Never guess requirements or fill gaps with defaults. Exception: **approved defaults** a sub-skill explicitly lists (e.g. `cbx-skopeo-migration.md` → Job Image); they are shown in the plan and can be overridden at the R4 confirmation.
- CI/CD variables (Vault paths, environment values) are never asked; they are handled by R5.

### R4 — One Confirmation

Show one plan per run and get one confirmation; it covers every flow in the run (flows do not re-confirm, sub-flow Q&A asks only what is still unanswered).

**Hard stops** (always, even with `--yes` or an approved plan): breaking change · image outside approved paths · registry 401 / credentials needed · Snyk unavailable and no CVE/report given · fix plan differs materially from the confirmed plan (e.g. an extra base image change).

Everything else still applies in every mode: templates, approved registries, FIPS rules and backups.

**`artifactory` (overrides "one confirmation per run"):** every `tag`, `promote` and `delete` gets its own plan and its own confirmation — run the dry run, show `plan_text` **verbatim**, and continue only on the user's `yes` typed after that plan (plus `Confirm production change? (yes/no)` for `trixie/cicd-images/`). `--yes`, earlier approvals or approval of another plan never count; never batch changes. Read operations need no confirmation. Never ask for, read, print or store the Artifactory token (see `artifactory-oci.md` → Token).

`migrate` `BLOCK` / `TODO` findings are **not** hard stops: the files are written with inline markers, the CI is migrated, and the findings are reported (and, in SDD Execute, committed and listed in the MR description).

### R5 — CI Prerequisites

Applies only to commands that write `.gitlab-ci.yml`: `ci`, `full`, `migrate`, `skopeo` (not `dockerfile …`). Each sub-skill lists its required variables in a **CI Prerequisites** table (`gitlab-ci-templates.md`, `cbx-skopeo-migration.md`).

| Variable kind | Where it lives |
|---------------|----------------|
| Vault secret paths (`VAULT_*_SECRET_PATH`, `ARTIFACTORY_SECRET_PATH`, …) and environment-specific values (`VAULT_ADDR`) | GitLab **Settings → CI/CD → Variables** (project or inherited group/instance) |
| Build description (`CONTAINER_REGISTRY`, `CONTAINER_NAMESPACE`, `APP_VERSION`, `CONTAINER_FILE_PATH`, image refs) and template constants with fixed values | `.gitlab-ci.yml` `variables:` (reviewed in the MR) |
| Credentials (usernames, passwords, tokens) | **Vault only**, fetched at runtime via `vaultcli.sh`; never in CI/CD variables or YAML |

1. **One place per variable.** Settings variables override YAML `variables:`, so never assign a settings-kind variable in YAML (no empty placeholders like `VAR: ""`). Exception: a value already assigned in the existing YAML is preserved there (found → ✅).
2. **Check:** existing YAML (job → global → `include: local`) → `gitlab` MCP project variables (`mcp_list_tools` first; needs Maintainer, group variables may be invisible) → otherwise ⚠️ *unverified*. Never ask for values and never block on R5.
3. **Plan** (shown with the R4 confirmation):

   ```
   | Variable | Purpose | Secret? | Where | Status |
   ```

   Status: ✅ found in YAML / via MCP · ⚠️ "Declare in Settings → CI/CD → Variables (or confirm it is inherited from the group). Not *Protected* — protected variables are unavailable on feature / `develop-{SPEC-ID}` branches. *Masked* only if the value is sensitive."
4. **Report** every ⚠️ item as a manual step in the final report (and, in SDD Execute, in the MR description). `--nosdlc`: list only, nothing runs in GitLab.

---

## SDD Execute Mode

### Pre-checks

1. POD workspace: `ai/` repo exists, the image repo is under `ai/submodules/`, its remote has a `develop` branch. Else STOP and suggest `--nosdlc`.
2. `ai/specs/{SPEC-ID}/specs.md` and `plan.md` exist. Else STOP: "Run `/sdd-create-specs {SPEC-ID}`" / "Run `/sdd-create-plan {SPEC-ID}`" first. Never generate them here.

### Step 1 — Image Plan Check

Skip if `plan.md` already has `## Image Manager Decisions` (re-run for MR review fixes).

1. Read `specs.md` + `plan.md`, apply R1.
2. For each Dockerfile / `.gitlab-ci.yml` / script in the plan, apply R2 (e.g. `dockerfile create --type=devops` → `devops-dockerfile-template.md` DEVOPS IMAGE; `migrate` → `application-dockerfile-template.md` Mode: MIGRATE + `gitlab-ci-templates.md` Application BuildKit; `skopeo` → `cbx-skopeo-migration.md`), then R3 and R5.
3. Show the proposed `plan.md` changes, confirm per R4, then write:

   ```markdown
   ## Image Manager Decisions
   | File | Command | Type | Name | Base image | Template | Notes |

   ### CI Prerequisites
   | Variable | Purpose | Secret? | Where | Status |
   ```

   `skopeo` rows: Type, Base image = `n/a`; Name = repo name; Template = `cbx-skopeo-migration.md`; Notes = files scanned · secret path variable · job image. Omit **CI Prerequisites** when no row writes `.gitlab-ci.yml`.

Only `plan.md` is updated; `specs.md` is read-only. A missing requirement (not an implementation detail) → STOP, direct to `/sdd-create-specs {SPEC-ID}`. Readiness, contract and fidelity gates belong to `execute-lifecycle.md` Step 2; do not fix them here.

### Step 2 — Execute (via execute-lifecycle.md)

Do NOT generate files directly in this mode. Read `$env:TEMP/execute-lifecycle.md` (or local fallback `image-sub-skills/execute-lifecycle.md`) in full and run **all** its steps in order (Step 1 → 16, or the MR Review Fix Phase on re-entry). If the template fetch failed, STOP with `Template fetch failed: execute-lifecycle.md`. Always register and announce solely as `sdd-image-manager`; never invoke another skill for the lifecycle. Only these points differ:

- **Step 6:** generate/modify files via the flow named in `Image Manager Decisions` (see **Flows**). The Step 1 confirmation satisfies R4.
- **Commits:** never commit backups (`*.bak`, `*.bak.*`, `Dockerfile.backup`); Git history keeps the originals.
- **`migrate` / `skopeo` MR:** commit and open the MR even when the verdict is `MANUAL_REVIEW`; put the migration report (DHI Migration Report / CBX → Skopeo Migration Report: findings, `TODO`/`BLOCK` list, verdict) in the MR description.
- **CI Prerequisites:** add the R5 table's ⚠️ items to the MR description as a "Before merging: declare these GitLab CI/CD variables" checklist.
- **Restricted DHI images:** if any `kob-1006479-oci-prd-local` image is used, put the **ACCESS REQUIRED** notice (`application-dockerfile-template.md` → DHI Catalog Lookup) at the top of the MR description.
- **Tests:** local checks only, each if the tool is available: `hadolint Dockerfile`, `docker build`, YAML syntax check of `.gitlab-ci.yml` (every `script` entry must parse as a string), `bash -n` / `shellcheck` on changed `*.sh` (`skopeo`). Skip unavailable tools and note it.
- **No pipeline waits:** never poll or wait for GitLab pipelines (before or after push/MR). CI results are reviewed on the MR by humans.
- **MCP fallback:** if `local.config` is missing, a key is missing, or the curl/API call fails (401/403/network error), retry the same operation via MCP (`mcp_list_tools` first):

  | Operation | Instead of | Use |
  |-----------|-----------|-----|
  | Attach `specs.md` / `plan.md` (Step 3) | curl + `JIRA_PAT` | `jira-it` → `jira_update_issue` with `fields: "{}"`, `attachments: "<abs path>/specs.md,<abs path>/plan.md"` (or `attachments_base64`) |
  | JIRA comments / transitions | curl + `JIRA_PAT` | `jira-it` → `jira_add_comment`, `jira_get_transitions`, `jira_transition_issue` |
  | MR list / create / discussions / replies (Steps 1A, 12, 14, R1–R7) | GitLab API + `GIT_PAT` | `gitlab` MCP server tools |
  | Branch, commit, push (Steps 5, 10, 11) | — | local `git` (existing credentials) |

  Report ❌ (with both errors) only if both paths fail.

If `execute-lifecycle.md` stops (Step 2 gate, no credentials via `local.config` or MCP), report its exact reason and STOP. Never fall back to local-only generation.

### Completion Check

Not complete until every item is done (fresh run). Report each ✅ / ❌ with the reason:

| # | Item | `execute-lifecycle.md` step |
|---|------|---------------------|
| 1 | `specs.md` + `plan.md` attached to the JIRA Spec | 3 |
| 2 | JIRA Spec → In Development | 4 |
| 3 | `develop-{SPEC-ID}` branch in the image repo and `ai/` | 5 |
| 4 | Changes committed and pushed | 10–11 |
| 5 | MR(s) for the image repo and `ai/` (show URLs) | 12, 14 |
| 6 | JIRA Spec → Ready to Deploy | 15 |

On MR review re-entry, report the MR Review Fix Summary instead. Exit immediately after the report (do not wait for pipelines). End with:

```
Next: after MR review comments are added, re-run /sdd-image-manager {SPEC-ID} to fix them.
Once the MR(s) are merged to develop, run /sdd-wrap-up {SPEC-ID} to close the Spec.
```

---

## Local Spec Mode

Local files only; no Git or JIRA updates unless the user explicitly asks.

1. **Fetch the Spec**
   - Preferred: `jira-it` → `jira_get_issue` (`fields: summary,description,issuetype,status,priority,labels,components,issuelinks,attachment,subtasks`, `comment_limit: 20`).
   - Fallback: `local.config` (`JIRA_BASE_URL`, `JIRA_PAT`):
     ```powershell
     $cfg = Get-Content local.config | ConvertFrom-StringData
     curl.exe -sL -k -H "Authorization: Bearer $($cfg.JIRA_PAT)" `
       "$($cfg.JIRA_BASE_URL)/rest/api/2/issue/<SPEC-ID>?fields=summary,description,issuetype,status,labels,components,issuelinks,attachment,comment"
     ```
   - Fetch linked issues/sub-tasks the description refers to. Download an attached Snyk JSON / Dockerfile to `$env:TEMP` as `--report` / reference.
   - Never print or store `JIRA_PAT`. Not found / 401 / 403 → report, ask the user to check the key, VPN or `JIRA_PAT`.
2. **Map & resolve:** apply R2, show `Spec ID · Summary · Action · Type · Name · Key inputs`, then R3.
3. **Confirm** per R4. `--yes` skips the confirmation only if R3 asked nothing.
4. **Run** the flow(s), then map each acceptance criterion to ✅ / ❌ with notes, and list R5 ⚠️ items as manual steps.

---

## Smart Mode

| Condition | Action |
|-----------|--------|
| Both missing | `dockerfile create` → `ci` |
| Only Dockerfile missing | Detect type from CI → `dockerfile create` |
| Only CI missing | Detect type from Dockerfile → `ci` (legacy `harbor.dell.com/tac-bitnami-containers` base → offer `migrate`, which also creates the CI job) |
| Both exist | Security scan (below) → menu: Optimize · Update CI · Upgrade packages · Remediate · Full review. Legacy `harbor.dell.com/tac-bitnami-containers` Application base → **Migrate to DHI (recommended)** is listed first |
| CI or scripts call `cbx` image operations (`cbx-skopeo-migration.md` → Detection) | Add **Migrate cbx → native skopeo** to the menu (or offer it alone when nothing else applies) |

**Security scan:** whenever a Dockerfile exists and Snyk CLI is available, run `snyk container test --file=Dockerfile --json`, show `Critical:X High:X Medium:X Low:X`, ask "Remediate now? (yes/no)".

**Type detection:** DevOps = base from `artifacts.dell.com/cicd-1003184-oci-prd-local/trixie/pre-release` (or legacy `harbor.dell.com/non-prod-devops` → offer the move to Artifactory, see `devops-dockerfile-template.md` → Approved Base Images), no USER directive, runs as root. Application = has USER directive, base from an **Approved Registries** Application path (`dhi-*-stack-images/debian13` or `tac-bitnami-containers/debian-12`), or legacy `harbor.dell.com/tac-bitnami-containers` (suggest `migrate`). `harbor.dell.com/devops-images/*` bases follow the DevOps rules unchanged (no DHI migration).

---

## Flows

| Command | Scope | Steps |
|---------|-------|-------|
| `dockerfile create` | Application: DHI Debian 13 FIPS (default) or Bitnami Debian 12 (fallback), non-root, multi-stage `-fips-dev` → `-fips`. DevOps: Artifactory `cicd-1003184-oci-prd-local/trixie/pre-release` (Debian 13 trixie), root. Python, Go, Node.js, Java, .NET, PHP | R1 → Q&A → base image via Artifactory storage API (Application: `kob-1006479-oci-dev-local` approved paths → not found → KOB Confluence DHI catalog, prd-local image ⇒ ACCESS REQUIRED notice → bitnami fallback · DevOps: `cicd-1003184-oci-prd-local/trixie/pre-release`) → Generate |
| `dockerfile migrate` | Application only: TAC-bitnami (Harbor) or non-approved `dhi-*` → DHI Debian 13 FIPS; bitnami Debian 12 (Artifactory) fallback | R1 → analyze D1–D26 (`application-dockerfile-template.md` → Mode: MIGRATE) → plan → R4 → `Dockerfile.bak` → edit in place → report + verdict |
| `migrate` | `dockerfile migrate` + Application CI | `dockerfile migrate` → `ci` (Application BuildKit, `.gitlab-ci.yml.bak` → edit in place), one R4 confirmation for both |
| `dockerfile upgrade` | Single/multiple packages. Application: + DHI Check; legacy bitnami base → offer `migrate` | Parse → dependency analysis → breaking-change detection → Apply |
| `dockerfile optimize` | Combine RUN, layer order Base → System → Lang → App, multi-stage, remove caches, pin versions. Application: + DHI Check | Backup → Apply template rules |
| `dockerfile remediate` | Snyk CLI, Snyk JSON, direct CVE | See below |
| `ci` | DevOps: full pipeline (build → test → deploy → verify → prod). Application: replace build-container job with BuildKit | Detect type → R1 → Generate/migrate |
| `full` | Dockerfile + CI | `dockerfile create` → `ci` |
| `artifactory` | Artifactory OCI repos (DevOps + Application): `repos`, `images`, `tags`, `inspect` (read) · `tag`, `promote` (default target `latest`), `delete` one tag (write). No Git / JIRA changes | R1 → resolve repo / image / tag (pick lists) → read: run `artifactory_oci.py` + summarise · write: dry run → plan verbatim → `yes` (+ production confirmation) → `--confirm <plan_id>` → report (`artifactory-oci.md`) |
| `skopeo` | DevOps + Application: `cbx login/logout/pull/tag/push/inspect/delete/list-tags/sync` in `.gitlab-ci.yml` / scripts → native `skopeo`; `cbx build*` → report, recommend `ci` | R1 → scan → map → plan → R4 → `<file>.bak` → edit in place → verify → report + verdict (`cbx-skopeo-migration.md`) |

### dockerfile remediate

1. Verify the Dockerfile exists.
2. Input priority: `--cve` → `--report` → Snyk CLI → ask for `--report` / `--cve`.
3. Categorize: Base Image | APT | PIP/NPM | Unfixable. Prefer base image upgrades; cascade dependency updates.
4. Check dependencies, then verify fix availability (approved Artifactory paths / apt / PyPI / npm). CVE not found → Debian tracker, Snyk DB. Not applicable → inform, no action.
5. Confirm per R4.
6. Backup → Apply → Offer verification scan. Details: `vulnerability-remediation.md`.

---

## Error Handling

| Error | Action |
|-------|--------|
| Template fetch fails (curl error, 404, non-Markdown content) | Use workspace `image-sub-skills/<file>` if present (warn); else STOP: `Template fetch failed: <file>` — check network/VPN and that the file exists on `image-sub-skills` `v1.1.0` |
| R5 variable not found | Not an error: ⚠️ in the plan, manual step in the report / MR |
| Artifactory unreachable | Manual input validated against **Approved Registries** |
| Artifactory 401/403 (DevOps `cicd-1003184-oci-prd-local`, normally anonymous; not `artifactory`) | Ask for Artifactory username + access token (never print/store), retry |
| `artifactory` exit 3 (no token / 401 / 403) | Never ask for the token in chat: tell the user to add `ARTIFACTORY_TOKEN` to `local.config`, set the environment variable, or run the command themselves (`--interactive`); report a missing permission as stated |
| `artifactory` exit 2 `Plan is stale…` | Re-run the dry run and show the new plan; never re-use the old confirmation |
| Legacy image not in the TAC → DHI mapping (`migrate`) | Never guess a DHI name: bitnami Debian 12 fallback, else `BLOCK` marker |

Policy violations, breaking changes and unapproved images: see R3 / R4.

---

## DHI FIPS Compliance

| Requirement | Application | DevOps |
|-------------|-------------|--------|
| Non-root user | ✅ UID/GID 65532 (DHI) · 1000 (bitnami fallback) | ❌ Root |
| No secrets | ✅ | ✅ |
| No own CA certificates (Dell CA ships in DHI; `dfn_*` excepted) | ✅ | – |
| Java FIPS options preserved (append `JAVA_TOOL_OPTIONS`, BCFKS) | ✅ | – |
| UID/GID ≤ 65535 | ✅ | – |
| Clean artifacts | ✅ | ✅ |
| Pinned versions | ✅ | ✅ packages · base image `:latest` (pre-release path, never `unstable_<sha>`) |
| --no-install-recommends | ✅ | ✅ |

## Approved Registries

### Application: `artifacts.dell.com/kob-1006479-oci-dev-local` + restricted `kob-1006479-oci-prd-local` (ONLY these paths)

| Priority | Repository / path | Lookup |
|----------|------|--------|
| 1 | `kob-1006479-oci-dev-local/dhi-os-stack-images/debian13` | Artifactory storage API (anonymous) |
| 1 | `kob-1006479-oci-dev-local/dhi-tech-stack-images/debian13` | 〃 |
| 1 | `kob-1006479-oci-dev-local/dhi-software-stack-images/debian13` | 〃 |
| 1 | `kob-1006479-oci-dev-local/dhi-dependencies-stack-images/debian13` | 〃 |
| 2 (restricted) | `kob-1006479-oci-prd-local/dhi-*-stack-images/debian13` | Only when priority 1 has no match: KOB Confluence DHI catalog (`debian13_container_image_tags.csv` on page 1383139475). Approved, but the user must request access from the KOB team → **ACCESS REQUIRED** notice in plan, report and MR |
| 3 (fallback) | `kob-1006479-oci-dev-local/tac-bitnami-containers/debian-12` | Only when no DHI match in priority 1 or 2 |

Any other folder or public registry is NOT approved for Application images (including builder stages). dev-local: anonymous pull; browse via `https://artifacts.dell.com/artifactory/api/storage/kob-1006479-oci-dev-local/<path>`. See `application-dockerfile-template.md` → Approved Base Images, DHI Catalog Lookup (and Legacy TAC → DHI Mapping).

### DevOps

- `artifacts.dell.com/cicd-1003184-oci-prd-local/trixie/pre-release` (Debian 13 trixie)
- Legacy `harbor.dell.com/non-prod-devops/debian-12` (Harbor is being retired): not approved for new or changed Dockerfiles; existing bases are moved to the path above
