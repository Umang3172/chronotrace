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
- **Demo Video (YouTube)**: `https://youtu.be/rkoeqMt3cDk` (1080p, 30fps, 4:47.9). The corrected cut, uploaded 2026-09-10. Superseded `xyjV-UmbvmA` (4:59), which YouTube cannot replace in place; keep that one unlisted rather than deleted until nothing points at it. All five references now carry the new ID: `README.md:8`, `README.md:562` (twice), `README.md:564`, this line, and the Devpost `software[video_url]` field.
- **AWS Builder Community Post (Bonus Points)**: `https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests`
- **GitHub Repository**: `https://github.com/Umang3172/chronotrace`
- **Live Dashboard (AWS Amplify Hosting)**: `https://main.d3k7wvrz5f9b6h.amplifyapp.com` — app id `d3k7wvrz5f9b6h`, branch `main`, `us-east-1`, deployed 2026-09-09 by manual zip deploy (not Git-connected). Verified against the live URL with `scripts/verify_deploy.py`: HTTP 200, 15 incident rows, no console errors. Screenshots in `assets/deploy/`.
- **AgentCore Runtime**: `arn:aws:bedrock-agentcore:us-east-1:044468733589:runtime/chronotrace-W8r1r453Mi` — deployed and invoked 2026-09-09 in `agent` mode with `amazon.nova-pro-v1:0`. The loop runs, including the pytest subprocesses; `propose_repair` fails on a permission error because the bundle is not writable, so the agent abstains. Not a submittable "try it out" link: the deploy IAM user is deleted after submission and the ARN then stops answering. Full transcript in README §"AgentCore Runtime entrypoint".

## 3. Architecture & Technical Contracts
- **Problem Space**: Order-dependency and concurrency races in Python asyncio tests (59% of Python flakes; 84% post-submit CI failures at Google; $1.14M/yr Microsoft).
- **Differential Trace Alignment**: Aligns OpenTelemetry traces of passing and failing runs from identical commit/environment fingerprint (`commit`, `python`, `lock_hash`, `env_hash`).
- **Causal Backward Slicing**: Static backward slice from failed assertion + Ochiai suspiciousness ranking across observed-order inversions.
- **Agentic Loop**: AWS Strands Agents SDK (`strands.Agent` in `chronotrace/agent/graph.py`), run by `chronotrace agent`. Bound to 9 `@tool`-decorated methods; `--dry-run` prints the registered surface without a model. Until 2026-09-09 the tools were undecorated and **zero** registered, silently. Tools:
  - `capture_traces`, `trace_slice`, `compare_orderings`, `force_replay`, `source_context`, `diagnose_now`, `check_patch`, `propose_repair`, `run_once`. (This list said eight while the count said nine; `propose_repair` was the missing one. Verified 2026-09-10: nine `@tool` decorators in `chronotrace/agent/tools.py`.)
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
- **Demo Video File**: `/Users/umangsingh/chronotrace-video/out/chronotrace-demo.mp4` (1080p, 8636 frames, 287.91s = 4:47.9). Re-rendered 2026-09-10 with the scene-6 retime, three desync fixes, ten terminal callouts, four spotlit, the Act II narration cut, and "local" removed from the scene-8 footnote — see §13. **Uploaded 2026-09-10** as `rkoeqMt3cDk` by the user (the browser automation's file-upload path caps at 10 MB against this file's 74.9 MB). Title, description and chapters as published are in `docs/posts/youtube-upload-pack.md`. **The superseded 4:59 cut is kept byte-for-byte at `out/chronotrace-demo-published.mp4`.** The 5:19 original is at `out/chronotrace-demo-519.mp4.bak`. Pre-edit narration: `assets/out-2.original.mp3` (scene 2) and `assets/out-7.original.mp3` + `assets/caption-7.original.json` (scene 7).
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
uv run mypy chronotrace/ tests/   # 0 errors, 74 files, strict = true
uv run pytest                     # 199 passed in 106s (spawns a pytest subprocess per benchmark case)
```

## 6. Current State & Pending Human Actions
1. **GitHub Remote**: Fully synchronized with `origin/main`.
2. **Devpost Submission** — still `DRAFT`, now **3/5 steps done**, deadline 2026-09-15.
   - **Project details: filled and SAVED 2026-09-10.** The step had been empty, not "pre-filled" as this section previously claimed. Now carrying an 8,211-character story (`docs/posts/devpost-project-story.md` is the source of truth — edit there and re-paste), 14 tags, 7 gallery images with captions, `software[video_url]` = `https://youtu.be/rkoeqMt3cDk`, and three try-it-out URLs (Amplify, GitHub, Builder Center).
   - **Additional info: saved, two required fields still blank.** Set: Submitter Type `Individual`, Track `Professional Agents`, repo URL, live demo URL, bonus blog URL, 2,109-character testing instructions, and `assets/video/arch-0-neutral.png` as the required architecture diagram. **Blank and required: Country of Residence, and AWS Builder ID** — neither is knowable from this repository, so both need the user. The step stays unchecked until they are filled.
   - **Not submitted.** The final Submit button was deliberately not pressed.

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

