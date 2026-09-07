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


def test_repair_reports_when_no_benchmark_corpus_is_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["repair", "--demo"])
    assert result.exit_code == 1
    assert "no benchmark cases found" in result.output


def test_help_lists_the_documented_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("capture", "diagnose", "repair", "verify", "report", "gauntlet", "eval"):
        assert command in result.stdout
