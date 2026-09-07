# Filming checklist

Repo: `/Users/umangsingh/Chronotrace`
Model: `qwen2.5-coder:14b` via Ollama. Every clip needs it running.

**Two terminals.** Terminal A runs the dashboard server and stays open all
session. Terminal B is the one on camera.

**Do not `export CHRONOTRACE_PROVIDER` in the camera terminal.** Without it the
demos auto-detect and print `using provider 'ollama' — found qwen2.5-coder:14b`,
which is the on-camera evidence that a real model is in the loop. Setup needs it;
the clips must not have it.

---

## Setup — run once, off camera

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
uv sync
ollama pull qwen2.5-coder:14b
```

Dashboard deps (skip if `ui/node_modules` exists — 2s when it does):

```bash
cd ui && npm install && cd ..
```

Generate the dashboard data. **`CHRONOTRACE_PROVIDER=ollama` is required here** —
`eval` does not auto-detect, and without it the run uses the hand-written
reference policy and writes a policy fixture you would then have to delete.

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
export CHRONOTRACE_PROVIDER=ollama
rm -rf eval-results .chronotrace
chronotrace eval --arm C --cases R01,R12,R14,N07 --runs 18 --out eval-results
```

**~4 min.** Ends with a results table and `written: eval-results/results.md`.
Produces 4 incidents covering all three UI states.

Then close this terminal, or `unset CHRONOTRACE_PROVIDER` before filming.

### Answers to the two questions

1. **Yes — bare `chronotrace` works** after `source .venv/bin/activate`.
   `which chronotrace` → `/Users/umangsingh/Chronotrace/.venv/bin/chronotrace`.
   Use the short form on camera. Only re-run `uv sync` if you change the code.
2. **Non-determinism, by clip:**

| Clip | Varies between takes |
|---|---|
| 1 | Every number. That is the point of the shot. |
| 2 | Nothing, unless you re-run Setup — incident IDs change if you do. |
| 3 | Flake %, incident id, overhead ms, the model's rationale wording. `FIXED`, `15/15`, `FORCED_HARMLESS` have been stable in every run. |
| 4 | **Nothing. Byte-identical across runs** (verified by diff). |
| 5 | The act-5 residual line takes one of two forms — see the clip. `INJECT_ASYNC_EVENT`, `approved: True`, `FAILED` stable. |

---

## Terminal A — dashboard server (start before Clip 2, leave running)

```bash
cd /Users/umangsingh/Chronotrace/ui
npm run dev
```

**~2s.** Wait for `Ready in ...ms`. Leave it running. Not on camera.

---

## Clip 1 — the test fails intermittently

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
pytest benchmark/cases/R01_unawaited_writer -q --count 20
```

**~1s.** Good take: a mixed line, e.g. `7 failed, 13 passed in 0.19s`.
Re-shoot if it comes out all-passed or all-failed.

Per-run sequence instead of a summary, if you prefer the PASS/FAIL rhythm:

```bash
for i in $(seq 1 8); do pytest benchmark/cases/R01_unawaited_writer -q 2>/dev/null | tail -1 | cut -d' ' -f1-2; done
```

**~4s.** Prints eight lines of `1 passed` / `1 failed`.

---

## Clip 2 — the dashboard

Terminal A must be running. Get the URL to open:

```bash
cd /Users/umangsingh/Chronotrace
python3 -c "import json;[print('http://localhost:3939/incident/'+i['incident_id'],i['test_id'].split('/')[2]) for i in json.load(open('eval-results/incidents.json'))]"
```

Open `http://localhost:3939` — the incident list, four rows, three state badges.
Then click through to the **R01** incident (the one showing `Fixed`).

Good take: verdict banner `Fixed` + `Reproduced on demand`, then the five
sections — divergence lanes, evidence, policy gate 15/15, verification, diff.

**Do not film `/eval` with this setup.** With only 4 cases it renders
"Repaired and verified 50%", a headline repair rate the README deliberately
refuses to quote.

---

## Clip 3 — R01 repaired and verified

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
chronotrace repair --demo --slow
```

**~95s** (80s without `--slow`). Most of it is the model call and ~50 test runs.

Good take, in order:

```
using provider 'ollama' — found qwen2.5-coder:14b on the local Ollama server
demo case: R01 unawaited_writer (unsynchronised async I/O)
FIXED  (<id>)
governor: 15/15 rules passed
tier    : FORCED_HARMLESS
proof   : forced ordering failed before the patch and passed after it
residual: 20/20 stable, overhead +0.2 ms
guard   : ...::test_chronotrace_regression_<id>
```

then the diff. Re-shoot if the verdict is not `FIXED`.

---

## Clip 4 — the governor gauntlet

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
chronotrace gauntlet
```

**<1s.** Good take: 17 `REJECTED` lines, ending
`17/17 attacks rejected by the rule that targets them`.
Deterministic — one take is enough.

---

## Clip 5 — R14, the self-rejection

```bash
cd /Users/umangsingh/Chronotrace
source .venv/bin/activate
chronotrace repair --demo-r14 --slow
```

**~115s.** Five numbered acts. Good take:

```
2. What the model proposed      transformation : INJECT_ASYNC_EVENT
3. What the policy gate said    15/15 rules passed — approved: True
4. What forced replay said      tier reached : FAILED   repaired : False
```

**Act 5 prints one of two endings, depending on the run.** Both are true and
both make the point; decide which you want before filming.

- Favourable: `flake rate 80% before, 45% with this patch — a rerun-based gate
  would accept this.`
- Otherwise: `... on this run it did not even get rarer`, followed by the note
  that the same patch has measured 45% against 80% on other runs, so a
  rerun-based gate is noisy enough to accept or reject the same wrong patch
  depending on the day.

In this session the favourable branch came up **once in four runs**. If you want
that line, budget several takes. The second ending is arguably the stronger
argument and needs no re-shoots.

---

## Reset between takes

Nothing is left in the working tree — the benchmark files are patched only
inside verification and restored afterwards (`git status` stays clean, verified
after every demo run). Only two things accumulate:

```bash
cd /Users/umangsingh/Chronotrace
rm -rf .chronotrace          # incident records; each demo run appends one
rm -f fixtures/*.json        # only if you ran a command without the provider set
git status --porcelain       # must print nothing
```

**~instant.** Clips 3, 4 and 5 do not touch `eval-results/`, so re-shooting them
never changes the dashboard. Re-running **Setup** does — it assigns new incident
IDs, so redo Clip 2's URL lookup if you do.

`rm -f fixtures/*.json` matters because a `chronotrace` command run without
`CHRONOTRACE_PROVIDER=ollama` falls back to the reference policy and writes a
`provider: "reference-policy"` fixture there. Those were deleted deliberately;
do not let one back in.

---

## Teardown

```bash
pkill -f "next dev"
ollama stop qwen2.5-coder:14b
```

**~2s.** `curl -s -o /dev/null http://localhost:3939` should now fail, and
`curl -s http://localhost:11434/api/ps` should show `{"models":[]}`.
