# Deployment summary — 2026-09-09

Executed from `DEPLOY_TASK.md`. Account `044468733589`, IAM user
`chronotrace-deploy`, region `us-east-1` throughout.

---

## 1. What is live

Only things invoked and observed responding are listed here.

| Thing | Address | Evidence |
|---|---|---|
| Dashboard | https://main.d3k7wvrz5f9b6h.amplifyapp.com | HTTP 200, 15 incident rows, 0 console errors — `scripts/verify_deploy.py` |
| AgentCore Runtime (`agent` mode) | `arn:aws:bedrock-agentcore:us-east-1:044468733589:runtime/chronotrace-W8r1r453Mi` | Two independent invocations returned a full agent result; transcript in README |
| Budget | `chronotrace-hackathon`, $10/month, email alert at 80% | Created via `budgets:CreateBudget` |

**Amplify.** App `d3k7wvrz5f9b6h`, branch `main`, deploy job 1 `SUCCEED`. The
deployed artifact is the `ui/out` static export (86 files, 434 KB zipped).
Screenshots: `assets/deploy/amplify-live.png` (list, 1440×900) and
`assets/deploy/amplify-incident.png` (detail, full page).

**AgentCore.** The agent loop genuinely runs in the runtime, including the parts
that were expected to be the blocker. `capture_traces` spawned pytest
subprocesses and measured a 0.7 flake rate over 10 runs (7 failing, 3 passing);
`force_replay` forced the candidate ordering to a failure rate of 1.0; the
governor approved the synthesized patch (`approved=True violations=[]`). Six
cycles, 16,347 tokens, `stop_reason: end_turn`.

## 2. What is not live, and why

**Applying a repair inside AgentCore.** `propose_repair` fails with a permission
error when it writes the patched file — the deployed bundle is not a writable
checkout. The agent handles this correctly: it abstains and says why, rather
than claiming a repair. So the runtime is a working *investigator* and not a
working *repairer*. Fixing it means writing to a writable scratch path instead
of the bundle, which is a code change, not a deploy change, and was out of scope
here. Caveat on precision: the permission error is what the tool returned to the
model; the raw traceback did not appear in the runtime logs, so the exact errno
is not recorded.

**`pipeline` mode was never invoked.** The 90-minute timebox on Task B expired
once `agent` mode was confirmed working. Nothing is claimed about `pipeline`
either way — it is untested in the runtime, not known-broken.

**The first AgentCore deploy failed** and is recorded because it shaped the
final shape of the bundle: `ModuleNotFoundError: No module named
'bedrock_agentcore'`, surfaced to the caller as `RuntimeClientError: Runtime
initialization time exceeded ... 30s`. Cause: for a direct-code deploy the
starter toolkit ignores the `--requirements-file` flag at deploy time
(`launch.py` calls `detect_dependencies(source_dir)` with no explicit file) and
auto-detects instead. It found `pyproject.toml`, which does not list the
AgentCore SDK.

## 3. Decisions made

- **Zip deploy, not Git-connected Amplify**, as briefed — the GitHub OAuth
  handshake cannot be completed headlessly. `ui/amplify.yml` is therefore unused
  by this deployment and left in place for a future Git-connected flow.
- **A root `requirements.txt` was added.** This is the only lever that controls
  the AgentCore bundle's dependencies, given the flag-is-ignored behaviour above.
  It is cross-compiled for `linux/arm64` with `uv pip install --only-binary
  :all:`, under which the local project *cannot* be installed from source — so
  the dependency set is listed explicitly and `chronotrace` is imported from the
  bundle rather than pip-installed. The file says all of this in a header
  comment, because in a `uv`/`pyproject.toml` project a bare `requirements.txt`
  otherwise reads as a mistake. `pyproject.toml` + `uv.lock` remain the source of
  truth for development.
- **`PYTEST_PLUGINS=chronotrace.capture.plugin` is set as a runtime env var.**
  ChronoTrace's pytest plugin normally registers through the `pytest11` entry
  point, which only exists if the package is pip-installed — which the previous
  point rules out. Without it the spawned `pytest` runs would reject
  `--chronotrace` as an unrecognised argument. This loads the real plugin; it
  substitutes nothing.
