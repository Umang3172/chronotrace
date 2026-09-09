# DEPLOY_TASK.md — autonomous AWS deployment brief

You are a Claude Code session starting fresh in `/Users/umangsingh/Chronotrace`.
This file is your complete brief. Execute it end to end. Decide on your own;
interrupt the user only where section 2 explicitly permits it.

---

## 0. Mission

Two deployments, one verification pass, one honest write-up.

| # | Deliverable | Risk | Required? |
|---|---|---|---|
| A | Dashboard live on AWS Amplify Hosting | Low | Yes — must ship |
| B | Agent live on Bedrock AgentCore Runtime | **High** | No — best effort, timeboxed |
| C | Playwright verification + screenshot of A | Low | Yes |
| D | README/docs updated to match what is *actually* live | — | Yes |
| E | AWS budget guardrail | Low | Yes |
| F | `DEPLOY_SUMMARY.md` written for the user | — | Yes |

Do them in order **A → E → C → B → D → F**. E moves early (cost guardrail before
the expensive step). B is last because it is the only task that can fail, and a
failed B must not block A/C/D shipping.

---

## 1. Non-negotiable honesty rules

This repository has an established culture of not claiming things that are not
true — see `README.md` §"What is *not* wired to AWS" and `HANDOVER.md` §12,
which is a list of exactly these mistakes made previously. Do not add to it.

1. **Never describe a deployment as working unless you invoked it and saw a real
   response.** A successful `create`/`deploy` API call is not evidence the thing
   responds. Invoke it. Paste the actual output.
2. **Never stub, mock, fake, or "simulate" a deploy step to make the task look
   complete.** A blocked step is a valid, reportable outcome. A faked one is not.
3. If Task B fails, **leave `README.md:638` (`**Not yet deployed.**` paragraph)
   byte-for-byte unchanged.** It is currently accurate. Making it inaccurate is
   strictly worse than any deploy failure.
4. Do not quote `docs/results/` numbers anywhere — that is reference-policy
   output, not a model result.
5. In `DEPLOY_SUMMARY.md`, state failures as plainly as successes.

---

## 2. Autonomy

Decide everything yourself: naming, regions, IAM policy shape, retry strategy,
whether a partial result is worth shipping.

**Stop and ask the user only if:**
- AWS returns an authentication/authorization error you cannot resolve in 2
  attempts (likely means the IAM user lacks a permission — report which action).
- A step would cost materially more than ~$5 in one go.
- A step would delete or overwrite something outside this repo.
- Task B would require making the repo public, changing the GitHub remote, or
  committing a credential.

Otherwise: proceed, and record the decision in the summary.

---

## 3. Credentials

The user downloaded IAM access keys to:

```
~/Downloads/chronotrace-deploy_accessKeys.csv
```

Load them **without printing them**:

```bash
CSV="$HOME/Downloads/chronotrace-deploy_accessKeys.csv"
unset AWS_BEARER_TOKEN_BEDROCK          # CRITICAL — see below
export AWS_ACCESS_KEY_ID=$(tail -n +2 "$CSV" | head -1 | cut -d, -f1 | tr -d '"\r' | xargs)
export AWS_SECRET_ACCESS_KEY=$(tail -n +2 "$CSV" | head -1 | cut -d, -f2 | tr -d '"\r' | xargs)
export AWS_DEFAULT_REGION=us-east-1
export AWS_REGION=us-east-1
aws sts get-caller-identity              # MUST print the chronotrace-deploy ARN
```

If `get-caller-identity` fails, stop and report — everything downstream depends
on it.

**The `unset` is critical.** Current botocore gives `AWS_BEARER_TOKEN_BEDROCK`
precedence for `bedrock-runtime` only. With both credential types set, model
calls authenticate as the Bedrock API key while `sts`/`iam`/`ecr`/`amplify`
authenticate as the IAM user — everything half-works and errors point nowhere.

**Security rules:**
- Never `echo`, `cat`, or log the key values. Never write them to a file in the
  repo. Never put them in a commit, a screenshot, or `DEPLOY_SUMMARY.md`.
- `.env` is gitignored (`.gitignore:17`); nothing else is. Do not create
  `.env.deploy`, `creds.sh`, or similar in the repo root.
- The user will delete this IAM user after submission. Do not build anything
  that depends on these keys continuing to exist.

---

## 4. Ground truth about this repo

Verified on 2026-09-09. Trust this over your assumptions, but re-verify anything
you are about to depend on.

