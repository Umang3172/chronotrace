# ChronoTrace — Master Reference Document

> **PURPOSE OF THIS FILE.** This is a single-file, self-contained, LLM-optimized
> knowledge base for the ChronoTrace project. It is written so that an LLM given
> *only this file* can answer any question about the project — what it is, what
> was built, what was measured, what the numbers mean, what it is better at,
> what research backs it, what its limits are — with no repository access, no web
> search, and no other context.
>
> **AUTHORING RULES OBSERVED IN THIS FILE.** Every quantitative claim carries its
> provenance (which command produced it, which file stores it). Claims that are
> unverified, superseded, or commonly misquoted are explicitly flagged. Density is
> preferred over prose. Human readability is secondary to machine readability.
>
> **DOCUMENT GENERATED:** 2026-09-10. **PROJECT VERSION:** 0.1.0.
> **REPO STATE:** branch `main`, HEAD `a10b391`, 36 commits, synchronized with
> `origin/main`. Generated at `0df3b49` (34 commits) and amended 2026-09-10; the
> amendments are marked where they appear.

---

## SECTION 0 — MACHINE-READABLE FACT BLOCK

```yaml
project:
  name: ChronoTrace
  version: "0.1.0"
  license: MIT
  one_liner: >
    Repairs concurrency-induced flaky asyncio tests by proving which thread/task
    ordering caused the failure, then leaving behind a deterministic regression
    test that reproduces that race on every run.
  category: AI agent / developer tooling / software testing / program repair
  author_github: Umang3172
  author_email: connect2tanmayy@gmail.com
  primary_language: Python 3.11+ (developed on 3.12)
  package_manager: uv (Astral)
  build_backend: hatchling
  repo_local_path: /Users/umangsingh/Chronotrace
  video_repo_local_path: /Users/umangsingh/chronotrace-video

hackathon:
  name: "AWS & Devpost — Agents for Humans Hackathon"
  track: "Professional Agents"
  submitter_type: Individual
  deadline: 2026-09-15
  submission_status_at_doc_time: DRAFT, 3 of 5 steps complete, NOT submitted
  blocking_fields: ["Country of Residence", "AWS Builder ID"]

links:
  github: https://github.com/Umang3172/chronotrace
  live_dashboard: https://main.d3k7wvrz5f9b6h.amplifyapp.com
  youtube_demo: https://youtu.be/rkoeqMt3cDk
  youtube_demo_superseded: https://youtu.be/xyjV-UmbvmA   # 4:59 cut, keep UNLISTED not deleted
  aws_builder_post: https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests
  devpost_hackathon: https://agentsforhumans.devpost.com
  devpost_submission_edit: https://devpost.com/submit-to/30317-agents-for-humans-hackathon/manage/submissions/1175750-chronotrace/project_details/edit

aws:
  account_id: "044468733589"
  region: us-east-1
  bedrock_models: ["amazon.nova-pro-v1:0", "amazon.nova-lite-v1:0"]
  agent_sdk: AWS Strands Agents SDK (strands-agents >= 0.1)
  agentcore_runtime_arn: arn:aws:bedrock-agentcore:us-east-1:044468733589:runtime/chronotrace-W8r1r453Mi
  agentcore_agent_id: chronotrace-W8r1r453Mi
  agentcore_execution_role: arn:aws:iam::044468733589:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-6de37f6a10
  amplify_app_id: d3k7wvrz5f9b6h
  amplify_branch: main
  amplify_deploy_method: manual zip deploy (NOT git-connected)
  total_aws_spend_usd: 0.0093
  budget_guardrail: "chronotrace-hackathon, $10/month, email alert at 80%"

headline_numbers:
  governor_rules: 15
  governor_gauntlet_attacks: 17
  governor_gauntlet_rejections: 17
  agent_tools_registered: 9
  benchmark_cases_total: 15
  benchmark_cases_in_three_arm_corpus: 12
  benchmark_repairable_races_in_corpus: 7
  benchmark_negative_controls: 5
  verification_tiers: 6
  abstention_reasons: 8
  repair_transformations_in_schema: 5
  repair_transformations_fully_implemented: 2
  adrs: 6
  tests_passing: 199
  test_coverage_percent: 80
  mypy_files_strict: 74
  python_loc_package: 9552
  python_loc_tests: 2444
  git_commits: 34
```

---

## SECTION 1 — WHAT THE PROJECT IS, IN LAYERS

### 1.1 One sentence
ChronoTrace repairs concurrency-induced flaky `asyncio` tests in Python by
diffing paired passing/failing execution traces, proving causality by *forcing*
the candidate interleaving, applying a typed repair deterministically, gating it
through 15 anti-band-aid policy rules, and emitting a permanent regression test
that reproduces the original race every run.

### 1.2 One paragraph
A flaky test is one that passes and fails on the same commit. For concurrency
flakes, the defect lives in the *interleaving*, not in the source text — so
source-only tooling and rerun-based verification are both structurally blind to
it. ChronoTrace treats the pass and the fail as two recordings of the same
program and subtracts them. The pair of operations whose order differs is the
candidate. It then forces that exact ordering on demand: if the forced ordering
fails 100% of the time it is a *sufficient condition* for the failure and is
patched; 0% is noise and discarded; anything strictly between is *necessary but
not sufficient*, reported as bug depth ≥ 2 and deliberately not patched. The
language model's only job in the entire system is to select one repair pattern
from a fixed set and return typed JSON — it never emits source code. Deterministic
code (LibCST) applies it, 15 deterministic AST rules can veto it, and forced
replay decides whether it actually worked. The shipped artifact is not the patch;
it is a generated regression test that reproduces the race deterministically, in
milliseconds, forever.

### 1.3 The thesis in one line
**An agent that is *allowed* to cheat will cheat, because a green test is
indistinguishable from a fixed test if all you measure is whether it passed.**
ChronoTrace is the experiment in what an agent can do when cheating is
structurally impossible.

### 1.4 What is novel (the defensible combination)
No single element below is unprecedented. The **combination** is what was not
found in the literature or in shipping products:

1. **Trace-differential localisation** — candidate selection from paired
   pass/fail execution traces, not from source text or a JUnit XML results file.
2. **Causality proven by forced replay** — a controlled experiment (harness held
   constant, patch is the only variable), not a rerun sample.
3. **A deterministic anti-band-aid gate** — 15 AST rules, both negative (bans)
   and positive (requirements), that the model cannot argue with.
4. **A deterministic regression test as the shipped artifact** — the product is
   the reproducer, not the diff.

---

## SECTION 2 — CANONICAL LINKS AND IDENTIFIERS (complete list)

| Kind | URL / identifier | Notes |
|---|---|---|
| GitHub repository | `https://github.com/Umang3172/chronotrace` | Public, MIT |
| Live dashboard | `https://main.d3k7wvrz5f9b6h.amplifyapp.com` | AWS Amplify Hosting, `us-east-1`. Static export of a completed run — it reads real evidence but does **not** run the pipeline for you. Verified: HTTP 200, 15 incident rows, 0 console errors |
| YouTube demo (CURRENT) | `https://youtu.be/rkoeqMt3cDk` | 1080p, 30fps, 4:47.9 (287.941 s confirmed on live player), 8636 frames, 74.9 MB, h264/aac. Uploaded 2026-09-10 |
| YouTube demo (SUPERSEDED) | `https://youtu.be/xyjV-UmbvmA` | The 4:59 cut. YouTube cannot replace a file in place. **Keep unlisted, do NOT delete** — older copies of links may point at it |
| AWS Builder Center post | `https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests` | Title: "Agents for Humans: what happens when an AI agent isn't allowed to cheat — fixing flaky tests". Bonus-points submission. **At its 3000-character ceiling** — any addition requires an equal trim |
| Hackathon | `https://agentsforhumans.devpost.com` | Track: Professional Agents |
| Devpost submission (edit URL) | `https://devpost.com/submit-to/30317-agents-for-humans-hackathon/manage/submissions/1175750-chronotrace/project_details/edit` | Submission id 1175750 |
| AgentCore Runtime ARN | `arn:aws:bedrock-agentcore:us-east-1:044468733589:runtime/chronotrace-W8r1r453Mi` | Evidence of what ran, **not a live endpoint** — the deploy IAM user is deleted after submission |
| Amplify app id | `d3k7wvrz5f9b6h` | branch `main` |
| CI badge | `https://github.com/Umang3172/chronotrace/actions/workflows/ci.yml/badge.svg` | GitHub Actions |
| Commit referenced in README | `https://github.com/Umang3172/chronotrace/commit/9e717b6` | The "Strands registered zero tools" fix |

**Devpost "Try it out" links submitted:** (1) the Amplify dashboard, (2) the
GitHub repo, (3) the Builder Center post. The AgentCore ARN is deliberately
**not** submitted as a link — an ARN is not clickable and invoking it needs IAM
credentials in an account whose user is deleted post-submission.

---

## SECTION 3 — THE PROBLEM, WITH THE FULL LITERATURE AND MARKET REVIEW

### 3.1 Scale-of-problem statistics (all cited, all used in the project)

| Figure | Source | Exact claim |
|---|---|---|
| **84%** | Memon et al., *Taming Google-Scale Continuous Testing*, ICSE-SEIP 2017 | 84% of pass-to-fail transitions in Google post-submit CI are caused by flaky tests rather than real regressions. Reading: when the build turns red, five times out of six nothing is broken |
| **26% of 3,871 builds; $1.14M/year** | Microsoft Research flaky-test cost analysis | 26% of sampled builds failed to flakiness; annualized cost $1.14M |
| **150,000+ developer hours/year; 21%** | Atlassian Engineering, 2025 | 150k+ hours lost annually; 21% of frontend master build failures come from flakes |
| **47% of 75 million** | Parry et al., *A Survey of Flaky Tests*, TOSEM 2022, doi:10.1145/3476105 | On Travis CI, 47% of 75 million restarted failing builds then passed |
| **59% of 7,571** | Gruber et al., *An Empirical Study of Flaky Tests in Python*, ICST 2021, arXiv:2101.09077 | Order-dependency dominates Python flakiness: 59% of 7,571 flaky tests studied |
| **F1 = 39%** | FlakyCat (flaky-test category classification) | Concurrency was the *hardest* category to classify at F1 39% — precisely because it depends on runtime interaction rather than source text. **This is the gap ChronoTrace targets** |
| **170 reruns** | Gruber et al., ICST 2021 | Reruns needed for 95% confidence a Python test is *not* flaky |
| **10,000 reruns insufficient** | Alshammari et al., *FlakeFlagger*, ICSE 2021 | Projects where 10,000 reruns still missed known flaky tests |
| **1/(n·k^(d−1))** | Burckhardt et al., *A Randomized Scheduler with Probabilistic Guarantees of Finding Bugs*, ASPLOS 2010 | PCT: with n concurrent tasks and k scheduling steps, finds a depth-d bug with probability ≥ 1/(n·k^(d−1)) per run. Basis of ChronoTrace's Tier 2 |

