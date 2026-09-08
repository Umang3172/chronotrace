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
- **Demo Video (YouTube)**: `https://youtu.be/rVpdhkXdIgU` (1080p, 5:19, 30fps)
- **AWS Builder Community Post (Bonus Points)**: `https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests`
- **GitHub Repository**: `https://github.com/Umang3172/chronotrace`

## 3. Architecture & Technical Contracts
- **Problem Space**: Order-dependency and concurrency races in Python asyncio tests (59% of Python flakes; 84% post-submit CI failures at Google; $1.14M/yr Microsoft).
- **Differential Trace Alignment**: Aligns OpenTelemetry traces of passing and failing runs from identical commit/environment fingerprint (`commit`, `python`, `lock_hash`, `env_hash`).
- **Causal Backward Slicing**: Static backward slice from failed assertion + Ochiai suspiciousness ranking across observed-order inversions.
- **Agentic Loop**: AWS Strands Agents SDK (`strands.Agent` in `chronotrace/agent/graph.py`). Bound to 8 tools:
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
- **Observability**: Complete trace retention via OpenTelemetry + AWS CloudWatch Transaction Search (lossless vs probabilistic sampling).

## 4. Local Files & Asset Registry
- **Desktop Assets Directory**: `/Users/umangsingh/Desktop/ChronoTrace-Blog-Assets/`
  - `00-thumbnail.jpg`: 16:9 thumbnail for YouTube and Devpost.
  - `01-hero-architecture.png`: 4K 6-stage architecture diagram still.
  - `02-google-amazon-impact.png`: Google & Amazon CI/CD telemetry cards.
  - `03-flakiness-terminal.png`: Terminal output of `chronotrace flake-check` (20 runs, 11 fails).
  - `04-bedrock-nova-governor.png`: Bedrock Nova Lite call + 15/15 governor approval.
  - `BLOG_POST.txt`, `BLOG_POST_3000.txt`, `BLOG_POST_ULTRA_SHORT.txt`: Prepared community copy.
- **Demo Video File**: `/Users/umangsingh/Desktop/ChronoTrace-Demo-Video.mp4` (78 MB, 1080p, 5:19).
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
