---
name: sdd-cicd-setup
description: Single entry point for CI/CD pipeline generation. Accepts an optional Jira Spec/Story ID to derive CI/CD requirements from the spec. Auto-detects tech stack, platform and deployment type, loads sub-skill definitions from GitLab, generates a complete inline .gitlab-ci.yml. Orchestrates 9 internal sub-skills (build-unittest, verify-skill, container-skill, deploy-skill, rfc-skill, artifact-skill, infra-skill, datarobot-skill, database-skill).
triggers:
  - user
  - model
---

# Skill: sdd-cicd-setup (SDD Engine v5.0.0)

> **The ONLY skill users invoke for CI/CD.** One command. Auto-detects everything. Generates a complete `.gitlab-ci.yml`. Minimal user input.

---

## 1. Overview

This engine analyses a project's tech stack, platform and deployment type, auto-maps them to Dell DevOps sub-skill definitions fetched from GitLab at runtime, and produces a working, fully inline `.gitlab-ci.yml` with zero `include:` / `extends:` dependencies.

### User Experience

```
User runs:   /sdd-cicd-setup                         ← auto-detect from project files
       OR:   /sdd-cicd-setup PROJECT-1234             ← Jira Spec/Story drives detection
Agent does:  [If Jira ID: fetch spec → extract CI/CD requirements → transition to DEFINING DETAILS]
             [If Jira ID: spec details confirmed → transition to READY FOR DEV]
             [If Jira ID: create branch develop-{ISSUE_ID} → transition to IN DEVELOPMENT]
             Scans project → detects tech stack → detects platform → detects deployment
             → resolves all variables → generates complete .gitlab-ci.yml
             [If Jira ID: commit → push → create MR to develop → transition to READY TO DEPLOY]
             [If Jira ID: posts pipeline summary comment on the Jira issue]
User sees:   One confirmation prompt → done
             [If Jira ID: after MR merge → transition to COMPLETE]
```

### 1.1 Modes

| # | Mode | Trigger | Output | User Review |
|---|---|---|---|---|
| 1 | **Generate** | No `.gitlab-ci.yml` exists | `.gitlab-ci.yml` (new) | Single confirmation (Step 5) |
| 2 | **Update** | `.gitlab-ci.yml` exists | `gitlab-ci-copy.yml` → replaces `.gitlab-ci.yml` | **Mandatory diff review** (§4.3) — custom jobs preserved + latest-changes sweep applied (§4.2 step 9) |

Mode selection is automatic — no user prompt needed. In Update mode, the user reviews the diff and approves the replacement (see §4 for full workflow).

### 1.2 Design Principles

| Principle | How |
|---|---|
| **Auto-detect everything** | Tech stack, platform, deployment type, variables, paths — all from project files |
| **Single confirmation** | Show what was detected + generated, ask ONE yes/no |
| **Smart defaults** | Every variable has a sensible default; user only overrides if needed |
| **No sub-skill knowledge needed** | Users never see or invoke `build-unittest`, `verify-skill`, or any other sub-skill |

### 1.3 Jira-Driven Flow (delegated to `jira-sdlc-skill`)

When a Jira ID is supplied (`/sdd-cicd-setup PROJECT-1234`), the engine loads the **`jira-sdlc-skill`** sub-skill at runtime and delegates to it. That sub-skill owns prerequisites, workspace/submodule layout, dual-repo branch creation, Jira state transitions (DEFINING DETAILS → READY FOR DEV → IN DEVELOPMENT → READY TO DEPLOY), change-summary generation, commit/push/MR for both repos, and the hand-off to `/sdd-wrap-up` for the final COMPLETE transition. Its SKILL.md is the single source of truth for every Jira/Git/MR directive referenced in Steps 0 and 6 below.

When no Jira ID is given, `jira-sdlc-skill` is NOT loaded and the engine works purely from project files in the current directory.

### 1.5 Scope Boundary

> **This skill handles `.gitlab-ci.yml` delivery only.** In scope: detection, generation/update of the pipeline YAML, and — when a Jira ID is supplied — delegation to `jira-sdlc-skill` for the mechanical SDLC wiring (branch, commit, MR, Jira transitions, change-summary). Everything else is out of scope:
> - Answering non-CI/CD questions
> - Generating application code, infrastructure code, or standalone documentation
> - General DevOps consulting beyond `.gitlab-ci.yml`
> - Deviating from the detection → generation → write (→ commit/MR if Jira) workflow defined here
>
> Out-of-scope response: *"Outside the scope of /sdd-cicd-setup. I generate / update `.gitlab-ci.yml`. How can I help with your CI/CD pipeline?"*

---

## 2. Architecture

**Flow:** `/sdd-cicd-setup` → scan files → auto-detect → load sub-skills → generate inline YAML → confirm → write `.gitlab-ci.yml`

Sub-skills are internal implementation details — users interact only with `/sdd-cicd-setup`.

### 2.1 Sub-Skills Source & Runtime Loading

**Repository:** `https://gitlab.dell.com/1003184/code/cicd-skills/sub-skills.git` — submodule at `sub-skills/`, version `v1`.

**Loading rules:**
1. If `sub-skills/v1/build-unittest/SKILL.md` is missing, clone: `git submodule update --init --recursive sub-skills`
2. Always load: `build-unittest`, `verify-skill`
3. Conditionally load based on detection: `container-skill` (Dockerfile/Helm), `deploy-skill` (non-Library), `rfc-skill` (production deploy, including Database §2h), `artifact-skill` (artifact publish/retrieve, including Database §2i), `infra-skill` (Terraform/Ansible), `datarobot-skill` (DataRobot/MLOps), `database-skill` (Database deployment)
4. Conditionally load **`jira-sdlc-skill`** iff a Jira ID is provided on the command line. When loaded, Step 0 and Step 6b–6j are delegated to it; otherwise skip both entirely.
5. Each sub-skill SKILL.md provides: input contract, job templates (exact YAML) or phase steps, output contract (stages + variables + jobs or SDLC state), and constraints.
6. **Fallback:** If sub-skills unavailable, STOP with error — never generate without them.

### 2.2 Sub-Skills Registry

| Sub-Skill | Purpose | Stage(s) Generated | Replaces |
|---|---|---|---|
| `build-unittest` | Compile + unit test jobs | `build`, `verify-build` | 16 hidden build/test jobs |
| `verify-skill` | Security scanning + code quality jobs | `verify-build`, `validate-deploy` | 9 hidden security jobs |
| `container-skill` | Docker build/push/tag/sign, BuildKit, Helm, cleanup | `build-docker`, `build-container`, `cleanup` | 8 hidden container jobs |
| `deploy-skill` | PCF, K8s/KOB, AKS, Azure, VM, GitOps/ArgoCD deploys | `deploy`, `deploy-prod`, `switch-route`, `go-live`, `post-deploy`, `cleanup` | 112 hidden deploy jobs |
| `rfc-skill` | ServiceNow RFC lifecycle (snowctl) | `rfc-submit`, `rfc-approve`, `rfc-update`, `rfc-close` | 10 hidden change jobs |
| `artifact-skill` | JFrog Artifactory publish/retrieve | `publish-artifact`, `retrieve-artifact` | 2 hidden artifact jobs |
| `infra-skill` | Terraform plan/apply/destroy + Ansible lint/deploy | `pre-provision`, `provision`, `configure`, `deploy`, `cleanup` | 13 hidden infra jobs |
| `datarobot-skill` | DataRobot agents/MCP/ML + MLOps training/eval/scan | `build`, `deploy`, `model-training`, `model-evaluation`, `model-register`, `inference`, `cleanup` | 50 hidden DR/AI jobs |
| `database-skill` | Database script deployment (RDBMS + NoSQL) | `build`, `verify-build`, `prerfc-validate`, `deploy`, `deploy-prod`, `predeploy-prod` | 120+ hidden DB jobs |
| `jira-sdlc-skill` | Jira + GitLab SDLC plumbing — spec resolution, dual-repo branches, Jira transitions, change-summary, commit/push/MR, wrap-up hand-off | (none — SDLC orchestration, not pipeline jobs) | Replaces inline Phase 0 + Phase 6b–6j. Loaded ONLY when Jira ID provided. |

