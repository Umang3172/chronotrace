## Inspiration

A test fails on Friday afternoon. You rerun it. It passes. Nothing changed.

At Google, **84% of pass-to-fail transitions** in post-submit CI are caused by flaky
tests rather than real regressions — when the build turns red, five times out of six
nothing is broken. Microsoft measured 26% of 3,871 sampled builds failing to flakiness at
a cost of **$1.14M a year**. In Python, order-dependency dominates: 59% of 7,571 flaky
tests studied.

So we pointed an AI coding assistant at one. It added `time.sleep(2)`. The test went
green. The race was still there, and CI was slower forever.

That is the whole problem. An agent that is *allowed* to cheat will cheat, because a
green test is indistinguishable from a fixed test if all you measure is whether it
passed. **We wanted to find out what an agent can do when cheating is structurally
impossible.**

## What it does

ChronoTrace repairs concurrency-induced flaky tests in Python `asyncio` code and
**proves** the repair worked.

It never reads only your source. When a test is flaky, you don't have one failure to
debug — you have two recordings of the same code, one where it worked and one where it
didn't. ChronoTrace captures OpenTelemetry traces from a passing and a failing run at an
identical fingerprint (commit, Python version, lock hash, env hash), subtracts them, and
finds the pair of operations that swapped places.

Then it does the thing reruns cannot do: it **forces** that ordering. Gate the coroutine
entry, replay the interleaving on demand. Pre-patch, the forced ordering fails 20/20.
Post-patch, the identical forced ordering passes 20/20. The harness never changed; the
only variable was the patch.

What ships is not the patch. It is a generated regression test that reproduces the
original race **on every run, in milliseconds**, so the bug can never come back quietly.

## How we built it

**AWS Strands Agents SDK** — `strands.Agent` runs the loop and chooses its own steps,
bound to 9 `@tool`-decorated methods (`capture_traces`, `trace_slice`,
`compare_orderings`, `force_replay`, `source_context`, `diagnose_now`, `check_patch`,
`run_once`, `propose_repair`). `chronotrace agent --dry-run` prints the tool surface the
SDK actually registered, with no model call, so the wiring is checkable without an AWS
account.

**Amazon Bedrock** — `amazon.nova-pro-v1:0` for cross-coroutine reasoning,
`amazon.nova-lite-v1:0` for fast mode (2.8s turnaround, 3,066 in / 286 out). The model
returns a typed `RepairIntent` JSON schema — `INJECT_ASYNC_EVENT`, `AWAIT_UNFINISHED_TASK`,
`ISOLATE_FIXTURE_SCOPE`, `RELAX_ASSERTION`, `NO_REPAIR` — and **never raw source code**.
LibCST applies the intent across two coroutines. The model picks *what kind* of fix; it
does not get to write the diff.

**A 15-rule deterministic AST governor** stands between the model and the disk. 8
negative rules (sleeps, sleeps reached through an import alias, retry and flaky
decorators, retry loops around the assertion, timeout inflation, weakened or deleted
assertions, swallowed exceptions, tests skipped or renamed out of collection), 3 positive
(a real synchronization primitive was added, it is reachable from *both* the signal and
the wait site, the patch is not a no-op), 4 structural (no cycle in the wait-for graph,
no production file without opt-in, never `site-packages`, the result parses). Every rule
reports pass or fail, so the verdict is auditable rather than a single fired rule.

Run `chronotrace gauntlet` with no credentials and no model: **17 adversarial patches, 17
rejections, each by the rule that targets it.**

**AWS Amplify Hosting** serves the incident dashboard as a static export.
**Bedrock AgentCore Runtime** hosts the agent entrypoint.

## Challenges we ran into

**The Strands agent silently registered zero tools.** The eight methods were passed to
`Agent(tools=[...])` undecorated. The SDK logs `unrecognized tool specification` per tool
and *continues* — so the agent built cleanly, answered fluently, and had no tools at all.
It looked like it was working.

**Then it could act, and still wouldn't.** The system prompt named only prohibitions and
no tool emitted a `RepairIntent`, so Nova Pro investigated correctly and then abstained,
because nothing was permitted.

**The benchmark had to be built to make us look bad.** Five of the twelve cases are
negative controls with nothing wrong. If your agent patches those, it is pattern-matching,
not diagnosing.

## Accomplishments we're proud of

The result we did not expect, and the one we kept:

**On R14 — a task-lifecycle race, the one case in the corpus of a different shape — our
own agent proposed a patch that was wrong.** It broke no rule. The governor passed it
**15/15**. No sleep, no retry, nothing weakened. And it did not fix the race.

Forced replay caught it. A rerun-based gate did not: on the recorded run it saw 15/20
failures before the patch and 14/20 after — **75% → 70%** — and every rerun-based signal
on the market reads that as improvement and ships it.

Both unconstrained baselines *repaired* R14 correctly. We didn't. Those same baselines
falsely repaired **5 of 5** negative controls under Nova Pro. They are not safer; they
are unconstrained, and on that one case it happened to help.

Three arms, same model, same corpus, produced by `chronotrace three-arm` — no number is
hand-entered:

| Amazon Nova Pro, R01–R06 | Arm A (code only) | Arm B (+ traces) | Arm C (ChronoTrace) |
|---|---|---|---|
| Repaired, verified | 1 / 6 | 3 / 6 | **6 / 6** |
| **Band-aids injected** | **6 / 6** | 3 / 6 | **0 / 6** |
| False repairs on 5 controls | 5 / 5 | 5 / 5 | **0 / 5** |

Given the test and the failure and nothing else, the frontier hosted model band-aided
*more* often than a 14B local one, not less. The trace diff alone halved it. The gate
removed it.

## What we learned

**A verification layer that only ever agrees with you is decoration.** The R14 case is
the only evidence in this project that the tier is doing work rather than the model — and
we only have it because the benchmark contained a case we could fail.

**"Fixed the race" and "made it rarer" look identical in a pass count.** That is not a
tooling gap the industry has overlooked; it is unfixable by rerunning, because a rerun is
a sample and a forced replay is an experiment with a control.

We also learned to distrust our own numbers. Three separate claims in this project were
true-sounding and wrong until we checked them: an unsourced statistic on a slide, a
narration describing a retry the footage does not contain, and a results table
attributing one model's numbers to another. All three are recorded as corrections in the
repository rather than quietly deleted.

## What's next

Honest limits, stated as they would have to be answered:

- **It does not generalize past the shape it was told about.** Six of our seven
  repairable cases are read-after-write races on a shared resource, and the intent prompt
  names that condition explicitly. On the one case of a different shape, both models chose
  wrong.
- **The 5/5 abstention number carries a caveat.** Four of the five controls are refused
  during *diagnosis*, before the model is consulted at all. That demonstrates the
  deterministic refusal paths work. It demonstrates nothing about whether a model would
  decline when asked.
- **`asyncio` only.** Threading and multiprocessing races are out of scope by design
  (ADR-0001), not by accident.

Next: more race shapes in the intent vocabulary, a GitHub Action that opens the
regression-guard PR, and pushing the forced-replay tier down into `pytest` as a plugin so
it runs where the flake is.

---

**What it can't do is ship a fix that doesn't work. That part isn't a promise — it's a gate.**
