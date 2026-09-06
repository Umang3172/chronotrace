# R04 — fixture_dirty_read

**Shape:** shared mutable fixture. A background refresher mutates the session
the test reads. Ground-truth fix: synchronise the read against the refresh.