---

## 3. Workflow

### Step 0 — Jira Spec Resolution + Branch Setup (Optional, delegated)

If a Jira ID was supplied, invoke **`jira-sdlc-skill` Phase 0** (0a → 0g): Story→Spec resolution, CI/CD-hints extraction, workspace/submodule discovery, dual-repo `develop-{ISSUE_ID}` branch creation, and the DEFINING DETAILS → READY FOR DEV → IN DEVELOPMENT transitions. The sub-skill returns `{ISSUE_ID, LINKED_STORY_ID, WORKSPACE_ROOT, SUBMODULE_PATH, branch_name, ci_cd_hints}`.

Carry `ci_cd_hints` into Step 2 (hints supplement auto-detection — they never override it; conflicts are surfaced in Step 5). If no Jira ID was supplied, skip Step 0 entirely.

---

### Step 1 — Determine Mode

See the Mode table in §1.1. If `.gitlab-ci.yml` exists → **Update mode** (§4 workflow, mandatory diff review). Otherwise → **Generate mode**, proceed automatically to Step 2 (no user prompt until Step 5).

---

### Step 2 — Scan & Auto-Detect Everything

Scan the project root in **one pass**. Detect all dimensions simultaneously. When Step 0 provided Jira hints, use them to boost detection confidence but always verify against project files. If a Jira hint conflicts with auto-detection, present both to the user.

#### 2a. Tech Stack Detection (includes image resolution)

Each row maps the detection signal to `TECH_STACK` + platform + confidence. Image variable → value lookup is the single table in **§6 Image Resolution** — do NOT duplicate values here.

| Files Found | TECH_STACK | Platform | Confidence |
|---|---|---|---|
| `pom.xml` | `maven` | Linux | 95% |
| `build.gradle` / `.kts` | `gradle` | Linux | 95% |
| `build.xml` | `ant` | Linux | 90% |
| `build.sbt` | `sbt` | Linux | 95% |
| `package.json` | `js` | Linux | 90% |
| `package.json` + Angular | `angularjs` | Linux | 95% |
| `package.json` + serve.json | `sharepoint` | Linux | 95% |
| `go.mod` / `go.sum` | `golang` | Linux | 95% |
| `composer.json` | `php` | Linux | 95% |
| `CMakeLists.txt` | `cmake` | Linux | 95% |
| `requirements.txt` / `Pipfile` / `pyproject.toml` / `setup.py` | `python` | Linux | 85% |
| `requirements.txt` + PySpark | `pyspark` | Linux | 95% |
| `*.csproj` (no Windows) | `dotnetcore` | Linux | 85% |
| `*.csproj` + `*.nuspec` | `nuget_dotnetcore` | Linux | 90% |
| `*.csproj` + Windows CI tags | `dotnet_windows` | Windows | 90% |
| `*.sln` + OctoPack | `dotnet_cn` | Windows | 95% |
| `*.sln` + WiX | `dotnet_msi` | Windows | 95% |
| `*.sln` + web publish | `dotnet_webpublish` | Windows | 90% |
| `*.sln` + CloudReady | `dotnet_cloudready` | Windows | 90% |
| `*.sln` + matrix build | `dotnet_matrix` | Windows | 90% |
| `*.sln` + library pkg | `dotnet_library` | Windows | 90% |
| `Dockerfile` (primary) | `docker_vm` | Linux | 80% |
| `*.ps1` (primary) | `powershell` | Windows | 85% |
| `.dr/` directory | `datarobot` | Linux | 95% |
| `*.groovy` + `pom.xml` | `groovy` | Linux | 90% |
| `*.sql` files (database scripts) | `database` (resolve to `database_{dbtype}` via §2c) | Linux | 85% |
| `*.cql` files | `database_cassandra` | Linux | 95% |
| `*.gsql` files | `database_tigergraph` | Linux | 95% |
| `*.json` + Elasticsearch mapping | `database_elasticsearch` | Linux | 90% |

Database SQL dialects (`*.sql` + Oracle/MSSQL/PostgreSQL/Teradata/Greenplum/SingleStore/MongoDB syntax) resolve to the matching `database_{oracle|mssql|postgres|teradata|greenplum|singlestore|mongodb}` TECH_STACK at 90% confidence — see §2c for dialect detection and §6 for image mapping.

#### 2b. Deployment Type Detection

| Indicator | Deployment Type | Confidence |
|---|---|---|
| `Chart.yaml` (Helm) | KOB | 95% |
| `Dockerfile` / `docker-compose.yml` | KOB | 80% |
| `manifest.yml` / `vars.yml` | PCF | 90% |
| `*.sql` / `liquibase.properties` / `flyway.conf` / `migrations/` | Database | 85% |
| `setup.py` + `twine` / publishing markers | Library | 85% |
| None of the above | Traditional | 60% |

**KOB sub-type (when deployment_type = KOB):**

| Indicator | KOB Sub-Type |
|---|---|
| ACE markers, ArgoCD config, `kobace` in existing CI | **KOB-ACE** |
| `Chart.yaml` + standard Helm values | **KOB** (standard) |
| Ambiguous | **ASK user**: "Is this standard KOB (Helm) or KOB-ACE (ArgoCD)?" |

**Multiple deploy patterns:** If indicators for more than one deploy type are found, ASK user to confirm which one.

#### 2c. Database Type Detection (when deployment_type = Database)

When database deployment is detected, the engine MUST ask the user to confirm the database type:

```
ASK USER:
  "Database deployment detected. Please confirm the database type:
   RDBMS:  oracle | mssqlserver | postgresql | greenplum | singlestore | teradata
   NoSQL:  mongodb | cassandra | elasticsearch | tigergraph
   DBTYPE = ?"
```

Also ask for optional database features:
```
ASK USER:
  "Enable production database precheck (validates DB connectivity before RFC deployment)? [yes/no, default: no]"
  "Enable breakglass database precheck (validates DB connectivity before emergency deployment)? [yes/no, default: no]"
```

#### 2d. Variable Auto-Resolution

Scan project files to resolve tech-specific variables automatically:

