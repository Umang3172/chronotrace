"""CLI behaviour. This is the documented interface, so it gets tested like one.

These assert what a user sees — exit codes, refusals, the words in the output —
not which functions were called to produce it.
"""

import json

from typer.testing import CliRunner

from chronotrace.cli import app
from chronotrace.contracts import (
    Diagnosis,
    GovernorVerdict,
    IncidentReport,
    RuleOutcome,
    VerificationResult,
)
from chronotrace.registry.store import IncidentStore

runner = CliRunner()


def _seed_store(tmp_path, monkeypatch, report):
    """Point the CLI's working directory at a temporary store holding ``report``."""
    monkeypatch.chdir(tmp_path)
    store = IncidentStore(tmp_path / ".chronotrace" / "incidents.sqlite3")
    store.save(report)
    return store


def _verified_report(incident_id="abc12345"):
    return IncidentReport(
        incident_id=incident_id,
        test_id="tests/test_x.py::test_y",
        ui_state="FIXED",
        diagnosis=Diagnosis(status="RACE_PROVEN", explanation="proven by forcing"),
        verdict=GovernorVerdict(
            approved=True,
            positive_check_passed=True,
            rules_evaluated=[RuleOutcome(rule_id="N1", description="no sleeps", passed=True)],
        ),
        verification=VerificationResult(
            tier_reached="FORCED_HARMLESS",
            pre_patch_forced_failed=True,
            post_patch_forced_passed=True,
            statistical_runs=20,
            statistical_failures=0,
            measured_overhead_ms=0.4,
            reproduction_seed={"random_seed_base": "1729"},
        ),
    )


def test_gauntlet_rejects_every_attack_and_exits_zero():
    """The demo asset is also the regression test for the gate."""
    result = runner.invoke(app, ["gauntlet"])
    assert result.exit_code == 0
    assert "17/17 attacks rejected" in result.stdout
    assert "ESCAPED" not in result.stdout


def test_gauntlet_reports_the_rule_that_caught_each_attack():
    result = runner.invoke(app, ["gauntlet"])
    for rule in ("N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8", "P1", "P2", "P3", "S1", "S3"):
        assert f"REJECTED  {rule:<3}" in result.stdout


