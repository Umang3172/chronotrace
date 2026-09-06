# Recorded results

The output of `uv run chronotrace eval --arm C --cases all`, committed so the
numbers in the project README can be checked without re-running the benchmark.

Regenerate with the same command. Two things will differ between runs and both
are expected:

- **Measured overhead** moves by a couple of tenths of a millisecond and can
  come out negative. It is a sub-millisecond quantity measured across process
  boundaries; read it as "too small to separate from noise at this sample size",
  which is why the README says exactly that rather than quoting it as a
  constant.
- **Natural flake rates** vary run to run, because the seeded races are genuinely
  nondeterministic. That is the point of them.

The categorical results — repair rate, false-repair rate, abstention accuracy,
band-aid rate, and which verification tier each case reached — have been stable
across runs.