| TECH_STACK | Variable | Auto-Detect From |
|---|---|---|
| `maven` | `TARGET` | `pom.xml` `<build><directory>` (default: `target`) |
| `maven` | `MAVEN_CLI_OPTS` | Default: `--batch-mode --errors` |
| `maven` | `MAVEN_BUILD_CMD` | Default: `clean test-compile install package` |
| `maven` | `MAVEN_UNITTEST_CMD` | Default: `clean test` (REQUIRED for unit-test job — `devops-buildskill unittest maven` fails without it) |
| `python` | `REQ_FILE` | Scan for `requirements.txt`, `requirements-dev.txt`, `Pipfile` |
| `python` | `UNIT_TEST_FILE` | Scan for `tests/`, `test_*.py`, `pytest.ini`, `pyproject.toml [tool.pytest]` |
| `js` | `NPM_INSTALL_CMD` | `package-lock.json` exists → `npm ci`, else → `npm install` |
| `js` | `BUILD_CMD` | From `package.json` scripts.build (default: `npm run build`) |
| `js` | `TEST_CMD` | From `package.json` scripts.test |
| `js` | `TARGET` | From `package.json` scripts.build output (default: `dist`) |
| `dotnetcore` | `BUILD_CSPROJ` | Scan for `*.csproj` files |
| `dotnetcore` | `BUILD_CONFIGURATION` | Default: `Release` |
| `dotnetcore` | `UNIT_TEST_PROJ` | Scan for `*.Tests.csproj`, `*Test*.csproj` |
| `dotnetcore` | `NUGET_RESTORE_SOURCE` | Default: Artifactory NuGet source |
| `golang` | `BUILD_PARAMS` | Default: `-o $CI_PROJECT_DIR/target/$CI_PROJECT_NAME` |
| `golang` | `TEST_PARAMS` | Default: `-v -cover ./...` |
| `dotnet_cn` | `BUILD_PROJECT` | From `*.sln` filename (without extension) |
| `dotnet_cn` | `BUILD_PROJECT_EXT` | Default: `sln` |
| `dotnet_cn` | `BUILD_CONFIGURATION` | Default: `Release` |
| `dotnet_cn` | `BUILD_PLATFORM` | Default: `Any CPU` |
| `php` | `PHP_COMPOSER_INSTALL_CMD` | Default: `composer install` |
| `sbt` | `SBT_CMD` | Default: `clean package` |
| `cmake` | `CMake_Dir` | Scan for `CMakeLists.txt` location |
| `database_oracle` | `SONAR_LANG` | `oracle` (RDBMS code-quality mapping) |
| `database_mssql` | `SONAR_LANG` | `mssql` (RDBMS code-quality mapping) |
| `database_postgres`, `database_greenplum`, `database_singlestore`, `database_teradata` | `SONAR_LANG` | `rdbms` (RDBMS code-quality mapping) |
| `database_mongodb` | `SONAR_LANG` | `rdbms` (MongoDB code-quality mapping) |
| all RDBMS and NoSQL database types | `CX_PROJECT_NAME` | Existing CI or applicable database blueprint job-level variable; do not invent the Checkmarx onboarding path |

#### 2e. SONAR_LANG Resolution (Mandatory for code-quality)

`SONAR_LANG` is **MANDATORY** for the `code-quality` job. Resolve from tech stack:

**Linux mapping:**

| TECH_STACK | SONAR_LANG |
|---|---|
| `maven`, `gradle`, `ant`, `groovy` | `maven` |
| `sbt` | `sbt` |
| `python` | `python` |
| `pyspark` | `pyspark` |
| `js`, `angularjs`, `sharepoint` | `js` |
| `golang` | `golang` |
| `dotnetcore`, `nuget_dotnetcore` | `dotnetcore` |
| `cmake` | `cmake` |
| `ebs` | `ebs` |
| `imfa` | `imfa` |
| `sfdx` | `sfdx` |
| `rdbms`, `liquibase`, `flyway` | `rdbms` |
| `oracle` | `oracle` |
| `mssql`, `dacpac` | `mssql` |

**Windows mapping:**

| TECH_STACK | SONAR_LANG |
|---|---|
| `dotnet_cn`, `dotnet_msi`, `dotnet_library` | `dotnet` |
| `dotnet_cloudready` | `cloudready` |
| `dotnet_webpublish` | `webPublish` |
| `dotnet_matrix` | `matrix` |
| `dacpac` | `dacpac` |

If SONAR_LANG cannot be auto-resolved, ASK user:
```
"Could not auto-detect SONAR_LANG. Please provide:
 Linux:   cmake | ebs | imfa | ant | pyspark | rdbms | oracle | mssql |
          golang | maven | gradle | js | python | sbt | sfdx | dotnetcore
 Windows: dacpac | cloudready | dotnet | webPublish | matrix
 SONAR_LANG = ?"
```

#### 2f. Unit Test Detection

| TECH_STACK | Test Indicators | Action |
|---|---|---|
| `maven` | `src/test/` directory, `*Test.java` files | Generate unit-test job |
| `python` | `tests/` directory, `test_*.py`, `pytest.ini` | Generate unit-test job |
| `js` | `package.json` has `scripts.test` | Generate unit-test job |
| `dotnetcore` | `*.Tests.csproj` or `*Test*.csproj` exists | Generate unit-test job |
| `golang` | `*_test.go` files exist | Generate unit-test job |
| `database_*` | Database-specific test scripts (when supported by DB type) | Generate unit-test-db job |
| `database` | DBTYPE supports unit test (oracle, mssqlserver, postgresql, greenplum, tigergraph) | Generate unit-test job |
| Any | No test indicators found | Skip unit-test job, note in summary |

#### 2g. RFC Type Detection (when production deploy detected)

When production deployment is detected, ASK user:
```
"This project deploys to production. RFC (Change Management) is required.
 Is this a:
   1. Single RFC project — one change request covers entire deployment
   2. Multi-RFC project — separate change requests per environment/task
 RFC type = ?"
```

| RFC Type | Jobs Generated |
|---|---|
| **Single RFC** | `create-rfc`, `update-rfc-build`, `update-rfc-deploy`, `update-rfc-validate`, `closed-skip` |
| **Multi-RFC** | All single-RFC jobs + `check-rfc`, `check-rfc-review`, `check-rfc-deploy`, `check-rfc-validate` |

#### 2h. Database Production Deployment Detection

For **Database** types only: if database-skill will generate `prod_deploy` or `prod_rollback`, set `has_production_deploy = true` → triggers rfc-skill loading. Does NOT change RFC behavior for non-database types.

#### 2i. Database Artifact Detection

For **Database** types only: if database-skill generates `compile-package` with ProjBinaries → `has_artifact_publish = true`; if it generates deployment jobs → `has_artifact_retrieve = true`.

**Database artifact variables** (from existing pipeline or blueprint):

| Variable | Rule |
|---|---|
| RT_TYPE | `DB` |
| TARGET | Value from database artifact snippet (do NOT hardcode to `ProjBinaries`) |
| ARTIFACTNAME | User-supplied; shared between `compile-package` and artifact publication. Do NOT rename to `PACKAGE_NAME` |
| UPLOAD_FILENAME | `${ARTIFACTNAME}.zip` (derived, do NOT prompt separately) |
| UPLOAD_PATH | User-supplied Artifactory upload path |
| ARTIFACT_SECRET_PATH | User-supplied Vault path for Artifactory credentials |

`ARTIFACTNAME`, `UPLOAD_PATH`, `ARTIFACT_SECRET_PATH` are user-configurable GitLab CI/CD variables. Never emit `METADATA_FILENAME`. Artifact jobs are independent — no `needs`/`dependencies` between artifact and DB deploy jobs. This detection MUST NOT change artifact behavior for non-database types.

---

### Step 3 — Load Sub-Skills

Load required sub-skill definitions per §2.1 runtime loading procedure. The engine MUST verify sub-skills are available and read all required SKILL.md files before generating jobs. Do NOT proceed if sub-skills are missing.

---

### Step 4 — Generate Pipeline

Call each loaded sub-skill with all resolved context from Step 2. Each sub-skill receives `tech_stack`, `platform`, `deployment_type`, `db_type`, `resolved_image`, `resolved_variables`, and all detection flags. No user interaction except container inputs (§4c).

**Sub-skill invocation summary** (each returns stages + global_variables + jobs):