- **Stack**: Python 3.12 via `uv`; Next.js 14 static-export dashboard in `ui/`.
- **Dashboard build**: `ui/package.json` → `prebuild` copies
  `eval-results/incidents.json` to `ui/public/`, falling back to the committed
  snapshot. `next build` emits a static site to `ui/out/`. No runtime, no
  credentials, no model needed.
- **Amplify build spec**: `ui/amplify.yml` exists (appRoot `ui`, artifacts
  `out`). It is only used by the Git-connected flow — see §6 for why you will
  not use that flow.
- **AgentCore entrypoint**: `chronotrace.agent.graph:handler`, config at
  `chronotrace/agent/deploy/agentcore.yaml`. Handler signature:
  `handler(payload: dict) -> dict`, payload
  `{"test_id":..., "cwd":..., "mode":"agent"|"pipeline", "runs":20, "apply":false}`.
- **`CHRONOTRACE_MODEL_ID_LARGE` is deliberately empty** in `agentcore.yaml`.
  Supply `amazon.nova-pro-v1:0` at deploy time, after confirming it is available
  in `us-east-1` with `aws bedrock list-foundation-models`.
- **Canonical R01 node id** (use verbatim):
  ```
  benchmark/cases/R01_unawaited_writer/test_R01_unawaited_writer.py::test_reader_sees_committed_value
  ```
- **Quality gates that must stay green**: `uv run ruff check .`,
  `uv run mypy chronotrace/ tests/`, `uv run pytest` (166 passed).
- **Do not claim** CloudWatch export or a DynamoDB registry work. They are not
  implemented and `Settings` now raises on those values.

---

## 5. Task E (do first) — cost guardrail

The account has ~$50 of credits and has spent under $1 so far.

```bash
aws budgets create-budget --account-id <from sts> --budget '{
  "BudgetName": "chronotrace-hackathon",
  "BudgetLimit": {"Amount": "10", "Unit": "USD"},
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}'
```

Add an SNS-notification subscriber at 80% to the user's email
(`connect2tanmayy@gmail.com`) if you can do it in one call. A budget *action*
that revokes `bedrock:InvokeModel` is better but needs an extra IAM role — do it
only if it is quick; a plain notification budget is acceptable.

The realistic cost risk is a deploy loop that retries model invocations, not the
hosting. Amplify static hosting and a handful of Nova Pro calls are cents.

---

## 6. Task A — Amplify Hosting (must ship)

**Use the manual zip-deploy API, not the GitHub-connected flow.** The Git flow
requires an interactive GitHub OAuth handshake in a browser, which you cannot
complete headlessly. The zip flow is fully scriptable with IAM credentials and
produces the same `*.amplifyapp.com` URL.

```bash
cd ui
npm ci
npm run build                      # emits ui/out/
cd out && zip -r ../../deploy.zip . && cd ../..

APP_ID=$(aws amplify create-app --name chronotrace \
  --platform WEB --query 'app.appId' --output text)
aws amplify create-branch --app-id "$APP_ID" --branch-name main

# create-deployment returns a presigned zipUploadUrl and a jobId
aws amplify create-deployment --app-id "$APP_ID" --branch-name main
curl -T deploy.zip "<zipUploadUrl>"
aws amplify start-deployment --app-id "$APP_ID" --branch-name main --job-id <jobId>
```

Poll `aws amplify get-job` until `status` is `SUCCEED`. Final URL:
`https://main.<APP_ID>.amplifyapp.com`

Notes:
- If `create-app` rejects `--platform WEB`, omit the flag; the default is right
  for a static export.
- Delete `deploy.zip` afterwards — do not commit it.
- If the build fails, fix it. `npm run prebuild` failing means neither
  `eval-results/incidents.json` nor `ui/public/incidents.json` exists; the
  committed snapshot should make that impossible, so investigate rather than
  regenerating eval data (which costs model calls).

---

## 7. Task C — Playwright verification

The repo already uses Playwright (`scripts/render_architecture.py`). Reuse that
setup rather than adding a dependency.

Against the **live Amplify URL** (not localhost):
1. Load the page; assert HTTP 200 and that the document title renders.
2. Assert the incident data actually loaded — the dashboard must show real
   incident rows, not an empty state or an error boundary.
3. Capture console errors; a page that renders but throws is a failure.
4. Screenshot at 1440×900 to `assets/deploy/amplify-live.png`.
5. Click through at least one incident detail view and screenshot that too.

If any assertion fails, fix the site and redeploy. A live URL that renders an
empty dashboard is worse than no URL, because it will be clicked by judges.

Save the script to `scripts/verify_deploy.py` so it is repeatable.

---

## 8. Task B — AgentCore Runtime (timeboxed, may fail)

**Timebox: 90 minutes. Then stop, regardless of state.**

