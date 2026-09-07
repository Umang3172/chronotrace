# Three-arm baseline evaluation

**No arm repaired anything. ChronoTrace scored 0 of 6, the same as both
baselines**, and the CI-cost story did not reproduce either: every sleep the
baselines injected had a duration of zero, so the projected annual CI cost is
0 hours for all three arms rather than the tens of hours the project's framing
assumes. Two of the project's marketing claims do not survive this run. The
band-aid and false-repair findings did survive, and strengthen with trace
evidence.

## The table

| Metric | Arm A (code only) | Arm B (+ traces) | Arm C (ChronoTrace) |
|---|---|---|---|
| Races repaired (verified) | 0 / 6 | 0 / 6 | 0 / 6 |
| **Band-aids injected** | **6 / 6** | **4 / 6** | **0 / 6** |
| CI seconds added per run | 0 s | 0 s | 0 s |
| Projected annual CI cost (50 runs/day) | 0 h | 0 h | 0 h |
| False repairs on 5 controls | 4 / 5 | 3 / 5 | 0 / 5 |
| Tokens per successful repair | undefined (8,124 tokens, 0 repairs) | undefined (9,447 tokens, 0 repairs) | undefined (7,390 tokens, 0 repairs) |
| Causality proven | no | no | no |

## Model and scope

| | |
|---|---|
| Model | `qwen3:8b` — 8.2B parameters, Q4_K_M quantisation, 40960 context, Apache-2.0 |
| Digest | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| Server | Ollama 0.32.14 at `http://localhost:11434` |
| Sampling | temperature 0.0, seed 1729, `num_predict` 4096, `think: false` |
| Cases | 11 — 6 repairable races (R01–R06), 5 negative controls (N01, N02, N03, N06, N07) |
| Combinations | 33 arm-case pairs |
| Wall clock | 16.5 min live; 7.4 min on fixture replay |

**This is a local-model baseline, not the submission numbers.** A Bedrock re-run
against a larger model is planned and those figures are the ones that will be
quoted in the submission. An 8B quantised model is a weak stand-in for what a
developer would actually point at this problem, and it is weak in both
directions: it may reach for cruder fixes than a frontier model would, and it
also failed to produce usable output at all on one case per baseline arm.

### Fairness

Everything except the information supplied and the constraints applied was held
identical: same model, temperature, seed, token cap, attempt budget (3 per case
for every arm), and per-run timeout. Capture and diagnosis ran **once per case**
and were shared by all three arms, so no arm was compared against a luckier set
of runs — the shared flake rates and diagnoses are recorded in the JSON.
Verification used the same three tiers with the same forced ordering for every
arm, taken from ChronoTrace's diagnosis; the baseline models never saw it, but
the verifier must, or the arms would be judged by different standards.

Two accommodations were made **in the baselines' favour**: markdown fences are
stripped before applying a patch, and a response that does not parse as Python
costs an attempt rather than the case.

## Per-case detail

### Arm A — code only (6/6 band-aids)

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | N1 — `await asyncio.sleep(0)  # Allow writer to possibly start` |
| R02 commit_before_select | modified | N1 — `await asyncio.sleep(0)  # Ensure the task is scheduled` |
| R03 taskgroup_teardown | modified | N1 — `await asyncio.sleep(0)  # Ensure the task is scheduled` |
| R04 fixture_dirty_read | modified | N1 — `await asyncio.sleep(0)  # Ensure the refresher task is scheduled` |
| R05 event_set_after_wait | modified | N1 — `await asyncio.sleep(0)  # Allow startup task to proceed` |
| R06 queue_consumer_early | modified | N1 — `await asyncio.sleep(0)  # Ensure the producer has a chance to run` |

Six for six, the same reflex every time, and the comments say the quiet part out
loud: *allow the writer to possibly start*. The model knows it is racing and
reaches for a yield rather than an ordering.

### Arm B — code plus trace evidence (4/6 band-aids)

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | N1 — `await asyncio.sleep(0)` |
| R02 commit_before_select | modified | none — deleted the `await io_latency()` jitter from the test |
| R03 taskgroup_teardown | unchanged | none — returned the file unmodified |
| R04 fixture_dirty_read | modified | N1 — `await asyncio.sleep(0)` |
| R05 event_set_after_wait | modified | N1 — `await asyncio.sleep(0)` |
| R06 queue_consumer_early | modified | **N6 + N8** — removed an assertion, relaxed `==`, and renamed the test out of collection |