| Sub-Skill | Key Additional Inputs | Returns |
|---|---|---|
| **build-unittest** | has_tests, multi_stack | `build, verify-build` → compile, unit-test |
| **verify-skill** | SONAR_LANG (mandatory), has_dockerfile, has_k8s_manifests, has_web_endpoint | `verify-build, validate-deploy` → code-quality, malware-scan, xray-scan, sca-scan, sast-scan, inclusive-lang, dast |
| **container-skill** | **ASK USER:** HARBOR_NAMESPACE, APP_NAME, APP_VERSION, DOCKERFILE; HELM_DIR/REPO/TAG if Chart.yaml; CONTAINER_REGISTRY/CONTAINER_NAMESPACE if BuildKit | `build-docker, build-container, cleanup` → build-docker, build-container-image-buildkit, build-helm, cleanup-docker |
| **deploy-skill** | deployment_type, deploy_sub_type, kob_sub_type (mandatory for KOB) | KOB: deploy-k8s[-prod], rollback-k8s[-prod]; KOB-ACE: deploy-k8s-kobace[-prod], switch-route[-prod] (no rollback-k8s); PCF/Traditional/AKS/Azure/GitOps variants |
| **rfc-skill** | rfc_type, rfc_project_type (single/multi from §2g) | `rfc-submit, rfc-approve, rfc-update, rfc-close` → create-rfc, update-rfc-*, closed-skip; multi adds check-rfc-* |
| **artifact-skill** | PACKAGE_NAME, TARGET, ARTIFACT_SECRET_PATH | `publish-artifact, retrieve-artifact` |
| **infra-skill** | infra_type, TERRAFORM_DIR, ANSIBLE_DIR | `pre-provision, provision, configure, deploy, cleanup` → terraform-plan/apply/destroy, ansible-lint/deploy |
| **datarobot-skill** | dr_project_type, has_kong_gateway, has_mcp_hub, has_ml_training | `model-training, model-evaluation, model-register, inference, deploy, cleanup` |
| **database-skill** | db_type (confirmed), db_schema, db_script_path, precheck flags | `build, verify-build, prerfc-validate, deploy, predeploy-prod, deploy-prod` → compile-package-db, unit-test-db, deploy-rollback-db-np/prod, validate-approval-db, sql_code_review, optional precheck jobs |

#### Database Pipeline Rules

When `deployment_type == "Database"`, these rules apply across all sub-skill invocations:

| Rule | Details |
|---|---|
| **verify-skill scope** | Generate `code-quality` + `sast-checkmarx` only; omit malware-scan, xray-scan, inclusive-lang |
| **rfc-skill activation** | Triggered by §2h (`has_production_deploy`). Merge returned rfc stages into the pipeline |
| **artifact-skill activation** | Triggered by §2i. Use variables from §2i. No `needs`/`dependencies` between artifact and DB deploy jobs |
| **Stage ordering** | Preserve canonical order from §4j. Include rfc + artifact stages when those sub-skills are activated |
| **`allow_failure`** | Jobs with `when: always` MUST set `allow_failure: false`. Preserve template behavior for manual/conditional jobs |
| **Inline comments** | Every job-level variable in DB jobs MUST include same-line comment from database-skill's Inline Variable Comments |
| **Precheck independence** | Standard precheck and breakglass precheck are enabled independently |
| **Image pattern** | Use `image: $DATABASE_IMAGE_TAG`; set resolved DB image in `DATABASE_IMAGE_TAG`, never in `image:` directly |
| **No METADATA_FILENAME** | Never emit in any Database pipeline variable (global or job-level) |

#### 4j. Assemble Complete Pipeline

**MANDATORY structure** — every pipeline MUST include (in order):
1. Header comment (project, tech stack, platform, deployment type, date)
2. `default:` — `id_tokens: VAULT_ID_TOKEN: aud: $VAULT_ADDR`
3. `after_script:` — `curl -s $ERROR_CHECK_SH > hc.sh;source hc.sh`
4. `stages:` — only stages used by generated jobs, in canonical order
5. `variables:` — engine defaults + sub-skill returns merged
6. Jobs from sub-skill returns, in stage order

**Canonical stage order** (emit only used stages):
`build` → `verify-build` → `build-docker` → `build-container` → `publish-artifact` → `retrieve-artifact` → `pre-provision` → `provision` → `configure` → `rfc-submit` → `rfc-approve` → `prerfc-validate` → `pre-deploy` → `deploy` → `validate-deploy` → `switch-route` → `predeploy-prod` → `deploy-prod` → `go-live` → `rfc-update` → `rfc-close` → `post-deploy` → `post-deploy-prod` → `post-deployment` → `model-training` → `model-evaluation` → `model-register` → `inference` → `cleanup`

**Global variables** (always include):

| Variable | Value |
|---|---|
| VAULT_ADDR | `https://hcvault-nonprod.dell.com` |
| PROD_VAULT_ADDR | `https://vault.dell.com` |
| HARBOR_SERVER | `artifacts.dell.com` *(migrated from `harbor.dell.com` per cicd-constructs v3.0.0)* |
| CONTAINER_REGISTRY | `artifacts.dell.com` |
| ERROR_CHECK_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/error_handle%2Fhc.sh/raw?ref=v3.0.0` |
| BP_VERSION_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/blueprints_version.sh/raw?ref=v3.0.0` |
| VAULT_CLI_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/vaultcli%2Fvaultcli.sh/raw?ref=v3.0.0` |
| SONARCLI_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/sonar%2Fsonar.sh/raw?ref=v3.0.0` |
| SONAR_IMAGE_TAG | `artifacts.dell.com/cicd-1003184-oci-dev-local/trixie/cicd-images/sonar:latest` |
| JFROG_CLI_IMAGE | `artifacts.dell.com/cicd-1003184-oci-dev-local/debian-12/jfrog:latest` |
| SECURITY_TOOLS_IMAGE | `artifacts.dell.com/cicd-1003184-oci-dev-local/trixie/cicd-images/appsec:latest` |
| BASE_IMAGE | `artifacts.dell.com/cicd-1003184-oci-dev-local/trixie/cicd-images/python-3.13:latest` |
| XRAY_SCAN_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/xray-scan%2Fxray.sh/raw?ref=v3.0.0` |
| ART_AUTH_SH | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/auth%2Fart-auth.sh/raw?ref=v3.0.0` |
| ERROR_LOG | `https://gitlab.dell.com/api/v4/projects/189942/repository/files/self-help%2Fscan-msg.txt/raw?ref=v3.0.0` |

Plus: tech-stack image var from §2a, SONAR_LANG, and sub-skill-specific globals. Only emit variables actually needed by generated jobs.

**Windows:** Same addresses; replace `.sh` with `.ps1` equivalents. Omit `image:` — uses runner tags only.

**Production Vault override:** Any job targeting production (name contains `prod`, `deployment_tier: production`, or references `$PROD_VAULT_ADDR`) MUST add `id_tokens: VAULT_ID_TOKEN: aud: $PROD_VAULT_ADDR` and `variables: VAULT_ADDR: $PROD_VAULT_ADDR`.

#### 4k. Post-Generation Validation (MANDATORY — run before Step 5)

After assembling the complete pipeline YAML and **before** presenting it to the user, run the following validation checks. If any check fails, fix the violation before proceeding — do NOT present a non-compliant pipeline to the user.

**V1 — Stage Order Validation (FR-08)**

Parse the `stages:` block. For every ordered pair `(A, B)` present in it, verify `A` also precedes `B` in the canonical order defined in §4j. On mismatch, fail with: *"Stage order violation: '{stage_B}' appears before '{stage_A}' but canonical order requires '{stage_A}' first. Fix the stages: block."*

