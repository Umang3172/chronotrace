# AWS Builder Center — applied 2026-09-10

**Post**: <https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests>

**Status: live.** Verified by reading the published page back: video link present, dashboard
link present, AgentCore named, `100% accurate abstention` gone, corrected figure caption
present, all four body images intact, body 2,800 characters.

## What changed

| Change | Why |
|---|---|
| **Added the demo video link** | The post had no video at all. |
| **Added the live Amplify dashboard URL** | Clickable by a judge with no install and no credentials. |
| **Added "Deployed on AWS: dashboard on Amplify Hosting, agent entrypoint on Bedrock AgentCore Runtime."** | The post never said the project was actually deployed. |
| **"0 False Repairs: 100% accurate abstention on non-race controls" → "abstained on all 5 controls; 4 are refused before the model is called"** | Four of five controls are refused during *diagnosis*, before the model is consulted. The old wording claimed the stronger thing. |
| **Figure caption rewritten** | It read "Amazon Nova Lite synthesizing a repair verified by the 15/15 AST Governor." The still is `repair --demo-r14`: the governor *did* approve it 15/15 and forced replay then **rejected** it. Presenting it as a verified repair sold the one case we get wrong as a success. |
| **R14 bullet → the video's own numbers (75% → 70%)** | The post now links the video, so the figure a viewer sees should be the figure the post quotes. |
| **~260 characters trimmed across nine text nodes** | Required — see below. |

The figure itself was correct and stayed: `model=amazon.nova-lite-v1:0 schema=RepairIntent
seconds=2.8 tokens_in=3066 tokens_out=286`, `governor.verdict approved=True violations=[]`.

## The 3000-character limit counts more than the visible text

Worth recording, because the first attempt was rejected while the arithmetic said it fit.

- Body plain text: 2,438
- The four images serialise as MDX `<Image url="https://prod-assets.cosmic.aws.dev/..." />`
  tags totalling **548** characters — 108 for a bare one, 162–170 with alt text
- 2,438 + 548 = 2,986, under 3,000 — **and the editor still rejected it**

So the validator also counts markdown syntax: `**bold**` pairs, `### ` headings, `- ` and
`1. ` list markers, `---`, blank lines between 20 blocks, and links written as
`[url](url)` (~84 characters for 40 characters of visible text). Budget roughly **300–350
characters of hidden overhead** beyond text + image tags.

There is no body character counter in the UI. The `93/100 characters` counter belongs to a
different field. The only ground truth is whether the red *"Post content must be under 3000
characters"* element is present in the DOM.

## How to edit this post programmatically

The editor is **Lexical** (`data-lexical-editor="true"`, `data-testid="draft-content"`).

- **Direct DOM mutation does not work** — Lexical reconciles from its own state and discards it.
- **`document.execCommand('insertText')` after setting a DOM Range does not work either.** It
  returns `true` and changes nothing, because Lexical never registered the selection.
- **What works**: `editor.getEditorState().toJSON()` → mutate the JSON → `editor.parseEditorState(json)`
  → `editor.setEditorState(...)`. Images are `type: "jsx"` leaf nodes carrying an `mdastNode`;
  they round-trip intact. Verify with a parse-only round trip first (block count and `jsx`
  count in vs out) before applying, and stash the original JSON on `window` as a restore point.

This route also avoids the hazard that cost the previous session real content: the post's
`...` menu puts **Delete** 34px below **Edit**.

## The published text

Blocks 1, 6, 9 and 11 are images and are not reproduced here.

```
A CI build fails on Friday and turns green on rerun with no code change. At Google, 84% of post-submit CI failures are flaky tests. Microsoft measured the cost at $1.14M/year.

For the Agents for Humans Hackathon, we built ChronoTrace: an agent on the AWS Strands Agents SDK and Amazon Bedrock that finds causal races in runtime traces and leaves a deterministic regression test.

### The time.sleep(2) Trap

AI coding assistants cheat: they insert time.sleep(2) or a retry loop. The test passes, the race is still live, and CI is permanently slower.

A rerun gate cannot separate fixing a race from making it rarer. ChronoTrace cannot take the shortcut.

How It Works: Strands SDK + Amazon Bedrock

ChronoTrace separates probabilistic reasoning from deterministic execution:

1. Autonomous Strands Agent Loop: Using strands.Agent with 9 tools (capture_traces, trace_slice, compare_orderings, force_replay, check_patch).
2. Amazon Bedrock (Nova Pro & Nova Lite): Nova Pro reasons across coroutines, Nova Lite runs in 2.8s. The model emits a typed RepairIntent JSON schema, never raw code.
3. 15-Rule AST Governor: before any diff touches disk it rejects sleeps, aliased imports, retry decorators and weakened assertions.
4. Forced Replay: ChronoTrace gates coroutine entry to force the interleaving. Pre-patch fails 20/20; post-patch passes 20/20.

Deployed on AWS: dashboard on Amplify Hosting, agent entrypoint on Bedrock AgentCore Runtime.

Figure: Nova Lite returns a typed RepairIntent in 2.8s; the governor approves it 15/15. This is R14, the patch forced replay rejects.

### Benchmark Results

Amazon Nova Pro, 7 races and 5 non-race controls:

- 0 Band-Aids: 0 sleeps or retries across the 7 races (vs 6/7 unconstrained).
- 0 False Repairs: abstained on all 5 controls; 4 are refused before the model is called.
- The R14 Proof: our own agent's patch broke no rule and passed the gate 15/15. Forced replay failed it. A rerun gate read 75% to 70% and would have shipped it.

### Link : https://github.com/Umang3172/chronotrace

---

Demo (4:47): https://youtu.be/rkoeqMt3cDk | Dashboard: https://main.d3k7wvrz5f9b6h.amplifyapp.com | How does your team handle flaky tests? Worst story in the comments.
```