Trace evidence moved two cases off the sleep reflex, but R06 went somewhere
worse: deleting the assertion and renaming the test so pytest stops collecting
it. That is quarantine written by hand, and it would have been invisible to a
green build.

### Controls — what the baselines did to tests that had no race

| Case | True cause | Arm A | Arm B |
|---|---|---|---|
| N01 random_seed_flake | unseeded `random` | **modified** — removed an assertion | **modified** — removed an assertion |
| N02 network_timeout | external instability | **modified** | unchanged |
| N03 dict_iteration_order | hash ordering | **modified** — removed an assertion, relaxed `==` | **modified** — removed an assertion, relaxed `==` |
| N06 wrong_assertion | the test is simply wrong | **modified** | **modified** |
| N07 threading_race | a real race, in threads | no usable output after 3 attempts | no usable output after 3 attempts |

### Arm C — abstention on all five controls

| Case | State | Reason | Ground truth | Correct |
|---|---|---|---|---|
| N01 | ABSTAINED | `NOT_A_RACE` | `NOT_A_RACE` | yes |
| N02 | ABSTAINED | `NOT_A_RACE` | `NOT_A_RACE` | yes |
| N03 | ABSTAINED | `NO_TRACE_PAIR` | `NO_TRACE_PAIR` | yes |
| N06 | ABSTAINED | `NO_TRACE_PAIR` | `NO_TRACE_PAIR` | yes |
| N07 | ABSTAINED | `NON_ASYNCIO_PARADIGM` | `NON_ASYNCIO_PARADIGM` | yes |

**Abstention accuracy 5/5, with the correct reason in every case.** These cost
zero model calls: diagnosis refuses before the model is ever consulted.

### Why Arm C repaired nothing

**Not a JSON capability failure.** `intent_parse_failures: 0` — the model
returned a schema-valid `RepairIntent` on every one of its six calls. It simply
chose the wrong pattern every time:

| Case | Transformation chosen | Primitive | Scope |
|---|---|---|---|
| R01 | `RELAX_ASSERTION` | none | NONE |
| R02–R06 | `RELAX_ASSERTION` | `asyncio.Event` | CLASS_ATTR |

Six for six `RELAX_ASSERTION` on six genuine read-after-write races. Five of the
six are internally incoherent: a relaxation needs no synchronization primitive
and no shared scope, yet the model filled both fields in.

Because ChronoTrace never applies `RELAX_ASSERTION` automatically — it is routed
to human review — a wrong model decision produced **no patch** rather than a bad
patch. That is the constraint working. It is also the reason Arm C's 0 band-aids
and 0 false repairs are cheap: you cannot inject a band-aid into a file you did
not write to.

## Cost and timing

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Model calls | 13 | 13 | 6 |
| Input tokens | 5,273 | 6,730 | 6,810 |
| Output tokens | 2,851 | 2,717 | 580 |
| Total wall clock | 430 s | 373 s | 49 s |
| Median per case | 53.6 s | 40.1 s | 0.0 s (controls) / 8.1 s (races) |

Tokens per successful repair is **undefined for all three arms**: no arm
produced a verified repair, and dividing by zero would be worse than saying so.
Arm C is cheapest per case because it abstains on the controls without a model
call at all, and because a typed intent is ~90 output tokens against ~250 for a
rewritten file.

## Reproducibility

The evaluation replays from recorded fixtures with no model, no credentials and
no GPU:

```bash
uv run chronotrace three-arm --provider fixture --cases R01,R02,R03,R04,R05,R06,N01,N02,N03,N06,N07
uv run chronotrace replay-check --live eval/results/three_arm_ollama_qwen3_8b.json --replay <replay>/three_arm_ollama_qwen3_8b.json
```

Result: **model-derived fields identical across 363 field comparisons**, zero
prompt drift. The captured traces and diagnoses are recorded alongside the model
calls, so the replay reasons about the same evidence — observed flake rates and
diagnoses come out identical, and so did every `ui_state`, `verified_repair` and
`tier_reached`. The only field that differs is wall-clock time (16.5 min live
versus 7.4 min replayed), which cannot be otherwise.

Recording the evidence was not the original design. Keying fixtures on prompt
text failed, because the Arm A and Arm B prompts embed the observed flake rate
and the captured traceback, which change every run; a replay could never find
its own recording. Fixtures are now keyed by which call was made — provider,
arm, case, attempt — and the prompt is stored and compared, with any difference
reported as drift rather than hidden.

## Written summary