- **`agentcore_entry.py` sits at the repository root**, not next to
  `agentcore.yaml`. The runtime launches the entrypoint as a script, so the
  file's own directory is what lands on `sys.path`; only at the root does that
  directory contain `chronotrace/` and `benchmark/`. It is a pass-through shim —
  it forwards the payload to `chronotrace.agent.graph:handler` and adds nothing.
- **Execution role and S3 bucket were auto-created** by the toolkit
  (`AmazonBedrockAgentCoreSDKRuntime-us-east-1-6de37f6a10`) rather than
  hand-shaped, since the whole account is disposable.
- **A plain notification budget, no budget action.** A budget action that revokes
  `bedrock:InvokeModel` needs an extra IAM role; the brief called that optional,
  and actual spend never came close to the limit.
- **`.bedrock_agentcore.yaml` and `.bedrock_agentcore/` are gitignored** — they
  hold machine-specific absolute paths and a 10 MB dependency cache. The
  deployable inputs are committed.
- **The deploy zip was built in a scratch directory**, not the repo root, so
  there was never a window in which it could be committed.
- **The AWS CLI was installed** (`brew install awscli`) — it was not present.

## 4. Cost

Month-to-date, from Cost Explorer at the time of writing:

| Service | USD |
|---|---|
| Amazon Bedrock | 0.0092 |
| Amazon S3 | 0.00004 |
| AWS Secrets Manager | 0.000005 |
| **Total** | **0.0093** |

Cost Explorer lags by roughly a day, so today's AgentCore Runtime and Amplify
charges are probably not in that figure yet. Both are small: Amplify static
hosting is fractions of a cent at this traffic, and the agent runs used 16 k
tokens each on Nova Pro. Guardrail in place: `chronotrace-hackathon`, $10/month,
email to `connect2tanmayy@gmail.com` at 80% actual spend.

## 5. What you must do manually

1. **Delete the IAM user** `chronotrace-deploy` after submission — IAM → Users →
   `chronotrace-deploy` → Delete. This is the one that matters.
2. **Delete `~/Downloads/chronotrace-deploy_accessKeys.csv`.** The secret access
   key is in that file in plaintext.
3. *(Optional)* Tear down the AgentCore runtime once it is no longer needed —
   `agentcore destroy` from the repo, or delete runtime `chronotrace-W8r1r453Mi`
   in the Bedrock AgentCore console. It bills per invocation, so leaving it idle
   is close to free; deleting it is just tidiness.
4. *(Optional)* Delete the Amplify app `d3k7wvrz5f9b6h` if you stop wanting the
   dashboard up. **Do not do this before judging** — it is a submitted link.
5. `DEPLOY_TASK.md` was deliberately left uncommitted; delete it or commit it as
   you prefer.

No credential appears in any file, commit, screenshot or in this summary.
Credentials were sourced for each command from the Downloads CSV via a script in
a session scratch directory outside the repository.

## 6. Devpost guidance

**Submit as "Try it out" links:**

1. `https://main.d3k7wvrz5f9b6h.amplifyapp.com` — verified working, and the
   thing a judge can actually look at.
2. `https://github.com/Umang3172/chronotrace` — the repo.

**Do not submit the AgentCore ARN as a link.** It responds, but an ARN is not
something a judge can click, invoking it requires IAM credentials in this
account, and step 5.1 above deletes the user that has them. Describe it in the
project text instead — the runtime ARN, the region, that `agent` mode was
invoked and returned, that the pytest-spawning tools ran inside the runtime, and
that applying a repair fails there on a read-only bundle. The README section
carries the full transcript, so a judge who wants proof has it without needing a
live endpoint.

That framing is also the honest one: the repair path is real and demonstrable
locally and in the video, and the hosted runtime demonstrates the investigation
half. Claiming a fully working hosted repairer would be a claim the transcript
itself contradicts.