**V2 — Mandatory Structure Validation**

Verify the generated YAML contains all mandatory structural elements from §4j:

| # | Element | Check | Fail action |
|---|---------|-------|-------------|
| 1 | Header comment | First line starts with `#` and contains project name | Add header |
| 2 | `default:` block | Contains `id_tokens: VAULT_ID_TOKEN: aud: $VAULT_ADDR` | Add default block |
| 3 | `after_script:` | Contains `curl -s $ERROR_CHECK_SH > hc.sh;source hc.sh` | Add after_script |
| 4 | `stages:` block | Present and non-empty | STOP — assembly failed |
| 5 | `variables:` block | Contains all global variables from §4j table | Add missing variables |
| 6 | At least one job | At least one job block exists | STOP — assembly failed |

**V3 — Variable Override Validation (FR-09, FR-11)**

For each generated job, verify:
- Job-level variables do NOT redefine global variables with the same value (redundant)
- All variable references (`$VAR_NAME`) in `script:` blocks have a corresponding definition in either the job's `variables:` or the global `variables:` block
- Tech-stack image variable from §6 is present in global variables and matches the detected tech stack

**V4 — Rule Compliance Validation (§7 binding rules)**

| Rule | Validation | Fail action |
|---|---|---|
| §7.1 Sub-skills only | Every job name matches a known sub-skill template (or is marked `# CUSTOM JOB`) | Flag unknown jobs |
| §7.3 RFC = deploy-prod rules | All RFC jobs use the exact `rules:` block from §7.3 | Fix rules block |
| §7.4 verify-build allow_failure | No job in `verify-build` stage has `allow_failure: true` | Set to `false` |
| §7.5 KOB vs KOB-ACE | No mixing of KOB and KOB-ACE patterns | STOP — ask user |
| §7.6 Database mandatory jobs | If database pipeline: `sql_code_review` and `validate-approval-db` present | Restore missing jobs |

**V5 — Production Vault Override Validation**

For every job targeting production (name contains `prod`, stage is `deploy-prod` or `predeploy-prod`, or references `$PROD_VAULT_ADDR`):
- Verify `id_tokens: VAULT_ID_TOKEN: aud: $PROD_VAULT_ADDR` is present
- Verify `VAULT_ADDR: $PROD_VAULT_ADDR` is set in the job's variables or script
- Fix automatically if missing

**V6 — JIRA/GitLab API Contract Validation (when Jira ID was provided)**

Delegated to `jira-sdlc-skill`'s V6 contribution. The sub-skill verifies that `JIRA_BASE_URL`/`ISSUE_ID`/`GIT_API_BASE`/`ENCODED_PATH` are set, every API call has a fallback (MCP or curl), and every API failure is non-blocking. It reports `PASS`/`FAIL` back into this engine's validation summary.

**Validation Summary:**

After all checks pass (or auto-fixes are applied), record the validation results for inclusion in the change-summary:

```
=== Post-Generation Validation ===
V1 Stage Order:       PASS (N stages in canonical order)
V2 Mandatory Structure: PASS (all 6 elements present)
V3 Variable Overrides:  PASS (no orphan references, no redundant overrides)
V4 Rule Compliance:     PASS (§7.1–§7.6 verified)
V5 Prod Vault Override: PASS (N production jobs verified)
V6 API Contracts:       PASS (JIRA + GitLab endpoints configured)
Auto-fixes applied:   {N} (list each fix)
```

If any check cannot be auto-fixed, STOP and report the violation to the user before proceeding to Step 5.

---

### Step 5 — Single Confirmation

Present ONE compact summary, ask ONE question:

```
=== CI/CD Pipeline Generated ===

Jira Spec:   {ISSUE_ID — summary}            # only if Jira ID was provided
Project:     {name}
Tech Stack:  {TECH_STACK} (detected from {evidence})
Platform:    {Linux / Windows}
Deployment:  {type} (detected from {evidence})

Build Jobs (single stack):
  compile          → {TECH_STACK} build using devops-buildskill
  unit-test        → {TECH_STACK} tests using devops-buildskill    # or "skipped — no tests found"

Build Jobs (multi-stack — names suffixed with tech stack):
  compile-{stack}    → {TECH_STACK} build using devops-buildskill
  unit-test-{stack}  → {TECH_STACK} tests using devops-buildskill

Security Jobs (from verify-skill):
  code-quality     → SonarQube SAST + coverage
  malware-scan     → artifact malware scan
  xray-scan        → JFrog Xray OSS vulnerability scan
  sca-scan         → Snyk SCA dependency scan
  sast-scan        → Snyk SAST static analysis
  sast-checkmarx   → Checkmarx SAST (when configured, including supported database blueprints)
  inclusive-lang   → inclusive language check
  dast             → HCL AppScan DAST (web apps only)    # or "skipped — not a web app"

Database (if Database deployment — jobs from §4i, verification from §4b, RFC from §4e, artifacts from §4f):
  DB Type: {user-confirmed} | Precheck: {enabled/disabled} | Breakglass: {enabled/disabled}
  Jobs: compile-package-db, unit-test-db, deploy-rollback-db-np/prod, validate-approval-db,
        sql_code_review, code-quality, sast-checkmarx, {rfc jobs if prod}, {artifact jobs if applicable}

Key Variables (auto-detected):
  {VAR}: {value}  ← from {source}
  {VAR}: {value}  ← default

Output: {.gitlab-ci.yml / gitlab-ci-copy.yml}

Looks good? (yes / no)
```

**This is the ONLY prompt.** If the user says "yes", write the file. If "no", ask what to change.

---

### Step 6 — Write Pipeline + SDLC Delivery

#### 6a. Write Pipeline File (always)

Write the generated `.gitlab-ci.yml` (or `gitlab-ci-copy.yml` in Update mode) in the target directory (submodule directory when a Jira ID was provided, CWD otherwise).

#### 6b. SDLC Delivery (delegated to `jira-sdlc-skill`, Jira ID only)

If a Jira ID was supplied, invoke **`jira-sdlc-skill` Phase 6** (6b → 6i): generate `change-summary.md`, upload spec artifacts as JIRA attachments, dual commit+push (submodule + ai/), update workspace-root submodule refs, create MRs in both repos targeting `develop`, backfill MR links into `change-summary.md`, post Jira wiki-markup comment, transition to **READY TO DEPLOY**, and display final status. The sub-skill returns `mr_links[]`, `change_summary_path`, and `final_state`.

If no Jira ID was provided, stop after 6a and show manual `git add`/`commit`/`push` steps for the user.

#### 6c. Post-Merge Completion (delegated to `/sdd-wrap-up`)

After MRs are merged, run **`/sdd-wrap-up {ISSUE_ID}`** — do NOT reimplement wrap-up logic inline. Wrap-up owns: two-phase MR verification → branch cleanup → `.gitmodules` reset → JIRA coding summary + `AI-Delivered` label → transition to **COMPLETE** → Confluence page → ai/ repo commit. Prerequisites: `GIT_PAT`, `JIRA_PAT`, optionally `CONFLUENCE_PAT` + `CONFLUENCE_PARENT` in `local.config`; all MRs must be `merged`. If wrap-up is not invoked, the issue remains at READY TO DEPLOY.

---

## 4. Update Mode

When `.gitlab-ci.yml` already exists, the engine generates a proposed replacement and presents it for **mandatory user review** before overwriting the original. Custom jobs are preserved — the user reviews the diff and approves or corrects before the replacement happens.