### 1. Did trace evidence alone reduce band-aid injection, or did it take the governor?

**Trace evidence helped, and it was not sufficient.** Band-aids fell from 6/6 to
4/6 and false repairs on controls from 4/5 to 3/5 when the model was handed the
trace diff and the ranked inversions, with no other change. That is a real
effect and it is the answer to the question people forget to ask.

But it is a partial effect in a bad direction as well as a good one. Arm B still
reached for `asyncio.sleep(0)` on four of six races, and on R06 it did something
worse than Arm A ever did — deleted an assertion and renamed the test out of
collection. Evidence made the model's output *more varied*, not reliably better.

Only the governor took band-aids to zero, and the honest caveat is that it did
so partly by refusing to patch at all. Arm C's 0/6 band-aids sits next to 0/6
repairs. On this model the gate is doing the work, but it is doing it on a model
whose pattern selection was wrong every single time.

### 2. What surprised me?

**Every injected sleep had duration zero.** Ten band-aids across two arms, and
not one had a non-zero duration — always `await asyncio.sleep(0)`, a scheduler
yield. The reflex to reach for a sleep reproduced perfectly; the *cost* of it
did not reproduce at all. The project's "adds 18 seconds of permanent CI cost
per run" framing has no support in this data.

**Arm C's failure mode was pattern selection, not JSON.** I expected an 8B model
to struggle with structured output. It never once failed: 6 valid intents from 6
calls. What it could not do is choose correctly, picking `RELAX_ASSERTION` for
six unambiguous read-after-write races and filling in a synchronization
primitive for a transformation that does not use one.

**A correct baseline repair was scored as a failure.** In an earlier run of this
same sweep, Arm B fixed R03 by moving `await handle` above the assertion — which
is the documented alternative ground truth for that case, and passes 30/30
naturally. The verifier scored it 0, because that repair makes the forced
ordering *unreachable* and the ladder reports INFEASIBLE, which is not
`causally_proven`. Detail in question 3.

### 3. What in this result weakens the project's claims?

Six things, worst first.

**a. The verification ladder is biased toward ChronoTrace's own transformation.**
This is the serious one. `INJECT_ASYNC_EVENT` leaves the racing ordering
reachable — the reader starts, blocks on the event — so it verifies at tier
FORCED. A repair that makes the bad ordering *impossible*, such as awaiting the
task before reading, is reported INFEASIBLE and scores zero, even though it is
arguably the stronger fix. Arm B produced exactly that repair for R03 and got no
credit. The ladder has no category for "the ordering can no longer occur", and
adding one would change a competitor's score, not ours. I did not change it
mid-evaluation, but it needs fixing and the current repair-rate metric quietly
favours us until it is.

**b. "18 seconds of permanent CI cost" is unsupported.** Measured CI cost added
was 0 s for every arm. If the Bedrock re-run also produces zero-duration sleeps,
that claim has to come out of the README and the video.

**c. Arm C's zero band-aid rate is partly a no-op result.** Zero band-aids
alongside zero repairs is exactly the G-1 concern the positive rules exist to
catch, one level up: the governor prevents bad patches, but on this model the
system also produced no good ones. "0% band-aids" is only impressive next to a
non-zero repair rate, and we do not have one yet.

**d. The comparison is unbalanced in an unexamined way.** Arms A and B were free
to write any Python; Arm C could only choose from five transformations. When the
model picks wrong, the baseline still ships something and ChronoTrace ships
nothing. That is the intended safety property, but it means "repair rate" is
measuring different things in the two designs, and a judge is entitled to say so.

**e. Run-to-run variance is larger than a single table admits.** Across three
live sweeps, Arm A was 6/6 band-aids and 4/5 false repairs every time and Arm C
was 0/6 and 0/5 every time, but Arm B moved between 2/5 and 3/5 false repairs and
its R03 output changed completely. The prompts embed the observed flake rate,
which differs per run, so the baselines are not deterministic even at temperature
0. Single-run baseline numbers should not be quoted without that caveat.

**f. N=6 repairable cases, seeded, one small local model.** Nothing here supports
a population claim. The direction of the band-aid and false-repair effects is
consistent and large; the magnitudes are not estimates of anything.

### What survived

Three findings held across every run: unconstrained models reach for timing
band-aids on concurrency races (6/6), they modify tests whose flakiness has
nothing to do with concurrency (4/5 controls), and the deterministic gate plus
the abstention paths stop both (0/6, 0/5, with the correct abstention reason 5/5
times). Those are the claims the data supports.
