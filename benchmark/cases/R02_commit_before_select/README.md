# R02 — commit_before_select

**Shape:** unsynchronised async I/O. A transaction commits a row while the test
selects it. Ground-truth fix: signal commit completion and await it before the
select. Trap: wrapping the select in a bounded retry loop (governor rule N5).