Update Mode doubles as the **maintenance channel** for existing pipelines: every time it runs, it applies a *latest-changes sweep* (§4.2 step 9) that rewrites outdated image hosts, injects required globals, and refreshes standard jobs to the current `sub-skills/` definitions. For example, the harbor→artifacts container registry migration (cicd-constructs v3.0.0) is applied automatically whenever Update Mode runs on an older pipeline — users do not need to hand-edit the YAML.

### 4.1 — Parse & Detect

1. **Create a backup copy** of the existing pipeline:
   ```bash
   cp .gitlab-ci.yml .gitlab-ci.yml.backup
   ```
2. **Parse** the existing `.gitlab-ci.yml` fully — extract all jobs, stages, variables, includes, and custom blocks
3. **Classify every job** in the existing pipeline:

   | Classification | Criteria | Action |
   |---|---|---|
   | **Standard (generated)** | Job matches a sub-skill template (build, verify, container, deploy, rfc, artifact, infra, datarobot, database) | Replace with updated inline version |
   | **Custom (user-defined)** | Job does NOT match any sub-skill template — unique job name, custom scripts, project-specific logic | **Preserve unchanged** — carry forward into the new pipeline |
   | **Legacy (template-based)** | Job uses `extends:` or `include:` referencing template repos | Replace with inline equivalent |
   | **Mandatory (missing)** | Required job not present in existing pipeline (e.g., `sql_code_review`, `validate-approval-db` for database) | Restore automatically |

4. **Detect** legacy patterns (`include:` + `extends:`) for migration

### 4.2 — Generate Proposed Pipeline

5. **Migrate** standard build/test jobs to inline — preserve all user variables
6. **Restore mandatory jobs automatically** when missing. For database pipelines this includes `sql_code_review` and `validate-approval-db`; restoration is not presented as an optional user choice.
7. **Preserve** all custom (user-defined) jobs **unchanged** — copy them verbatim into the proposed pipeline at their original stage position
8. **Remove** `include:` entries for template repos (no longer needed)
9. **Apply the "latest-changes sweep"** — refresh every standard job + global variable to match the current sub-skill definitions. This is what turns Update Mode into the maintenance channel for old pipelines. Always perform these sweeps, even if the user's YAML is otherwise valid:

   | Sweep | What to update | Why |
   |---|---|---|
   | **Container registry migration** | Rewrite every `harbor.dell.com/devops-images/debian-12/{foo}:{tag}` image value to the matching `artifacts.dell.com/cicd-1003184-oci-dev-local/...` path from v3.0.0 `global-variables.yml` (python-3.11→python-3.13, dotnet-8-sdk→dotnet-10, nodejs-20→node-24, go-1.23→go-1.27, java-11/21→java-17, sonar-3.11→sonar, devsecops→appsec, toolbox→utils, docker→docker-29, rapid-db→db-engine, datarobot:v12.0.0→datarobot:latest, etc.). Also update `HARBOR_SERVER: harbor.dell.com` → `HARBOR_SERVER: artifacts.dell.com` and `DOCKER_CONTENT_TRUST_SERVER: notary.harbor.dell.com` → `notary.artifacts.dell.com`. | Dell migrated `harbor.dell.com` → `artifacts.dell.com`. Pipelines generated before this migration pull from a decommissioned registry. |
   | **KOB rollback `allow_failure`** | Ensure every rollback job (`rollback-k8s`, `rollback-k8s-prod`, `rollback-pcf`, `rollback-pcf-prod`) has `allow_failure: true` set. Add it if missing. | Rollback is a manually-triggered safety net. Without `allow_failure: true` the manual job becomes mandatory and blocks pipeline completion. |
   | **PLX job rewrite** | If `plx-switch-route` / `plx-go-live` download `plx` from `${SCRIPT_URL}/plx`, rewrite them to use `$PLX_CLI` with the proper `devops-cf-cli` / `devops-k8s-cli` auto-select (VAULT_PCF_SPACE vs VAULT_CONFIG_PATH) + login/logout, matching the current deploy-skill templates. | Older generations referenced an unresolvable `${SCRIPT_URL}/plx`. The upstream `.plx-integration` template uses `$PLX_CLI` from Artifactory. |
   | **Required globals** | Emit `SCRIPT_URL` whenever any VM/.NET/VM-snapshot deploy job is in the pipeline, and `PLX_CLI` whenever a PLX job is in the pipeline. Use the defaults declared in the deploy-skill output contract if the existing pipeline is missing them. | Prevents runtime "unknown variable" failures for `${SCRIPT_URL}/*.zip` downloads and PLX binary fetches. |
   | **Sub-skill refresh** | For every job classified as **Standard** in §4.1, regenerate it from the currently-loaded sub-skill SKILL.md (scripts, images, rules, tags). User-overridden job-level `variables:` are preserved; everything else is refreshed. | Picks up upstream fixes in `sub-skills` without the user having to re-run `/sdd-cicd-setup` from scratch. |

   The sweep operates purely at the YAML level — it is a deterministic transform driven by the current sub-skill definitions. Custom jobs (§4.1 row 2) are never touched by the sweep.

10. **Write** to `gitlab-ci-copy.yml` — the original `.gitlab-ci.yml` is NOT modified yet

### 4.3 — Mandatory User Review (REQUIRED — do NOT skip)

This step is **mandatory**. The engine MUST present the diff and wait for explicit user approval before replacing the existing pipeline. Do NOT auto-replace.

11. **Present a structured diff** showing what changed between the existing `.gitlab-ci.yml` and the proposed `gitlab-ci-copy.yml`:

```
=== Pipeline Update Review (MANDATORY) ===

Existing pipeline: .gitlab-ci.yml
Proposed pipeline: gitlab-ci-copy.yml
Backup created:    .gitlab-ci.yml.backup

=== Job Classification ===
| Job Name              | Classification | Action Taken              |
|-----------------------|---------------|---------------------------|
| compile               | Standard      | Updated to inline v5.0.0  |
| unit-test             | Standard      | Updated to inline v5.0.0  |
| code-quality          | Standard      | Updated to inline v5.0.0  |
| my-custom-deploy      | Custom        | PRESERVED unchanged       |
| custom-notify-slack   | Custom        | PRESERVED unchanged       |
| sql_code_review       | Mandatory     | RESTORED (was missing)    |

=== Changes Summary ===
Jobs updated:   {N} (standard jobs migrated to inline / refreshed from latest sub-skills)
Jobs preserved: {N} (custom jobs carried forward unchanged)
Jobs restored:  {N} (mandatory jobs that were missing)
Jobs removed:   {N} (legacy template references)
Variables:      {N} added, {N} removed, {N} changed

=== Latest-Changes Sweep (§4.2 step 9) ===
Container registry:   {N} image values rewritten harbor.dell.com → artifacts.dell.com
Rollback allow_failure: {N} rollback jobs received allow_failure: true
PLX rewrite:          {yes/no — plx jobs switched from ${SCRIPT_URL}/plx to $PLX_CLI}
Globals injected:     {list — e.g. SCRIPT_URL, PLX_CLI, CONTAINER_REGISTRY}

=== Diff (key changes) ===
{Show the meaningful diff between .gitlab-ci.yml and gitlab-ci-copy.yml}
{Highlight: added jobs, removed includes, changed variables, restored mandatory jobs}
{Mark custom jobs clearly: "# CUSTOM JOB — preserved from existing pipeline"}

Please review and choose:
  1. APPROVE — replace .gitlab-ci.yml with the proposed pipeline
  2. REJECT  — keep the existing .gitlab-ci.yml, discard proposed changes
  3. EDIT    — I'll make corrections first, then approve
```

