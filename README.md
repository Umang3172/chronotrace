# ChronoTrace

[![CI](https://github.com/OWNER/chronotrace/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/chronotrace/actions/workflows/ci.yml)
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

Existing tools **detect and quarantine**: Datadog Test Visibility, Trunk,
Gradle Develocity, CircleCI, BuildPulse, Launchable. None repair. General coding
assistants do attempt repairs, and reach for `time.sleep(2)`, which makes the
test green, leaves the race in place, and adds permanent CI cost forever.

## The pitch

ChronoTrace is structurally prevented from doing either.

It aligns a passing and a failing execution trace from the same commit, ranks
the orderings that differ, and then **forces** each candidate to decide which
one is causal rather than inferring it. The model's only job is to pick a repair
pattern and return typed JSON; deterministic code applies it, and a policy gate
rejects sleeps, retries, timeout inflation and weakened assertions before
anything runs.

We found no comparable system in the reviewed literature combining
trace-differential diagnosis, deterministic synchronization patching, an
explicit anti-band-aid policy gate, and adversarial replay.

## 60-second demo

```bash
git clone https://github.com/OWNER/chronotrace && cd chronotrace
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
actually reproduced the failure when forced — 8 of the 10 candidates that were
forced were causally sufficient. The other two were the depth-2 case, correctly
classified as necessary-but-insufficient rather than patched.

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

| Work | Venue | Scope |
|---|---|---|
| **FlakeSync** | ICSE 2024 | Closest prior art: repairs *asynchronous* flaky tests by finding critical points and inserting barriers at runtime |
| **FlakyGuard** | arXiv:2511.14002 (UT Austin + Uber) | 47.6% repair rate, 51.8% developer acceptance; graph-based context selection |
| **FlakyDoctor** | ISSTA 2024, arXiv:2404.09398 | 57% OD / 59% ID on 873 tests; neuro-symbolic, code-static |
| **FlakyFix** | arXiv:2307.00012 | Fix-category driven, first full LLM automation attempt |
| **iFixFlakies** | ESEC/FSE 2019 | Order-dependent flakiness only, symbolic |

How ChronoTrace differs, stated narrowly:

1. **Runtime, not code.** FlakyDoctor extracts test code; FlakyGuard explores the
   code graph. Neither ingests execution traces. For a concurrency bug the defect
   lives in the interleaving, not the code text.
2. **Causality is tested, not inferred.** FlakeSync searches for critical points
   at runtime; ChronoTrace diffs *paired* pass/fail traces and then forces the
   candidate ordering to decide. Pre-patch under forced ordering must fail;
   post-patch under the identical ordering must pass.
3. **The anti-band-aid governor.** No prior work has a deterministic gate that
   rejects sleeps, retries and timeout inflation, with a positive check that a
   real primitive was actually added.
4. **Abstention, deadlock pre-checking, and a regression artifact.** FlakeSync
   has none of these.

FlakyGuard names the "context problem" — too little context misses critical
code, too much overwhelms the model. The trace diff *is* a context-selection
mechanism, which reframes this as a different solution to a problem the state of
the art already identified.

> **On FlakeSync's reported numbers:** the ~83.75% repair rate and ~1.00× median
> overhead figures circulating for FlakeSync came to this project through a
> secondary review, not a primary source check. Verify them against the paper
> before quoting them anywhere.

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

## License

MIT — see [LICENSE](LICENSE).
