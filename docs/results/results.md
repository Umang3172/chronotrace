## Results — deterministic layers only (no model)

Seeded benchmark, produced by `chronotrace eval`. N is small and the corpus is seeded rather than mined from the wild, so this is a controlled comparison between arms on identical inputs — a directional effect, not a population estimate.

| Metric | Arm C |
|---|---|
| Cases run | 14 |
| Repair rate on supported races | 100% (6/6) |
| **False-repair rate on controls** | 0% (0/5) |
| Abstention accuracy | 100% (8/8) |
| Causal precision | 80% (8/10) |
| **Band-aid injection rate** | 0% (0/6) |
| Ground-truth transformation match | 7/7 |
| Median measured overhead | 0.19 ms |
| Model calls | 42 |
| Tokens per successful repair | n/a |
| Wall clock | 240 s |
| Verification tiers reached | FORCED x6, NOT_REACHED x8 |

- **Arm C** — full ChronoTrace, provider `local`, which is the **reference
  policy**: a hand-written decision procedure, not a model. The repair rate
  above is therefore not a repair rate. See [README.md](README.md) in this
  directory before quoting anything here.
- Token and cost figures are reported only for providers that return usage. The local reference policy is not a model and has no tokens to report; inventing a number there would be a fabricated metric.
- Overhead is a measured median delta in test-call duration, natural runs before versus after the patch. ChronoTrace never claims zero added cost: a synchronization primitive changes scheduling even when it adds no fixed delay. The claim is *no fixed sleep-based delay introduced*, plus this number.