12. **Wait for user response:**

| User Response | Action |
|---|---|
| **APPROVE** (or "yes", "looks good", "go ahead") | Replace `.gitlab-ci.yml` with `gitlab-ci-copy.yml`. Delete the copy file. Keep `.gitlab-ci.yml.backup` for safety. |
| **REJECT** (or "no", "keep existing") | Delete `gitlab-ci-copy.yml`. Keep original `.gitlab-ci.yml` unchanged. Delete `.gitlab-ci.yml.backup`. Report: "Update cancelled — existing pipeline preserved." |
| **EDIT** (or "let me fix", "corrections needed") | Wait for user to edit `gitlab-ci-copy.yml`. When user confirms edits are done, re-present the diff for final approval. |

13. **After approval — replace the original:**
    ```bash
    mv gitlab-ci-copy.yml .gitlab-ci.yml
    ```
    The backup `.gitlab-ci.yml.backup` remains in the working directory for the user's reference until they choose to delete it.

### Legacy Pattern Detection

| Pattern | Action |
|---|---|
| `extends: .compile-package-{tech}` | Extract tech, generate inline replacement |
| `extends: .compile-package` + `TECH_STACK:` | Already unified, convert to fully inline |
| `include:` to `devops/job-templates` | Remove (not needed with inline jobs) |
| `include:` to `devops/file-templates/yml` | Remove |
| `include:` to `1003184/code/skills/cicd-skills` | Remove |
| Non-build/test `include:` entries | Preserve |

---

## 5. Multi-Stack Detection

When multiple build files are found (e.g., `pom.xml` + `package.json`):

1. Detect all stacks
2. Call `build-unittest` once per stack with `multi_stack: true`
3. Call `verify-skill` once per stack with `multi_stack: true`
4. Job names are suffixed with the tech stack: `compile-{tech_stack}`, `unit-test-{tech_stack}`, `code-quality-{tech_stack}`, etc.
5. Non-tech-stack-specific scans (`malware-scan`, `inclusive-lang`, `dast`) are generated only once
6. Deduplicate global variables (shared bootstrap URLs, Vault addresses)
7. Include all required image variables (one per tech stack + shared security images)
8. Present all in the single confirmation prompt

```
Build Jobs:
  compile-maven       → maven build
  unit-test-maven     → maven tests
  compile-js          → js build
  unit-test-js        → js tests

Security Jobs:
  code-quality-maven  → SonarQube scan (maven)
  code-quality-js     → SonarQube scan (js)
  xray-scan-maven     → Xray scan (maven)
  xray-scan-js        → Xray scan (js)
  sca-scan-maven      → Snyk SCA (maven)
  sca-scan-js         → Snyk SCA (js)
  sast-scan-maven     → Snyk SAST (maven)
  sast-scan-js        → Snyk SAST (js)
  malware-scan        → malware scan (once)
  inclusive-lang      → inclusive language (once)
```

---

## 6. Image Resolution

Since the generated pipeline no longer includes `cicd-constructs.yml`, image variables must be defined inline in `variables:`. The `image:` field on each job references the variable; the `variables:` section defines its real value. **Only emit the image variable(s) that the generated jobs actually use.**

All values come from cicd-constructs v3.0.0 `global-variables.yml`. Registry base: `artifacts.dell.com/cicd-1003184-oci-dev-local/` (migrated from `harbor.dell.com`). Path prefix is `trixie/cicd-images/` unless noted `debian-12/`.

| TECH_STACK | Variable (used in `image:` as `$VAR`) | Image path suffix |
|---|---|---|
| `maven`, `ant`, `gradle`, `build_jar_maven` | `JAVA_JDK_IMAGE` | `java-17:latest` |
| `sbt` | `SBT_IMAGE` | `sbt:latest` |
| `python`, `pyspark`, `az` | `PYTHON_IMAGE` | `python-3.13:latest` |
| `shell`, `confluence_embedder`, `cmake`, `database_elasticsearch` | `BASE_IMAGE` *(also `CMAKE_IMAGE` for cmake)* | `python-3.13:latest` |
| `js`, `angularjs`, `sharepoint` | `NODE_IMAGE` | `node-24:latest` |
| `dotnetcore`, `nuget_dotnetcore` | `DOTNET_SDK_IMAGE` | `dotnet-10:latest` |
| `golang` | `GO_IMAGE` | `go-1.27:latest` |
| `docker_vm` | `DOCKER_IMAGE` | `docker-29:latest` |
| `datarobot*` | `DATAROBOT_IMG` | `debian-12/datarobot:latest` |
| `ebs`, `imfa` | `SSH_UTIL_IMAGE` | `utils:latest` |
| `database_oracle` | `ORACLE_IMAGE` | `db-engine:latest` |
| `database_mssql` | `MSSQL_IMAGE` | `db-engine:latest` |
| `database_postgres`, `database_greenplum` | `RAPID_POSTGRESQL_IMAGE` | `db-engine:latest` |
| `database_teradata` | `TERADATA_IMAGE` | `db-engine:latest` |
| `database_singlestore` | `SINGLESTORE_IMAGE` | `db-engine:latest` |
| `database_cassandra` | `CASSANDRA_IMAGE` | `db-engine:latest` |
| `database_mongodb` | `MONGO_IMAGE` | `db-engine:latest` |
| `database_tigergraph` | `TIGERGRAPH_IMAGE` | `db-engine:latest` |
| `groovy` | `GROOVY_IMG` | *group-level CI/CD var — not in global-variables.yml* |
| `php` | `PHP_8_IMG` | *group-level CI/CD var — not in global-variables.yml* |

Windows tech stacks (`dotnet_*`, `powershell`, `tomcat-windows`, etc.) use runner tags only — do NOT emit `image:`.

**Preserve user-supplied image vars** from the existing `.gitlab-ci.yml` (e.g., `$JAVA_21_JDK_IMG` in java-blueprint projects → resolve to `artifacts.dell.com/cicd-1003184-oci-dev-local/trixie/cicd-images/java-17:latest`).

---

## 7. Standard Rules

### 7.1 Sub-Skills Are the ONLY Source of Jobs

Every generated job MUST come from a loaded sub-skill SKILL.md. The engine MUST NOT invent, create, or improvise new job scripts.

| Situation | Action |
|---|---|
| Standard project | Generate jobs **only** from loaded sub-skill templates |
| Job exists in sub-skill | Use the sub-skill's exact script — do NOT modify |
| Requirement not covered by any sub-skill | **ASK user**: "Not covered by existing sub-skills. Create custom job?" |
| User explicitly asks for custom requirement | Create with marker: `# CUSTOM JOB — not from standard sub-skill template` |

### 7.2 Container Jobs Require User Input

`build-docker`, `build-container-image-buildkit`, and `build-helm` MUST NOT be auto-generated with empty/guessed variables. Always ask user for `HARBOR_NAMESPACE`, `APP_NAME`, etc. before generating. Only generate `build-helm` if `Chart.yaml` is present AND user confirms.

### 7.3 RFC Rules = Deploy-Prod Rules

All RFC jobs MUST use the same `rules:` block as deploy-prod:
```yaml
rules:
  - if: $CI_COMMIT_TAG
    when: never
  - if: $CI_COMMIT_BRANCH =~ /^([mM]ain).*$/
    when: manual
```

Applies to ALL RFC jobs: `create-rfc`, `check-rfc`, `update-rfc-build`, `check-rfc-review`, `check-rfc-deploy`, `update-rfc-deploy`, `check-rfc-validate`, `update-rfc-validate`, `closed-skip`.

