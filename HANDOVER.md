# ChronoTrace: LLM Context Handover

## 1. Project & Repository Identity
- **Project**: ChronoTrace (Autonomous concurrency-induced flaky test repair)
- **Local Repo Path**: `/Users/umangsingh/Chronotrace`
- **Video Repo Path**: `/Users/umangsingh/chronotrace-video`
- **Git Remote**: `https://github.com/Umang3172/chronotrace.git`
- **Git Branch**: `main` (synchronized with `origin/main`)
- **License**: MIT (`LICENSE`)
- **Python / Runtime**: Python 3.12, managed via Astral `uv`

## 2. Live URLs & Submissions
- **Hackathon**: AWS & Devpost "Agents for Humans Hackathon" (Track: Professional Agents)
- **Devpost Submission Edit**: `https://devpost.com/submit-to/30317-agents-for-humans-hackathon/manage/submissions/1175750-chronotrace/project_details/edit`
- **Demo Video (YouTube)**: `https://youtu.be/rVpdhkXdIgU` (1080p, 30fps). NOTE: the published cut is 5:19 and the hackathon caps video at 5:00. A 4:59 re-cut exists locally and must be re-uploaded.
- **AWS Builder Community Post (Bonus Points)**: `https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests`
- **GitHub Repository**: `https://github.com/Umang3172/chronotrace`

## 3. Architecture & Technical Contracts
- **Problem Space**: Order-dependency and concurrency races in Python asyncio tests (59% of Python flakes; 84% post-submit CI failures at Google; $1.14M/yr Microsoft).
- **Differential Trace Alignment**: Aligns OpenTelemetry traces of passing and failing runs from identical commit/environment fingerprint (`commit`, `python`, `lock_hash`, `env_hash`).
- **Causal Backward Slicing**: Static backward slice from failed assertion + Ochiai suspiciousness ranking across observed-order inversions.
- **Agentic Loop**: AWS Strands Agents SDK (`strands.Agent` in `chronotrace/agent/graph.py`), run by `chronotrace agent`. Bound to 9 `@tool`-decorated methods; `--dry-run` prints the registered surface without a model. Until 2026-09-09 the tools were undecorated and **zero** registered, silently. Tools:
  - `capture_traces`, `trace_slice`, `compare_orderings`, `force_replay`, `source_context`, `diagnose_now`, `check_patch`, `run_once`.
- **Bedrock Models**:
  - `amazon.nova-pro-v1:0` (default reasoning model in `chronotrace/providers/bedrock.py` and `graph.py`).
  - `amazon.nova-lite-v1:0` (fast mode: 2.8s turnaround, 3,066 input tokens, 286 output tokens).
  - Emits typed `RepairIntent` JSON schema (`INJECT_ASYNC_EVENT`, `AWAIT_UNFINISHED_TASK`, `ISOLATE_FIXTURE_SCOPE`, `RELAX_ASSERTION`, `NO_REPAIR`), never raw source code.
- **15-Rule Deterministic AST Governor** (`chronotrace/govern/`):
  - 8 Negative: blocks sleeps, aliased imports (`from time import sleep as p`), retries (`@flaky`, `tenacity`), loops around assertions, timeout inflation, swallowed exceptions (`except AssertionError: pass`).
  - 3 Positive: requires real synchronization primitive (`asyncio.Event`), reachable from both signal and wait sites, non-noop patch.
  - 4 Structural: cycle check in wait-for graph, no production edits without opt-in, no `site-packages`, valid syntax.
- **Forced Replay Engine (Tier 1)**:
  - Gates instrumented coroutines to force candidate interleavings.
  - Pre-patch under forced schedule fails 20/20; post-patch under identical forced schedule passes 20/20.
  - Produces deterministic regression test file as shipped artifact.
- **R14 Benchmark Finding**:
  - Task-lifecycle race where unconstrained patch reduces flake rate from 80% to 45%. Rerun gates accept it as fixed; ChronoTrace's forced replay catches and rejects it.
- **AgentCore Entrypoint**: `chronotrace.agent.graph.handler(payload)` for serverless AWS CI/CD execution.
- **Observability**: JSONL under `telemetry/`, and SQLite under `.chronotrace/`. CloudWatch export and a DynamoDB registry are **NOT implemented**; `CHRONOTRACE_TELEMETRY=cloudwatch` and `CHRONOTRACE_REGISTRY=dynamodb` now raise rather than silently no-op. Do not describe either as working.