## 13. Video corrections applied 2026-09-09 (second pass)

All four were in the cut that is currently on YouTube.

- **Scene 6 never showed its own verdict.** `GAUNTLET_FIRST_ROW_FRAME` and friends were
  absolute frames left over from an earlier timeline. On the shipped 8970-frame cut the
  first row landed 13.2s into a 26.7s scene, so the narration named six attacks over an
  empty screen; only 9 of the 17 rows ever rendered; and `GAUNTLET_VERDICT_FRAME` (5970)
  sat 375 frames past the end of the scene (5595), so "17/17 attacks rejected by the rule
  that targets them" — the line the whole scene exists to land — was never on screen.
  `Root.tsx`'s standalone loop had the same bug (verdict at 810 in an 800-frame clip).
  Both are now derived from `scene(6).audioFrom` plus the second each line is spoken in
  `caption-6.json`.
- **Two more narration/footage desyncs of the same family.** In Act I the model call ran
  at 2x, so `governor.verdict` printed two seconds *after* the narration had said
  "Fifteen policy rules pass" — now 5x, and the line is up first. In Act II
  `R14_BEAT.modelCall` was 500 against a line spoken at frame 263, so the screen sat
  frozen on `confirm.sufficient` for eight seconds while the narration described a model
  call that had not started.
- **Nothing checked any of this.** `npm run verify` now has two new sections: one asserts
  every gauntlet row and the verdict land inside scene 6 *and* that the offsets they are
  derived from still match the whisper transcript; the other computes the frame at which
  a named log line actually reaches the screen and asserts it is not after the sentence
  about it. A beat that never fires renders as a still frame, not an error, which is why
  three of these shipped.
- **`demo/COMMANDS.md` describes a terminal geometry that was never recorded.** It says
  "The video crops 30 terminal rows into 1080px, so one row is 36px and the caption bar's
  top edge lands at y=870 — inside row 25." The recordings are a letterboxed macOS window
  with a title bar: the real pitch is 29.21px, row 1 starts at y=97.5, and the caption bar
  lands inside row 27. Measured values now live in `chronotrace-video/src/terminal.ts`.
  The `CHRONOTRACE_RECORDING` six-blank-line padding still does its job; only the
  arithmetic in the note is wrong.

### Resolved: Act II's narration described a retry that is not in the footage

Scene 7 said "Notice it took two attempts. The first intent was incomplete, the validator
rejected it, and the agent corrected itself," and then "But it corrected the format, not
the choice."

`assets/03-repair-r14.mp4` contains one `bedrock.call attempt=1` followed 27ms later by
`governor.verdict approved=True violations=[]`. No `intent.rejected`, no `attempt=2`; the
row count in the recording does not change between 17.9s and 56.8s, so nothing appears
later either. `_propose_with_retries` in `chronotrace/pipeline.py` logs both, so a take
that had retried would show it. The take on screen and the take being narrated were
different runs.

**Cut, 2026-09-09.** All three sentences removed from `out-7.mp3` — 11.133s, spliced
11.000s to 22.133s, both ends inside detected silence, leaving a 0.727s join that matches
the 0.71-0.79s pauses elsewhere in the take. Originals kept at `out-7.original.mp3` and
`caption-7.original.json`.

The argument is better without them. The retry was a mechanical aside about the SDK's
intent loop and never fed the point the scene exists to make; the scene now runs
proposal -> gate passes -> "the problem is judgement" with nothing in between.

Everything downstream moved: scene 7 2230 -> 1896 frames, scenes 8 and 9 back 334,
`TOTAL_FRAMES` 8970 -> 8636 (4:47.9), the `S8`/`S9` beat tables, three of the four
`R14_BEAT` constants, and every scene-7 callout window. `R14_MODEL_CALL_RATE` went 1x ->
2x because the cut pulled "The policy gate passes it" to six frames *before*
`governor.verdict` reached the screen — verify caught that, which is the whole reason
that check was written.

### Resolved: the AWS Builder Center post, corrected and republished 2026-09-10

Live and updated. Two of these were worse than the four text claims first found.

- **The hero image carried the unsourced Amazon statistic** that §12 records as cut from
  the video — "30% deployment triage lost", "#1 CI/CD Blocker", attributed on the card to
  *Amazon Builders' Library · Hands-Off Deployments*, plus a burned-in subtitle "And at
  Amazon, flaky tests are the single biggest blocker to automated releases." Published on
  Amazon's own Builder Center. `BLOG_POST.txt` has a different and narrower claim — "test
  execution routinely accounts for over 30% of total build times" — so the card had drifted
  from a build-time figure into a deployment-triage one with a named source attached.
  Replaced with `02-google-ci-telemetry.png`, the same design cropped to the Google card,
  which cites Memon et al.
- **The second figure was a video still with "But it corrected the format, not the choice."
  burned into it** — one of the three sentences cut from Act II for describing a retry the
  footage does not contain. The terminal in that very still shows `attempt=1` approved on
  the spot. Replaced with `04-nova-governor-clean.png`, cropped above the subtitle band.