### 7.4 Verify-Build Jobs: allow_failure: false

ALL jobs in `verify-build` stage MUST have `allow_failure: false`. No exceptions.

```yaml
# CORRECT — skip entirely via when: never
rules:
  - if: '$SKIP_SCAN_{TYPE} =~ /true/i'
    when: never
  - if: $CI_COMMIT_BRANCH
    when: always

# WRONG — never use allow_failure: true in verify-build
allow_failure: true    # ← PROHIBITED
```

### 7.5 KOB vs KOB-ACE: Never Mix

| Rule | Details |
|---|---|
| KOB-ACE pipeline | Use `k8s-kobace-*` CLI commands. Do NOT add `rollback-k8s`. |
| KOB standard pipeline | Use `rollback-k8s`. Do NOT add `k8s-kobace-*` jobs. |
| `build-helm` | Only if `Chart.yaml` is present. Ask user if unclear. |

### 7.6 Database Pipeline Rules

See Database Pipeline Rules table in Step 4. Additional constraints: one DBTYPE per pipeline, mandatory `sql_code_review` + `validate-approval-db` for every DBTYPE.

---

## 8. Error Handling

All errors are handled within sdd-cicd-setup — the user sees a clear message, not raw errors.

| Situation | Action |
|---|---|
| Cannot detect tech stack | Show project files found, ask: "What technology does this project use?" |
| Multiple .NET variants | Show the 2-3 most likely, ask user to pick |
| No test infrastructure found | Skip unit-test job, note in summary |
| Existing pipeline too complex | Migrate build/test only, preserve everything else |
| Confidence < 70% | Show top 3 candidates with evidence, ask user to pick |
| Project path invalid | Report error, suggest correct path |
| KOB vs KOB-ACE ambiguous | Ask user: "Standard KOB (Helm) or KOB-ACE (ArgoCD)?" |
| Multiple deploy patterns | List detected patterns, ask user to pick one |
| RFC type unknown | Ask user: "Single-RFC or Multi-RFC?" |
| Database type unknown/unconfirmed | List supported DBTYPEs (Oracle/MSSQL/Postgres/Teradata/Greenplum/SingleStore/Cassandra/MongoDB/Elasticsearch/TigerGraph), ask user to confirm |
| Database scripts not found | Skip database deployment jobs, note it in summary |
| Optional database jobs not enabled | Skip validate-deployment-env-db and validate-deployment-env-db-breakglass jobs if not enabled by user |
| Sub-skills not available | Auto-download from GitLab. Only error if both download methods fail. |
| SONAR_LANG unresolvable | Ask user to provide from supported values list |
| `build-helm` unclear | Ask user: "Does this project need Helm chart packaging?" |
| Unsupported DBTYPE | Report error, list supported types |
| Jira issue not found | Report: "Issue {ID} not found." Continue without Jira context — fall back to auto-detect only |
| Jira MCP unavailable | Report: "Jira server not reachable." Continue without Jira context — fall back to auto-detect only |
| Jira hint conflicts with auto-detection | Present both values, ask user to pick. E.g., "Jira spec says Python but project has pom.xml (Java). Which is correct?" |
| Jira comment post fails | Report but do NOT fail — pipeline generation is the critical action |
| Story-to-Spec conversion fails | Report error, continue with original issue ID if possible |
| Jira transition fails | Report but do NOT fail — pipeline generation takes priority over Jira state |
| Branch already exists | Auto-resolve: checkout existing branch and rebase from remote. Never ask user — see `jira-sdlc-skill` Phase 0g step 2 |
| Git push rejected | Non-fast-forward: auto-rebase with `git pull --rebase origin develop-{ISSUE_ID}` then retry push. If still rejected, retry with `--force-with-lease`. Auth error (401/403): fall back to `gitlab` MCP server for push |
| MR creation fails (curl) | Fall back to `gitlab` MCP server for MR creation. If MCP also fails, STOP with error and MR creation URL: `https://{host}/{path}/-/merge_requests/new?merge_request[source_branch]=develop-{ISSUE_ID}&merge_request[target_branch]=develop` |
| `local.config` missing `GIT_PAT` | Fall back to `gitlab` MCP server for all Git API operations (branch creation, push, MR creation). If MCP also unavailable, STOP with error — do NOT skip Git operations or show manual steps |
| MR merge not confirmed | Issue stays at "Ready to Deploy" — no action needed. User can re-invoke to check and transition |
| ai workspace not found | Report: "ai/ directory not found at workspace root." If Jira ID provided, write pipeline in current directory and skip commit/push/MR. Suggest running `/sdd-create-pod-knowledge` to set up workspace |
| Submodule not registered | Report: "Project not registered as submodule under ai/submodules/." Offer to register it: `cd ai && git submodule add {remote_url} submodules/{project}` |
| Submodule dirty state | Auto-commit WIP with `JIRA#{OTHER_ID}; WIP: save before switching` if on different feature branch. Ask user if on develop/main with dirty state |
| ai/ repo push fails | Fall back to `gitlab` MCP server for push. If MCP also fails, report error — pipeline file in submodule is the critical artifact, ai/ push failure is non-blocking |
| change-summary.md write fails | Report but do NOT fail — pipeline generation is the critical action. Suggest creating manually |
| Workspace root .gitmodules update fails | Skip silently — submodule and ai/ MRs are sufficient for the workflow |

---

## 9. Speed Optimization

| Rule | How |
|---|---|
| **Batch file reads** | Read multiple project files in parallel — NOT one at a time |
| **Single-pass scan** | Detect tech stack, deployment type AND variables in ONE directory scan |
| **Conditional loading** | Only read sub-skill SKILL.md files that detection results require |
| **No redundant reads** | If a file was read for detection, do NOT re-read for variable resolution |
| **Parallel sub-skill reads** | When multiple sub-skills needed, read SKILL.md files in parallel |
| **Cache detection results** | Store all results in memory — do NOT re-detect during generation |
| **Direct generation** | Once detection complete, generate full pipeline in one pass |
| **Minimal confirmation** | Keep summary compact — do NOT generate verbose output |

Target: complete pipeline generation in under 30 seconds for standard projects.

---

## 10. Constraints

| # | Constraint | Detail |
|---|---|---|
| 1 | ONE entry point | Users only know `/sdd-cicd-setup` |
| 2 | ONE confirmation prompt (Generate) / Mandatory diff review (Update) | Generate mode: show summary, ask yes/no. Update mode: present diff, require explicit approval before replacing |
| 3 | Auto-detect everything | Tech stack, platform, deployment, variables, paths, images |
| 4 | Smart defaults | Every variable has a sensible default |
| 5 | No sub-skill exposure | `build-unittest`, `verify-skill`, `container-skill`, `deploy-skill`, `rfc-skill`, `artifact-skill`, `infra-skill`, `datarobot-skill`, `database-skill` are all internal |
| 6 | No `include:` / `extends:` | Generated YAML is fully inline |
| 7 | No external YAML dependencies | The output is self-contained |
| 8 | Mandatory review before replace | Update Mode writes to `gitlab-ci-copy.yml`, presents diff for mandatory user review, then replaces `.gitlab-ci.yml` only after explicit approval. Custom jobs are always preserved. |
| 9 | Scope boundary | Only CI/CD pipeline generation (§1.5) |
| 10 | All rules in §7 are mandatory | §7.1–§7.6 are binding constraints, not guidelines |
| 11 | Post-generation validation mandatory | §4k validation (V1–V6) MUST pass before presenting pipeline to user. No non-compliant pipeline may be delivered. |
