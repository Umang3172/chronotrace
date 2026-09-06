# N03 — dict_iteration_order (negative control)

Set iteration order depends on the hash seed. ChronoTrace pins `PYTHONHASHSEED` for every captured run, so the test is deterministic under capture and never yields a pass/fail pair. Expected: ABSTAINED / NO_TRACE_PAIR.
