# R03 — taskgroup_teardown

**Shape:** task lifecycle race. The task handle is awaited *after* the
assertion, so the side effect may not have happened yet. Two correct repairs
exist: synchronise on the write, or await the handle before asserting.