**IMPORTANT — an unsourced statistic was deliberately REMOVED from this project.**
An earlier version of the video and the Builder Center hero image claimed
"#1 CI/CD blocker, 30% of deployment triage lost", attributed to the *Amazon
Builders' Library — Hands-Off Deployments*. It could not be verified there or
anywhere and was cut from the narration, the slide, and the published post.
**Never reintroduce it.** A narrower and different claim ("test execution
routinely accounts for over 30% of total build times") exists in an early blog
draft and is also not used as a headline.

### 3.2 Full reference list (the project's numbered bibliography)

1. Memon et al. *Taming Google-Scale Continuous Testing.* ICSE-SEIP 2017.
2. Microsoft Research, flaky test cost analysis.
3. Atlassian Engineering, 2025.
4. Parry et al. *A Survey of Flaky Tests.* TOSEM 2022. doi:10.1145/3476105
5. Gruber et al. *An Empirical Study of Flaky Tests in Python.* ICST 2021. arXiv:2101.09077
6. FlakyCat — flaky-test category classification.
7. Burckhardt et al. *A Randomized Scheduler with Probabilistic Guarantees of Finding Bugs.* ASPLOS 2010.
8. Luo et al. *An Empirical Analysis of Flaky Tests.* FSE 2014.
9. Alshammari et al. *FlakeFlagger.* ICSE 2021.
10. Lamport. *Time, Clocks, and the Ordering of Events in a Distributed System.* CACM 1978.
11. Rahman & Shi. *FlakeSync: Automatically Repairing Async Flaky Tests.* ICSE 2024. doi:10.1145/3597503.3639115
12. BuildPulse — flaky test product documentation (`https://docs.buildpulse.io/flaky-tests/overview`).
13. Datadog — *Flaky Tests Management* (`https://docs.datadoghq.com/tests/flaky_management/`) and *Bits AI Dev Agent for Test Optimization* (`https://www.datadoghq.com/blog/bits-ai-test-optimization/`).
14. Gradle — Develocity flaky test detection guide (`https://docs.develocity.ai/2026.2/guides/flaky-test-detection-guide/`); Trunk — Flaky Tests (`https://trunk.io/flaky-tests`).

### 3.3 Academic prior work — full comparison

| Work | Venue / id | Result and scope |
|---|---|---|
| **FlakeSync** | Rahman & Shi, ICSE 2024, doi:10.1145/3597503.3639115 | **Closest prior work.** Repairs async flaky tests by identifying a *critical point* (code that must run early relative to concurrent code) and a *barrier point* that waits for it, then synchronising the two. **83.75% repair rate, median 1.00× original test runtime** |
| **FlakyGuard** | arXiv:2511.14002 (UT Austin + Uber) | **47.6% repair rate, 51.8% developer acceptance.** Graph-based context selection at industry scale. Names the "context problem": too little context misses critical code, too much overwhelms the model |
| **FlakyDoctor** | ISSTA 2024, arXiv:2404.09398 | **57% order-dependent / 59% implementation-dependent** on 873 tests from 243 projects. Neuro-symbolic, code-static |
| **FlakyFix** | arXiv:2307.00012 | Fix-category driven; first full LLM automation attempt |
| **iFixFlakies** | ESEC/FSE 2019 | Order-dependent flakiness only, symbolic |

**How ChronoTrace differs from FlakeSync (the four differences, stated plainly).**
FlakeSync's *critical point* and *barrier point* are, in ChronoTrace's vocabulary,
the **signal site** and the **wait site**, and it synchronises them exactly as
`INJECT_ASYNC_EVENT` does. The differences are:

1. **Localisation.** ChronoTrace diffs paired pass/fail *execution traces* rather
   than searching for a critical point at runtime. The pair is the instrument: an
   ordering present in every failure and no pass is a candidate; one present in
   half of each is noise.
2. **Causality.** ChronoTrace proves it by *forcing* the interleaving.
   Pre-patch under the forced ordering must fail and post-patch under the
   identical ordering must pass, with the harness unchanged. That is a controlled
   experiment; a rerun is a sample.
3. **Abstention.** ChronoTrace refuses when evidence is insufficient — non-race
   flakiness, no observable inversion, a race needing two constraints, a race in
   production code. Each is a documented refusal with a machine-readable reason.
4. **Artifact.** ChronoTrace emits a deterministic regression test.

**FlakeSync's 83.75% is NOT comparable to anything ChronoTrace reports** —
different corpora, different languages, and ChronoTrace deliberately quotes no
headline repair rate. Theirs is the serious number; say so when asked.

**FlakyGuard reframing.** FlakyGuard identifies the "context problem". The trace
diff *is* a context-selection mechanism, which positions ChronoTrace as a
different solution to a problem the state of the art already named.

### 3.4 Commercial / production landscape

| Product | What it does | Category |
|---|---|---|
| **BuildPulse** | Opt-in Claude-powered agent that opens flaky-test **fix PRs** with a diff and a root-cause explanation, working from JUnit XML. Confirms through PR checks | Repair |
| **Datadog** | Test Optimization's **attempt-to-fix** remediation flow, which retries a candidate fix **20 times** to confirm it. Bits AI Dev Agent delivers a patch as a draft PR labelled "Attempt to Fix" | Repair |
| **Trunk** | Detect and quarantine | Quarantine |
| **Gradle Develocity** | Detect and quarantine | Quarantine |
| **Harness** | Detect and quarantine | Quarantine |
| **Buildkite** | Detect and quarantine | Quarantine |
| **CircleCI** | Detect and quarantine | Quarantine |

**Honest positioning (use this verbatim when asked "isn't this already a product?").**
Flaky-test repair is a *shipping product category*, not an open problem. ChronoTrace
makes **no claim to be the only system that repairs flaky tests.** The shipping
auto-fix products run largely unconstrained agents from **test results** — a JUnit
XML report, a failure message, the test source — and confirm by rerunning. That is
a reasonable design and a different one, in three specific ways:

- **Input.** ChronoTrace works from paired *execution traces*, not test results.
  For a concurrency bug the defect lives in the interleaving, and a results file
  does not contain one.
- **Confirmation.** Datadog's 20 retries and BuildPulse's PR checks establish that
  a patch made the test stop failing; they cannot separate "fixed the race" from
  "made it rarer". Forcing the ordering can. A patch that merely moves the timing
  fails ChronoTrace's Tier 1 while passing a rerun gate.
- **Constraint.** Every ChronoTrace patch passes a deterministic policy checker.
  An unconstrained agent optimising for a green rerun has every incentive to reach
  for exactly the constructs that gate rejects.

---

## SECTION 4 — SYSTEM ARCHITECTURE (6 STAGES)

### 4.1 Pipeline overview

```
capture     paired pass/fail traces, occurrence-indexed spans, execution fingerprint
diagnose    observed-order graph -> backward slice -> Ochiai ranking -> force each candidate
schedule    the control point: harness gates instrumented operation entry (used by diagnose + verify)
synthesize  model returns a typed RepairIntent; LibCST applies it across two coroutines
govern      15 deterministic rules; nothing runs without passing all of them
verify      forced replay -> PCT -> statistical, with the tier reached always reported
```

### 4.2 Stage 1 — CAPTURE (`chronotrace/capture/`, 524 LOC)

- **Instrumentation is explicit, because pytest emits no OpenTelemetry spans on
  its own.** `@operation(name, resource=..., access=...)` wraps a coroutine,
  records an occurrence-indexed span, and — critically — provides the single
  point at which a forced-ordering gate can be applied.
- **Spans are keyed by name AND occurrence** (`"name#N"`), never by name alone.
  A loop emitting fifty `SELECT` spans must not collapse into one entry.
- **Execution fingerprint** on every run: `commit_sha`, `python_version`,
  `dependency_lock_hash`, `container_image`, `test_id`, `env_hash`. **Traces with
  different fingerprints are never diffed.** This is the answer to "how do you
  know the difference wasn't environmental?"
- **Probe effect is measured, not hidden.** Capture measures the flake rate with
  and without instrumentation and reports the delta
  (`CaptureBundle.probe_effect_delta`).
- Delivered as a pytest plugin registered through the `pytest11` entry point:
  `pytest --chronotrace`.
- Files: `collect.py`, `fingerprint.py`, `instrument.py`, `plugin.py`.

### 4.3 Stage 2 — DIAGNOSE (`chronotrace/diagnose/`, 893 LOC)

Order of operations is the design. Paradigm detection and trace-pair availability
are settled **before** any graph is built.

1. **Observed-order graph** built from three edge sources: parent-child nesting,
   program order within a task, and resource access.
   - **It is called *observed order*, NOT happens-before.** The order is derived
     from observed start times plus structural edges, not from a partial order
     over synchronization events. Naming it after Lamport while shipping a
     timestamp sort would be a claim the implementation has not earned. *(This is
     a deliberate, load-bearing honesty constraint. Do not upgrade the language.)*
2. **Candidate pair filter** — restricted to pairs touching the same resource
   with at least one write. Assertion spans are excluded (the assertion is the
   observation point, not a reorderable operation).
3. **Backward slice** from the failed assertion.
4. **Ochiai suspiciousness ranking** (spectrum-based fault localization) computed
   across *all* captured traces, not one pass and one fail.
5. **Tie-break by earliest causal position** — ranking by proximity to the
   assertion biases toward the symptom rather than the cause.
6. **"Absence is evidence."** In a failing run the write that should have
   happened often never happens at all. If a run flushed spans normally, an
   operation observed elsewhere but missing here is ordered last. If the run
   crashed/hung (`complete=False`) the same absence means nothing and the pair is
   skipped.
7. **Iteration order is sorted everywhere** — nondeterministic output from a
   determinism tool would be indefensible.
8. **Force each candidate** — this converts a ranking into a decision.

Files: `engine.py`, `graph.py`, `slice.py`, `rank.py`, `depth.py`, `abstain.py`.

### 4.4 The forced-failure-rate decision table (THE core mechanism)

| Forced failure rate | Meaning | Action taken |
|---|---|---|
| **100%** | sufficient condition for the failure | **patch it** |
| **0%** | noise | discard the candidate |
| **strictly between 0 and 1** | necessary but not sufficient | report **bug depth ≥ 2**, do NOT patch |
| **gate timed out** | ordering is unreachable | **INFEASIBLE**, discard the candidate |

**Directly observable on R01:** the test is naturally flaky at ~50%. Under the
forced ordering it fails **20/20**; under the opposite ordering it passes
**20/20**. Same code, same harness — the ordering is the variable. After the
patch, under the *identical* forced ordering, it passes 20/20. The harness does
not change between the two runs, so the only variable is the patch. **That is a
controlled experiment, not a sample.**

### 4.5 Stage 3 — SCHEDULE (`chronotrace/schedule/`, 401 LOC)

- **Why asyncio is tractable:** tasks run cooperatively on one thread and yield
  only at `await` boundaries, and the loop picks the next ready callback. That
  choice is the control point. The harness does not fight an OS scheduler.
- **The gate opens for an operation as soon as its predecessor has *STARTED*, not
  finished.** This distinction is what makes the experiment sound:
  - pre-patch: forcing `read` before `write` lets `read` observe stale state → assertion fails;
  - post-patch: `read` starts, blocks on the injected primitive, `write` is released → test passes.
- The harness is **identical in both runs**, is installed by the verifier for the
  duration of a run and removed afterwards, is never written into a patch, and
  never ships in the repository under test.
- **INFEASIBLE handling:** a gate-wait breach means the ordering cannot be
  produced by this code — a diagnostic result (Tier 1b), not a test failure.
- Also ships: a deterministic event loop with a ready-queue policy, and a **PCT
  priority scheduler** (Burckhardt et al., ASPLOS 2010) for Tier 2.
- Files: `harness.py`, `pct.py`, `loop.py`, `determinism.py`.
- Key constant: `FORCED_SEED = 1729`.

### 4.6 Stage 4 — SYNTHESIZE (`chronotrace/synthesize/apply.py`, 425 LOC)

- The model returns a `RepairIntent` and **nothing else**.
- **LibCST** applies it, format-preserving: the primitive is created in shared
  scope, `set()` goes into one coroutine and `await ….wait()` into another, after
  any docstring.
- **A race is between two coroutines by definition, so a single-function edit
  would be a no-op.** Cross-scope application is required, not optional.
- Generates an autouse pytest fixture that gives each test a fresh gate.
- `ISOLATE_FIXTURE_SCOPE` and cross-module shared scope are **refused with an
  explicit error** rather than half-applied.

### 4.7 Stage 5 — GOVERN (`chronotrace/govern/`, 1030 LOC) — see Section 6

### 4.8 Stage 6 — VERIFY (`chronotrace/verify/`, 575 LOC) — see Section 7

### 4.9 Flow control / abstention map

```
capture -> comparable pass/fail pair?
   no  -> ABSTAIN: NO_TRACE_PAIR
   yes -> diagnose
diagnose -> force each candidate
   100%   -> synthesize
   0%     -> ABSTAIN: NOT_A_RACE
   between-> NEEDS_INVESTIGATION: DEPTH_GE_2_UNRESOLVED
synthesize -> govern (15 rules)
   rejected -> NEEDS_INVESTIGATION: governor rejection
   approved -> verify (tier ladder)
verify -> emit regression guard -> IncidentReport (diff, evidence, seed, guard)
```

---

## SECTION 5 — DATA CONTRACTS (`chronotrace/contracts.py`, 436 LOC)

Rationale: the pipeline crosses **four process boundaries** (pytest subprocess,
agent loop, verifier, UI) and **one model boundary**. A single set of pydantic
models keeps them honest — every stage validates its input rather than trusting
the stage before it. **All state reaching the agent must be JSON-serializable
primitives** — no raw OTel spans, CST nodes or callables.

### 5.1 Capture contracts
- `ExecutionFingerprint` — `commit_sha`, `python_version`, `dependency_lock_hash`, `container_image`, `test_id`, `env_hash`.
- `SpanRecord` — `span_id`, `parent_span_id`, `name`, `occurrence`, `start_ns`, `end_ns`, `task_name`, `source_file`, `source_line`, `attributes`. Property `key` = `"{name}#{occurrence}"`.
- `TraceCapture` — `run_id`, `outcome` (`PASS`/`FAIL`), `fingerprint`, `spans`, `complete`, `instrumented`, `failure_message`, `failing_resource`.
- `CaptureBundle` — `passing[]`, `failing[]`, `runs_executed`, `runs_timed_out`, `natural_flake_rate`, `uninstrumented_flake_rate`, `fingerprint_conflicts`; properties `has_pair`, `probe_effect_delta`.

### 5.2 Diagnosis contracts
- `OperationRef` — `span_name`, `occurrence`, `source_file`, `source_line`, `qualname`, `is_test_scope`, `access` (`read`/`write`/`unknown`), `resource`. **Matching is by structured identity, never substring against source text** — `select` must not match `preselect`.
- `CandidateInversion` — `op_a`, `op_b`, `causal_position`, `ochiai_score`, `in_backward_slice`, `classification`, `forced_failure_rate`, `failing_order[]`.
  - `classification` ∈ `UNTESTED`, `IRRELEVANT`, `SUSPICIOUS`, `NECESSARY_INSUFFICIENT`, `CAUSALLY_SUFFICIENT`, `INFEASIBLE`.
- `Diagnosis` — `status` ∈ `RACE_PROVEN` | `NEEDS_INVESTIGATION` | `ABSTAINED`; `abstain_reason`; `proven_inversion`; `bug_depth`; `candidates_evaluated`; `candidates[]`; `explanation` (*plain-language for the UI; never the basis of a decision*).

### 5.3 The 8 abstention reasons (complete, machine-readable)
`NOT_A_RACE` · `NO_INVERSION` · `DEPTH_GE_2_UNRESOLVED` · `NO_TRACE_PAIR` ·
`SPAN_GRANULARITY_TOO_COARSE` · `PRODUCTION_SCOPE_RACE` · `NON_ASYNCIO_PARADIGM` ·
`THIRD_PARTY_CODE`

Plus one post-diagnosis abstention on `IncidentReport`: `INVALID_INTENT_AFTER_RETRY`
(a race was proven but the model never produced a usable intent).

### 5.4 `RepairIntent` — the ONLY thing the model emits

```python
transformation: Literal["INJECT_ASYNC_EVENT", "AWAIT_UNFINISHED_TASK",
                        "ISOLATE_FIXTURE_SCOPE", "RELAX_ASSERTION", "NO_REPAIR"]
shared_scope:   Literal["FIXTURE", "CLASS_ATTR", "MODULE", "NONE"]
scope_target:   str | None
signal_site:    OperationRef | None
wait_site:      OperationRef | None
primitive:      Literal["asyncio.Event", "asyncio.Barrier", "task_await", "none"]
rationale:      str
```

**Schema-level validators (fail fast, give the model a usable error on the spot):**
- `INJECT_ASYNC_EVENT` requires **both** `signal_site` and `wait_site`.
- `AWAIT_UNFINISHED_TASK` requires `scope_target` (the task variable the test already holds).

**Implementation status of the five transformations:**

| Transformation | Status |
|---|---|
| `INJECT_ASYNC_EVENT` | **Fully implemented** |
| `AWAIT_UNFINISHED_TASK` | **Fully implemented** |
| `ISOLATE_FIXTURE_SCOPE` | Declared in schema; refused with explicit error, not half-applied |
| `RELAX_ASSERTION` | Declared; proposed relaxations go to a human, never auto-applied |
| `NO_REPAIR` | Abstention signal |

- `IntentAttempt` — `attempt`, `accepted`, `transformation`, `error`, `tokens_input`, `tokens_output`. **Retries are recorded, not collapsed** — a repair that took three tries is a different result from one that took a single call.

### 5.5 Governance contracts
- `GovernorVerdict` — `approved`, `negative_violations[]`, `positive_check_passed`, `deadlock_cycle_detected`, `scope_violation`, `diff_checks[]`, `rules_evaluated[]`.
- `RuleOutcome` — `rule_id`, `description`, `passed`, `detail`. **Every rule reports, so the gauntlet is auditable rather than a single fired rule.**

### 5.6 Verification contract
- `VerificationResult` — `tier_reached`, `pre_patch_forced_failed`, `post_patch_forced_passed`, `post_patch_forced_infeasible`, `pct_runs`/`pct_failures`, `statistical_runs`/`statistical_failures`, `pre_patch_natural_failures`, `deadlock_detected`, `measured_overhead_ms` (*measured, never assumed zero*), `reproduction_seed`, `isolation`, `symptom_patch_suspected`.
- Property `causally_proven` — requires pre-patch forced failure **and** the patch defeating it (either harmless or unreachable).
- Property `repair_strength` — plain language for reports/UI.

### 5.7 Presentation + output contracts
- `LaneSpan` / `TraceLane` — spans on a shared, run-relative millisecond time axis so a passing and a failing execution can be drawn against each other without leaking absolute clocks into the UI.
- `IncidentReport` — the unit the UI renders: `incident_id`, `test_id`, `ui_state` (`FIXED`/`NEEDS_INVESTIGATION`/`ABSTAINED`), `diagnosis`, `intent`, `verdict`, `verification`, `unified_diff`, `regression_test_path`, `regression_verified`, `natural_flake_rate`, `probe_effect_delta`, `pass_lane`, `fail_lane`, `rejected_attempts[]`, `intent_attempts[]`, `abstain_reason`, `tokens_input`, `tokens_output`, `llm_calls`, `wall_clock_s`, `provider`.

### 5.8 Typed exception hierarchy (`chronotrace/errors.py`)
`ChronoTraceError` → `ConfigurationError`, `CaptureError` (→ `NoTracePairError`,
`FingerprintMismatchError`), `DiagnosisError`, `ScheduleError` (→
`InfeasibleOrderingError`, `UnsupportedRuntimeError`), `PatchError`,
`GovernorRejectionError` (*never caught to "try harder"*), `VerificationError`
(→ `DeadlockDetectedError`), `ProviderError`.

**Why:** the difference between an infrastructure failure and a test failure is
load-bearing. An OOM-killed container is not a flake; a timeout is a deadlock
signal, not a red test.

---

## SECTION 6 — THE GOVERNOR: 15 RULES AND 17 ADVERSARIAL ATTACKS

### 6.1 The 15 rules, verbatim from `chronotrace/govern/gate.py`

| ID | Class | Rule |
|---|---|---|
| **N1** | Negative | no sleep calls introduced |
| **N2** | Negative | no aliased sleep imports introduced |
| **N3** | Negative | no timeout marker added or inflated |
| **N4** | Negative | no retry or flaky decorator added |
| **N5** | Negative | no retry loop wrapped around the assertion |
| **N6** | Negative | no assertion removed or weakened |
| **N7** | Negative | no exception handler swallowing the failure |
| **N8** | Negative | no test skipped, xfailed or renamed out of collection |
| **P1** | Positive | a real synchronization primitive was added |
| **P2** | Positive | the primitive is reachable from both the signal and the wait site |
| **P3** | Positive | the patch is not a no-op |
| **S1** | Structural | the proposed wait edge creates no wait-for cycle |
| **S2** | Structural | no production-scope file modified without opt-in |
| **S3** | Structural | no third-party or vendored file modified |
| **S4** | Structural | the patched module parses |

**Why positive rules exist (this is the subtle, important part).** Without P1–P3,
"0% band-aid rate" would be **satisfiable by changing nothing**. Bans alone are a
bypass. The gate is both negative (rejects) and positive (requires).

**`DIFF_RULES = {N3, N6, N8}`** — rules that cannot be decided from the
post-patch tree alone and therefore compare *before* against *after*: timeout
inflation, a weakened assertion, a decollected test.

**Name resolution through the import table.** Negative rules resolve names
through the module's import table, so `from time import sleep as _settle` is
caught as a sleep. A naive name-text scan would miss it — and one of the 17
attacks is exactly that.

**Short-circuit:** if S4 fails (the patched module does not parse), the verdict
returns immediately.

### 6.2 The 17 adversarial gauntlet attacks (`chronotrace/govern/gauntlet.py`)

Runnable with **zero credentials and zero models** in a fresh checkout:
`uv run chronotrace gauntlet` → **17 attacks, 17 rejections, each by the rule that
targets it.** Also run as a CI step.

| # | Rule caught by | Attack | Why it's crafted this way |
|---|---|---|---|
| 1 | N1 | `time.sleep(0.05)` before the read | The classic band-aid: wait long enough that the writer usually wins |
| 2 | N1 | `await asyncio.sleep(0.05)` before the read | The async flavour, just as permanent in CI |
| 3 | **N2** | `from time import sleep as _settle` then `_settle(0.05)` | **Defeats a name-text check for "sleep"** — requires import-table resolution |
| 4 | **N3** | `@pytest.mark.timeout(30)` → `(300)` | **Only the diff shows it** — the post AST alone looks fine |
| 5 | N4 | `@pytest.mark.flaky(reruns=3)` | Quarantine wearing a repair's clothes |
| 6 | **N4** | `@tenacity.retry` | **Third-party retry**, resolved through the import table, not matched by name |
| 7 | N5 | `while True:` poll loop around the assertion | A sleep with extra steps |
| 8 | N6 | `assert observed == "ready"` → `assert observed in {None, "ready"}` | Equality weakened to membership so a stale read passes |
| 9 | N6 | Assertion deleted entirely | Test is green and checks nothing |
| 10 | N7 | `try: assert … except AssertionError: pass` | A caught assertion is a deleted test |
| 11 | N8 | `@pytest.mark.skip(reason="flaky")` | Quarantine by another name |
| 12 | N8 | `test_x` renamed to `_disabled_x` | Renamed out of pytest collection |
| 13 | **P3** | No-op patch — changes nothing | **Passes every ban trivially. This is why bans alone are a bypass** |
| 14 | P1 | Cosmetic edit only (docstring changed) | Reformats without establishing any ordering |
| 15 | **P2** | `asyncio.Event` `set()` and `wait()` **in the same coroutine** | The operations there are already ordered; the primitive does nothing |
| 16 | **S1** | Two events awaited in opposite order (mutual wait) | **Turns an intermittent failure into a permanent hang** |
| 17 | S3 | Patch targets `.venv/lib/python3.11/site-packages/somelib/runner.py` | Fixes the test by editing an installed dependency, which nobody can review or ship |

**Governor design constraint:** the gate cannot be bypassed, weakened, or relaxed
"just for the demo" — it is the entire differentiator.

Files: `gate.py`, `negative.py`, `positive.py`, `scope.py`, `deadlock.py`,
`resolve.py`, `gauntlet.py`.

---

## SECTION 7 — THE VERIFICATION LADDER

### 7.1 Tiers (`chronotrace/verify/tiers.py`)

| Tier | `tier_reached` value | Method | Claim |
|---|---|---|---|
| 1 | `FORCED_HARMLESS` | Harness gates reproduce the ordering; it still occurs and no longer fails | **Causality proven** |
| 1 | `FORCED_UNREACHABLE` | The patch made the interleaving impossible to produce at all | **Causality proven — stronger** |
| 1b | `INFEASIBLE` | The ordering times out pre-patch | Candidate was never reachable → discarded |
| 2 | `PCT` | Seeded randomized scheduling (Burckhardt et al.) | Probabilistic bound only |
| 3 | `STATISTICAL` | Plain reruns | Residual flake check only |
| — | `FAILED` | Forced ordering failed before and still fails after | **Patch rejected** |

### 7.2 The three honesty rules attached to the ladder

1. **Tier 1 requires BOTH halves.** Pre-patch must fail under the forced ordering
   **and** post-patch must pass under the *identical* ordering, with the harness
   unchanged. One half alone proves nothing.
2. **A Tier 2 or Tier 3 result is NEVER reported as causal proof.** Silently
   degrading while still claiming causality is the one thing that would make the
   project dishonest, so the tier travels with the result everywhere it is
   displayed — CLI, JSON, and UI.
3. **Both Tier-1 outcomes count as repairs, and this is anti-bias.** An injected
   event leaves the ordering reachable (`FORCED_HARMLESS`); awaiting the task
   eliminates it (`FORCED_UNREACHABLE`). Scoring only the first would quietly
   reward ChronoTrace's own transformation over repairs that eliminate the
   ordering entirely. That is a bias in its own favour, and it is why the
   distinction is made rather than collapsed.

### 7.3 Seeding policy
Seeds are **pinned for Tier 1** (`FORCED_SEED = 1729`) and **left alone for
Tier 3**. Pinning them for the residual check would make "N/N stable" true by
construction. Forced runs sweep **consecutive seeds** rather than repeating one,
so that what is *not* being forced stays free — freezing it would make a bug
needing two constraints read as a single sufficient one.

### 7.4 `symptom_patch_suspected`
Tier 1 passed but Tier 3 is still flaky — the signature of patching a symptom.
Surfaced rather than suppressed.

### 7.5 The regression guard (`chronotrace/verify/regression.py`) — THE PRODUCT
- Appended to the module it guards, which keeps the module's fixtures (including
  the one managing the injected primitive's lifetime) in scope and puts the fix
  and its guard in the same reviewable diff.
- Named `test_chronotrace_regression_<incident_slug>`.
- Imports `ScheduleHarness, force_order` and re-forces the exact ordering.
- **Effect: a race that appeared once in a thousand runs now reproduces every
  run, in milliseconds.**
- `IncidentReport.regression_verified` records that the emitted guard was
  actually executed and reproduced the ordering it claims to.

---

## SECTION 8 — THE AGENT (AWS Strands Agents SDK)

### 8.1 Construction (`chronotrace/agent/graph.py`, part of 607 LOC agent package)
```python
Agent(
  model=BedrockModel(model_id=model_id, region_name=settings.aws_region),
  system_prompt=SYSTEM_PROMPT,
  tools=[...9 @tool-decorated bound methods...],
)
```
Default `model_id` = `amazon.nova-pro-v1:0` (`DEFAULT_BEDROCK_MODEL`).
Strands is an **optional extra** — imported lazily so the package imports without it.

### 8.2 The 9 registered tools (`chronotrace/agent/tools.py`)

| Tool | What the agent gets |
|---|---|
| `capture_traces` | Comparable pass/fail trace pairs, and the measured flake rate |
| `trace_slice` | The backward slice from the failed assertion |
| `compare_orderings` | Observed-order inversions, Ochiai-ranked |
| `force_replay` | The forced failure rate for one ordering — **the tool that turns a ranking into a decision** |
| `source_context` | Source around an operation, before proposing anything |
| `diagnose_now` | The full diagnosis and its decided status |
| `check_patch` | The governor's verdict on a candidate patch |
| `propose_repair` | **The only way to act** — patches, governs and verifies |
| `run_once` | One natural run |

> **NUMBERING NOTE FOR FUTURE LLMs.** The count is **9**. Some project text
> historically said "8 tools" because it enumerated the investigation tools and
> omitted `propose_repair`. That was corrected on 2026-09-10 (verified: nine
> `@tool` decorators in `chronotrace/agent/tools.py`). The README's tool *table*
> still lists 8 investigation tools; the registered surface is 9.

### 8.3 Authority boundary
Authority stays deterministic on **both** sides of that list. The agent may
*request* a forced replay; it cannot decide that a rejected patch is acceptable,
and it never writes source. `check_patch` **returns** the governor's answer — it
does not ask for one. A rejection is information, not a dead end.

### 8.4 The agent system prompt (structure)
- 7 numbered steps: capture → slice → compare → force → source → check → propose.
- States the decision rule explicitly: forced failure rate **1.0 = sufficient**,
  **0.0 = noise**, **in between = needs more than one constraint**.
- Names exactly two repairing transformations and the condition that selects each:
  - `INJECT_ASYNC_EVENT` — a reader observed state a writer had not yet published.
  - `AWAIT_UNFINISHED_TASK` — the assertion depends on a task *completing*, not on a single write landing.
- Explicitly: *"Choosing between them is the judgement being asked of you: look at
  what the assertion actually depends on, not at which one the inversion
  superficially resembles."* **(R14 is the case where the model failed exactly
  this instruction.)**
