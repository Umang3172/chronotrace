# Security policy

## Reporting

Open a private security advisory on the repository. Please do not open a public
issue for a vulnerability.

## Threat model

ChronoTrace executes the test suite of the repository it is pointed at, in
subprocesses, repeatedly. Run it only against code you already trust enough to
run tests for.

Properties it maintains:

- **It does not write to your repository unless asked.** The default output is a
  diff and a report; `--apply` is opt-in.
- **It never modifies installed dependencies.** Governor rule S3 refuses any
  patch touching `site-packages` or a vendored path.
- **It does not modify application code without an explicit opt-in.** Rule S2
  requires `--allow-production-repair`, because a barrier injected into product
  code to make a test green can hide a real defect.
- **Every subprocess has a wall-clock timeout.** A timeout is treated as a
  deadlock signal and triggers rollback, so a hanging test cannot wedge a run.
- **No credentials are required for the default configuration.** The local
  provider makes no network calls.
