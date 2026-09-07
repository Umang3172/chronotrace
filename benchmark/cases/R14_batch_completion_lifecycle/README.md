# R14 — batch_completion_lifecycle

**Shape:** task lifecycle race — deliberately *not* the read-after-write shape
that R01–R06 all share.

A worker publishes three items, each after its own round trip. The test reads
the batch after a single delay and asserts all three are present.

**Ground-truth fix:** `AWAIT_UNFINISHED_TASK` — await the `handle` the test
already holds, before the assertion instead of after it.

**Why an event is the wrong answer here.** `INJECT_ASYNC_EVENT` would have
`record_item` signal and `read_batch` wait. `record_item` signals on the *first*
item, so the reader wakes and observes `["alpha"]`. The test still fails. This
is checkable, not merely arguable: that patch fails forced-replay verification.

**Trap:** the operations still look like a read-after-write on a shared
resource, which is exactly the condition that selects `INJECT_ASYNC_EVENT`. A
system that pattern-matches on shape rather than reasoning about what the
assertion depends on will get this wrong.
