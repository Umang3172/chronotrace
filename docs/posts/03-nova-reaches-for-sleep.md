# Amazon Nova Pro reached for `sleep()` on six races out of six

*Third in a series on building ChronoTrace, an agent that repairs
concurrency-induced flaky tests, for the Agents for Humans hackathon.*

I expected the bigger model to behave better. On the measurement that matters
most to this project, it behaved worse — and that is the most useful result I
have.

## What is being measured

A flaky test that fails because two coroutines can interleave two ways has one
honest repair and one dishonest one. The honest repair establishes the ordering:
a real synchronization primitive, so the reader waits for the write it depends
on. The dishonest repair is `await asyncio.sleep(0.1)`, which makes the test
green, leaves the race exactly where it was, and bills your CI for the delay on
every run, forever.

Both turn the build green. Only one fixes anything. So the question is not
"can a model repair a flaky test" — it is **what does a model reach for when
nobody is stopping it.**

ChronoTrace answers that with three arms over the same twelve seeded cases:

* **Arm A** — the model gets the test and the failure. Nothing else.
* **Arm B** — the same, plus a diff of the passing and failing execution traces
  and a ranked list of the orderings that differ.
* **Arm C** — full ChronoTrace: the model emits a *typed intent* rather than
  source, deterministic code applies it, a 15-rule AST policy gate can reject
  it, and forced replay decides whether it actually worked.

Capture and diagnosis are deterministic and involve no model at all, so I
recorded them once and replayed them into every arm and both models. Only the
model differs. That is what makes the columns comparable.

## The numbers

`amazon.nova-pro-v1:0` on Bedrock, against `qwen2.5-coder:14b` (Q4_K_M) locally.
Six read-after-write races:

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Repaired and verified — **Nova Pro** | 1 / 6 | 3 / 6 | **6 / 6** |
| Repaired and verified — qwen2.5-coder | 4 / 6 | 4 / 6 | **6 / 6** |
| **Band-aids injected — Nova Pro** | **6 / 6** | 3 / 6 | **0 / 6** |
| **Band-aids injected — qwen2.5-coder** | 3 / 6 | 3 / 6 | **0 / 6** |

Given the test and the failure and nothing else, Nova Pro added a timing delay
to **every single race**. On one of them it added a sleep *and* a retry loop
around the assertion. The 14-billion-parameter local model did it half as often.

And on five tests that are flaky for reasons that have nothing to do with
concurrency — a seeded RNG, a network timeout, dict iteration order — the
unconstrained arms "repaired" **5 of 5** under Nova Pro, against 4 of 5 for
qwen. It confidently modified code that had no race in it at all.

I want to be careful about what this does and does not say. It is not "Nova Pro
is a worse model." It is better than qwen at nearly everything else I threw at
it, including choosing the right repair pattern when it was asked for one. What
it says is narrower and, I think, more interesting:

> A more capable model asked to make a failing test pass will produce a more
> confident, more fluent, more plausible-looking wrong answer. Capability is not
> alignment with the thing you actually wanted.

The interesting middle column is Arm B. Just handing over the trace diff — no
gate, no rules, no instructions about sleeps — halved Nova Pro's band-aid rate
on its own. Give a model better evidence and it makes a better choice, without
being told to. It just does not make a *reliable* one, which is what Arm C is
for.

## The result that argues against my own system

One case in the corpus, R14, is a different shape of race: the assertion depends
on a background task *completing*, not on a single write landing. It is the only
case of that shape, and I added it specifically to test generalisation.

| | Arm A | Arm B | Arm C |
|---|---|---|---|
| Repaired, verified | **yes** | **yes** | **no** |
| Verification tier | `FORCED_UNREACHABLE` | `FORCED_UNREACHABLE` | `FAILED` |

**The unconstrained baselines got it right and ChronoTrace got it wrong.** Both
wrote `await handle`, with a comment saying why. ChronoTrace's arm chose to
inject an event — which wakes the reader after the *first* item, not after the
task finishes — and forced replay rejected it.

That happened identically on both models. A hosted frontier model and a 14B
local one made the same wrong call, for the same reason: the case looks, at the
surface, exactly like the six that came before it, and the intent prompt names
that shape explicitly. Neither model reasoned about what the assertion actually
depended on.

Two models failing the same way is not noise. It says the prompt taught a
pattern rather than a principle, and that is a limitation of my system, not of
theirs.

## Why this is the argument for verification

Here is the part I would not have believed without measuring it. That rejected
R14 patch took the flake rate from **80% to 45%**.

Every rerun-based verification gate on the market accepts that. The test used to
fail most of the time and now fails less than half. Datadog's attempt-to-fix
flow retries a candidate 20 times; BuildPulse confirms through PR checks.
Neither can separate *fixed the race* from *made it rarer*, because in a pass
count those are the same event.

Worse, the residual is noisy. Across runs the same wrong patch measured anywhere
from 45% to 75% against a pre-patch rate of 70–80%. Sometimes it reads as a fix.
Sometimes it reads as a regression.

Forcing the ordering returns the same verdict every time, because it is an
experiment with a control rather than a sample: the ordering failed before the
patch and still fails after it, with the harness unchanged between the two. My
own agent's judgement was wrong, my own policy gate passed it 15 out of 15, and
the layer that caught it was the one that does not ask anybody's opinion.

## What Bedrock and Strands did for this

Three things mattered, none of them glamorous.

**One model id changed the whole experiment.** The provider is one environment
variable, so the local build and the Bedrock build are the same code path. Going
from "a Bedrock run is planned" to real numbers took adding a `propose_patch`
method — the unconstrained baseline channel — and one CLI flag.

**Bedrock's `converse` tool schema is the constraint mechanism.** ChronoTrace's
core rule is that the model emits a typed `RepairIntent` and never source code,
because source cannot be checked the way a typed intent can. `toolChoice` with a
Pydantic-generated JSON schema enforces that at the API boundary rather than by
asking nicely in a prompt.

**The Strands loop is where deciding happens.** Ranking a candidate ordering is
correlation. Forcing it is causation. The agent calls `force_replay` itself,
reads the failure rate, and decides — a rate of 1.0 means sufficient, 0.0 means
noise, anything in between means the bug needs more than one constraint and it
should stop. That is a decision made from evidence it chose to gather, which is
the only part of this system where the word "agent" is doing real work.

**Cost, for the record:** the entire three-arm sweep across both models, plus
every exploratory run, came to well under a dollar of Bedrock spend. Nova Pro
answered a typed-intent call in about 3 seconds at ~3,400 input tokens. The
constraint on this project was never the credits.

## The honest summary

* Constraint prevents harm, and the effect is **larger** on the better model:
  0 band-aids against 6/6, 0 false repairs against 5/5.
* Verification catches wrong repairs, **including mine**.
* Constraint does not confer judgement. On a race shape the prompt did not name,
  both models chose wrong, and the unconstrained baselines happened to choose
  right.

I do not quote a headline repair rate anywhere, because six of my seven
repairable cases share one race shape and the intent prompt names that shape. A
percentage would look like a claim about flaky tests in general, and what I have
is a claim about six tests of one kind.

The thing I would defend is smaller and holds on every run and both models: a
system that is structurally unable to reach for `sleep()` does not reach for it,
and a system that proves causality by forcing an interleaving will tell you when
its own answer is wrong.

---

ChronoTrace is MIT-licensed, and every number here is produced by
`chronotrace three-arm` rather than typed by hand:
<https://github.com/Umang3172/chronotrace>
