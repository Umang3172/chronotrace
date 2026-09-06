# Demo assets

## The sequence

The demo is built around **causal proof**, not around code generation. The
interesting claim is not "an agent wrote a patch" — it is "we can show you which
ordering caused the failure, and prove it".

1. Run the flaky test a few times: `PASS PASS PASS FAIL PASS`.

   ```bash
   uv run pytest benchmark/cases/R01_unawaited_writer -q --count 20
   ```

2. Show where the two runs diverge — the trace lanes, with the inverted pair
   outlined.

3. **Force that ordering against the unpatched code.** It fails every time.

   ```bash
   echo '{"test_id":"*","order":["read_value#0","commit_value#0"],"gate_timeout_s":3}' > /tmp/force.json
   uv run pytest benchmark/cases/R01_unawaited_writer -q --count 20 --chronotrace-force /tmp/force.json
   ```

   That is not correlation. Twenty out of twenty, on a test that is otherwise a
   coin flip.

4. The agent emits a typed intent — JSON, not code.

5. **Attack the governor, live:**

   ```bash
   uv run chronotrace gauntlet
   ```

   Seventeen crafted patches — a sleep, an aliased sleep import, a retry
   decorator, `tenacity.retry`, a `while True` loop, a weakened assertion, a
   swallowed `AssertionError`, a skip marker, a timeout raised from 30 to 300, a
   no-op patch, a mutual-wait deadlock, an edit to `site-packages`. All rejected.

6. Apply the patch.

7. **Force the same ordering again.** It passes every time. The harness did not
   change between step 3 and step 7, so the only variable is the patch.

8. The emitted regression guard reproduces the race deterministically, forever.

Steps 3 → 7 are the heart of it. Everything else is engineering.

## Also worth showing

`R08_gather_order_assumption`, where the correct answer is **not** to
synchronise:

```bash
uv run chronotrace repair 'benchmark/cases/R08_gather_order_assumption/test_R08_gather_order_assumption.py::test_completion_order_is_alpha_then_beta'
```

Two independent fetches may complete in either order; the test insists on one.
ChronoTrace recommends relaxing the assertion and hands it to a human rather
than serialising concurrency the code never promised. A tool that always
synchronises would get this wrong and look confident doing it.

## Cached traces

Reproducing a 1-in-20 flake takes runs before the pipeline can start. For a
recorded walkthrough, use the fixture-replay path — every `LocalModelProvider`
call records its request and response under `fixtures/`, so a run replays
offline and byte-for-byte. **Say so on camera.** A pre-captured trace presented
as a live capture is the kind of thing that unravels afterwards.
