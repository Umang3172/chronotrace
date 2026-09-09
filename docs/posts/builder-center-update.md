# AWS Builder Center — pending update

**Post**: <https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests>

**Status: not applied.** The Chrome profile the automation is attached to is signed out of
Builder Center, and signing in requires credentials I will not enter. Sign in as
`connect2tanmayy@gmail.com`, open the post's edit view, and replace the body with the text
below — then this file can be deleted.

## What changes and why

| Change | Reason |
|---|---|
| **Add the demo video link** | The post has no video at all. It is the single most valuable thing missing. |
| **Add the live Amplify dashboard URL** | Judges can click it with no install and no credentials. |
| **Add one line naming Amplify Hosting and Bedrock AgentCore Runtime** | The post never says the project is actually deployed on AWS. |
| **Correct "0 False Repairs: 100% accurate abstention"** | Four of the five controls are refused during *diagnosis*, before the model is consulted. `README.md` states this caveat; the post claimed the stronger version. |
| **Correct the figure caption** | It reads "Amazon Nova Lite synthesizing a repair verified by the 15/15 AST Governor." The still is `repair --demo-r14` — the governor *did* approve it 15/15, and forced replay then **rejected** it. Calling it "a repair" in the How-It-Works section sells the one case we get wrong as a success. |
| **Trim four sentences** | The post sits at the 3000-character ceiling and Update is validation-blocked above it. |

The figure itself is correct and stays: `model=amazon.nova-lite-v1:0 schema=RepairIntent
seconds=2.8 tokens_in=3066 tokens_out=286`, `governor.verdict approved=True violations=[]`.
Verified against `~/Desktop/ChronoTrace-Blog-Assets/04-nova-governor-clean.png` on 2026-09-10.

## Character budget

Body below is **2,429 characters** (2,417 without the bold markers, which the editor supplies as formatting rather than text). The ceiling is 3,000 *including image markdown*, which
measured ~490 on the live post, leaving ~2,510. Headroom ~80. Keep both existing images and
their short alt texts; adding a third image will not fit.

## Replacement body — paste verbatim

Keep the two images where they already sit (hero after the intro, Nova/governor still after
the Forced Replay bullet). Headings stay headings.

---

A CI build fails on Friday and turns green on rerun with no code change. At Google, 84% of post-submit CI failures are caused by flaky tests. Microsoft measured flakiness costing $1.14M/year.

For the Agents for Humans Hackathon, we built ChronoTrace: an autonomous agent using the AWS Strands Agents SDK and Amazon Bedrock that isolates causal race conditions from runtime traces and leaves behind a deterministic regression test.

**The time.sleep(2) Trap**

Standard AI coding assistants cheat: they insert time.sleep(2) or a retry loop. The test passes, the race is still live, and CI is permanently slower.

Worse, a rerun gate cannot separate fixing a race from making it rarer. ChronoTrace is structurally prevented from taking shortcuts.

**How It Works: Strands SDK + Amazon Bedrock**

ChronoTrace separates probabilistic reasoning from deterministic execution:

Autonomous Strands Agent Loop: strands.Agent with 9 tools - capture_traces, trace_slice, compare_orderings, force_replay, check_patch.

Amazon Bedrock (Nova Pro & Nova Lite): Nova Pro handles cross-coroutine reasoning, while Nova Lite provides sub-2.8s turnaround. The model emits a structured RepairIntent JSON schema, never raw code.

15-Rule AST Governor: Before diffs touch disk, our policy gate rejects sleeps, aliased imports, retry decorators, and weakened assertions.

Forced Replay: Rather than rerunning, ChronoTrace gates coroutine entry to force candidate interleavings. Pre-patch fails 20/20; post-patch passes 20/20.

Deployed on AWS: the dashboard runs on Amplify Hosting, the agent entrypoint on Bedrock AgentCore Runtime.

Figure: Nova Lite returns a typed RepairIntent in 2.8s and the governor approves it 15/15. This is R14 - the patch forced replay then rejects.

**Benchmark Results**

Tested on Amazon Nova Pro across 7 races and 5 non-race controls:

0 Band-Aids: 0 sleeps or retries across the 7 races (vs 6/7 in unconstrained LLMs).

0 False Repairs: abstained on all 5 controls, though 4 are refused before the model is called.

The R14 Proof: our own agent's patch broke no rule and passed the gate 15/15. Forced replay failed it. A rerun gate read 75% to 70% and would have shipped it.

Watch the 4:47 demo: https://youtu.be/rkoeqMt3cDk

Live dashboard: https://main.d3k7wvrz5f9b6h.amplifyapp.com

Code: https://github.com/Umang3172/chronotrace

How does your team handle flaky tests in CI? Worst flakiness story in the comments.

---

## Editing hazards, learned the hard way on this editor

- **`shift+End` selects to the end of the document, not the end of the line.** It deleted
  three bullets, the Link line and the CTA in one keystroke. Select a block by triple-clicking
  it, or double-click the first word and shift-click the last.
- **Clicking past the end of a heading snaps the caret into the block below** and splits it.
  Click *inside* the text you mean to edit.
- Toolbar undo works and recovers both of the above, but it over-undoes: it will walk back
  past image replacements too.