- Abstention is named as a correct outcome with four qualifying conditions.
- Sleeps/retries/timeout increases/weakened assertions/skips are named as
  auto-rejected, so proposing one wastes a round.

### 8.5 Verifiable wiring with no AWS account
```bash
uv run chronotrace agent --demo --dry-run   # prints the registered tool surface; no model contacted
```
**Why this command exists:** this is a failure mode with **no symptom**. Strands
logs `unrecognized tool specification` for a tool it cannot read and *carries on*,
so an agent wired wrongly still constructs, still answers fluently, and reports no
error. It did exactly that in this project for **three commits** (fixed in
`9e717b6`). `tests/test_agent_tools.py` now asserts all nine register.

---

## SECTION 9 — AWS SURFACE: WHAT IS WIRED, WHAT IS NOT

### 9.1 Amazon Bedrock (the one judgement call)
- **`amazon.nova-pro-v1:0`** — default for the agent loop and for intent synthesis.
- **`amazon.nova-lite-v1:0`** — measured at **2.8 s** for one `RepairIntent`,
  **3,066 input / 286 output tokens**. *(This figure comes from the R14 run — do
  not attribute it to the Act I footage, which is Nova Pro at 3.0 s / 2,693 in /
  296 out.)*
- **Structured output enforced through Bedrock's `converse` tool-use schema**, so
  the model returns a validated `RepairIntent` and **has no channel for source code**.
- Inference config for intent: `temperature: 0.0`, `maxTokens: 2048`.
- Model ids are **configuration with no hardcoded default in `.env`** — ids
  change between regions and releases, and a stale hardcoded id fails confusingly
  at runtime.

### 9.2 Bedrock AgentCore Runtime — DEPLOYED AND INVOKED 2026-09-09
- **Runtime ARN:** `arn:aws:bedrock-agentcore:us-east-1:044468733589:runtime/chronotrace-W8r1r453Mi`
- Entrypoint: `chronotrace.agent.graph:handler`, configured in
  `chronotrace/agent/deploy/agentcore.yaml`; shim at `agentcore_entry.py`.
- Two modes: `agent` (Strands loop) and `pipeline` (fixed sequence, full incident
  report). Everything crossing the boundary is primitive JSON.
- **`agent` mode responds. `pipeline` mode was never invoked** — the 90-minute
  timebox expired. Nothing is claimed about it either way (untested, not
  known-broken).

**What genuinely ran inside the runtime (measured):**
- `capture_traces` spawned pytest subprocesses and measured a **0.7 flake rate
  over 10 runs (7 failing, 3 passing)**.
- `force_replay` forced the candidate ordering to a failure rate of **1.0**.
- The governor **approved** the synthesized patch (`approved=True violations=[]`).
- **6 cycles, 16,347 total tokens** (15,536 in / 811 out), `stop_reason: end_turn`.

**What does NOT work there:** `propose_repair` fails with a **permission error**
when it writes the patched file — the deployed bundle is not a writable checkout.
The agent handles this correctly: it **abstains and says why**, rather than
claiming a repair. **The runtime is therefore a working *investigator* and not a
working *repairer*.** The fix is writing to a writable scratch path, which is a
code change not a deploy change, and was out of scope. Precision caveat: the
permission error is what the tool returned to the model; the raw traceback did
not appear in the runtime logs, so the exact errno is not recorded.

**Deploy detail worth knowing (the first deploy failed).**
`ModuleNotFoundError: No module named 'bedrock_agentcore'`, surfaced to the caller
as `RuntimeClientError: Runtime initialization time exceeded ... 30s`. **Cause:**
for a direct-code deploy the starter toolkit **ignores the `--requirements-file`
flag** at deploy time (`launch.py` calls `detect_dependencies(source_dir)` with no
explicit file) and auto-detects instead. It found `pyproject.toml`, which does not
list the AgentCore SDK. **Fix:** a root `requirements.txt`, cross-compiled for
`linux/arm64` with `uv pip install --only-binary :all:` — under which the local
project *cannot* be installed from source, so dependencies are listed explicitly
and `chronotrace` is imported from the bundle rather than pip-installed.

**Consequence:** `PYTEST_PLUGINS=chronotrace.capture.plugin` is set as a runtime
env var. The pytest plugin normally registers through the `pytest11` entry point,
which only exists if the package is pip-installed. Without it the spawned pytest
runs would reject `--chronotrace` as an unrecognised argument.

**`agentcore_entry.py` sits at the repository root, not next to `agentcore.yaml`** —
the runtime launches the entrypoint as a script, so the file's own directory lands
on `sys.path`; only at the root does that directory contain `chronotrace/` and
`benchmark/`.

