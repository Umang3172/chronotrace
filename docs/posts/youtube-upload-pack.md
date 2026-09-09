# YouTube re-upload pack

**File**: `/Users/umangsingh/chronotrace-video/out/chronotrace-demo.mp4`
1920x1080 · 30fps · 8636 frames · **4:47.9** · 74.9 MB · h264/aac

I could not perform the upload: the browser automation's file-upload path caps at 10 MB
and this file is 74.9 MB. Everything below is ready to paste.

---

## Title

```
ChronoTrace — an AI agent that isn't allowed to cheat at fixing flaky tests
```

## Description

```
ChronoTrace is an autonomous agent that repairs concurrency-induced flaky tests in Python
asyncio code, and proves the repair worked — built on the AWS Strands Agents SDK and
Amazon Bedrock for the Agents for Humans Hackathon.

The problem: a test that passes on rerun without a code change. At Google, 84% of
post-submit CI failures are flaky tests rather than real bugs. Microsoft measured
flakiness costing $1.14M a year.

Most AI coding assistants "fix" these by inserting a sleep or a retry. The test goes
green, the race is still live, and CI is permanently slower. ChronoTrace cannot do that:

• A 15-rule deterministic AST governor rejects sleeps, aliased sleep imports, retry
  decorators, timeout inflation, weakened assertions and no-op patches — 17 adversarial
  attacks, 17 rejections, each by the rule that targets it.
• The model (Amazon Nova Pro / Nova Lite) emits a typed RepairIntent, never raw code.
• Forced replay gates coroutine entry to reproduce the exact failing interleaving, so
  "fixed the race" and "made it rarer" cannot be confused.

Act II is the part worth watching: our own agent proposes a patch that breaks no rule,
passes the policy gate 15/15 — and is still wrong. Forced replay catches it. A
rerun-based gate reads the same patch as a 75%-to-70% improvement and ships it.

Chapters
0:00 A failing test, 20 runs
0:18 What a flaky test actually is
0:58 What everyone else does about it
1:27 How ChronoTrace works
2:06 Act I — a race, repaired and proven
2:39 The governor gauntlet
3:06 Act II — a caught mistake
4:09 Results
4:35 What this is and isn't

Code: https://github.com/Umang3172/chronotrace
Live dashboard (AWS Amplify Hosting): https://main.d3k7wvrz5f9b6h.amplifyapp.com
Write-up: https://builder.aws.com/post/3J3xhnusTT8tD8z4ALJ2hiobWeJ_p/agents-for-humans-what-happens-when-an-ai-agent-isnt-allowed-to-cheat-fixing-flaky-tests

#AWS #AmazonBedrock #FlakyTests #Python #asyncio #AIagents
```

The chapter timestamps above are derived from the scene table in
`chronotrace-video/src/timing.ts` at 30fps. Check the first one lands right after upload;
YouTube needs 0:00 present and at least three chapters to render them.

## Thumbnail

`~/Desktop/ChronoTrace-Blog-Assets/00-thumbnail.jpg` (1376x768)

## Settings

- Not made for kids
- Category: Science & Technology
- Visibility: **Unlisted first.** A fresh 1080p upload serves 360p until HD processing
  finishes. Flip to Public once the quality selector offers 1080p.

---

## After the upload — five places carry the old video ID

The old URL is `https://youtu.be/xyjV-UmbvmA`. YouTube cannot replace a file in place, so
the new upload has a new ID and every one of these needs it:

| File | Line |
|---|---|
| `README.md` | 8 — badge link |
| `README.md` | 562 — thumbnail image URL **and** link (the ID appears twice) |
| `README.md` | 564 — "Watch the Full Demo (4:59)" — the runtime also changes to 4:47 |
| `HANDOVER.md` | 15 |
| Devpost | `software[video_url]` |

`grep -rn "xyjV-UmbvmA" .` finds them all.

Keep the old video unlisted rather than deleted until you have confirmed nothing still
points at it.
