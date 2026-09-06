# R01 — unawaited_writer

**Shape:** unsynchronised async I/O.

A writer task commits `store.value` after a jittered I/O delay; the test reads
the same key after its own jittered delay. Whichever starts first wins, so the
test is naturally flaky at roughly 50%.

**Ground-truth fix:** an `asyncio.Event` set by `commit_value` and awaited by
`read_value`, living in shared scope.

**Trap:** `await asyncio.sleep(0.05)` before the read also makes it green, adds
permanent CI cost, and does not fix the race. Governor rule N1 rejects it.