```bash
uv sync --extra bedrock
aws bedrock list-foundation-models --region us-east-1 \
  --query "modelSummaries[?contains(modelId,'nova-pro')].modelId"
# confirm amazon.nova-pro-v1:0 is present and access-enabled
```

Install the `bedrock-agentcore-starter-toolkit`, configure from
`chronotrace/agent/deploy/agentcore.yaml`, set
`CHRONOTRACE_MODEL_ID_LARGE=amazon.nova-pro-v1:0`, and deploy the entrypoint
`chronotrace.agent.graph:handler`.

Then **invoke it for real**:

```json
{"test_id": "benchmark/cases/R01_unawaited_writer/test_R01_unawaited_writer.py::test_reader_sees_committed_value",
 "mode": "agent"}
```

### The failure you should expect

This is the crux, and it is why the task is timeboxed and optional.

`AgentTools.capture_traces` and `force_replay` **spawn `pytest` subprocesses** —
dozens of them per run. This is not a model-only agent. For the deploy to work:

- the runtime sandbox must permit spawning subprocesses;
- `benchmark/cases/` and the full test tree must be inside the deployment
  bundle, not just the `chronotrace` package;
- the runtime's ephemeral filesystem must be writable for `telemetry/` and
  `.chronotrace/`.

It is entirely plausible that the **deploy succeeds and the first invocation
fails**. That is a legitimate outcome. Report it precisely — which call, what
error — and move on. Do not:
- replace the pytest calls with canned data to make it respond;
- deploy a reduced "demo" handler and present it as the agent;
- describe the runtime as live because the ARN exists.

If you get a real invocation response, capture the **full transcript verbatim**
for §9. Try `"mode": "pipeline"` as a fallback if `agent` fails — it is a fixed
sequence and may survive where the loop does not. Report clearly which mode
works.

---

## 9. Task D — documentation, conditional on results

**If Amplify shipped (expected):**
- Add the live URL to `README.md` §"Dashboard" (line ~533).
- Add it near the top of the README as a "Try it live" line.
- Update `HANDOVER.md` §2 "Live URLs & Submissions" with the URL.

**If AgentCore genuinely responded:**
- Replace the `**Not yet deployed.**` paragraph at `README.md:638` with the
  runtime ARN, the region, the mode that works, and the real invocation
  transcript in a fenced block.
- Note explicitly if only `pipeline` mode works and `agent` does not.

**If AgentCore did not respond:**
- Change nothing at `README.md:638`. It is already correct.
- Record the failure in `DEPLOY_SUMMARY.md` only.

**Then:**
```bash
uv run ruff check . && uv run mypy chronotrace/ tests/ && uv run pytest
```
All three must pass before committing. Commit with a message describing what is
actually live. Push to `origin/main`.

---

## 10. Task F — `DEPLOY_SUMMARY.md`

Write to the repo root. Structure:

1. **What is live** — URLs, ARNs, regions. One line each. Only things you
   personally invoked and saw respond.
2. **What is not live** — and the specific reason, with the error.
3. **Decisions you made** — and why (naming, IAM shape, zip-vs-Git deploy, any
   fallback you chose).
4. **Cost** — actual spend from Cost Explorer if available, plus the budget you
   set.
5. **What the user must do manually** — including: delete the
   `chronotrace-deploy` IAM user after submission (IAM → Users → Delete), and
   delete `~/Downloads/chronotrace-deploy_accessKeys.csv`.
6. **Devpost guidance** — which URLs are safe to submit. Rule: list the
   AgentCore endpoint **only** if it actually responds. Otherwise submit the
   Amplify URL plus the GitHub repo, and leave AgentCore described as an
   entrypoint that exists but is not deployed. AgentCore is not required by the
   hackathon rules; a broken link is far more damaging than an absent one.

Put both the Amplify URL and (if live) the AgentCore ARN in **both** the GitHub
README and the Devpost submission. There is no reason to split them — Devpost
accepts multiple "Try it out" links, and a judge seeing both is strictly better
off than one seeing either alone.

---

## 11. Definition of done

- [ ] `aws sts get-caller-identity` returned the deploy user
- [ ] Budget created
- [ ] Amplify URL live and returning 200
- [ ] Playwright verified real incident data renders, screenshots saved
- [ ] AgentCore either invoked successfully **or** failure documented precisely
- [ ] `README.md:638` accurate either way
- [ ] ruff + mypy + pytest all green
- [ ] Committed and pushed
- [ ] `DEPLOY_SUMMARY.md` written, including the IAM-user-deletion reminder
- [ ] No credential in any file, commit, screenshot, or summary
