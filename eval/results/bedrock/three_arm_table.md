| Metric | Arm A (code only) | Arm B (+ traces) | Arm C (ChronoTrace) |
|---|---|---|---|
| Races repaired (verified) | 2 / 7 | 4 / 7 | 6 / 7 |
| **Band-aids injected** | **6 / 7** | **3 / 7** | **0 / 7** |
| CI seconds added per run | 0.01 s | 0 s | 0 s |
| Projected annual CI cost (50 runs/day) | 0.1 h | 0 h | 0 h |
| False repairs on 5 controls | 5 / 5 | 5 / 5 | 0 / 5 |
| Tokens per successful repair | 5,128 | 2,990 | 3,524 |
| Causality proven | no | no | yes — 6/7 at forced tier |

Hosted model: **amazon.nova-pro-v1:0** via `bedrock`, 12 cases per arm (7 repairable races, 5 negative controls), 17 min wall clock.
Same corpus, same arms and the same recorded evidence as the qwen2.5-coder:14b run, so the two are comparable case by case. Capture and diagnosis are deterministic and were replayed rather than re-run; only the model differs.

*(The two paragraphs above were corrected by hand: the sweep ran before the report learned to tell a hosted provider from a local one, and printed "these are local-model numbers, a Bedrock re-run is planned" over real Bedrock numbers. No figure in this file was touched.)*

### Arm A — per case

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost; N5: patch adds 1 retry loop(s) around an assertion; polling until the state arrives is a sleep with extra steps |
| R02 commit_before_select | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R03 taskgroup_teardown | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R04 fixture_dirty_read | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R05 event_set_after_wait | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R06 queue_consumer_early | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R14 batch_completion_lifecycle | modified | none |

### Arm B — per case

| Case | Patch | Band-aid pattern |
|---|---|---|
| R01 unawaited_writer | modified | none |
| R02 commit_before_select | modified | none |
| R03 taskgroup_teardown | modified | none |
| R04 fixture_dirty_read | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R05 event_set_after_wait | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R06 queue_consumer_early | modified | N1: patch adds 1 sleep call(s) (asyncio.sleep -> asyncio.sleep); a timing delay hides the race and adds permanent CI cost |
| R14 batch_completion_lifecycle | modified | none |

### Arm C — abstention on the negative controls

| Case | State | Reason |
|---|---|---|
| N01 random_seed_flake | ABSTAINED | NOT_A_RACE |
| N02 network_timeout | ABSTAINED | NOT_A_RACE |
| N03 dict_iteration_order | ABSTAINED | NO_TRACE_PAIR |
| N06 wrong_assertion | ABSTAINED | NO_TRACE_PAIR |
| N07 threading_race | ABSTAINED | NON_ASYNCIO_PARADIGM |