## 4. Local Files & Asset Registry
- **Desktop Assets Directory**: `/Users/umangsingh/Desktop/ChronoTrace-Blog-Assets/`
  - `00-thumbnail.jpg`: 16:9 thumbnail for YouTube and Devpost.
  - `01-hero-architecture.png`: 4K 6-stage architecture diagram still.
  - `02-google-amazon-impact.png`: Google & Amazon CI/CD telemetry cards.
  - `03-flakiness-terminal.png`: Terminal output of `chronotrace flake-check` (20 runs, 11 fails).
  - `04-bedrock-nova-governor.png`: Bedrock Nova Lite call + 15/15 governor approval.
  - `BLOG_POST.txt`, `BLOG_POST_3000.txt`, `BLOG_POST_ULTRA_SHORT.txt`: Prepared community copy.
- **Demo Video File**: re-cut at `/Users/umangsingh/chronotrace-video/out/chronotrace-demo.mp4` (1080p, 8970 frames, 4:59). The 5:19 original is kept at `out/chronotrace-demo-519.mp4.bak`, and the pre-cut narration at `assets/out-2.original.mp3`.
- **In-Repo Architecture Assets**:
  - `assets/architecture.html`: Claude Design 6-stage component source.
  - `assets/video/arch-[0-6]-*.png`: 7 rendered pipeline stills.
  - `scripts/render_architecture.py`: Playwright automated still generator.

## 5. CLI Commands & Verification
```bash
# Setup
uv sync --extra bedrock
export AWS_REGION="us-east-1"

# Flakiness measurement
chronotrace flake-check [test_id]

# Offline Governor Gauntlet (17 adversarial attacks rejected)
chronotrace gauntlet

# Bedrock Nova Repair Demo
uv run chronotrace repair --demo

# R14 Gate Rejection Demo
uv run chronotrace repair --demo-r14

# Full Quality Suite (all passing)
uv run ruff check .               # 0 errors
uv run mypy chronotrace/ tests/   # 0 errors, 73 files, strict = true
uv run pytest                     # 166 passed in 50s
```

## 6. Current State & Pending Human Actions
1. **GitHub Remote**: Fully synchronized with `origin/main`.
2. **Devpost Submission (`project_details/edit`)**:
   - Form fields are pre-filled in Chrome (`software[description]`, `software[tag_list]`, `software[video_url]`, and both try-it-out URLs).
   - User action: Drag `~/Desktop/ChronoTrace-Thumbnail.jpg` into "Drop files here", click "Save & continue", verify "Additional info" (track: Professional Agents, AWS Builder ID, builder post URL), and click Submit.

## 12. Corrections applied 2026-09-09

Recorded because each of these was stated as fact somewhere before it was true.

- **Strands registered zero tools.** The eight `AgentTools` methods were passed
  to `Agent(tools=[...])` undecorated; the SDK logs `unrecognized tool
  specification` per tool and continues, so the agent built cleanly and answered
  with no tools. `build_agent` also had no callers -- the CLI had no `agent`
  command and the AgentCore handler went straight to the single-shot provider.
- **The agent could not act.** The system prompt named only prohibitions, and no
  tool emitted a `RepairIntent`. Nova Pro investigated correctly and then
  abstained because nothing was permitted. `propose_repair` and a prompt naming
  `INJECT_ASYNC_EVENT` / `AWAIT_UNFINISHED_TASK` fixed it.
- **CI had been red for three commits** -- `ruff format --check .` on four files,
  and the coverage gate at 74% against `fail_under = 80`.
- **Bedrock numbers now exist.** `three-arm --provider bedrock`; Nova Pro
  band-aids 6/6 unconstrained against qwen's 3/6, and R14 fails identically on
  both models. Canonical: `eval/results/bedrock/three_arm_table.md`.
- **`docs/results/` is reference-policy output**, not a model result, and its
  100% repair rate must never be quoted.
- **The video timeline had three stale absolute-frame tables** (S3, S8, S9) and
  `build-captions.mjs` kept its own copy of the scene offsets. All now derive
  from `SCENES`, and `npm run verify` asserts every beat lands inside its scene.
- **An unsourced Amazon statistic was cut** from scene 2 (narration and card):
  "#1 CI/CD blocker, 30% of deployment triage lost", attributed on screen to the
  Amazon Builders' Library. Could not be verified there or anywhere.
