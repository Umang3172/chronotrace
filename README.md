# ChronoTrace

[![CI](https://github.com/Umang3172/chronotrace/actions/workflows/ci.yml/badge.svg)](https://github.com/Umang3172/chronotrace/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

**Repairs concurrency-induced flaky asyncio tests by proving which ordering
caused the failure, then leaving behind a test that reproduces it every run.**

A race that appeared once in a handful of runs becomes a deterministic
regression test that reproduces it every run, in milliseconds. That artifact —
not the patch — is the product.

---

## The problem

At Google, **84% of pass-to-fail transitions** in post-submit CI are caused by
flaky tests rather than real regressions.¹ When the build turns red, five times
out of six nothing is broken. Microsoft measured 26% of 3,871 sampled builds
failing to flakiness at a cost of $1.14M/year;² Atlassian reports 150,000+
developer hours lost annually, with 21% of frontend master build failures coming
from flakes.³ On Travis, 47% of 75 million restarted failing builds then
passed.⁴

Flakiness is heterogeneous — order-dependency dominates in Python at 59% of
7,571 flaky tests⁵ — and ChronoTrace deliberately targets the **concurrency**
subset, where runtime schedule evidence gives information that source-only
approaches do not have. FlakyCat found concurrency the hardest category to
classify at F1 39%, precisely because it depends on interaction rather than
text.⁶

Most CI tooling **detects and quarantines**: Trunk, Gradle Develocity, Harness,
Buildkite and CircleCI find flaky tests and isolate them from the gate. That
stops the bleeding; the race is still there.

A second group now **attempts repairs**. BuildPulse ships an opt-in
Claude-powered agent that opens fix PRs with a diff and a root-cause
explanation, and Datadog's Bits AI Dev Agent delivers a patch as a draft PR
labelled "Attempt to Fix". Both are real products and both do more than
quarantine. General coding assistants attempt repairs too, and reach for
`time.sleep(2)` — which makes the test green, leaves the race in place, and adds
permanent CI cost forever.

## The pitch

ChronoTrace is structurally prevented from taking that shortcut.

It aligns a passing and a failing execution trace from the same commit, ranks
the orderings that differ, and then **forces** each candidate to decide which
one is causal rather than inferring it. The model's only job is to pick a repair
pattern and return typed JSON; deterministic code applies it, and a policy gate
rejects sleeps, retries, timeout inflation and weakened assertions before
anything runs.

ChronoTrace is not the only system that repairs flaky tests — see
[prior work](#prior-work), where several do. What we did not find, in the
literature or in shipping products, is one that combines trace-differential
localisation, causality proven by forced replay, a deterministic anti-band-aid
gate, and a deterministic regression test as the artifact.

## 60-second demo

```bash
git clone https://github.com/Umang3172/chronotrace && cd chronotrace
uv sync
uv run chronotrace repair --demo
```

No AWS account, no credentials, no signup. It runs against a seeded flaky test
in `benchmark/`, and prints the diagnosis, the governor's verdict, the
verification tier reached, and the proposed diff.

Watch the governor refuse to be talked around:

```bash
uv run chronotrace gauntlet
```

Seventeen crafted attack patches — a sleep, an aliased sleep import, a retry
decorator, `tenacity.retry`, a `while True` loop, a weakened assertion, a
swallowed `AssertionError`, a skip marker, a timeout raised from 30 to 300, a
no-op patch, a mutual-wait deadlock, an edit to `site-packages` — each rejected
by the rule that targets it.

## How it works

```
capture     paired pass/fail traces, occurrence-indexed spans, execution fingerprint
diagnose    observed-order graph -> backward slice -> Ochiai ranking -> force each candidate
synthesize  model returns a typed RepairIntent; LibCST applies it across two coroutines
govern      15 deterministic rules; nothing runs without passing all of them
verify      forced replay -> PCT -> statistical, with the tier reached always reported
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and the walkthrough, and
[docs/adr/](docs/adr/) for the six decisions that shaped it.

### What makes the diagnosis causal rather than correlational

The trace diff identifies the pair of operations whose order differs. The
harness then forces that exact ordering:

| Forced failure rate | Meaning | Action |
|---|---|---|
| 100% | sufficient condition for the failure | patch it |
| 0% | noise | discard |
| strictly between | necessary but not sufficient | report depth ≥ 2, do not patch |
| gate timed out | ordering is unreachable | INFEASIBLE, discard |

On R01 in the benchmark, this is directly observable. The test is naturally
flaky at roughly 50%. Under the forced ordering it fails **20 out of 20**; under
the opposite ordering it passes **20 out of 20**. Same code, same harness — the
ordering is the variable.

After the patch, under the *identical* forced ordering, it passes 20 out of 20.
The harness does not change between the two runs, so the only variable is the
patch. That is a controlled experiment, not a sample.

### What the model is allowed to do

Exactly one thing: choose a repair pattern from a fixed set and emit a
`RepairIntent` — which transformation, which shared scope, which signal and wait
sites. It never emits source code. Diagnosis, patch application, policy
enforcement and verification are all deterministic. The thing that decides is
not the thing that verifies.

### The governor

Fifteen rules, every one of them reported pass or fail so the whole gauntlet is
visible rather than only the rule that fired.

- **Negative (8)** — sleeps; sleeps reached through an import alias; timeout
  markers added or inflated; retry and flaky decorators; retry loops around the
  assertion; assertions removed or weakened; exception handlers swallowing the
  failure; tests skipped, xfailed or renamed out of collection.
- **Positive (3)** — a real synchronization primitive was added; it is reachable
  from *both* the signal and the wait site; the patch is not a no-op. Without
  these, "0% band-aid rate" would be satisfiable by changing nothing.
- **Structural (4)** — the proposed wait edge closes no cycle in the wait-for
  graph; no production file without an explicit opt-in; never `site-packages`;
  the result parses.

Rules that cannot be decided from the patched file alone — timeout inflation, a
weakened assertion, a decollected test — compare before against after.

## Results

Produced by `uv run chronotrace eval --arm C --cases all`. Every number below
comes from that command; none is hand-entered.

| Metric | Arm C |
|---|---|
| Cases run | 14 |
| Repair rate on supported races | **100%** (6/6) |
| **False-repair rate on negative controls** | **0%** (0/5) |
| Abstention accuracy | **100%** (8/8) |
| Causal precision | 80% (8/10) |
| **Band-aid injection rate** | **0%** (0/6) |
| Ground-truth transformation match | 7/7 |
| Median measured overhead | 0.19 ms |
| Verification tiers reached | FORCED ×6, not reached ×8 |
| Wall clock, whole benchmark | 240 s |

Read the second and third rows first. For a system that modifies code, the
false-repair rate matters more than the repair rate: a patch that makes a
non-race green is worse than no patch, because it buries the real cause under a
green build.

**Causal precision** is the fraction of proposed candidate orderings that
reproduced the failure on every attempt when forced — 8 of the 10 candidates
that were forced. The remaining 20% is worth reading in full, because it is the
mechanism working rather than failing.

### Where the missing 20% went

Every candidate that was forced, across the whole benchmark:

| Case | Candidate ordering | Suspiciousness | Fails when forced | Verdict |
|---|---|---|---|---|
| R01 | `read_value` → `commit_value` | 1.00 | 100% | causally sufficient |
| R02 | `db_select` → `db_commit` | 1.00 | 100% | causally sufficient |
| R03 | `read_status` → `finalize_report` | 1.00 | 100% | causally sufficient |
| R04 | `use_token` → `refresh_token` | 1.00 | 100% | causally sufficient |
| R05 | `subscribe` → `publish_ready` | 1.00 | 100% | causally sufficient |
| R06 | `drain_queue` → `enqueue_job` | 1.00 | 100% | causally sufficient |
| R08 | `finish_beta` → `finish_alpha` | 1.00 | 100% | causally sufficient |
| R13 | `cache_get` → `cache_fill` | 1.00 | 100% | causally sufficient |
| **R12** | **`read_secondary` → `set_secondary`** | **1.00** | **60%** | **necessary, not sufficient** |
| **R12** | **`read_primary` → `set_primary`** | **0.87** | **40%** | **necessary, not sufficient** |

Both shortfalls are the same case, `R12_depth2_two_constraints`, and neither was
noise. No candidate in the corpus scored 0% when forced.

**Why they were proposed.** R12 brings up two replicas concurrently and asserts
`primary or secondary`. In the failing runs the test reads both flags before
either replica has published, so `read_secondary` before `set_secondary` appears
in *every* failing trace and in *no* passing trace. That is an Ochiai
suspiciousness of exactly 1.00 — a perfect statistical score. On ranking alone
it is indistinguishable from R01, which really is a single sufficient cause.

**Why forcing was right to withhold it.** The assertion fails only when *both*
reads are stale. Forcing one of the two orderings leaves the other a coin flip,
so the test fails some of the time and passes the rest — 60% and 40% across five
forced runs each. A rate strictly between 0 and 1 means the ordering is
*necessary but not sufficient*: it is part of the cause, not the whole of it.
ChronoTrace reports depth ≥ 2 and generates no patch.

**What that prevented.** Patching on the suspiciousness score would have
synchronised one replica and left the bug live. The test would then have failed
roughly half as often — which reads as improvement on any rerun-based metric,
and is exactly the "patched a symptom" outcome. Tier 1 catches it because a
symptom fix cannot make a forced ordering pass; a rerun gate cannot, because
half as flaky still looks better.

So 80% is not "20% of our candidates were wrong". It is "20% of our candidates
were partial causes, and the system said so instead of guessing". A tool that
always patched its top-ranked candidate would score 100% on repair rate here and
be wrong about R12.

**Overhead** is a measured median delta in test-call duration, natural runs
before the patch versus after. ChronoTrace does not claim zero added cost: a
synchronization primitive changes scheduling and contention even when it
introduces no fixed delay. The claim is *no fixed sleep-based delay introduced*,
plus that measured number. It is a sub-millisecond quantity and it moves between
runs — 0.19 ms and 0.38 ms on two runs of the same benchmark — so read it as
"too small to separate from measurement noise at this sample size", not as a
precise constant. Compare it against the 18+ seconds per run that a
`sleep(2)`-per-case baseline would add permanently.

**Tokens and cost are reported as n/a** for this run, and that is deliberate.
The default offline provider is a deterministic reference policy, not a model;
it has no tokens, and inventing a number for it would be a fabricated metric.
Set `CHRONOTRACE_PROVIDER=bedrock` to produce real token and cost figures.

### The benchmark

Fourteen seeded cases. **Labelled as seeded, not mined from the wild** — no
public Python concurrency flaky-test dataset exists; iDoFT is Java and
order-dependent-biased, and ReproFlake is Java too.

| | Cases | Expected |
|---|---|---|
| Repairable races | R01–R06 | FIXED |
| Over-constrained assertion | R08 | NEEDS INVESTIGATION — do **not** synchronise |
| Depth-2 race | R12 | NEEDS INVESTIGATION — two constraints needed |
| Production-scope race | R13 | ABSTAINED — the defect is in app code |
| Negative controls | N01, N02, N03, N06, N07 | ABSTAINED |

Five of fourteen are tests ChronoTrace **must refuse**: unseeded `random`, an
upstream timeout, hash-ordered iteration, a simply-incorrect assertion, and a
genuine race in *threads* rather than asyncio. Without them, a reader could
reasonably ask whether the benchmark was designed around the algorithm.

R08 is worth singling out. Two independent fetches may complete in either order,
and the test insists on one. Synchronising there would destroy real concurrency
to satisfy a wrong assertion, so ChronoTrace recommends relaxing the assertion
and hands it to a human instead of editing it. An assertion change is never
applied automatically.

## Prior work

### Research

| Work | Venue | Result and scope |
|---|---|---|
| **FlakeSync** | Rahman & Shi, ICSE 2024, [doi:10.1145/3597503.3639115](https://doi.org/10.1145/3597503.3639115) | **The closest prior work.** Repairs async flaky tests by identifying a *critical point* — code that must run early relative to concurrent code — and a *barrier point* that waits for it, then synchronising the two. 83.75% repair rate, median 1.00× original test runtime. |
| **FlakyGuard** | arXiv:2511.14002 (UT Austin + Uber) | 47.6% repair rate, 51.8% developer acceptance; graph-based context selection at industry scale |
| **FlakyDoctor** | ISSTA 2024, arXiv:2404.09398 | 57% order-dependent / 59% implementation-dependent on 873 tests from 243 projects; neuro-symbolic, code-static |
| **FlakyFix** | arXiv:2307.00012 | Fix-category driven; first full LLM automation attempt |
| **iFixFlakies** | ESEC/FSE 2019 | Order-dependent flakiness only, symbolic |

**FlakeSync is structurally similar to our `INJECT_ASYNC_EVENT`.** Its critical
point and barrier point are, in our vocabulary, the signal site and the wait
site, and it synchronises them exactly as we do. Four differences, stated
plainly:

1. **We localise by diffing paired pass/fail execution traces**, rather than by
   searching for a critical point at runtime. The pair is the instrument: an
   ordering present in every failure and no pass is a candidate, and one present
   in half of each is noise.
2. **We prove causality by forcing the interleaving**, rather than validating by
   rerun. Pre-patch under the forced ordering must fail and post-patch under the
   identical ordering must pass, with the harness unchanged between the two.
   That is a controlled experiment; a rerun is a sample.
3. **We abstain when the evidence is insufficient.** Non-race flakiness, no
   observable inversion, a race needing two constraints, a race in production
   code — each is a documented refusal with a reason, not a patch.
4. **We emit a deterministic regression test as the artifact.** A race that
   appeared once in a few runs gets a test that reproduces it every run.

FlakeSync's 83.75% and our 100% are **not comparable**: different corpora,
different languages, and ours is 6 seeded cases. Theirs is the serious number.

FlakyGuard names the "context problem" — too little context misses critical
code, too much overwhelms the model. The trace diff *is* a context-selection
mechanism, which reframes this as a different solution to a problem the state of
the art already identified.

### Production tools

Flaky-test repair is a shipping product category, not an open problem.

| Product | What it does |
|---|---|
| **BuildPulse** | Opt-in Claude-powered agent that opens flaky-test **fix PRs**, with a diff and a root-cause explanation, working from JUnit XML |
| **Datadog** | Test Optimization's **attempt-to-fix** remediation flow, which retries a candidate fix 20 times to confirm it; the Bits AI Dev Agent delivers a patch as a draft PR labelled "Attempt to Fix" |
| **Trunk, Gradle Develocity, Harness, Buildkite, CircleCI** | Detect and quarantine only — isolate the test from the gate without repairing it |

### Honest positioning

The shipping auto-fix products run largely unconstrained agents from **test
results** — a JUnit XML report, a failure message, the test source — and confirm
the result by rerunning. That is a reasonable design, and it is a different one
from ours in three specific ways:

- **Input.** ChronoTrace works from paired *execution traces*, not from test
  results. For a concurrency bug the defect lives in the interleaving, and a
  results file does not contain one.
- **Confirmation.** ChronoTrace proves causality by *forced replay*. Datadog's
  20 retries and BuildPulse's PR checks establish that a patch made the test
  stop failing; they cannot separate "fixed the race" from "made it rarer".
  Forcing the ordering can, and a patch that merely moves the timing fails our
  Tier 1 while passing a rerun gate.
- **Constraint.** Every ChronoTrace patch passes a deterministic policy checker
  that rejects sleeps — including aliased imports — retries, timeout inflation
  and weakened assertions, and separately requires that a real synchronization
  primitive reachable from both sites was actually added. An unconstrained agent
  optimising for a green rerun has every incentive to reach for exactly the
  constructs that gate rejects.

We make no claim to be the only system that repairs flaky tests. Several do, in
research and in production. The combination we did not find elsewhere is
trace-differential localisation, causality proven by forced replay, a
deterministic anti-band-aid gate, and a regression test as the shipped artifact.

## Limitations

These are load-bearing. Removing them to make the project look stronger would
make it weaker.

1. **The benchmark is seeded, not mined from the wild.** Fourteen cases written
   for this project, with recorded ground truth. It shows a directional effect,
   not a population estimate. N is small and we do not claim otherwise.
2. **asyncio only.** Threading and multiprocessing are detected in order to
   abstain. In CPython, OS threads cannot be scheduled deterministically from
   user space, so a "forced ordering" there would be theatre. See
   [ADR 0001](docs/adr/0001-asyncio-only-scope.md).
3. **It is observed-order inversion, not happens-before.** The ordering is
   derived from observed start times plus structural edges, not from a partial
   order over synchronization events. Claiming Lamport while shipping a
   timestamp sort would be a claim the implementation has not earned.
4. **Tier 1 requires instrumented operations.** Races between operations that
   emit no spans degrade to Tier 3, reported as such. Span granularity that is
   too coarse to see the race is detected and abstained on, rather than
   localised to the wrong place.
5. **The probe effect is real.** Instrumentation changes timing. Capture measures
   the flake rate with and without instrumentation and reports the delta rather
   than hiding it.
6. **Depth ≥ 2 races are reported, not repaired.** When no single ordering is
   sufficient, ChronoTrace says so and stops.
7. **One transformation family is fully implemented.** `INJECT_ASYNC_EVENT` and
   `AWAIT_UNFINISHED_TASK`. `ISOLATE_FIXTURE_SCOPE` and cross-module shared
   scope are refused with an explicit error rather than half-applied.
8. **Baseline arms A and B did not run here.** They require a real model
   provider; running them against the offline reference policy would produce a
   baseline that describes this repository rather than a model. The harness
   refuses rather than reporting a caveated number.
9. **Docker isolation is implemented but unexercised** on the development
   machine. Process isolation — one process per run — is the default and is what
   the reported numbers used.

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # runtime
uv sync --extra dev     # plus ruff, mypy, hypothesis, coverage
uv sync --extra bedrock # plus boto3 and the Strands SDK
```

## CLI

```bash
chronotrace capture <test_id> --runs 50      # gather pass/fail trace pairs
chronotrace diagnose <test_id>               # diagnosis only, no patch
chronotrace repair <test_id>                 # full pipeline; --apply to write
chronotrace verify <incident_id>             # what verification established
chronotrace report <incident_id>             # the report as JSON
chronotrace gauntlet                         # adversarial governor demo
chronotrace eval --arm C --cases all         # every number in this README
pytest --chronotrace                         # plugin-mode capture
```

Global options: `--allow-production-repair` (off by default), `--apply` (off by
default — ChronoTrace proposes a diff, it does not write to your repository),
`--json`.

## Running against your own tests

Instrument the operations that touch shared state:

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

Then `chronotrace repair 'path/to/test.py::test_name'`. The instrumentation is
inert when ChronoTrace is not running, which is what makes the probe-effect
measurement possible.

## Dashboard

```bash
uv run chronotrace eval --arm C --cases all
cd ui && npm install && npm run dev
```

Three states, all visible: **Fixed**, **Needs investigation**, **Abstained**.
Each incident page shows where the two runs diverge on a shared time axis, the
evidence and what forcing each ordering established, every policy rule with its
verdict, the verification tiers reached, and the proposed diff. See
[ui/README.md](ui/README.md).

## AWS

Bedrock hosts the agent. Everything else — trace diffing, the LibCST patcher,
the governor, the verification harness — is local and AWS-independent, so the
project is self-hostable and the evaluation runs offline.

CloudWatch Transaction Search is the right enterprise architecture for this
method, because differential analysis needs both traces **complete** and
standard sampled tracing would silently destroy the pipeline. It is the audit
and post-mortem export layer, deliberately **not** in the interactive path: a
remote log query mid-demo is a stalled demo.

## References

1. Memon et al. *Taming Google-Scale Continuous Testing.* ICSE-SEIP 2017.
2. Microsoft Research, flaky test cost analysis.
3. Atlassian Engineering, 2025.
4. Parry et al. *A Survey of Flaky Tests.* TOSEM 2022. doi:10.1145/3476105
5. Gruber et al. *An Empirical Study of Flaky Tests in Python.* ICST 2021. arXiv:2101.09077
6. FlakyCat, flaky-test category classification.
7. Burckhardt et al. *A Randomized Scheduler with Probabilistic Guarantees of Finding Bugs.* ASPLOS 2010.
8. Luo et al. *An Empirical Analysis of Flaky Tests.* FSE 2014.
9. Alshammari et al. *FlakeFlagger.* ICSE 2021.
10. Lamport. *Time, Clocks, and the Ordering of Events in a Distributed System.* CACM 1978.
11. Rahman & Shi. *FlakeSync: Automatically Repairing Async Flaky Tests.* ICSE 2024. doi:10.1145/3597503.3639115
12. BuildPulse, [flaky test product documentation](https://docs.buildpulse.io/flaky-tests/overview).
13. Datadog, [Flaky Tests Management](https://docs.datadoghq.com/tests/flaky_management/) and [Bits AI Dev Agent for Test Optimization](https://www.datadoghq.com/blog/bits-ai-test-optimization/).
14. Gradle, [Develocity flaky test detection guide](https://docs.develocity.ai/2026.2/guides/flaky-test-detection-guide/); Trunk, [Flaky Tests](https://trunk.io/flaky-tests).

## License

MIT — see [LICENSE](LICENSE).