- 15 seeded concurrency races → "Tested on Amazon Nova Pro across 7 races and 5 non-race
  controls".
- "vs 3/6 in unconstrained LLMs" → "across the 7 races (vs 6/7 in unconstrained LLMs)".
  The published figure cited the weakest comparator against the wrong denominator; 6/7 is
  the real Arm A number and the stronger result.
- 8 tools → 9.
- One redundant sentence cut from the "Worse," paragraph (the 80%-to-45% point is already
  made by the R14 Proof bullet).

**The post is at its 3000-character ceiling.** The Update button is validation-blocked
above it, and the count includes image markdown, so any future addition needs an equal
trim first. That is why the Amplify URL, the AgentCore paragraph and the video link are
*not* in the post.

Alt text was added to both replaced images and then shortened to ~50 characters each for
the same reason.

## 14. Pass of 2026-09-10 — video published, repo images, Devpost filled

### The corrected video is live

`https://youtu.be/rkoeqMt3cDk`, uploaded by the user. Verified against the live player:
`video.duration` **287.941 s**, which is the 8636-frame render and not the 4:59 cut. Title
matches the pack. Every reference in the repo now carries the new id; the two remaining
mentions of `xyjV-UmbvmA` (this file §2 and the upload pack) name it deliberately, as the
record of what it superseded. **Keep the old video unlisted rather than deleted.**

Re-verified on the render itself: `npx tsc --noEmit` clean, `npm run verify` "All checks
passed", and the narration re-read end to end against `assets/caption-*.json`. Scene 8's
spoken figures were checked against `eval/results/three_arm_final_table.md` case by case —
Arm A repairs 5/7 including R14, so 4/6 over R01–R06, and its three band-aids (R01, R04,
R05) all fall inside those six. The table on screen is right. **No new defect was found in
the video.**

### Two claims in README's Demo Video section had drifted from the footage

Both were about the video and both are now fixed:

- **"an unconstrained patch makes a race rarer (80% -> 45%)"** — the recorded run shows
  15/20 then 14/20, i.e. **75% -> 70%**. Both figures are real; §"The comparison that
  matters" already documented the variance, and now says explicitly that the video's run is
  the other sample of the same distribution.
- **"Amazon Nova Lite synthesizes an INJECT_ASYNC_EVENT repair in 2.8 seconds"** — the Act I
  footage is `model=amazon.nova-pro-v1:0 ... seconds=3.0 tokens_in=2693 tokens_out=296`. The
  2.8s Nova Lite figure is real but comes from the **R14** run. The bullet named the wrong
  model for the shot it described.
- **"Systematic 15-case evaluation"** — the corpus is 12 (7 races + 5 controls).

The whole bullet list was replaced with a chapter table whose timestamps are derived from
`SCENES` in `timing.ts` (0:00 / 0:18 / 0:58 / 1:27 / 2:06 / 2:39 / 3:06 / 4:09 / 4:35, all
confirmed against the caption offsets).

### Five stills cut from the published render into `assets/readme/`

The README had exactly one non-badge image. It now has six. All five new ones are frames of
the shipped video, so they cannot drift from it:

| File | Source frame | Placed in |
|---|---|---|
| `01-flake-check.png` | 16.5s | §The problem |
| `02-gauntlet.png` | 179s | §The governor |
| `03-forced-replay.png` | 157s | §Option B (Bedrock) |
| `04-r14-rejected.png` | 226.5s | §R14 |
| `05-results.png` | 272s | §Demo Video |

Terminal crops are `crop=1450:945:238:40`, derived from `terminal.ts` (text spans x
261–1664, y 97.5–974, plus the window chrome). Full-bleed slides are `crop=1920:880:0:0`,
which cuts the caption bar at y=870. `assets/deploy/amplify-live.png` was already committed
and unused; it is now in §Dashboard. `05-results.png` is labelled in its caption as the
**qwen** run, because that is what the narration over it speaks.

### The quality-suite line in §5 was stale

`uv run pytest` is **199 passed in 106s**, not 166 in 50s, and mypy covers **74** files, not
73. §3's tool list named eight tools while the count said nine; `propose_repair` was
missing. All verified 2026-09-10.

### Devpost — the step that mattered was empty

§6 claimed the Devpost form fields were "pre-filled in Chrome". They were not:
`software[description]`, `software[tag_list]`, `software[video_url]` and every URL field
were **empty strings**, with the submission at 2/5 steps and five days to the deadline. Both
form steps are now filled and saved — see §6 for exactly what is in each and for the two
required fields that still need the user.

### AWS Builder Center — blocked on sign-in

The Chrome profile the automation is attached to is signed out, and the sign-in dialog wants
credentials. The full replacement body, the character budget, the reasons for each change
and the editor hazards are in `docs/posts/builder-center-update.md`. Two of the changes are
corrections, not additions: the "100% accurate abstention" claim, and a figure caption that
presents the R14 patch — the one forced replay rejects — as "a repair verified by the 15/15
AST Governor".