**IAM permissions granted (least privilege, tracks what the code does):**
`bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`,
`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.
*(DynamoDB grants that used to be there were removed — no code path calls it.)*

**Verbatim AgentCore response (the record of what ran):**
```json
{"mode": "agent", "test_id": "benchmark/cases/R01_unawaited_writer/test_R01_unawaited_writer.py::test_reader_sees_committed_value", "stop_reason": "end_turn", "cycles": 6, "tool_calls": {"capture_traces": 1, "compare_orderings": 1, "force_replay": 1, "propose_repair": 1, "trace_slice": 1}, "usage": {"inputTokens": 15536, "outputTokens": 811, "totalTokens": 16347}, "conclusion": "I abstain from making any repairs ... due to a permission error. The analysis suggests that injecting an asyncio event to ensure the reader waits for the writer to commit the value would be an appropriate repair. However, I do not have the necessary permissions to modify the file."}
```

### 9.3 AWS Amplify Hosting — the dashboard
- App `d3k7wvrz5f9b6h`, branch `main`, `us-east-1`, deploy job 1 `SUCCEED`.
- **Deployed artifact:** the `ui/out` static export — **86 files, 434 KB zipped**.
- **No runtime, no credentials, no model call behind it** — which is why it can be
  published at all.
- **Zip deploy, not Git-connected** — the GitHub OAuth handshake could not be
  completed headlessly. `ui/amplify.yml` is therefore unused by this deployment
  and left in place for a future Git-connected flow.
- **Verified against the live URL** by `scripts/verify_deploy.py` (Playwright):
  HTTP 200, **15 incident rows** (not the empty state), **0 console errors**, plus
  two screenshots. *(Both the empty state and the Next.js error boundary return
  HTTP 200, so the row assertion is what actually separates working from broken.)*

### 9.4 What is explicitly NOT wired to AWS (state this; an earlier draft claimed both)

| Claimed capability | Reality |
|---|---|
| **CloudWatch trace export** | **NOT implemented.** Traces are JSONL under `telemetry/`. Differential analysis needs 100% complete traces — probabilistic sampling would destroy the diff — and CloudWatch Transaction Search is the right answer to that. `CHRONOTRACE_TELEMETRY=cloudwatch` now **raises** rather than silently keeping local behaviour |
| **DynamoDB incident registry** | **NOT implemented.** Incidents are SQLite under `.chronotrace/`. `CHRONOTRACE_REGISTRY=dynamodb` **raises** for the same reason |

**Why they raise rather than no-op:** both knobs were readable long before either
backend existed, and neither value was ever consulted — so selecting `cloudwatch`
silently kept local behaviour. *A telemetry setting that quietly does nothing is
worse than no setting: it reads, in a config file and in a review, as evidence
that traces are being retained somewhere.*

**Scope of AWS dependence:** trace diffing, patching, policy enforcement and
verification are **all local and AWS-independent by design**. Bedrock is where the
**one** judgement call happens, and that is the whole of ChronoTrace's dependence
on it.

### 9.5 AWS cost (Cost Explorer, month-to-date at deploy time)

| Service | USD |
|---|---|
| Amazon Bedrock | 0.0092 |
| Amazon S3 | 0.00004 |
| AWS Secrets Manager | 0.000005 |
| **Total** | **0.0093** |

Cost Explorer lags ~1 day, so AgentCore Runtime and Amplify charges are likely not
yet included; both are small (Amplify static hosting is fractions of a cent at this
traffic; agent runs used ~16k tokens each on Nova Pro). Guardrail:
`chronotrace-hackathon` budget, **$10/month**, email alert at 80% actual spend.

### 9.6 Security / credential hygiene
- No credential appears in any file, commit, screenshot, or summary.
- Credentials were sourced per-command from a Downloads CSV via a script in a
  session scratch directory **outside** the repository.
- The deploy zip was built in a scratch directory, not the repo root, so there was
  never a window in which it could be committed.
- `.bedrock_agentcore.yaml` and `.bedrock_agentcore/` are gitignored (machine-specific
  absolute paths and a 10 MB dependency cache).
- Post-submission manual actions: delete IAM user `chronotrace-deploy`; delete
  `~/Downloads/chronotrace-deploy_accessKeys.csv`.

---

## SECTION 10 — COMPLETE TECHNOLOGY STACK (A to Z)

### 10.1 Core runtime dependencies (`pyproject.toml [project.dependencies]`)

| Package | Constraint | Role in ChronoTrace |
|---|---|---|
| `pydantic` | `>=2.7` | Every data contract; schema validation at each of 4 process boundaries + the model boundary |
| `pydantic-settings` | `>=2.3` | `Settings` with `CHRONOTRACE_` env prefix; the single config surface |
| `libcst` | `>=1.4` | Format-preserving CST transformation — applies `RepairIntent` across two coroutines |
| `networkx` | `>=3.3` | Observed-order graph; wait-for cycle detection (deadlock rule S1) |
| `structlog` | `>=24.1` | Structured logging (the `bedrock.call` / `governor.verdict` lines seen in the demo) |
| `typer` | `>=0.12` | CLI framework |
| `pytest` | `>=8.2` | Test runner; also a **runtime** dependency because capture and forced replay spawn pytest subprocesses |
| `pytest-asyncio` | `>=0.23` | `asyncio_mode = "auto"` |
| `pytest-json-report` | `>=1.5` | Machine-readable run outcomes for capture |
| `pytest-repeat` | `>=0.9` | `--count N` for flake-rate measurement |

### 10.2 Optional extras

| Extra | Packages | Purpose |
|---|---|---|
| `bedrock` | `boto3>=1.34`, `strands-agents>=0.1` | Amazon Bedrock provider + AWS Strands Agents SDK |
| `dev` | `ruff>=0.5`, `mypy>=1.10`, `pytest-cov>=5.0`, `hypothesis>=6.100`, `types-networkx>=3.3`, `playwright>=1.44` | Lint, strict typing, coverage, property-based testing, browser automation for architecture stills + deploy verification |

### 10.3 Frontend stack (`ui/`)

| Technology | Version | Role |
|---|---|---|
| Next.js | 14.2.15 | App Router; **static export** to `ui/out` |
| React | ^18.3.1 | UI |
| React DOM | ^18.3.1 | |
| TypeScript | ^5.6.2 | |
| Tailwind CSS | ^3.4.13 | Styling |
| Framer Motion | ^11.5.4 | Transitions |
| PostCSS / Autoprefixer | ^8.4.47 / ^10.4.20 | Build |
| Dev port | 3939 | `npm run dev` |

**UI components:** `TraceDivergence.tsx` (233 LOC — the two-lane time axis),
`Verification.tsx` (153), `GovernorGauntlet.tsx` (86), `TierBadge.tsx` (57),
`StateBadge.tsx` (27), `DiffView.tsx` (27), `Section.tsx` (17).
**Routes:** `/` (incident list, 58 LOC), `/incident/[id]` (169 LOC), `/eval` (169 LOC).
**Data path:** a `prebuild` Node script copies `../eval-results/incidents.json` into
`public/`, falling back to a committed snapshot, and hard-failing with an
actionable message if neither exists. **No service, no network round-trip — a demo
cannot stall on a request.**

### 10.4 Infrastructure and tooling

| Layer | Technology |
|---|---|
| Package/dependency manager | **uv** (Astral) — `uv.lock` (409 KB) is the source of truth |
| Build backend | hatchling |
| Linter + formatter | **ruff** 0.16.6 — line length 100, target py311, rule sets `E,F,I,N,UP,B,A,C4,SIM,ARG,PTH,RUF,ANN,D` |
| Type checker | **mypy**, `strict = true`, `warn_unreachable = true`, 74 files |
| Property-based testing | **hypothesis** |
| Coverage | **coverage.py**, `fail_under = 80` |
| Pre-commit | ruff (+`--fix`), ruff-format, mypy, trailing-whitespace, end-of-file-fixer, check-added-large-files, check-merge-conflict, **detect-private-key** |
| CI | **GitHub Actions** (`.github/workflows/ci.yml`), 2 jobs |
| Model providers | Amazon Bedrock (`converse` API), **Ollama** (local), fixture replay, reference policy |
| Local model used in eval | **qwen2.5-coder:14b** (14.8B, Q4_K_M, digest `9ec8897f747e…`, context 32768) via Ollama 0.32.14 |
| Second local model tested | **qwen3:8b** (8.2B, Q4_K_M, digest `500a1f067a9f…`, context 40960) |
| Storage — traces | JSONL under `telemetry/` |
| Storage — incidents | SQLite under `.chronotrace/incidents.sqlite3` (tables: `incidents`, index `incidents_by_test`) |
| Isolation | `process` (default, one process per run) or `docker` (implemented, **unexercised**) |
| Static hosting | AWS Amplify Hosting |
| Serverless agent host | AWS Bedrock AgentCore Runtime (`PYTHON_3_11`, `linux/arm64`, direct code deploy, network mode PUBLIC, HTTP protocol, `NO_MEMORY`) |
| Video render pipeline | Remotion (separate repo `chronotrace-video`), 1920×1080 @ 30fps, whisper-derived caption offsets, `npm run verify` timeline assertions |

### 10.5 CI pipeline (`.github/workflows/ci.yml`)

**Job `check`** (on push to `main` and all PRs):
1. `uv sync --extra dev --extra bedrock`
2. `uv run ruff check .`
3. `uv run ruff format --check .`
4. `uv run mypy chronotrace`
5. `uv run pytest tests -m "not benchmark" -q`
6. **`uv run chronotrace gauntlet`** ← the adversarial governor runs in CI
7. `uv run python -c "import chronotrace; print(chronotrace.__version__)"` (public API imports cleanly)

**Job `benchmark`:**
1. `uv run coverage run -m pytest tests -q`
2. `uv run coverage report` (gate at 80%)

**Non-obvious detail, documented in `pyproject.toml`:** coverage must be measured
with `coverage run -m pytest`, **not** `pytest --cov`. ChronoTrace ships a pytest
plugin through the `pytest11` entry point, so pytest imports the package while
loading plugins — *before* pytest-cov starts measuring — and every module body
would otherwise be recorded as unexecuted.

**Coverage omissions, and why they are principled:** `providers/bedrock.py`,
`providers/ollama.py`, `eval/three_arm.py`, `eval/three_arm_report.py` are omitted
because each needs a live model provider to execute a single line — in CI they are
not undertested, they are *unreachable*. `chronotrace/agent/*` is deliberately
**not** omitted: tool registration happens without contacting a model, and that
registration is exactly what regressed once already.

### 10.6 Configuration surface (`chronotrace/config.py`, env prefix `CHRONOTRACE_`)

| Setting | Default | Notes |
|---|---|---|
| `provider` | `reference-policy` | ∈ `reference-policy`, `bedrock`, `ollama`, `fixture` |
| `telemetry` | `jsonl` | `cloudwatch` **raises** |
| `registry` | `sqlite` | `dynamodb` **raises** |
| `isolation` | `process` | or `docker` |
| `aws_region` | `us-east-1` | |
| `model_id_small` / `model_id_large` | `""` | Deliberately no default |
| `ollama_host` | `http://localhost:11434` | |
| `ollama_model` | `qwen2.5-coder:14b` | The only local model observed driving the full pipeline end to end |
| `model_temperature` | `0.0` | |
| `model_seed` | `1729` | |
| `model_max_tokens` | `4096` | |
| `model_timeout_s` | `600.0` | |
| `max_intent_retries` | `2` | Bounded — an unbounded loop against a model that cannot comply is a spend, not a repair |
| `max_attempts` | `3` | Binds **every** arm equally |
| `run_timeout_s` | `30.0` | A breach is a deadlock |
| `gate_timeout_s` | `5.0` | A breach means INFEASIBLE, **not** FAIL |
| `statistical_runs` | `20` | Tier 3 sample size |
| `pct_runs` | `0` | Zero disables PCT, reported as *not attempted* |
| `max_rounds` | `5` | |
| `allow_production_repair` | `false` | Production-scope races abstain by default |
| `workdir` / `fixtures_dir` / `telemetry_dir` | `.chronotrace` / `fixtures` / `telemetry` | |

**Design note:** config lives in exactly one module. Scattered `os.getenv` calls
are how a system ends up with two different timeouts for the same thing.

---

## SECTION 11 — REPOSITORY MAP AND CODE METRICS

### 11.1 Package structure and size

| Package | LOC | Responsibility |
|---|---|---|
| `chronotrace/eval/` | 1,773 | Three-arm harness, scoring, reporting, baselines, band-aid detection, replay check |
| `chronotrace/providers/` | 1,061 | Bedrock, Ollama, reference policy, fixture recording, prompts, detection |
| `chronotrace/govern/` | 1,030 | 15 rules + 17-attack gauntlet |
| `chronotrace/cli.py` | 1,020 | Typer CLI, demo renderers |
| `chronotrace/diagnose/` | 893 | Graph, slice, rank, depth, abstain, engine |
| `chronotrace/agent/` | 607 | Strands agent, 9 tools, AgentCore handler |
| `chronotrace/verify/` | 575 | Tier ladder, runner, regression guard |
| `chronotrace/capture/` | 524 | pytest plugin, instrumentation, fingerprint, collection |
| `chronotrace/contracts.py` | 436 | Every data contract |
| `chronotrace/synthesize/` | 425 | LibCST application |
| `chronotrace/schedule/` | 401 | Forced harness, PCT, deterministic loop |
| `chronotrace/pipeline.py` | 351 | End-to-end orchestration |
| `chronotrace/registry/` | 172 | SQLite incident store, loop safety |
| `chronotrace/config.py` | 118 | Settings |
| `chronotrace/errors.py` | 64 | Typed exception hierarchy |
| `chronotrace/__init__.py` | 63 | Deliberately small public surface |
| `chronotrace/logging.py` | 39 | structlog setup |
| **Total package** | **9,552** | **62 Python files** |
| `tests/` | 2,444 | 12 test files |
| `benchmark/` | 685 | 15 seeded cases |
| `ui/` | ~1,240 (excl. generated) | Next.js dashboard |

### 11.2 Test files

| File | LOC | Covers |
|---|---|---|
| `test_units.py` | 478 | Unit + property-based (hypothesis) |
| `test_three_arm.py` | 468 | Three-arm harness invariants |
| `test_cli.py` | 294 | CLI surface |
| `test_apply.py` | 215 | LibCST transformation |
| `test_graph.py` | 168 | Observed-order graph |
| `test_verify.py` | 150 | Tier ladder |
| `test_contracts.py` | 146 | pydantic contracts + validators |
| `test_agent_tools.py` | 145 | **Asserts all 9 Strands tools register** |
| `test_abstain.py` | 111 | 8 abstention paths |
| `test_harness.py` | 107 | **Both orderings of a seeded race reproducible on demand** |
| `test_governor.py` | 96 | 15 rules + gauntlet |
| `test_pipeline.py` | 66 | End-to-end |

### 11.3 Quality metrics — MEASURED 2026-09-10, not asserted

| Metric | Value | Command |
|---|---|---|
| Tests passing | **199 passed in ~103 s** | `uv run pytest` |
| Coverage | **80%** (3,423 statements, 694 missed) | `uv run coverage run -m pytest && uv run coverage report` |
| Coverage gate | `fail_under = 80` — **currently passing exactly at the line** | |
| mypy | **Success: no issues found in 74 source files**, `strict = true` | `uv run mypy chronotrace/ tests/` |
| ruff lint | **All checks passed!** | `uv run ruff check .` |
| ruff format | **106 files already formatted**, 0 to reformat (`verify_deploy.py` fixed in `a10b391`) | `uv run ruff format --check .` |
| ruff format — note | ruff 0.16.6 also formats Python blocks *inside Markdown*. `MASTER_DOC.md` is therefore listed in `extend-exclude` in `pyproject.toml`, alongside `docs/posts`, for the reason already recorded there: formatting a prose snippet rewrites the example being explained | |

> **RESOLVED 2026-09-10 in `a10b391`.** The CI `Format check` step was red on
> `scripts/verify_deploy.py:88` — a two-line `_check(...)` call ruff wanted on one.
> That step had failed on *every* run since `0b372a1` on 2026-09-08 (eight
> consecutive runs, different files each time), and because the job stops at the
> first failure, Type check, the tests, the gauntlet and the import check had not
> executed on CI in two days. Run `34446628164` is green with all six steps run.

**100% coverage modules:** `govern/deadlock.py`, `govern/gate.py`, `govern/scope.py`,
`providers/base.py`, `providers/prompts.py`, `providers/reference_policy.py`,
`registry/store.py`. **High:** `govern/negative.py` 99%, `govern/positive.py` 98%,
`verify/regression.py` 97%, `schedule/harness.py` 94%, `govern/gauntlet.py` 94%.
**Lowest measured:** `verify/tiers.py` 72%, `eval/score.py` 78%.

### 11.4 Documentation inventory

| File | Size / count | Content |
|---|---|---|
| `README.md` | 42 KB | The full project statement, all results, prior work, limitations, references |
| `ARCHITECTURE.md` | 5.7 KB | Mermaid diagram + 6-stage walkthrough |
| `HANDOVER.md` | 16 KB | LLM context handover; corrections log |
| `DEPLOY_SUMMARY.md` | 8.1 KB | What is live, what is not, decisions, cost |
| `DEPLOY_TASK.md` | 13 KB | The deploy brief (deliberately uncommitted) |
| `docs/adr/` | 6 ADRs | The six decisions that shaped the system |
| `eval/results/FINDINGS.md` | — | Canonical local-model findings write-up |
| `docs/posts/` | 5 files | Build-journey posts, YouTube pack, Devpost story, Builder Center update |
| `demo/` | 2 files | Demo sequence + terminal geometry |
| `fixtures/` | 78 JSON | Recorded provider (request, response) pairs for byte-exact offline replay |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE` | — | Project hygiene |

### 11.5 Visual assets

| Path | Content |
|---|---|
| `assets/architecture.html` | Claude Design 6-stage component source |
| `assets/video/arch-[0-6]-*.png` | 7 rendered pipeline stills (`0-neutral`, `1-trigger`, `2-capture`, `3-diagnose`, `4-agent`, `5-governor`, `6-verify`) |
| `assets/readme/00-thumbnail.jpg` | 16:9 thumbnail used for YouTube and Devpost (also at `~/Desktop/ChronoTrace-Blog-Assets/`, 1376×768) |
| `assets/readme/01-flake-check.png` | Video frame @ 16.5 s — 20 runs, 11 failures |
| `assets/readme/02-gauntlet.png` | Video frame @ 179 s — 17/17 rejections |
| `assets/readme/03-forced-replay.png` | Video frame @ 157 s — Bedrock repair, FORCED_HARMLESS |
| `assets/readme/04-r14-rejected.png` | Video frame @ 226.5 s — forced replay returns FAILED |
| `assets/readme/05-results.png` | Video frame @ 272 s — three-arm table (**qwen run**, labelled as such) |
| `assets/deploy/amplify-live.png` | Live dashboard list, 1440×900 |
| `assets/deploy/amplify-incident.png` | Live dashboard detail, full page |
| `scripts/render_architecture.py` | Playwright still generator |

**All five README stills are frames of the shipped video, so they cannot drift
from it.** Terminal crops: `crop=1450:945:238:40`. Full-bleed slides:
`crop=1920:880:0:0` (cuts the caption bar at y=870).

---

## SECTION 12 — THE BENCHMARK CORPUS (15 seeded cases)

### 12.1 Complete case table

| ID | Name | Shape / true cause | Expected UI state | Expected transformation | Expected abstain reason | In 3-arm corpus? |
|---|---|---|---|---|---|---|
| **R01** | `unawaited_writer` | unsynchronised async I/O | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R02** | `commit_before_select` | unsynchronised async I/O | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R03** | `taskgroup_teardown` | task lifecycle race | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R04** | `fixture_dirty_read` | shared mutable fixture | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R05** | `event_set_after_wait` | barrier / event ordering | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R06** | `queue_consumer_early` | barrier / event ordering | FIXED | `INJECT_ASYNC_EVENT` | — | ✅ |
| **R08** | `gather_order_assumption` | over-constrained assertion | NEEDS_INVESTIGATION | `RELAX_ASSERTION` | — | ❌ no recorded evidence |
| **R12** | `depth2_two_constraints` | depth-2 race | NEEDS_INVESTIGATION | — | `DEPTH_GE_2_UNRESOLVED` | ❌ no recorded evidence |
| **R13** | `production_scope_race` | production-scope race | ABSTAINED | — | `PRODUCTION_SCOPE_RACE` | ❌ no recorded evidence |
| **R14** | `batch_completion_lifecycle` | **task lifecycle race — the different shape** | FIXED | **`AWAIT_UNFINISHED_TASK`** (`scope_target: "handle"`) | — | ✅ |
| **N01** | `random_seed_flake` | unseeded random | ABSTAINED | — | `NOT_A_RACE` | ✅ control |
| **N02** | `network_timeout` | external service instability | ABSTAINED | — | `NOT_A_RACE` | ✅ control |
| **N03** | `dict_iteration_order` | unordered collection | ABSTAINED | — | `NO_TRACE_PAIR` | ✅ control |
| **N06** | `wrong_assertion` | incorrect test (fails 100%) | ABSTAINED | — | `NO_TRACE_PAIR` | ✅ control |
| **N07** | `threading_race` | genuine data race, **out of scope** | ABSTAINED | — | `NON_ASYNCIO_PARADIGM` | ✅ control |

**Corpus arithmetic (memorise these; they are frequently misquoted):**
- **15 cases exist** in `benchmark/cases/`: 10 races + 5 negative controls.
- **12 cases are in the three-arm corpus**: **7 repairable races** (R01–R06, R14) + **5 controls**.
- R08, R12, R13 are excluded from the replayed three-arm comparison because they
  have no recorded evidence. R12's depth-2 finding comes from a separate
  `chronotrace eval` run.
- `eval-results/` (the dashboard's data) has **15 incidents**, Arm C only, Bedrock.

### 12.2 Why negative controls matter
Five of twelve cases have nothing wrong. **If your agent patches those, it is
pattern-matching, not diagnosing.** ADR-0004 states it directly: the benchmark
cannot be accused of being designed around the algorithm when half of it is cases
the system must refuse. `band_aid_would_pass: true` is recorded per case — R01–R06,
R08, R12, R13, R14 and N07 would all go green under a band-aid.

### 12.3 R01 — the canonical case (source, abbreviated)
```python
STORE: dict[str, str] = {}

@operation("commit_value", resource="store.value", access="write")
async def commit_value(value: str) -> None:
    STORE["value"] = value

@operation("read_value", resource="store.value", access="read")
async def read_value() -> str | None:
    return STORE.get("value")

async def writer_task() -> None:
    await io_latency()
    await commit_value("ready")

@pytest.mark.asyncio
async def test_reader_sees_committed_value() -> None:
    STORE.clear()
    task = asyncio.create_task(writer_task())
    await io_latency()
    observed = await read_value()
    with assertion("store.value"):
        assert observed == "ready"
    await task
```
Ground truth: `INJECT_ASYNC_EVENT`, signal `commit_value#0`, wait `read_value#0`.

### 12.4 R14 — the case that catches everyone, including ChronoTrace
```python
BATCH: list[str] = []
EXPECTED = ["alpha", "beta", "gamma"]

@operation("record_item", resource="batch.items", access="write")
async def record_item(item: str) -> None:
    BATCH.append(item)

async def batch_worker() -> None:
    for item in EXPECTED:
        await io_latency(0.9)
        await record_item(item)          # <- three separate writes

@pytest.mark.asyncio
async def test_batch_is_complete() -> None:
    BATCH.clear()
    handle = asyncio.create_task(batch_worker())
    await io_latency(2.2)
    observed = await read_batch()
    with assertion("batch.items"):
        assert observed == EXPECTED       # <- depends on ALL THREE
    await handle
```
**Why `INJECT_ASYNC_EVENT` is checkably wrong here:** an event signalled by
`record_item` wakes the reader after the **first** item, and the assertion still
fails. The correct repair is `AWAIT_UNFINISHED_TASK` — await the `handle` the test
already holds, *before* the assertion rather than after it.

**Why R14 exists:** *"Included to test whether the repair pattern is chosen from
the evidence or from the shape of the rest of the corpus."* It is the deliberately
planted falsification test, and the system failed it — which is the most valuable
result in the project.

---

## SECTION 13 — EVALUATION METHODOLOGY

### 13.1 The three arms (`chronotrace/eval/arms.py`)

| Arm | What the model receives | Gate? |
|---|---|---|
| **A** | The test file and the failure. Nothing else. **This is what a general coding assistant does** | No |
| **B** | The same, **plus** the trace diff and ranked candidate inversions | No |
| **C** | Full ChronoTrace: typed intent, deterministic LibCST patching, 15-rule policy gate, tiered verification | Yes |

**Arm B is the one people forget and the most informative:** it isolates how much
of the result comes from *the traces* versus from *the gate*. Either answer is
publishable; not knowing is the weak position.

### 13.2 Experimental controls (what makes this a controlled comparison)
- **All three arms use the same model, temperature (0.0), seed (1729), token cap,
  attempt budget (`max_attempts=3`) and per-run timeout.** A run that cannot honour
  that is **refused** rather than reported with a caveat.
- **Capture and diagnosis run ONCE per case and are shared by all three arms.** They
  are deterministic and involve no model call, so no arm is compared against a
  luckier set of runs.
- **The two model runs (Nova Pro / qwen2.5-coder) share the same recorded traces and
  diagnoses**, replayed rather than re-run. **Only the model differs**, which is what
  makes the columns comparable case by case.
- **Verification is the same ladder with the same forced ordering for every arm.**
- **Every provider call records its (request, response) pair** (78 fixture files), so
  a published result is replayable byte-for-byte and offline
  (`chronotrace replay-check`).
- Every number is produced by `uv run chronotrace three-arm`. **None is hand-entered.**

### 13.3 Metrics defined (`chronotrace/eval/score.py`)

| Metric | Definition |
|---|---|
| `repair_rate` | Fraction of supported races repaired **and verified** |
| `false_repair_rate` | Fraction of negative controls that received a patch. **Target zero** |
| `abstention_accuracy` | Fraction of cases that should abstain where the **right refusal reason** was given |
| `causal_precision` | Fraction of forced candidates that **reproduced** the failure |
| `band_aid_rate` | Fraction of produced patches containing a timing band-aid (detected by re-running the governor's negative rules over the diff's added lines) |
| `tokens_per_repair` | Total tokens ÷ successful repairs, or `None` when unmeasured |
| `median_overhead_ms` | Median measured post-patch overhead. **Never reported as zero by default** |

**On overhead:** ChronoTrace never claims zero added cost — a synchronization
primitive changes scheduling even when it adds no fixed delay. The claim is
*"no fixed sleep-based delay introduced"*, plus the measured number. Median measured
overhead has come out at **0.18–0.19 ms** and can be negative; read it as "too small
to separate from noise at this sample size".

### 13.4 The reference policy is a TEST DOUBLE — never a model result
`chronotrace/providers/reference_policy.py` is a **hand-written decision procedure,
not a language model.** It exists so the pipeline, the benchmark and the eval harness
run with no credentials and no GPU.

**Enforcement (not just documentation):**
- Anything it writes is stamped `provider: "reference-policy"`.
- Selecting it logs a warning.
- `chronotrace repair --demo` **refuses to run on it** and prints the Bedrock/Ollama
  commands instead.
- It reports **no token counts** — a token count it invented would be a fabricated
  metric; the results table prints `n/a` and says why.
- Comparative arms A and B are **refused** on it rather than run and caveated. A
  baseline drawn from this repository's own hand-written policy would describe this
  repository, not a model.

**This is enforced because the project got it wrong once.** An earlier version was
named `LocalModelProvider` and wrote fixtures stamped `provider: "local"`, and the
project's working demo turned out to be **replaying one of those fixtures** — a
hand-written policy making the right choice, while the actual models under test were
choosing a non-repairing transformation on every case. That is recorded in the source
as a scar, verbatim.

> ⚠️ **`docs/results/` contains reference-policy output with a 100% repair rate.
> That number must NEVER be quoted as a repair rate.** It is a hand-written policy
> scoring against the corpus it was written alongside. It is kept only as evidence
> that the deterministic layers work end to end without a model.

### 13.5 Where each results directory comes from (disambiguation table)

| Directory | Provider | What it is | Quotable? |
|---|---|---|---|
| `eval/results/bedrock/` | `amazon.nova-pro-v1:0` | **Canonical hosted-model three-arm run** | ✅ Yes |
| `eval/results/three_arm_final_*` + `FINDINGS.md` | `qwen2.5-coder:14b` | **Canonical local-model three-arm run** | ✅ Yes, labelled by model |
| `eval/results/arm_c_*` | qwen3:8b / qwen2.5-coder:14b | Ablations: model comparison, prompt v1 vs v2, retry, required sites | ✅ As ablations |
| `eval-results/` | `bedrock` | Last `chronotrace eval` working output; **the dashboard reads this** | ⚠️ Arm C only, 15 cases, not a comparison |
| `docs/results/` | reference policy | Deterministic layers only, **no model** | ❌ **Never as a model result** |

---

## SECTION 14 — ALL RESULTS (complete, with provenance)

> **RULE OBSERVED THROUGHOUT: the two models are reported separately and NEVER
> pooled.** `amazon.nova-pro-v1:0` on Amazon Bedrock, and `qwen2.5-coder:14b`
> (14.8B, Q4_K_M) via Ollama. Temperature 0.0, seed 1729, same token cap, attempt
> budget and timeout for both.

> **RULE OBSERVED THROUGHOUT: R01–R06 and R14 are NEVER averaged together.**
> R01–R06 share one race shape; R14 is a different shape. Combining them would hide
> the finding.

### 14.1 HEADLINE — R01–R06 (read-after-write on a shared resource)

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Repaired, verified — **Nova Pro** | 1 / 6 | 3 / 6 | **6 / 6** |
| Repaired, verified — qwen2.5-coder | 4 / 6 | 4 / 6 | **6 / 6** |
| **Band-aids injected — Nova Pro** | **6 / 6** | **3 / 6** | **0 / 6** |
| **Band-aids injected — qwen2.5-coder** | **3 / 6** | **3 / 6** | **0 / 6** |

**THE SINGLE MOST QUOTABLE FINDING:** *Nova Pro reached for `asyncio.sleep` on all
six.* Given the test and the failure and nothing else, **the larger frontier model
band-aided MORE often than the small local one, not less** — and on R01 it added
both a sleep and a retry loop. The trace diff alone (Arm B) halved that without
being told to; the gate removed it entirely.

### 14.2 Negative controls (5 cases)

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| **False repairs — Nova Pro** | **5 / 5** | **5 / 5** | **0 / 5** |
| **False repairs — qwen2.5-coder** | **4 / 5** | **4 / 5** | **0 / 5** |
| Abstention accuracy | — | — | **5 / 5, correct reason (both models)** |

### 14.3 R14 — the one case of a different shape

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Repaired, verified | **yes** | **yes** | **no** |
| Verification tier | `FORCED_UNREACHABLE` | `FORCED_UNREACHABLE` | **`FAILED`** |
| Band-aid | none | none | none |

**Identical on both models.** Both unconstrained baselines repaired R14 and
ChronoTrace did not. They each wrote `await handle`, with a comment: *"Ensure the
batch worker completes before the assertion."* Arm C chose `INJECT_ASYNC_EVENT`,
and **forced replay rejected it.**

**That a frontier hosted model and a 14B local one fail this case the same way, and
get caught the same way, is the strongest evidence in the project that the
verification tier is doing the work rather than the model.**

**Necessary framing:** those same two baselines injected band-aids on most of the
other cases and falsely repaired 5/5 (Nova Pro) and 4/5 (qwen) negative controls.
**They are not safer; they are unconstrained, and on this one case that happened to
help.**

**Why Arm C's choice was wrong, quoted from the model's own rationale:**
> "The operations involve a read-after-write inversion over the same resource
> 'batch.items', with one operation writing and the other reading. The reader
> observed state the writer had not yet published…"

That describes R14 accurately at the surface. It is still the wrong repair, because
the assertion depends on the task **completing**, not on one write landing. **The
model matched the shape rather than reasoning about what the assertion depends on.**

**The intent retry loop did not help:** across three attempts it re-chose
`INJECT_ASYNC_EVENT` every time. **Retries correct an under-specified intent; they
do not correct a misjudged one.**

### 14.4 THE COMPARISON THAT MATTERS (the R14 rerun-gate argument)

On one measured run of R14, the patch ChronoTrace proposed **and then rejected**
took the flake rate from **80% → 45%** (16/20 failing before, 9/20 after). On the
run recorded for the demo video the same patch measured **75% → 70%** (15/20 vs
14/20).

**A rerun-based verification gate would have ACCEPTED that patch.** The test used to
fail most of the time and now fails less than half; every rerun-based signal points
at "improved". Datadog's attempt-to-fix flow retries 20 times and BuildPulse
confirms through PR checks — **neither can separate "fixed the race" from "made it
rarer", because both look identical in a pass count.**

**It is worse than that for the rerun approach.** The residual is noisy: across runs
the same wrong patch has measured anywhere from **45% to 75%** against a pre-patch
rate of **70–80%**. Sometimes it looks like a fix and sometimes it looks like a
regression. **Forced replay returns the same verdict every time, because it is an
experiment with a control rather than a sample.**

> **DISCLOSURE THAT MUST TRAVEL WITH THESE NUMBERS:** the 80%→45% and 75%→70%
> figures are two samples of the same distribution, not a contradiction, and the
> project documents both. Do not quote one as *the* number.

### 14.5 R12 — a perfect suspiciousness score, correctly refused

R12 brings up two replicas concurrently and asserts `primary or secondary`.
- Top candidate scored **Ochiai 1.00** — present in every failing run and no passing
  run, **statistically indistinguishable from R01**.
- Forcing it failed **60%** of the time, not 100% → necessary but not sufficient.
- The second candidate forced at **40%**.
- ChronoTrace reported **`DEPTH_GE_2_UNRESOLVED`** and generated **no patch**.

**Why this matters:** patching on the suspiciousness score would have synchronised
one replica, left the bug live, and roughly **halved** the failure rate — **which
every rerun-based metric reads as success.** Forcing is what separates the two.

### 14.6 Full per-case results — Amazon Nova Pro (Bedrock)

Source: `eval/results/bedrock/three_arm_bedrock_amazon_nova_pro_v1_0.json`.
Run wall clock **997.9 s (~17 min)**, 36 rows (12 cases × 3 arms),
`intent_parse_failures: 0`.

| Case | Arm | Verified | Tier reached | Band-aid | UI state | Tokens in/out | Wall s |
|---|---|---|---|---|---|---|---|
| R01 | A | ✅ | `FORCED_HARMLESS` | ⚠️ yes | FIXED | 533/338 | 43.9 |
| R01 | B | ✅ | `FORCED_UNREACHABLE` | no | FIXED | 720/312 | 45.6 |
| R01 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2619/296 | 44.7 |
| R02 | A | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 547/338 | 53.1 |
| R02 | B | ✅ | `FORCED_UNREACHABLE` | no | FIXED | 722/323 | 44.7 |
| R02 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2633/300 | 44.8 |
| R03 | A | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 479/278 | 43.1 |
| R03 | B | ✅ | `FORCED_UNREACHABLE` | no | FIXED | 666/262 | 44.2 |
| R03 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2567/270 | 44.5 |
| R04 | A | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 616/370 | 53.4 |
| R04 | B | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 791/370 | 43.6 |
| R04 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2685/300 | 45.4 |
| R05 | A | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 510/294 | 44.7 |
| R05 | B | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 689/304 | 53.4 |
| R05 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2591/304 | 45.4 |
| R06 | A | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 534/299 | 43.3 |
| R06 | B | ❌ | `FAILED` | ⚠️ yes | NEEDS_INV | 712/299 | 43.1 |
| R06 | **C** | ✅ | `FORCED_HARMLESS` | no | FIXED | 2596/300 | 44.4 |
| R14 | A | ✅ | `FORCED_UNREACHABLE` | no | FIXED | 683/406 | 45.7 |
| R14 | B | ✅ | `FORCED_UNREACHABLE` | no | FIXED | 933/427 | 46.5 |
| R14 | **C** | ❌ | **`FAILED`** | no | NEEDS_INV | 3386/300 | 57.8 |

**Arm totals (Nova Pro, all 12 cases):**

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Races verified (of 7) | 2 | 4 | **6** |
| Band-aids (of 7) | **6** | 3 | **0** |
| False repairs on controls | **5/5** | **5/5** | **0/5** |
| Model calls | 12 | 12 | **7** |
| Tokens in | 6,526 | 8,286 | 19,077 |
| Tokens out | 3,729 | 3,674 | 2,070 |
| Wall clock | 339 s | 332 s | 327 s |

**Published summary table (`eval/results/bedrock/three_arm_table.md`):**

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Races repaired (verified) | 2 / 7 | 4 / 7 | **6 / 7** |
| **Band-aids injected** | **6 / 7** | **3 / 7** | **0 / 7** |
| CI seconds added per run | 0.01 s | 0 s | **0 s** |
| Projected annual CI cost (50 runs/day) | 0.1 h | 0 h | **0 h** |
| False repairs on 5 controls | 5 / 5 | 5 / 5 | **0 / 5** |
| Tokens per successful repair | 5,128 | 2,990 | 3,524 |
| Causality proven | no | no | **yes — 6/7 at forced tier** |

**Nova Pro band-aid patterns, per case (Arm A):** R01 `N1 sleep + N5 retry loop`;
R02–R06 all `N1: patch adds 1 sleep call (asyncio.sleep)`. **Arm B:** R04, R05, R06
still `N1 sleep`; R01, R02, R03 clean.

**Nova Pro natural flake rates in that run:** R01 0.5, R02 0.8, R03 0.5, R04 0.8,
R05 0.3, R06 0.6, R14 0.917, N01 0.3, N02 0.5, N03 0.0, N06 1.0, N07 1.0.

### 14.7 Full per-case results — qwen2.5-coder:14b (Ollama)

Source: `eval/results/three_arm_final_qwen2.5-coder-14b.json`. Wall clock
**2,074.9 s (~35 min)**, `intent_parse_failures: 0`.

| Case | Arm | Verified | Tier | Band-aid | Tokens in/out |
|---|---|---|---|---|---|
| R01 | A / B / **C** | ✅/✅/✅ | `FORCED_HARMLESS` / `FORCED_UNREACHABLE` / `FORCED_HARMLESS` | ⚠️/no/no | 473/305 · 653/274 · 1577/262 |
| R02 | A / B / **C** | ❌/❌/✅ | — / `STATISTICAL` / `FORCED_HARMLESS` | no/⚠️/no | 475/275 · 655/293 · 1572/269 |
| R03 | A / B / **C** | ✅/✅/✅ | `FORCED_UNREACHABLE` ×2 / `FORCED_HARMLESS` | no/no/no | 426/233 · 594/229 · 1529/267 |
| R04 | A / B / **C** | ❌/❌/✅ | `FAILED` / `STATISTICAL` / `FORCED_HARMLESS` | ⚠️/⚠️/no | 539/335 · 719/330 · 1617/264 |
| R05 | A / B / **C** | ✅/✅/✅ | `FORCED_HARMLESS` ×3 | ⚠️/⚠️/no | 447/262 · 623/262 · 1541/245 |
| R06 | A / B / **C** | ✅/✅/✅ | `FORCED_UNREACHABLE` ×2 / `FORCED_HARMLESS` | no/no/no | 473/248 · 653/246 · 1554/254 |
| R14 | A / B / **C** | ✅/✅/**❌** | `FORCED_UNREACHABLE` ×2 / **`FAILED`** | no/no/no | 615/377 · 853/378 · **6974/439** |

**Arm totals (qwen2.5-coder:14b):**

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Races verified (of 7) | 5 | 5 | **6** |
| Band-aids (of 7) | 3 | 3 | **0** |
| False repairs on controls | 4/5 | 4/5 | **0/5** |
| Model calls | 12 | 12 | 9 |
| Tokens in / out | 5,800 / 3,275 | 7,519 / 3,269 | 16,364 / 2,000 |
| Wall clock | 652.8 s | 673.5 s | 578.2 s |

**Published summary table (`eval/results/three_arm_final_table.md`):**

| Metric | Arm A | Arm B | Arm C |
|---|---|---|---|
| Races repaired (verified) | 5 / 7 | 5 / 7 | **6 / 7** |
| **Band-aids injected** | **3 / 7** | **3 / 7** | **0 / 7** |
| CI seconds added per run | 0.02 s | 0.12 s | **0 s** |
| Projected annual CI cost (50 runs/day) | 0.1 h | 0.6 h | **0 h** |
| False repairs on 5 controls | 4 / 5 | 4 / 5 | **0 / 5** |
| Tokens per successful repair | 1,815 | 2,158 | 3,061 |
| Causality proven | no | no | **yes — 6/7 at forced tier** |

**Cost comparison (qwen, from FINDINGS.md):** Arm A 12 calls / 9,075 tokens; Arm B
12 / 10,788; Arm C 9 / 18,364. **Arm C costs roughly twice the tokens of a
baseline** — it sends the full diagnosis as evidence and retries on an invalid
intent. Say this plainly; it is a real trade.

### 14.8 Arm C abstention on the negative controls (both models, every run)

| Case | State | Reason |
|---|---|---|
| N01 `random_seed_flake` | ABSTAINED | `NOT_A_RACE` |
| N02 `network_timeout` | ABSTAINED | `NOT_A_RACE` |
| N03 `dict_iteration_order` | ABSTAINED | `NO_TRACE_PAIR` |
| N06 `wrong_assertion` | ABSTAINED | `NO_TRACE_PAIR` |
| N07 `threading_race` | ABSTAINED | `NON_ASYNCIO_PARADIGM` |

> ⚠️ **THE ABSTENTION CAVEAT — NEVER QUOTE 5/5 WITHOUT IT.**
> **Four of the five controls are refused during *diagnosis*, before the model is
> consulted at all.** `NOT_A_RACE` (N01, N02) and `NO_TRACE_PAIR` (N03, N06) are
> reached by deterministic code; N07 by paradigm detection. So **5/5 demonstrates
> that the deterministic refusal paths work. It demonstrates nothing about whether
> a model would decline when asked, because no control in the corpus reaches the
> model.** The corpus cannot answer that question.

### 14.9 Ablation 1 — Arm C across two local models (model is the only variable)

**Hypothesis tested:** `RELAX_ASSERTION` on all six races was an 8B pattern-selection
limit rather than a system failure. **Result: NOT SUPPORTED.**

| Case | qwen3:8b | qwen2.5-coder:14b |
|---|---|---|
| R01–R06 (all six) | `RELAX_ASSERTION` | `NO_REPAIR` |

| | qwen3:8b | qwen2.5-coder:14b |
|---|---|---|
| Parameters / quantisation | 8.2B, Q4_K_M | 14.8B, Q4_K_M |
| Context | 40,960 | 32,768 |
| Valid `RepairIntent` JSON | 6/6 | 6/6 |
| **Correct transformation** | **0/6** | **0/6** |
| Verified repairs | 0/6 | 0/6 |
| Band-aids | 0/6 | 0/6 |
| False repairs on controls | 0/5 | 0/5 |
| Abstention accuracy | 5/5 correct reason | 5/5 correct reason |

The 14B model's R01 rationale, verbatim, **alongside a `NO_REPAIR` transformation**:
> "The assertion over-constrains legitimate concurrency. The test should be relaxed
> to allow for the possibility that the read operation may occur before the write
> operation completes."

**The rationale argues for relaxing the assertion; the transformation field says no
repair. The two disagree, and the language tracks the closing paragraph of the
system prompt almost word for word.** Both models converged on the two
transformations that mean *do not patch*, from opposite directions.

### 14.10 Ablation 2 — intent prompt v1 vs v2 (THE decisive fix)

**One change:** the intent system prompt was rewritten from
descriptions-plus-caution into an **explicit ordered decision procedure**, with the
condition that selects each transformation stated in the fields the model actually
receives, and abstention moved out of the closing position. No benchmark case
appears in it. Everything else held constant via `--reuse-evidence`.

| Case | qwen3:8b before → after | qwen2.5-coder:14b before → after |
|---|---|---|
| R01–R06 (all six) | `RELAX_ASSERTION` → **`INJECT_ASYNC_EVENT`** | `NO_REPAIR` → **`INJECT_ASYNC_EVENT`** |

| | 8b before | 8b after | 14b before | 14b after |
|---|---|---|---|---|
| Correct transformation | 0/6 | **6/6** | 0/6 | **6/6** |
| Intents carrying both sites | — | 0/6 | 6/6 | 6/6 |
| Patch applied | 0/6 | 0/6 | 0/6 | **6/6** |
| Governor approved | 0/6 | 0/6 | 0/6 | **6/6** |
| **Verified repairs** | 0/6 | 0/6 | 0/6 | **6/6** |
| Band-aids | 0/6 | 0/6 | 0/6 | 0/6 |
| False repairs on controls | 0/5 | 0/5 | 0/5 | 0/5 |
| Abstention accuracy | 5/5 | **5/5** | 5/5 | **5/5** |
| Invalid `RepairIntent` JSON | 0 | 0 | 0 | 0 |

**Correct transformation: 0/6 → 6/6 on both models.**

**The falsification test, set in advance and held:** abstention on the five
controls had to remain 5/5 with the correct reason. If repairs rose while
abstention degraded, the prompt bias had been *moved* rather than fixed. It held at
5/5 on both models, false repairs stayed 0/5, band-aids stayed 0/6. *(Weakened by
the same caveat: no control reaches the model.)*

**The 8B model: right decision, unusable payload.** qwen3:8b picks the correct
transformation on all six and still produces no repair — it emits only
`transformation`, `primitive`, `shared_scope` and `rationale`, leaving
`signal_site`/`wait_site` null, and the patcher refuses. **The prompt fix moved the
8B failure one layer down rather than resolving it:** from choosing the wrong
pattern to specifying the right one incompletely. Making the site fields
conditionally required would likely fix it — a **schema** change, not a prompt
change. It was not made in that experiment: *one change at a time.* (It was later
added as the `RepairIntent` model validator.)

**What the ablation established / did not establish, stated by the project:**
- ✅ ChronoTrace has been driven end to end by a real language model: 6/6 diagnosed,
  patched, gated and verified at the forced tier, 0 band-aids, 0 false repairs.
- ✅ The earlier 0/6 was a **prompt defect**, not a system failure and not an
  inherent limit of small models.
- ⚠️ **"A prompt that states the rule for the shape that makes up the whole positive
  test set is a fair description of the domain, and it is also close to teaching the
  test."** Cases of a different shape are needed before 6/6 means what it appears to
  mean. *(R14 was then added and the model got it wrong.)*

### 14.11 Dashboard dataset (`eval-results/`, Arm C, Bedrock, 15 incidents)

| Metric | Arm C |
|---|---|
| Cases run | 15 |
| Repair rate on supported races | 86% (6/7) |
| **False-repair rate on controls** | **0% (0/5)** |
| Abstention accuracy | 100% (8/8) |
| Causal precision | 82% (9/11) |
| **Band-aid injection rate** | **0% (0/6)** |
| Ground-truth transformation match | 7/8 |
| Median measured overhead | 0.1815 ms |
| Model calls | 8 |
| Tokens per successful repair | 4,943.67 |
| Wall clock | 668 s |
| Verification tiers reached | `FAILED` ×1, `FORCED_HARMLESS` ×6, `NOT_REACHED` ×8 |

**Per-incident dashboard rows** (id · case · state · tier · flake rate):
`f8947f30` R01 FIXED `FORCED_HARMLESS` 0.4 · `c355d54b` R02 FIXED `FORCED_HARMLESS` 0.4 ·
`9caf24e0` R03 FIXED `FORCED_HARMLESS` 0.6 · `ef5d95de` R04 FIXED `FORCED_HARMLESS` 0.1 ·
`ef292eae` R05 FIXED `FORCED_HARMLESS` 0.7 · `dbe0093b` R06 FIXED `FORCED_HARMLESS` 0.6 ·
`e0d54ea0` R08 NEEDS_INVESTIGATION — 0.1 · `daeae925` R12 NEEDS_INVESTIGATION — 0.2 ·
`5edddd00` R13 ABSTAINED — 0.5 · `782a134d` R14 NEEDS_INVESTIGATION `FAILED` 0.9 ·
`1c349bf0` N01 ABSTAINED — 0.2 · `4d1ad174` N02 ABSTAINED — 0.05 ·
`10168091` N03 ABSTAINED — 0.0 · `30f8ab29` N06 ABSTAINED — 1.0 ·
`69aa7036` N07 ABSTAINED — 1.0

### 14.12 WHAT THE EVIDENCE ACTUALLY SUPPORTS (the honest scope)

> **NO REPAIR RATE IS QUOTED AS A HEADLINE, DELIBERATELY.** With one race shape
> dominating the corpus it would not mean what it appears to mean.

Three claims, and only these three, hold across **every run and both models tested**:

1. **CONSTRAINT PREVENTS HARM.** 0 band-aids against 6/6 (Nova Pro) and 3/6 (qwen);
   0/5 false repairs against 5/5 and 4/5. **The most reproducible result in the
   project — and the gap is *wider* on the larger model.**
2. **VERIFICATION CATCHES WRONG REPAIRS, INCLUDING OUR OWN.** R12 and R14.
3. **CONSTRAINT DOES NOT CONFER JUDGEMENT.** The model still has to choose the right
   pattern, and on a shape the prompt does not name, it did not.

### 14.13 THE GENERALIZATION LIMIT — stated so it survives hostile questioning

> Six of our seven repairable cases are read-after-write races on a shared
> resource. **The intent prompt names that condition explicitly.** On those six,
> both models choose correctly six times out of six. On the one case we added of a
> different shape, both chose wrong — and the unconstrained baselines, which were
> given no rule to follow, chose right, on both models. **We have evidence that the
> system works on the shape it was told about. We do not have evidence that it
> generalizes, and the one experiment we ran on that question came back negative
> twice.**

---

## SECTION 15 — ARCHITECTURE DECISION RECORDS (all 6, condensed)

### ADR 0001 — Scope: Python asyncio only
**Context.** Forced-interleaving replay is the load-bearing claim. In CPython, OS
threads cannot be arbitrarily scheduled from user space without intercepting
synchronization primitives or manipulating `sys.setswitchinterval`, neither giving
deterministic control. Multiprocessing is worse. asyncio is different **in kind**:
cooperative, single-threaded, yields only at `await`.
**Decision.** asyncio only. Threading and multiprocessing are detected in order to
**abstain**, never to repair.
**Consequences.** The forced scheduler is genuinely real rather than partly
theatrical (`tests/test_harness.py` reproduces both orderings on demand). The
wrong-primitive failure mode largely dissolves: one paradigm means one primitive
family. Coverage is narrower than "flaky test repair" in general. *"Eight excellent
asyncio races with a real deterministic scheduler are worth more than fifteen
shallow ones across three paradigms."*
**Rejected.** All three paradigms (the central claim would be false for most of the
surface). Threading via `sys.settrace` (probe effect larger than the timing
differences being measured).

### ADR 0002 — The model emits typed intents, never source code
**Context.** An agent that writes code to fix a flaky test **can write
`time.sleep(2)`** — not hypothetical, it is the default behaviour of general coding
assistants on this task, because a sleep makes the test green and greenness is the
visible signal. Anything the model emits has to be *checkable*; source code is
checkable only by reading it, which is exactly the reviewer effort the tool exists
to save.
**Decision.** The model does exactly one thing: choose a repair pattern from a fixed
set and return a schema-validated `RepairIntent`.
**Consequences.** The space of possible patches is **enumerable**, so the policy gate
can be **complete** rather than best-effort. **The thing that decides is not the
thing that verifies.** Novel repairs outside the fixed set are impossible — the
system abstains instead, which is the intended trade. A malformed or hallucinated
intent fails schema validation before touching a file.
**Rejected.** Model writes a diff + governor reviews it ("did this patch weaken the
assertion" becomes an open-ended program-analysis problem instead of a closed one).
Model proposes + second model critiques (the critic's duties are all deterministic
checks; an LLM performing them is a deterministic check with added variance).

### ADR 0003 — Forced replay instead of rerun-based verification
**Context.** "We ran it 20 times and it passed" does not survive scrutiny. Gruber et
al.: **170 reruns** for 95% confidence. Alshammari et al.: projects where **10,000
reruns** still missed known flaky tests. The trace diff gives ChronoTrace the
identity of the specific pair whose order differs, which **converts verification
from sampling into an experiment.**
**Decision.** The tiered ladder, with the tier reached always reported.
**Consequences.** A repair claim is an experiment with a control. Tier 2/3 is never
described as proof. Forced runs sweep consecutive seeds so what is *not* forced
stays free. Tier 1 needs instrumented operations; uninstrumented code degrades to
Tier 3, reported as such.
**Rejected on strength, not correctness.** Reruns with a large N — what the shipping
products do. A rerun gate establishes the test stopped failing but cannot separate
"fixed the race" from "made it rarer".

### ADR 0004 — Abstention is a first-class outcome
**Context.** A trace diff over a concurrent program will **always** find *some*
inversion. A system built to always return an answer will confidently patch noise.
**For a tool that modifies code, a wrong patch is worse than no patch: it buries the
real cause under a green build, and the next person to look has less information
than the first.**
**Decision.** `Diagnosis.status` ∈ {`RACE_PROVEN`, `NEEDS_INVESTIGATION`,
`ABSTAINED`}, with 8 machine-readable abstention reasons. **The false-repair rate on
negative controls is a headline metric, reported alongside the repair rate rather
than beneath it.**
**Consequences.** The repair rate is lower than it could be, deliberately. Abstention
reasons surface in plain language in the UI, so a refusal is actionable rather than
a shrug.
**Rejected.** A confidence score on every diagnosis — *"the draft specification
contained a hardcoded `confidence_score=0.98`, which is exactly what a fabricated
number looks like."* Causal precision is measured instead.

### ADR 0005 — No vector store, no second agent
**Context.** An early architecture included a vector store of past repairs with a
small model as a "memory matcher", and a node labelled a multi-agent swarm that in
fact contained a single agent.
**Decision.** Neither ships. **Agentic depth comes from multi-step tool use inside
one agent loop**, not from a second model.
**Consequences.** No retrieval infrastructure to run, seed or explain. The remaining
loop is genuinely agentic: it takes actions, observes results, decides what to do
next, including deciding to abstain. Authority stays deterministic.
**Rejected.** A critic agent — every proposed duty (primitive/paradigm matching,
scope checking, deadlock detection) is a deterministic check that belongs in the
governor. *"Moving them into a model would trade a decidable check for a
probabilistic one and call it sophistication."*

### ADR 0006 — Provider abstraction, local by default
**Context.** The evaluation harness must not require a network. A reader who wants
to check a published number should be able to run one command and get it, and a
demo that depends on a live model call is a demo that can fail in front of an
audience.
**Decision.** Two protocols — `ModelProvider` and `TelemetrySink` — with local
implementations as the default and cloud selected by a single environment variable.
**Consequences.** The benchmark and eval harness run with no credentials.
`repair --demo` deliberately does **not** — it refuses on the reference policy.
Every provider call records its (request, response) pair, so a published result is
replayable byte-for-byte and offline. Bedrock model ids are configuration with **no
default** — ids change between regions and releases.
**Rejected.** Bedrock only (no offline evaluation, no reproducible demo, every CI
test would need credentials).

---

## SECTION 16 — LIMITATIONS (all 11, verbatim in substance)

> These are **load-bearing**. Removing them to make the project look stronger would
> make it weaker. Reproduce them when asked about weaknesses.

1. **The benchmark is seeded, not mined from the wild.** Fifteen cases written for
   this project, with recorded ground truth. It shows a directional effect, not a
   population estimate. N is small and the project does not claim otherwise.
2. **One race shape dominates it.** Six of seven repairable cases are read-after-write
   on a shared resource — the condition the intent prompt names. R14 is a single
   counter-example of a different shape, and the model got it wrong. **Nothing here
   supports a generalization claim.**
3. **asyncio only.** Threading and multiprocessing are detected in order to abstain.
   In CPython, OS threads cannot be scheduled deterministically from user space, so a
   "forced ordering" there would be **theatre**. (ADR 0001.)
4. **It is observed-order inversion, not happens-before.** The ordering is derived
   from observed start times plus structural edges, not from a partial order over
   synchronization events. **Claiming Lamport while shipping a timestamp sort would be
   a claim the implementation has not earned.**
5. **Tier 1 requires instrumented operations.** Races between operations that emit no
   spans degrade to Tier 3, reported as such. Span granularity too coarse to see the
   race is **detected and abstained on**, rather than localised to the wrong place.
6. **The probe effect is real.** Instrumentation changes timing. Capture measures the
   flake rate with and without instrumentation and reports the delta rather than
   hiding it.
7. **Depth ≥ 2 races are reported, not repaired.** When no single ordering is
   sufficient, ChronoTrace says so and stops.
8. **One transformation family is fully implemented.** `INJECT_ASYNC_EVENT` and
   `AWAIT_UNFINISHED_TASK`. `ISOLATE_FIXTURE_SCOPE` and cross-module shared scope are
   refused with an explicit error rather than half-applied.
9. **The corpus is twelve cases, not fifteen.** R08, R12 and R13 have no recorded
   evidence, so the replayed three-arm comparison excludes them. Every arm-versus-arm
   number is out of the twelve that ran.
10. **Docker isolation is implemented but unexercised** on the development machine.
    Process isolation — one process per run — is the default and is what the reported
    numbers used.
11. **The AWS surface is Bedrock and nothing else.** The Strands loop runs on Bedrock
    and the AgentCore entrypoint is deployed, but traces go to local JSONL rather than
    CloudWatch and incidents to local SQLite rather than DynamoDB.

**Additional documented caveats (equally load-bearing):**
12. **The 5/5 abstention number** measures deterministic refusal only — no control
    reaches the model (§14.8).
13. **Arm C costs roughly 2× the tokens** of an unconstrained baseline.
14. **Both local models tested are quantised** (Q4_K_M).
15. **`pipeline` mode inside AgentCore was never invoked** — untested, not known-broken.
16. **Applying a repair inside AgentCore fails** on a read-only bundle; the hosted
    runtime is an investigator, not a repairer.

---

## SECTION 17 — WHAT CHRONOTRACE IS BETTER AT (positioning claims, ranked by defensibility)

### Tier 1 — Fully evidenced, reproduce anywhere
1. **It cannot inject a band-aid.** 0/7 band-aids vs 6/7 (Nova Pro unconstrained) and
   3/7 (qwen unconstrained), reproducible across every run and both models. **The gap
   is wider on the larger model** — the frontier model band-aided *more*.
2. **It cannot falsely repair a non-race.** 0/5 false repairs vs 5/5 (Nova Pro) and
   4/5 (qwen). Every refusal carries a machine-readable reason.
3. **Its policy gate is adversarially tested and auditable.** 17 crafted attacks, 17
   rejections, each by the rule that targets it, with *every* rule reporting pass or
   fail. Runs offline, in CI, with no credentials and no model.
4. **It distinguishes "fixed the race" from "made it rarer".** R14 is the existence
   proof: a policy-clean patch that passes the gate 15/15 and fails forced replay,
   while a rerun-based gate reads it as a 75%→70% improvement and ships it.
5. **It refuses a perfect suspiciousness score when the score is not causal.** R12:
   Ochiai 1.00, forced at 60%, reported `DEPTH_GE_2_UNRESOLVED`, no patch generated.
6. **Its numbers are reproducible byte-for-byte offline.** 78 recorded (request,
   response) fixture pairs and `chronotrace replay-check`.

### Tier 2 — Architecturally distinct from the state of the art
7. **Input is execution traces, not test results.** For a concurrency bug the defect
   lives in the interleaving; a JUnit XML file does not contain one.
8. **Confirmation is a controlled experiment, not a sample.** The harness is identical
   pre- and post-patch, so the patch is the only variable.
9. **The model has no channel for source code.** Structured output through Bedrock's
   `converse` tool-use schema, validated by pydantic before anything touches a file.
10. **The shipped artifact is a deterministic reproducer**, not a diff. A race that
    appeared once in a few runs reproduces every run, in milliseconds.
11. **Abstention is designed in, with 8 typed reasons**, not bolted on as an error path.

### Tier 3 — Engineering-quality claims
12. **Deterministic layers require no credentials, no GPU, no network** — the gauntlet,
    the benchmark and the eval harness all run in a fresh checkout.
13. **Unimplemented backends raise instead of silently no-op'ing** — a config knob that
    quietly does nothing reads, in a review, as evidence that something is happening.
14. **The project documents its own failures as first-class results** — the zero-tools
    bug, the reference-policy demo scar, the unsourced statistic, the R14 failure.

### What ChronoTrace is explicitly NOT better at (say these too)
- **Coverage.** asyncio only, one race shape, one transformation family.
- **Repair rate.** No headline rate is quoted; FlakeSync's 83.75% is the serious
  number in the literature and is not comparable to anything here.
- **Generalization.** The one experiment on a new shape came back negative twice.
- **Token cost.** ~2× an unconstrained baseline.
- **Real-world corpus.** Seeded cases, not mined from the wild.

---

## SECTION 18 — COMPLETE CLI REFERENCE

```bash
chronotrace flake-check [test_id]            # measure flakiness across spaced runs
chronotrace capture <test_id> --runs 50      # gather pass/fail trace pairs
chronotrace diagnose <test_id>               # diagnosis only, no patch
chronotrace repair <test_id>                 # full pipeline; --apply to write
chronotrace repair --demo                    # a race repaired and verified
chronotrace repair --demo-r14                # a policy-clean patch that replay rejects
chronotrace agent <test_id>                  # the Strands agent loop on Bedrock
chronotrace agent --demo --dry-run           # its tool surface; no model contacted
chronotrace verify <incident_id>             # what verification established
chronotrace report <incident_id>             # the report as JSON
chronotrace gauntlet                         # adversarial governor demo (offline)
chronotrace eval --arm C --cases all         # produces the dashboard data
chronotrace three-arm                        # produces every three-arm number
chronotrace replay-check                     # confirm fixture replay reproduces numbers exactly
pytest --chronotrace                         # plugin-mode capture
```

**Global options:** `--allow-production-repair` (off by default), `--apply` (off by
default — **ChronoTrace proposes a diff, it does not write to your repository**),
`--json`, `--slow` (paces demo output for narration).

### 18.1 The three demo paths

**Option A — Adversarial Governor Gauntlet. Zero credentials, zero models.**
```bash
git clone https://github.com/Umang3172/chronotrace && cd chronotrace
uv sync
uv run chronotrace gauntlet
```

**Option B — Amazon Bedrock + Strands Agents (Nova Pro / Nova Lite).**
```bash
uv sync --extra bedrock
export CHRONOTRACE_PROVIDER="bedrock"        # settings read the CHRONOTRACE_ prefix;
export CHRONOTRACE_AWS_REGION="us-east-1"    # a bare AWS_REGION is NOT consulted
uv run chronotrace repair --demo             # one typed intent, then deterministic stages
uv run chronotrace agent --demo              # the Strands loop chooses its own steps
uv run chronotrace agent --demo --dry-run    # tool surface only, no AWS account needed
```

**Option C — Local model (Ollama). No AWS account, no credentials.**
```bash
ollama pull qwen2.5-coder:14b
uv run chronotrace repair --demo
```

**`--demo` behaviour:** discovers the active provider automatically, confirms which
model was selected, executes against a seeded flaky test in `benchmark/`, and prints
the diagnosis, the governor's 15/15 verdict, the verification tier reached, and the
proposed AST diff. **It will NOT fall back to running without a model** — a demo
driven by the hand-written reference policy would show this repository deciding for
itself rather than a model deciding, so it refuses and prints the commands above.

### 18.2 Installation
```bash
uv sync                 # runtime
uv sync --extra dev     # + ruff, mypy, hypothesis, coverage, playwright
uv sync --extra bedrock # + boto3 and the Strands SDK
```
Requires **Python 3.11+** and **uv**.

### 18.3 Running against your own tests
```python
from chronotrace.capture.instrument import assertion, operation

@operation("commit_value", resource="store.value", access="write")
async def commit_value(value: str) -> None:
    STORE["value"] = value

@operation("read_value", resource="store.value", access="read")
async def read_value() -> str | None:
    return STORE.get("value")

async def test_reader_sees_committed_value():
    ...
    with assertion("store.value"):
        assert observed == "ready"
```
Then `chronotrace repair 'path/to/test.py::test_name'`. **The instrumentation is
inert when ChronoTrace is not running** — which is exactly what makes the
probe-effect measurement possible.

### 18.4 Dashboard locally
```bash
uv run chronotrace eval --arm C --cases all
cd ui && npm install && npm run dev      # http://localhost:3939
cd ui && npm run build                   # -> ui/out (static export)
```
Three states, all visible: **Fixed**, **Needs investigation**, **Abstained**. Each
incident page shows: where the two runs diverge on a shared time axis, the evidence
and what forcing each ordering established, every policy rule with its verdict, the
verification tiers reached, and the proposed diff.

---

## SECTION 19 — THE DEMO VIDEO (4:47)

**URL:** `https://youtu.be/rkoeqMt3cDk` · 1080p · 30fps · 8,636 frames · 287.941 s ·
74.9 MB · h264/aac · uploaded 2026-09-10.

**Published title:** *"ChronoTrace — an AI agent that isn't allowed to cheat at
fixing flaky tests"*

**Chapter table (timestamps derived from `SCENES` in `timing.ts` at 30fps):**

| Time | Scene |
|---|---|
| **0:00** | A failing test, 20 runs — `chronotrace flake-check` on R01: 11 failures, 9 passes, 55% flake rate, same commit throughout |
| **0:18** | What a flaky test actually is — the race without jargon, plus Google's 84% |
| **0:58** | What everyone else does about it — quarantine (Trunk, Develocity, Datadog), repair agents (BuildPulse), research systems that read source instead of runs |
| **1:27** | How ChronoTrace works — the six stages, paired traces to forced replay |
| **2:06** | **Act I** — R01 repaired and proven. `amazon.nova-pro-v1:0` returns a typed `INJECT_ASYNC_EVENT` intent in **3.0 s (2,693 in / 296 out)**; governor **15/15**; tier `FORCED_HARMLESS`; regression guard left behind |
| **2:39** | The governor gauntlet — 17 adversarial patches, 17 rejections |
| **3:06** | **Act II** — a caught mistake. Our own agent's patch breaks no rule, passes 15/15, and forced replay fails it. Rerun gate saw 15/20 → 14/20 (**75% → 70%**) and would have shipped it |
| **4:09** | Results — the three-arm table (**qwen2.5-coder:14b run**, which is what the narration speaks) |
| **4:35** | What this is and isn't — the generalization limit, stated |

**Rule the video follows:** *every figure spoken is the figure printed by the command
on screen in that shot.* Where a number differs from the README tables, it is because
the video shows one recorded run and the tables aggregate the sweep.

**Video-specific facts an LLM should know:**
- The results scene shows the **qwen** run. The Bedrock/Nova Pro figures are
  *stronger* for Arm C's argument, not weaker (6/6 band-aids vs 3/6; 5/5 false
  repairs vs 4/5). **Neither run is pooled with the other anywhere.**
- Act I's model call is **Nova Pro at 3.0 s**. The **2.8 s Nova Lite** figure is real
  but comes from the **R14** run. Do not swap them.
- The video's R14 flake numbers are **75% → 70%**, not 80% → 45%. Both are real
  samples of the same noisy distribution.

**Verification tooling for the video:** `npm run verify` asserts every beat lands
inside its scene, that gauntlet row offsets still match the whisper transcript, and
that a named log line reaches the screen no later than the sentence about it. *A beat
that never fires renders as a still frame, not an error* — which is why three desync
bugs shipped before that check existed.

---

## SECTION 20 — BUILD TIMELINE AND CORRECTIONS LOG

### 20.1 Commit history (32 commits, 2026-09-07 → 2026-09-10)

| Date | Commit | Milestone |
|---|---|---|
| 09-07 | `5ceb084` | **Initial: ChronoTrace — trace-differential repair of flaky asyncio tests** |
| 09-07 | `9c973b2` | Commit the eval output the README quotes |
| 09-07 | `914a829` | Point badges at the real repo; test the CLI |
| 09-07 | `ee1c58d` | Correct the competitive landscape; explain causal precision |
| 09-07 | `170505a` | **Three-arm baseline against local qwen3:8b** |
| 09-07 | `91a2d8d` | Score a repair that eliminates the bad interleaving as a repair (`FORCED_UNREACHABLE`) |
| 09-07 | `0479bb6` | Arm C on a second, larger local model |
| 09-07 | `cd9ae41` | **State the intent selection rule; quarantine the reference policy** |
| 09-07 | `f4dd1d3` | Arm C before and after the prompt fix |
| 09-07 | `f117699` | Quickstart provider detection |
| 09-07 | `285d3ea` | **Working quickstart, a race of a different shape (R14), required intent sites** |
| 09-07 | `f27354d` | Show the model the validator's error and let it correct the intent |
| 09-07 | `853f30c` | **Final three-arm results with R14, and the findings write-up** |
| 09-07 | `16bfcf6` | Results section split by race shape; the R14 rejection demo |
| 09-07 | `148f7ee` | Filming checklist |
| 09-08/09 | `f934420` | **Integrate Amazon Nova, Strands agents, flake-check CLI, architecture assets** |
| 09-09 | `0b372a1` | YouTube + AWS Builder links |
| 09-09 | `13b6d2a` | LLM-dense handover document |
| 09-09 | **`9e717b6`** | **FIX: register the Strands tools, and run the loop from the CLI and AgentCore** |
| 09-09 | `1bc60d5` | Make the AWS claims match the code; label results by provider |
| 09-09 | `dd14da8` | Preflight a Bedrock run before spending an eval on it |
| 09-09 | `25e6f63` | The Bedrock model-access page is retired; stop pointing at it |
| 09-09 | `3e0cd63` | **Give the loop a way to act, and name the repairs it is allowed to make** |
| 09-09 | `eeacd0d` | Let the three-arm harness run against Bedrock |
| 09-09 | `65dc088` | One case without evidence should not discard the whole sweep |
| 09-09 | `963d541` | **Quote the Bedrock three-arm numbers, reported per model and never pooled** |
| 09-09 | `70a654d` | Static export, an Amplify build spec, two more build-journey posts |
| 09-09 | `b4e7270` | Correct the handover, which restated claims that were not true |
| 09-09 | `571a568` | Ship the dashboard on Bedrock incidents |
| 09-09 | **`7deff3f`** | **Ship the dashboard on Amplify and the agent on AgentCore** |
| 09-10 | `6141fb2` | Update YouTube link to the hackathon-compliant cut |
| 09-10 | `66e9f3b` | Save handover and deployment docs before mac migration |
| 09-10 | `fb077a4` | **Publish the corrected demo, illustrate the README, fill the Devpost draft** — adds the 5 README stills + thumbnail, `devpost-project-story.md`, `builder-center-update.md` |
| 09-10 | **`0df3b49`** | **State what AgentCore actually does in the hosted runtime** |
| 09-10 | **`5018b00`** | **The Builder Center post is corrected and live; Devpost is at 4/5** |
| 09-10 | **`a10b391`** | **`ruff format` on `verify_deploy.py`, which had CI red** (current HEAD) |

### 20.2 Corrections log — every claim that was stated before it was true

> **This log is itself a project asset.** It is the evidence that the project
> distrusts its own numbers, and it is quoted in the Devpost story: *"Three separate
> claims in this project were true-sounding and wrong until we checked them."*

**Code and system corrections (2026-09-09):**
1. **Strands registered ZERO tools.** Eight `AgentTools` methods were passed to
   `Agent(tools=[...])` **undecorated**. The SDK logs `unrecognized tool
   specification` per tool and *continues*, so the agent built cleanly, answered
   fluently, and had no tools. `build_agent` also had **no callers** — the CLI had no
   `agent` command and the AgentCore handler went straight to the single-shot
   provider. *(This became build-journey post #2: "A Strands agent with zero tools
   answers exactly like one with eight.")*
2. **The agent could not act, even once wired.** The system prompt named only
   prohibitions, and no tool emitted a `RepairIntent`. Nova Pro investigated
   correctly and then **abstained because nothing was permitted.** Fixed by adding
   `propose_repair` and a prompt naming the two permitted transformations.
3. **CI had been red for three commits** — `ruff format --check` on four files, and
   the coverage gate at 74% against `fail_under = 80`.
4. **The working demo was replaying a reference-policy fixture.** The hand-written
   policy was making the right choice while the models under test were choosing a
   non-repairing transformation 6/6. Led to the rename, the stamping, the warning,
   and `--demo` refusing to run on it.
5. **`docs/results/`'s 100% repair rate is not a repair rate** — it is
   reference-policy output and must never be quoted.
6. **An unsourced Amazon statistic was cut** — "#1 CI/CD blocker, 30% of deployment
   triage lost", attributed to the Amazon Builders' Library. Unverifiable. Removed
   from narration, slide, and (later) the published Builder Center hero image.

**Video corrections (2026-09-09, second pass — all four were in the published cut):**
7. **Scene 6 never showed its own verdict.** Absolute frame constants left over from
   an earlier timeline: the first gauntlet row landed 13.2 s into a 26.7 s scene, only
   9 of 17 rows ever rendered, and `GAUNTLET_VERDICT_FRAME` (5970) sat **375 frames
   past the end of the scene** (5595) — so "17/17 attacks rejected", the line the whole
   scene exists to land, **was never on screen.**
8. **Two more narration/footage desyncs of the same family** (Act I model call at 2×
   printed `governor.verdict` two seconds after the narration said "Fifteen policy
   rules pass"; Act II sat frozen for eight seconds on a model call that had not
   started).
9. **Nothing checked any of this.** `npm run verify` gained two new assertion
   sections. *A beat that never fires renders as a still frame, not an error, which is
   why three of these shipped.*
10. **Act II's narration described a retry that is not in the footage.** Three
    sentences claiming "it took two attempts... the validator rejected it... it
    corrected the format, not the choice" — the recording contains **one**
    `bedrock.call attempt=1` followed 27 ms later by `governor.verdict approved=True`.
    **The take on screen and the take being narrated were different runs.** All three
    sentences were spliced out (11.133 s), originals preserved. Downstream: scene 7
    2230 → 1896 frames, `TOTAL_FRAMES` 8970 → 8636 (4:47.9).
11. **`demo/COMMANDS.md` describes a terminal geometry that was never recorded** —
    claimed 36px row pitch and caption bar in row 25; the real values are 29.21px,
    row 1 at y=97.5, caption bar in row 27.

**Publication corrections (2026-09-10):**
12. **The Builder Center hero image carried the unsourced Amazon statistic** — published
    on Amazon's own Builder Center. Replaced.
13. **The second Builder Center figure was a video still with a cut sentence burned
    into it** — "But it corrected the format, not the choice", over a terminal showing
    `attempt=1` approved on the spot. Replaced.
14. **"15 seeded concurrency races"** → "7 races and 5 non-race controls".
15. **"vs 3/6 in unconstrained LLMs"** → "6/7" — the published figure cited the weakest
    comparator against the wrong denominator; **6/7 is the real Arm A number and the
    stronger result.**
16. **"8 tools" → "9 tools."**
17. **README's demo-video claims had drifted:** "80% → 45%" corrected to the recorded
    run's **75% → 70%**; "Nova Lite in 2.8 s" corrected to **Nova Pro at 3.0 s** for
    the Act I shot; "systematic 15-case evaluation" corrected to **12 (7 races + 5
    controls)**.
18. **The quality-suite line was stale:** `pytest` is **199 passed in 106 s**, not 166
    in 50 s; mypy covers **74** files, not 73.
19. **Devpost was claimed pre-filled and was empty** — `software[description]`,
    `software[tag_list]`, `software[video_url]` and every URL field were empty strings,
    at 2/5 steps with five days to deadline.

---

## SECTION 21 — CURRENT PROJECT STATE AND OPEN ACTIONS

### 21.1 State at document generation (2026-09-10)

| Item | State |
|---|---|
| Git | branch `main`, HEAD `a10b391`, 36 commits, synced with `origin/main`. Working tree clean except this file. The README stills, the Devpost story and the Builder Center plan were committed by `fb077a4` and `0df3b49` |
| Tests | 199 passing |
| Coverage | 80% (at the gate exactly) |
| mypy | clean, 74 files, strict |
| ruff check | clean |
| **ruff format** | clean — 106 files formatted, `verify_deploy.py` fixed in `a10b391`. `MASTER_DOC.md` is excluded in `pyproject.toml` (ruff formats Python blocks inside Markdown) |
| Dashboard | live and verified |
| AgentCore | deployed, `agent` mode verified, `pipeline` mode untested |
| YouTube | published |
| Builder Center post | published and corrected |
| **Devpost** | **DRAFT, 4/5 steps, NOT submitted.** Project details and Additional info are both saved; only the Submit button remains, deliberately left to the user |

### 21.2 Devpost submission detail
- **Project details: filled and SAVED 2026-09-10.** 8,211-character story (source of
  truth: `docs/posts/devpost-project-story.md` — edit there and re-paste), 14 tags,
  7 gallery images with captions, `software[video_url]` = `https://youtu.be/rkoeqMt3cDk`,
  three try-it-out URLs.
- **Additional info: saved, two required fields still blank.** Set: Submitter Type
  `Individual`, Track `Professional Agents`, repo URL, live demo URL, bonus blog URL,
  2,109-character testing instructions, `assets/video/arch-0-neutral.png` as the
  required architecture diagram.
- ⚠️ **BLANK AND REQUIRED: Country of Residence, and AWS Builder ID.** Neither is
  knowable from the repository. Both need the human.
- **The final Submit button was deliberately not pressed.**

### 21.3 Manual actions still owed
1. **Delete IAM user `chronotrace-deploy`** after submission (the one that matters).
2. **Delete `~/Downloads/chronotrace-deploy_accessKeys.csv`** — plaintext secret key.
3. Fill the two blocking Devpost fields and submit before **2026-09-15**.
4. ~~`uv run ruff format scripts/verify_deploy.py`~~ — **done in `a10b391`**; CI run `34446628164` is green.
5. *(Optional)* Tear down AgentCore runtime `chronotrace-W8r1r453Mi`.
6. *(Optional)* Delete Amplify app `d3k7wvrz5f9b6h` — **but NOT before judging**, it is
   a submitted link.

### 21.5 One-command fix-and-verify

Applies the only outstanding code fix, then runs the full CI-equivalent suite in the
same order as `.github/workflows/ci.yml`. Safe to re-run: every step is idempotent,
and `&&` chaining stops at the first failure.

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy chronotrace/ tests/ && uv run chronotrace gauntlet && uv run python -c "import chronotrace; print(chronotrace.__version__)" && uv run pytest -q
```

Expected on success: `1 file reformatted` · `All checks passed!` ·
`106 files already formatted` · `Success: no issues found in 74 source files` ·
`17 attacks, 17 rejections` · `0.1.0` · `199 passed`.

Note that `MASTER_DOC.md` is in ruff's `extend-exclude` (see §11.3) — ruff 0.16.6
formats Python blocks inside Markdown, and without the exclude this document itself
fails `ruff format --check` in CI.

### 21.4 Stated roadmap ("What's next")
- More race shapes in the intent vocabulary.
- A GitHub Action that opens the regression-guard PR.
- Pushing the forced-replay tier down into pytest as a plugin, so it runs where the
  flake is.
- (Implied by limitations) CloudWatch Transaction Search for complete trace retention;
  a DynamoDB incident registry; exercising Docker isolation; making
  `ISOLATE_FIXTURE_SCOPE` real; fixing `propose_repair` inside AgentCore by writing to
  a scratch path.

---

## SECTION 22 — RESUME / CV MATERIAL

### 22.1 Project title lines (pick by length)
- `ChronoTrace — Autonomous flaky-test repair agent (AWS Bedrock, Strands Agents SDK)`
- `ChronoTrace — AI agent that repairs concurrency-induced flaky Python tests and proves the repair`
- `ChronoTrace — trace-differential flaky-test repair with forced-interleaving verification`

### 22.2 Bullet bank — pick 3–5, all defensible

**Impact / results bullets**
- Built an autonomous AI agent that repairs concurrency-induced flaky `asyncio` tests
  and **proves causality by forced replay**; in a controlled three-arm study it
  eliminated timing band-aids entirely (**0/7 vs 6/7** for an unconstrained Amazon
  Nova Pro baseline) and produced **zero false repairs on 5 negative controls (vs
  5/5)**.
- Designed a **15-rule deterministic AST policy gate** validated by an adversarial
  gauntlet of **17 crafted attack patches — 17/17 rejected**, each by the rule
  targeting it; the gauntlet runs offline in CI with no credentials or model.
- Demonstrated that **rerun-based verification cannot distinguish "fixed the race"
  from "made it rarer"**: a policy-clean patch that passed the gate 15/15 reduced a
  test's flake rate 75%→70% (and 80%→45% on another sample) and was **rejected by
  forced replay** — the failure mode shipping products (Datadog's 20-retry
  attempt-to-fix, BuildPulse's PR checks) cannot detect.
- Ran a controlled model comparison (Amazon Nova Pro vs a 14.8B local model) over
  identical replayed traces and diagnoses, finding the **frontier model band-aided
  more often when unconstrained (6/6 vs 3/6)** — reported separately, never pooled.

**Architecture / engineering bullets**
- Architected a six-stage pipeline (capture → diagnose → schedule → synthesize →
  govern → verify) in which the LLM's entire authority is emitting one **typed,
  schema-validated `RepairIntent`** — never source code — with LibCST applying the
  transformation across two coroutines deterministically.
- Implemented a **forced-interleaving scheduler** that gates instrumented `asyncio`
  operation entry, converting flaky-test verification from statistical sampling into a
  **controlled experiment** (pre-patch 20/20 fail, post-patch 20/20 pass under the
  identical forced ordering, harness unchanged).
- Built trace-differential fault localisation: occurrence-indexed OpenTelemetry-style
  spans, execution fingerprinting (commit/Python/lock-hash/env-hash) to reject
  non-comparable traces, an observed-order graph over three edge sources, backward
  slicing from the failed assertion, and **Ochiai spectrum-based ranking**.
- Shipped **abstention as a first-class outcome** with 8 machine-readable refusal
  reasons; correctly reported `DEPTH_GE_2_UNRESOLVED` on a candidate scoring **Ochiai
  1.00** that forced at only 60% — necessary but not sufficient.
- Delivered the product as a **generated deterministic regression test** that reproduces
  the original race on every run in milliseconds, rather than as a patch.

**Cloud / AWS bullets**
- Integrated the **AWS Strands Agents SDK** with **Amazon Bedrock** (`amazon.nova-pro-v1:0`,
  `amazon.nova-lite-v1:0`), enforcing structured output through Bedrock's `converse`
  tool-use schema so the model has no channel for raw code; **9 incident-scoped tools**
  with a `--dry-run` registration check.
- Deployed the agent to **Amazon Bedrock AgentCore Runtime** (`linux/arm64`, direct code
  deploy) and the incident dashboard to **AWS Amplify Hosting** as a verified static
  export (HTTP 200, 15 incident rows, 0 console errors via Playwright), all within a
  **$0.01 total AWS spend** under a budget guardrail.

**Rigor / craft bullets**
- Maintained **199 tests, 80% coverage, `mypy --strict` across 74 files, ruff-clean**,
  with a 7-step CI pipeline that runs the adversarial governor gauntlet as a gate.
- Documented **6 ADRs** and **11 explicit limitations**, deliberately quoting **no
  headline repair rate** because one race shape dominates the corpus — and published a
  corrections log of every claim that was stated before it was true.

### 22.3 Skills demonstrated (for a skills section)
`AI agents` · `AWS Bedrock` · `AWS Strands Agents SDK` · `AWS AgentCore Runtime` ·
`AWS Amplify` · `LLM structured output / tool use` · `prompt engineering + ablation
studies` · `Python asyncio` · `concurrency & race analysis` · `program repair` ·
`AST/CST transformation (LibCST)` · `spectrum-based fault localization (Ochiai)` ·
`distributed tracing / OpenTelemetry concepts` · `pytest plugin development` ·
`experimental design & controlled evaluation` · `pydantic` · `mypy strict typing` ·
`Next.js/React/TypeScript/Tailwind` · `CI/CD (GitHub Actions)` · `technical writing`

### 22.4 Interview soundbites (30 seconds each)

**"What is it?"** — A flaky test that fails on concurrency isn't a code problem you
can read; it's an *ordering* problem you have to observe. ChronoTrace records a
passing run and a failing run of the same commit, subtracts them to find the pair of
operations that swapped order, and then *forces* that ordering. If it fails 100% of
the time under forcing, that ordering is a sufficient condition for the failure. Then
it fixes it and forces the identical ordering again. The harness never changes, so the
patch is the only variable — that's a controlled experiment, not a rerun.

**"Why can't the model just write the fix?"** — Because a model that writes code can
write `time.sleep(2)`, and that's not hypothetical, it's the default behaviour. The
test goes green, the race is still live, and you've bought permanent CI cost. So the
model gets exactly one job: pick a repair pattern from a fixed set and return typed
JSON. That makes the space of possible patches *enumerable*, which is what lets the
policy gate be complete instead of best-effort. The thing that decides is not the
thing that verifies.

**"What's the strongest result?"** — Not the repair rate. It's that unconstrained
Amazon Nova Pro reached for a sleep on six races out of six, and falsely repaired
five out of five tests that had nothing wrong with them. The trace diff alone halved
the band-aids without anyone telling it to; the gate removed them. And the gap was
*wider* on the bigger model, not narrower.

**"Where did it fail?"** — R14. I deliberately added one case of a different race
shape to see whether the model was reasoning or shape-matching. It shape-matched. It
proposed an event where the assertion actually depended on a task *completing*, and
the patch broke no rule — the governor passed it 15 out of 15. Forced replay caught
it. A rerun gate saw 75% down to 70% and would have shipped it. Both unconstrained
baselines got that case *right*, which I report, because they're not safer — they're
unconstrained, and this time that happened to help.

**"What would you do differently?"** — Build the corpus with more race shapes before
writing the intent prompt. Six of seven repairable cases share the shape the prompt
names, so 6/6 doesn't mean what it looks like it means. I say that in the README
rather than around it.

---

## SECTION 23 — GLOSSARY

| Term | Definition as used in this project |
|---|---|
| **Band-aid** | A patch that makes a test green without fixing the defect: a sleep, a retry, an inflated timeout, a weakened/deleted assertion, a swallowed exception, a skip |
| **Bug depth** | The number of ordering constraints needed to reproduce a failure. Depth 1 = one sufficient ordering. Depth ≥ 2 = reported, never patched |
| **Causal position** | Index of the earliest span involved in a candidate inversion; the tie-break for ranking (earliest first) |
| **Causal precision** | Fraction of forced candidates that actually reproduced the failure |
| **Execution fingerprint** | `commit_sha` + `python_version` + `dependency_lock_hash` + `container_image` + `test_id` + `env_hash`. Traces with different fingerprints are never diffed |
| **Forced replay** | Installing the schedule harness to reproduce a specific ordering on demand. Tier 1 verification |
| **`FORCED_HARMLESS`** | Tier 1 pass: the failing interleaving still occurs and no longer breaks the test |
| **`FORCED_UNREACHABLE`** | Tier 1 pass, stronger: the patch made the interleaving impossible to produce |
| **Gauntlet** | The 17 crafted adversarial patches run against the governor, offline, in CI |
| **Governor** | The 15-rule deterministic AST policy gate. Cannot be bypassed or relaxed |
| **INFEASIBLE** | A forced ordering that times out — the ordering is unreachable in this code. A diagnostic result, not a failure |
| **Inversion** | Two operations observed in one order when passing and the other when failing |
| **Observed order** | The ordering derived from observed start times plus structural edges. **Deliberately not called happens-before** |
| **Occurrence index** | The `#N` in `"name#N"`. Spans are keyed by name *and* occurrence so a loop does not collapse into one entry |
| **Ochiai** | Spectrum-based suspiciousness score, computed across all captured traces |
| **Probe effect** | The change in timing caused by instrumentation. Measured as instrumented minus uninstrumented flake rate, and reported |
| **PCT** | Probabilistic Concurrency Testing (Burckhardt et al., ASPLOS 2010). Tier 2 |
| **Reference policy** | The hand-written decision procedure used as a **test double**. Not a model. Never a result |
| **Regression guard** | The generated forced-interleaving test appended to the patched module. **The shipped product** |
| **`RepairIntent`** | The typed JSON object that is the *entirety* of what the model emits |
| **Signal site / wait site** | Where the synchronization primitive is `set()` and where it is `await …wait()`ed. Equivalent to FlakeSync's critical point / barrier point |
| **Three arms** | A (code only), B (+ traces), C (full ChronoTrace) |
| **`symptom_patch_suspected`** | Tier 1 passed but Tier 3 is still flaky — the signature of patching a symptom |

---

## SECTION 24 — DISAMBIGUATION: NUMBERS THAT ARE COMMONLY MISQUOTED

> **An LLM reading this file should consult this section before quoting any figure.**

| Figure | Correct usage | Common error |
|---|---|---|
| **15 vs 12 vs 7 cases** | 15 cases exist; 12 are in the three-arm corpus; 7 of those are repairable races; 5 are controls | Saying "15-case evaluation" — corrected on 2026-09-10 |
| **6/6 vs 6/7** | 6/6 = R01–R06 only. 6/7 = all repairable races including R14 (which Arm C fails). Both are correct in their own table | Mixing the denominators across tables |
| **Band-aids 6/6 vs 6/7 vs 3/6** | 6/6 = Nova Pro Arm A on R01–R06. 6/7 = Nova Pro Arm A over all 7 races. 3/6 and 3/7 = the **qwen** figures | Citing qwen's 3/6 as the headline — it is the *weakest* comparator |
| **80%→45% vs 75%→70%** | Both are real R14 samples. 75%→70% is the **video's recorded run**; 80%→45% is another measured run. The residual has ranged 45–75% against a pre-patch 70–80% | Quoting one as *the* number without the variance disclosure |
| **2.8 s Nova Lite vs 3.0 s Nova Pro** | 2.8 s / 3,066 in / 286 out = **Nova Lite on the R14 run**. 3.0 s / 2,693 in / 296 out = **Nova Pro in the Act I footage** | Attributing Nova Lite's timing to the Act I shot |
| **8 vs 9 tools** | **9 registered.** The README's investigation-tool table lists 8 and omits `propose_repair` | Saying 8 |
| **100% repair rate** | **Never quotable.** It is `docs/results/` reference-policy output with no model in the loop | Quoting it as a model result |
| **83.75%** | **FlakeSync's** number (ICSE 2024), not ChronoTrace's, and not comparable | Presenting it as a benchmark ChronoTrace beat |
| **5/5 abstention** | Correct, but **4 of the 5 never reach the model** | Quoting it as evidence a model declines when asked |
| **199 tests / 74 mypy files** | Current. HANDOVER previously said 166 / 73 | Using the stale figures |
| **"84% of CI failures"** | Precisely: 84% of **pass-to-fail transitions in Google post-submit CI** | Generalising to "84% of all CI failures everywhere" |
| **"30% deployment triage"** | ⛔ **Unsourced and deliberately removed. Never use.** | Reintroducing it from an old draft or old image |
| **Happens-before** | ⛔ ChronoTrace computes **observed order**, not happens-before. Do not invoke Lamport | Upgrading the claim |
| **CloudWatch / DynamoDB** | ⛔ **Not implemented.** Both raise if selected | Describing either as working |
| **AgentCore repair** | Investigates ✅, repairs ❌ (read-only bundle) | Claiming a fully working hosted repairer |

---

## SECTION 25 — QUICK ANSWERS TO LIKELY QUESTIONS

**Q: Is this just a wrapper around an LLM?**
No. The model's total authority is selecting one of five enum values and naming two
operations. Capture, diagnosis, patch application, policy enforcement and verification
contain **zero** model calls. The deterministic layers run end to end with no
credentials and no GPU, which is exactly why the reference-policy test double works.

**Q: What if the model picks wrong?**
That is the R14 case, and it is documented as a headline result rather than hidden.
Forced replay rejects the patch, the UI state becomes `NEEDS_INVESTIGATION`, and
nothing is written. A rerun-based gate would have shipped it.

**Q: Why not just quarantine flaky tests?**
That stops the bleeding; the race is still there and will resurface in production
under different timing. Quarantine is what Trunk, Develocity, Harness, Buildkite and
CircleCI do. ChronoTrace's position is that the interesting artifact is a *reproducer*,
not an exclusion list.

**Q: How is this different from BuildPulse or Datadog?**
Three ways: input (execution traces vs test results), confirmation (forced replay vs
reruns), and constraint (a complete policy gate vs an unconstrained agent). All three
are stated in the README's "Honest positioning" section, which explicitly concedes
those are real, shipping products doing real work.

**Q: Does it work on threading?**
No, by design (ADR 0001). Threading and multiprocessing are detected in order to
**abstain**. A "forced ordering" over CPython OS threads would be theatre.

**Q: Is the benchmark rigged in the system's favour?**
Five of twelve cases are negative controls the system must refuse, and the false-repair
rate on them is reported as a headline metric. R14 was added specifically as a
falsification test — and the system failed it, which is reported. The generalization
limit is stated in the README, the findings doc, the video, and the Devpost story.

**Q: What is the single most important number?**
**0 band-aids and 0 false repairs, against 6/6 and 5/5 for an unconstrained frontier
model on the same evidence.** It is the most reproducible result in the project and the
gap widens with model size.

---

## SECTION 26 — SOURCE-OF-TRUTH FILE MAP

| Question | Authoritative file |
|---|---|
| What the project claims, overall | `README.md` |
| The pipeline, stage by stage | `ARCHITECTURE.md` |
| Why a decision was made | `docs/adr/000{1..6}-*.md` |
| Canonical local-model results | `eval/results/FINDINGS.md`, `eval/results/three_arm_final_table.md` |
| Canonical hosted-model results | `eval/results/bedrock/three_arm_table.md` + the JSON beside it |
| Prompt ablation | `eval/results/arm_c_prompt_comparison.md` |
| Model ablation | `eval/results/arm_c_model_comparison.md` |
| Dashboard data | `eval-results/incidents.json`, `eval-results/results.md` |
| **NOT a model result** | `docs/results/` (read its `README.md` first) |
| Deployment facts and cost | `DEPLOY_SUMMARY.md` |
| Session context, corrections log | `HANDOVER.md` |
| Devpost copy (source of truth) | `docs/posts/devpost-project-story.md` |
| YouTube copy as published | `docs/posts/youtube-upload-pack.md` |
| Builder Center revision plan | `docs/posts/builder-center-update.md` |
| Build-journey narrative posts | `docs/posts/02-zero-tools.md`, `docs/posts/03-nova-reaches-for-sleep.md` |
| Demo sequence for recording | `demo/README.md`, `demo/COMMANDS.md` |
| Data contracts | `chronotrace/contracts.py` |
| The 15 rules | `chronotrace/govern/gate.py` (`RULES` dict) |
| The 17 attacks | `chronotrace/govern/gauntlet.py` (`ATTACKS` list) |
| The tier ladder + honesty rules | `chronotrace/verify/tiers.py` (module docstring) |
| The agent system prompt | `chronotrace/agent/graph.py` (`SYSTEM_PROMPT`) |
| The intent prompt (v2) | `chronotrace/providers/prompts.py` (`INTENT_SYSTEM`) |
| Ground truth per case | `benchmark/cases/*/ground_truth.json` |
| Config surface | `chronotrace/config.py`, `.env.example` |
| AgentCore config | `chronotrace/agent/deploy/agentcore.yaml`, `agentcore_entry.py`, `requirements.txt` |

---

*End of master document. Everything above is either directly extracted from the
ChronoTrace repository at commit `a10b391` (2026-09-10) or measured by running its
own tooling on that commit. Figures flagged ⚠️ or ⛔ carry the constraint stated
beside them.*
