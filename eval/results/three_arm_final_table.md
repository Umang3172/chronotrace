| Metric | Arm A (code only) | Arm B (+ traces) | Arm C (ChronoTrace) |
|---|---|---|---|
| Races repaired (verified) | 5 / 7 | 5 / 7 | 6 / 7 |
| **Band-aids injected** | **3 / 7** | **3 / 7** | **0 / 7** |
| CI seconds added per run | 0.02 s | 0.12 s | 0 s |
| Projected annual CI cost (50 runs/day) | 0.1 h | 0.6 h | 0 h |
| False repairs on 5 controls | 4 / 5 | 4 / 5 | 0 / 5 |
| Tokens per successful repair | 1,815 | 2,158 | 3,061 |
| Causality proven | no | no | yes — 6/7 at forced tier |

Local-model baseline: **qwen2.5-coder:14b** via `ollama`, 12 cases per arm (7 repairable races, 5 negative controls), 35 min wall clock.
These are **local-model numbers, not the submission numbers.** A Bedrock re-run against a larger model is planned, and those figures are the ones that will be quoted in the submission. A small quantised local model is a weak stand-in for what a developer would actually have pointed at this problem, in both directions: it may reach for cruder fixes than a frontier model would, and it may also fail to produce a usable patch at all.

### Arm A — per case

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost; N5: patch adds 1 retry loop(s) around an assertion; polling until the state arrives is a sleep with extra steps |
| R02 commit_before_select | unchanged | none |
| R03 taskgroup_teardown | modified | none |
| R04 fixture_dirty_read | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R05 event_set_after_wait | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R06 queue_consumer_early | modified | none |
| R14 batch_completion_lifecycle | modified | none |

### Arm B — per case

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | none |
| R02 commit_before_select | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R03 taskgroup_teardown | modified | none |
| R04 fixture_dirty_read | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R05 event_set_after_wait | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R06 queue_consumer_early | modified | none |
| R14 batch_completion_lifecycle | modified | none |

### Arm C — abstention on the negative controls

| Case | State | Reason |
|---|---|---|
| N01 random_seed_flake | ABSTAINED | NOT_A_RACE |
| N02 network_timeout | ABSTAINED | NOT_A_RACE |
| N03 dict_iteration_order | ABSTAINED | NO_TRACE_PAIR |
| N06 wrong_assertion | ABSTAINED | NO_TRACE_PAIR |
| N07 threading_race | ABSTAINED | NON_ASYNCIO_PARADIGM |
