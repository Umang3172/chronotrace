# MASTER_DOC.md — changes-only brief

**Audience: an LLM already holding `MASTER_DOC.md`.** This file lists only what changed
after that document was generated. If your copy disagrees with anything below, **this file
wins** — it is the later record.

**Your copy was generated at commit `0df3b49`, 34 commits.**
**Current state: `bc753f0`, 37 commits, `main`, synced with `origin/main`.**

---

## 0. Machine-readable delta

```yaml
generated_at:   {commit: 0df3b49, commits: 34}
current:        {commit: bc753f0, commits: 37, branch: main, synced: true}
new_commits:    [5018b00, a10b391, bc753f0]
ci:             {status: GREEN, run: 34448606734, all_six_check_steps: passed}
devpost:        {status: SUBMITTED, steps: "5/5", date: 2026-09-10, editable_until_deadline: true}
builder_center: {status: LIVE, corrected: 2026-09-10, body_chars: 2800}
youtube:        {id: rkoeqMt3cDk, duration_s: 287.941, unchanged: true}
unchanged:      [benchmark_numbers, three_arm_results, governor_rules, architecture,
                 verification_ladder, adrs, limitations, cli_reference]
```

**Nothing about the project's substance changed.** No result, no benchmark number, no
architectural claim, no ADR, no limitation was revised. Every delta below is repo hygiene,
submission status, or a correction to a claim `MASTER_DOC.md` itself made about its own
freshness. If you are answering questions about what ChronoTrace *is* or *measured*, your
copy is still correct.

---

## 1. Claims in your copy that are now FALSE

| Your copy says | Correct as of `bc753f0` |
|---|---|
| `⚠️ CURRENT KNOWN ISSUE: the CI Format check step would be red on scripts/verify_deploy.py` | **Resolved in `a10b391`.** CI is green. |
| `ruff format: ⚠️ 1 file would be reformatted (scripts/verify_deploy.py:88), 105 already formatted` | **106 files already formatted, 0 to reformat.** |
| `Devpost: DRAFT, 3/5 steps, NOT submitted` (or `4/5`) | **SUBMITTED, 5/5 steps**, 2026-09-10. |
| `HEAD 0df3b49, 34 commits` | **HEAD `bc753f0`, 37 commits.** |
| Action item: `uv run ruff format scripts/verify_deploy.py` to green CI | **Already done.** No action outstanding. |

Everything else in your copy still holds, including the figures it is most likely to be
asked about: **199 tests passing**, **mypy strict clean over 74 files**, **17/17 governor
attacks rejected**, **15 cases in `benchmark/cases/` of which 12 form the three-arm corpus
(7 races + 5 controls)**, and the Nova Pro three-arm table.

---

## 2. The three new commits

| Commit | What it did |
|---|---|
| `5018b00` | Recorded that the AWS Builder Center post was corrected and republished, and that Devpost had reached 4/5. |
| `a10b391` | `ruff format` on `scripts/verify_deploy.py`. One-line reflow, no behaviour change. This is what turned CI green. |
| `bc753f0` | Replaced the pre-commit hooks with ones that match CI, and committed `MASTER_DOC.md` itself. |

---

## 3. CI was red for eight consecutive runs, and is now green

Your copy correctly flagged the `verify_deploy.py` formatting issue but understated the
consequence.

- The `Format check` step failed on **every run since `0b372a1` (2026-09-08)** — eight in a
  row, on different files each time (earlier: `chronotrace/cli.py`, `conftest.py`,
  `scripts/render_architecture.py`).
- **A GitHub Actions job stops at the first failing step.** So `Type check`, `Unit and
  property tests`, `Adversarial governor gauntlet` and `Public API imports cleanly` had not
  actually executed on CI for two days. Their passing status was inferred, not observed.
- Since `a10b391`, all six steps run and pass. Latest: run `34448606734` on `bc753f0`,
  ✓ check 37s, ✓ benchmark 2m32s.

---

## 4. The pre-commit hooks were misconfigured (new, not in your copy)

`.pre-commit-config.yaml` was rewritten in `bc753f0`. Three independent problems, all the
same root cause: **a pinned, isolated copy of a tool drifting from the one the project runs.**

| Hook | Pinned copy reported | Project toolchain reports |
|---|---|---|
| `ruff` (`rev: v0.6.9` → ruff 0.6.9) | 121 errors, **all `ANN101`** | `Rule ANN101 was removed and cannot be selected` (ruff **0.16.6**) |
| `mypy` (`mirrors-mypy`) | 34 errors — untyped decorators, `CSTTransformer` as `Any` | `Success: no issues found in 62 source files` |

The mypy hook's isolated env was missing **`typer`** and **`libcst`**. `pyproject` selects
`"ANN"` wholesale, so ruff 0.6.9 flagged every `self`. Combined, **155 phantom errors that
CI never sees would have blocked every commit.** Both are now `repo: local` hooks invoking
`uv run ruff …` / `uv run mypy chronotrace`, so they cannot drift from the CI steps again.

`trailing-whitespace` and `end-of-file-fixer` were **contained rather than replaced**. Run
across the tree they rewrote 139 files, including:

- `fixtures/` — committed deliberately per `.gitignore` so published numbers can be replayed
- `eval/results/`, `docs/results/` — recorded evidence
- `ui/out/` — the built Amplify export, whose chunk filenames are **content hashes**
- `README.md` — stripped the two trailing spaces that form a **Markdown hard line break**

That sweep was reverted in full. `trailing-whitespace` now carries
`--markdown-linebreak-ext=md`, both hooks exclude the generated/evidence paths, and
`check-added-large-files` uses `--maxkb=1000` (the README stills reach ~875 KB).

---

## 5. `pyproject.toml`

`[tool.ruff] extend-exclude` gained `"MASTER_DOC.md"`, joining `benchmark/cases`, `demo`,
`docs/posts`. Reason: **ruff 0.16.6 formats Python blocks inside Markdown**, so it would
rewrite the deliberately-wrong example snippets the document explains — and would fail
`ruff format --check .` in CI. Verified on the runner: `106 files already formatted`.

---

## 6. Submission surfaces

- **Devpost — SUBMITTED**, 5/5 steps, 2026-09-10. Verified on the manage page (`SUBMITTED`,
  not draft). Devpost permits editing after submission until the deadline.
- **AWS Builder Center — live and corrected.** Two of six changes were *corrections*, not
  additions: `"0 False Repairs: 100% accurate abstention on non-race controls"` became
  `"abstained on all 5 controls; 4 are refused before the model is called"` (four of five
  controls are refused during diagnosis, before the model is consulted); and a figure
  caption that described the **R14** patch — the one forced replay *rejects* — as "a repair
  verified by the 15/15 AST Governor". Also added: the video link, the Amplify dashboard
  URL, and a line naming Amplify Hosting and Bedrock AgentCore Runtime.
- **YouTube — unchanged**: `rkoeqMt3cDk`, 287.941 s confirmed on the live player.