def test_report_prints_a_stored_incident_as_json(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, _verified_report())
    result = runner.invoke(app, ["report", "abc12345"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ui_state"] == "FIXED"


def test_report_fails_loudly_on_an_unknown_incident(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, _verified_report())
    result = runner.invoke(app, ["report", "nosuchid"])
    assert result.exit_code == 1
    assert "unknown incident" in result.output


def test_verify_states_the_tier_actually_reached(tmp_path, monkeypatch):
    _seed_store(tmp_path, monkeypatch, _verified_report())
    result = runner.invoke(app, ["verify", "abc12345"])
    assert result.exit_code == 0
    assert "tier reached : FORCED" in result.stdout
    assert "residual flake check     : 20/20" in result.stdout


def test_verify_refuses_to_dress_a_lower_tier_as_the_requested_one(tmp_path, monkeypatch):
    """Asking for FORCED must not make a STATISTICAL result read as proof."""
    report = _verified_report("stat0001")
    report.verification.tier_reached = "STATISTICAL"
    _seed_store(tmp_path, monkeypatch, report)
    result = runner.invoke(app, ["verify", "stat0001", "--tier", "forced"])
    assert "tier reached : STATISTICAL" in result.stdout
    assert "never presented as causal proof" in result.stdout


def test_verify_fails_when_nothing_was_verified(tmp_path, monkeypatch):
    report = _verified_report("noverif1")
    report.verification = None
    _seed_store(tmp_path, monkeypatch, report)
    result = runner.invoke(app, ["verify", "noverif1"])
    assert result.exit_code == 1
    assert "no verification recorded" in result.output


def test_eval_refuses_an_unknown_case_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["eval", "--cases", "R99"])
    assert result.exit_code == 1
    assert "no matching benchmark cases" in result.output


def test_demo_refuses_the_reference_policy_and_says_how_to_fix_it(tmp_path, monkeypatch):
    """A demo driven by the hand-written policy shows this repo's own decision,
    not a model's. It must refuse — but a bare refusal is the worst thing a
    reviewer following the README can hit, so it has to carry the fix."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CHRONOTRACE_PROVIDER", raising=False)
    # No model provider reachable anywhere.
    monkeypatch.setenv("CHRONOTRACE_OLLAMA_HOST", "http://127.0.0.1:1")
    monkeypatch.setenv("CHRONOTRACE_MODEL_ID_LARGE", "")
    result = runner.invoke(app, ["repair", "--demo"])
    assert result.exit_code == 2
    assert "needs a language model" in result.output
    assert "not a model" in result.output
    assert "ollama pull" in result.output, "the refusal must name the command that fixes it"


def test_demo_uses_a_detected_provider_rather_than_refusing(tmp_path, monkeypatch):
    """When a real model is available, the demo proceeds on it."""
    from chronotrace.providers import detect as detect_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CHRONOTRACE_PROVIDER", raising=False)
    monkeypatch.setattr(detect_mod, "ollama_models", lambda host: ["qwen2.5-coder:14b", "other:7b"])
    result = runner.invoke(app, ["repair", "--demo"])
    # It gets past the refusal and fails later, on the empty corpus.
    assert result.exit_code == 1
    assert "using provider 'ollama'" in result.output
    assert "no benchmark cases found" in result.output


def test_repair_reports_when_no_benchmark_corpus_is_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CHRONOTRACE_PROVIDER", "ollama")
    result = runner.invoke(app, ["repair", "--demo"])
    assert result.exit_code == 1
    assert "no benchmark cases found" in result.output


def test_help_lists_the_documented_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("capture", "diagnose", "repair", "verify", "report", "gauntlet", "eval"):
        assert command in result.stdout


def _rejection_report(*, before: int, after: int):
    """An R14-shaped report: policy-clean patch, rejected by forced replay."""
    from chronotrace.contracts import IntentAttempt, RepairIntent

    report = _verified_report("r14demo")
    report.ui_state = "NEEDS_INVESTIGATION"
    report.natural_flake_rate = 0.8
    report.intent = RepairIntent(
        transformation="INJECT_ASYNC_EVENT",
        shared_scope="FIXTURE",
        primitive="asyncio.Event",
        signal_site=_ref(),
        wait_site=_ref(),
        rationale="looks like a read-after-write",
    )
    report.intent_attempts = [IntentAttempt(attempt=1, accepted=True)]
    report.verification.tier_reached = "FAILED"
    report.verification.post_patch_forced_passed = False
    report.verification.statistical_runs = 20
    report.verification.statistical_failures = after
    report.verification.pre_patch_natural_failures = before
    return report


def _ref():
    from chronotrace.contracts import OperationRef

    return OperationRef(
        span_name="op",
        occurrence=0,
        source_file="a.py",
        source_line=1,
        qualname="op",
        is_test_scope=True,
    )


def test_rejection_demo_claims_a_rerun_gate_would_accept_only_when_it_would(capsys):
    """The sentence has to follow the measurement, not the script."""
    from chronotrace.cli import _print_rejection_demo

    _print_rejection_demo(_rejection_report(before=16, after=9))
    improved = capsys.readouterr().out
    assert "a rerun-based gate would accept this" in improved
    assert "80% before, 45% with this patch" in improved


def test_rejection_demo_does_not_claim_improvement_that_did_not_happen(capsys):
    from chronotrace.cli import _print_rejection_demo

    _print_rejection_demo(_rejection_report(before=14, after=15))
    worse = capsys.readouterr().out
    assert "a rerun-based gate would accept this" not in worse
    assert "did not even get rarer" in worse


def test_rejection_demo_shows_the_gate_passing_and_replay_refusing(capsys):
    from chronotrace.cli import _print_rejection_demo

    _print_rejection_demo(_rejection_report(before=16, after=9))
    out = capsys.readouterr().out
    assert "INJECT_ASYNC_EVENT" in out
    assert "approved: True" in out
    assert "tier reached : FAILED" in out
    assert "judgement, not policy" in out


def test_flake_check_default_runs_and_reports_seeded(monkeypatch):
    """chronotrace flake-check defaults to R01, marks seeded, and reports flake rate."""
    result = runner.invoke(app, ["flake-check", "-n", "3", "--interval", "0"])
    assert result.exit_code == 0
    assert "test_reader_sees_committed_value" in result.stdout
    assert "3 runs" in result.stdout
    assert "commit " in result.stdout
    assert "seeded" in result.stdout
    assert "failed ·" in result.stdout
    assert "passed" in result.stdout
    assert "flake rate " in result.stdout
    assert "of test time" in result.stdout

    # Rendered lines in terminal must stay contained without scrolling (< 10 lines)
    rendered_lines = [
        raw.split("\r")[-1].replace("\x1b[K", "").strip()
        for raw in result.stdout.strip().split("\n")
        if raw.split("\r")[-1].replace("\x1b[K", "").strip()
    ]
    assert len(rendered_lines) == 7
    assert "test_reader_sees_committed_value" in rendered_lines[0]
    assert "seeded" in rendered_lines[0]
    assert "run  1/3:" in rendered_lines[2]
    assert "run  2/3:" in rendered_lines[3]
    assert "run  3/3:" in rendered_lines[4]
    assert "failed ·" in rendered_lines[4]
    assert "passed" in rendered_lines[4]
    assert "flake rate " in rendered_lines[6]
    assert "of test time" in rendered_lines[6]


def test_flake_check_unseeded_test_has_no_marker(monkeypatch):
    """User tests that are not benchmark cases do not get the 'seeded' marker."""
    target = "tests/test_cli.py::test_rejection_demo_shows_the_gate_passing_and_replay_refusing"
    result = runner.invoke(app, ["flake-check", target, "-n", "1", "--interval", "0"])
    assert result.exit_code == 0
    assert "test_rejection_demo_shows_the_gate_passing_and_replay_refusing" in result.stdout
    assert "seeded" not in result.stdout
    assert "flake rate " in result.stdout


def test_flake_check_git_sha_fallback(monkeypatch):
    """When git is unavailable, commit sha falls back to 'unknown' without crashing."""
    import chronotrace.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_git_short_sha", lambda root: "unknown")
    result = runner.invoke(app, ["flake-check", "-n", "1", "--interval", "0"])
    assert result.exit_code == 0
    assert "commit unknown" in result.stdout


def test_flake_check_env_interval(monkeypatch):
    """CHRONOTRACE_FLAKE_INTERVAL_S overrides the default interval when flag is omitted."""
    monkeypatch.setenv("CHRONOTRACE_FLAKE_INTERVAL_S", "0.001")
    result = runner.invoke(app, ["flake-check", "-n", "2"])
    assert result.exit_code == 0
    assert "flake rate " in result.stdout


def test_flake_check_verbose():
    """--verbose prints per-run lines rather than an in-place tally."""
    result = runner.invoke(app, ["flake-check", "-n", "2", "--interval", "0", "--verbose"])
    assert result.exit_code == 0
    assert "run  1/2:" in result.stdout
    assert "run  2/2:" in result.stdout
    assert "flake rate " in result.stdout

