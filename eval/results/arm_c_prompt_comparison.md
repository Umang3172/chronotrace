# Arm C: intent prompt v1 vs v2

One change: the intent system prompt was rewritten from descriptions-plus-caution
into an explicit decision procedure, with the condition that selects each
transformation stated in the fields the model actually receives, and abstention
moved out of the closing position. No benchmark case appears in it. Nothing else
changed — same models, temperature, seed, token cap, attempt budget, and the
same recorded traces, diagnoses and evidence via `--reuse-evidence`, so the
prompt is the only variable.

## Transformation chosen, per case

Ground truth for R01–R06 is `INJECT_ASYNC_EVENT`.

| Case | qwen3:8b before | qwen3:8b after | qwen2.5-coder:14b before | qwen2.5-coder:14b after |
|---|---|---|---|---|
| R01 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |
| R02 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |
| R03 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |
| R04 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |
| R05 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |
| R06 | `RELAX_ASSERTION` | `INJECT_ASYNC_EVENT` | `NO_REPAIR` | `INJECT_ASYNC_EVENT` |

**Correct transformation: 0/6 → 6/6 on both models.**

## Outcomes

| | qwen3:8b before | qwen3:8b after | 14b before | 14b after |
|---|---|---|---|---|
| Correct transformation | 0 / 6 | **6 / 6** | 0 / 6 | **6 / 6** |
| Intents carrying both sites | — | 0 / 6 | 6 / 6 | 6 / 6 |
| Patch applied | 0 / 6 | 0 / 6 | 0 / 6 | **6 / 6** |
| Governor approved | 0 / 6 | 0 / 6 | 0 / 6 | **6 / 6** |
| **Verified repairs** | 0 / 6 | 0 / 6 | 0 / 6 | **6 / 6** |
| Band-aids injected | 0 / 6 | 0 / 6 | 0 / 6 | 0 / 6 |
| **False repairs on controls** | 0 / 5 | 0 / 5 | 0 / 5 | 0 / 5 |
| **Abstention accuracy** | 5 / 5 | **5 / 5** | 5 / 5 | **5 / 5** |
| Invalid `RepairIntent` JSON | 0 | 0 | 0 | 0 |

Every 14B repair verified at tier `FORCED_HARMLESS`: the forced ordering failed
before the patch and passed after it, with the harness unchanged.

## The falsification test: held

The condition set in advance was that abstention accuracy on the five negative
controls must remain 5/5 with the correct reason. If repairs rose while
abstention degraded, the prompt bias had been *moved* rather than fixed, and
that would have been a failure of the change rather than an improvement.

**Abstention held at 5/5 with the correct reason on both models**, unchanged
from before: `NOT_A_RACE` (N01, N02), `NO_TRACE_PAIR` (N03, N06),
`NON_ASYNCIO_PARADIGM` (N07). False repairs stayed at 0/5. Band-aids stayed at
0/6.

Worth stating plainly: this test is weaker than it looks. Four of the five
controls are refused during *diagnosis*, before the model is consulted at all,
so the prompt cannot influence them. The prompt could only have degraded
abstention on a case that reaches the model, and none of the controls do. The
test is therefore evidence that the change did not break the deterministic
refusal paths — not evidence that a model would still decline when asked. That
weaker claim is the one the data supports.

## The 8B model: right decision, unusable payload

qwen3:8b now picks the correct transformation on all six cases and still
produces no repair. It emits only `transformation`, `primitive`, `shared_scope`
and `rationale`, leaving `signal_site` and `wait_site` null, so the patcher
refuses with *"INJECT_ASYNC_EVENT requires both a signal site and a wait site"*.
Those fields are `Optional` in the schema, so omitting them is legal.

The prompt fix moved the 8B failure one layer down rather than resolving it:
from choosing the wrong pattern to specifying the right one incompletely. Making
the site fields conditionally required would likely fix it, and that is a schema
change, not a prompt change. It was not made here — one change at a time.

## What this establishes

ChronoTrace has now been driven end to end by a real language model: 6/6 races
diagnosed, patched, gated and verified at the forced tier, with 0 band-aids and
0 false repairs, by `qwen2.5-coder:14b`. The earlier 0/6 was a prompt defect,
not a system failure and not an inherent limit of small models.

## What it does not establish

The prompt now names the selecting condition for the common case explicitly. It
does not name a benchmark case, and no worked example was added — but the
benchmark's six repairable cases are all the same shape, a read-after-write on a
shared resource, which is precisely the shape condition 1 describes. A prompt
that states the rule for the shape that makes up the whole positive test set is
a fair description of the domain, and it is also close to teaching the test.
Cases of a different shape are needed before 6/6 means what it appears to mean.

The honest reading: the system works with a model in the loop, on the shape it
was built for, once told which evidence selects which repair.
