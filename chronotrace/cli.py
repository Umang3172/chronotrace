"""Command-line surface (spec 26).

The only module allowed to print. Everything else logs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from chronotrace.capture.collect import collect
from chronotrace.config import Settings, set_settings
from chronotrace.contracts import IncidentReport
from chronotrace.diagnose.engine import diagnose
from chronotrace.eval.arms import run_arm
from chronotrace.eval.cases import load_cases
from chronotrace.eval.report import write_report
from chronotrace.govern.gate import review
from chronotrace.govern.gauntlet import ATTACKS
from chronotrace.logging import configure
from chronotrace.pipeline import repair
from chronotrace.providers.base import ModelProvider
from chronotrace.providers.local import LocalModelProvider
from chronotrace.registry.store import IncidentStore

app = typer.Typer(
    add_completion=False,
    help="Repair concurrency-induced flaky asyncio tests by proving which ordering caused them.",
)

DEFAULT_CASES = Path("benchmark/cases")


def _settings(**overrides: object) -> Settings:
    settings = Settings(**overrides)  # type: ignore[arg-type]
    set_settings(settings)
    settings.ensure_dirs()
    return settings


def _provider(settings: Settings) -> ModelProvider:
    if settings.provider == "bedrock":
        from chronotrace.providers.bedrock import BedrockProvider

        return BedrockProvider(settings)
    return LocalModelProvider(fixtures_dir=settings.fixtures_dir)


def _store(settings: Settings) -> IncidentStore:
    return IncidentStore(settings.workdir / "incidents.sqlite3")


@app.command()
def capture(
    test_id: str,
    runs: Annotated[int, typer.Option(help="capture budget")] = 30,
    probe_runs: Annotated[int, typer.Option(help="uninstrumented runs for probe effect")] = 10,
    as_json: Annotated[bool, typer.Option("--json", help="emit JSON")] = False,
) -> None:
    """Gather comparable pass/fail trace pairs for a flaky test."""
    configure()
    settings = _settings()
    bundle = collect(
        test_id,
        cwd=Path.cwd(),
        runs=runs,
        timeout_s=settings.run_timeout_s,
        probe_runs=probe_runs,
    )
    if as_json:
        typer.echo(bundle.model_dump_json(indent=2))
        return
    typer.echo(f"runs           : {bundle.runs_executed} ({bundle.runs_timed_out} timed out)")
    typer.echo(f"passing traces : {len(bundle.passing)}")
    typer.echo(f"failing traces : {len(bundle.failing)}")
    typer.echo(f"flake rate     : {bundle.natural_flake_rate:.0%}")
    if bundle.probe_effect_delta is not None:
        typer.echo(
            f"probe effect   : {bundle.probe_effect_delta:+.0%} "
            f"(instrumented {bundle.natural_flake_rate:.0%} vs "
            f"uninstrumented {bundle.uninstrumented_flake_rate:.0%})"
        )
    if not bundle.has_pair:
        typer.echo("no comparable pass/fail pair — diagnosis would abstain (E1)")


@app.command(name="diagnose")
def diagnose_cmd(
    test_id: str,
    runs: Annotated[int, typer.Option(help="capture budget")] = 30,
    as_json: Annotated[bool, typer.Option("--json", help="emit JSON")] = False,
) -> None:
    """Diagnose a flaky test without patching it."""
    configure()
    settings = _settings()
    cwd = Path.cwd()
    bundle = collect(test_id, cwd=cwd, runs=runs, timeout_s=settings.run_timeout_s)
    result = diagnose(
        bundle,
        cwd=cwd,
        timeout_s=settings.run_timeout_s,
        gate_timeout_s=settings.gate_timeout_s,
        allow_production_repair=settings.allow_production_repair,
    )
    if as_json:
        typer.echo(result.model_dump_json(indent=2))
        return
    typer.echo(f"status : {result.status}")
    if result.abstain_reason:
        typer.echo(f"reason : {result.abstain_reason}")
    typer.echo(f"why    : {result.explanation}")
    for candidate in result.candidates:
        rate = (
            "untested"
            if candidate.forced_failure_rate is None
            else f"{candidate.forced_failure_rate:.0%} when forced"
        )
        typer.echo(
            f"  {' -> '.join(candidate.failing_order)}  "
            f"suspiciousness {candidate.ochiai_score:.2f}  {candidate.classification} ({rate})"
        )


@app.command(name="repair")
def repair_cmd(
    test_id: Annotated[str, typer.Argument(help="pytest node id, or --demo")] = "",
    demo: Annotated[bool, typer.Option("--demo", help="run the bundled demo case")] = False,
    runs: Annotated[int, typer.Option(help="capture budget")] = 24,
    apply_patch: Annotated[bool, typer.Option("--apply", help="write the patch to disk")] = False,
    allow_production_repair: Annotated[
        bool, typer.Option(help="permit product-code edits")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="emit the full report as JSON")] = False,
) -> None:
    """Run the full pipeline: capture, diagnose, prove, patch, govern, verify."""
    configure()
    settings = _settings(allow_production_repair=allow_production_repair)
    if demo or not test_id:
        cases = load_cases(DEFAULT_CASES)
        if not cases:
            typer.echo("no benchmark cases found", err=True)
            raise typer.Exit(1)
        # The demo leads with a repairable race, because the point being
        # demonstrated is the causal proof. The abstention cases are reachable
        # by naming them, and are shown by `chronotrace eval`.
        chosen = next((case for case in cases if case.is_supported_race), cases[0])
        test_id = chosen.test_id
        typer.echo(f"demo case: {chosen.case_id} {chosen.name} ({chosen.shape})\n")
    report = repair(
        test_id,
        cwd=Path.cwd(),
        provider=_provider(settings),
        settings=settings,
        capture_runs=runs,
        apply=apply_patch,
    )
    _store(settings).save(report)
    if as_json:
        typer.echo(report.model_dump_json(indent=2))
        return
    _print_report(report)


@app.command()
def verify(
    incident_id: str,
    tier: Annotated[str, typer.Option(help="forced | pct | statistical")] = "forced",
) -> None:
    """Show what verification established for a stored incident, at a given tier."""
    configure(quiet=True)
    settings = _settings()
    report = _store(settings).get(incident_id)
    if report is None or report.verification is None:
        typer.echo(f"no verification recorded for {incident_id}", err=True)
        raise typer.Exit(1)
    result = report.verification
    typer.echo(f"tier reached : {result.tier_reached}")
    typer.echo(f"requested    : {tier.upper()}")
    if result.tier_reached != tier.upper():
        typer.echo(
            "note: the tier reached is reported as measured. A lower tier is never "
            "presented as causal proof."
        )
    typer.echo(f"pre-patch forced failed  : {result.pre_patch_forced_failed}")
    typer.echo(f"post-patch forced passed : {result.post_patch_forced_passed}")
    typer.echo(
        f"residual flake check     : "
        f"{result.statistical_runs - result.statistical_failures}/{result.statistical_runs}"
    )
    typer.echo(f"measured overhead        : {result.measured_overhead_ms} ms")
    typer.echo(f"reproduction seed        : {json.dumps(result.reproduction_seed)}")


@app.command()
def report(incident_id: str) -> None:
    """Print a stored incident report as JSON."""
    configure(quiet=True)
    settings = _settings()
    stored = _store(settings).get(incident_id)
    if stored is None:
        typer.echo(f"unknown incident {incident_id}", err=True)
        raise typer.Exit(1)
    typer.echo(stored.model_dump_json(indent=2))


@app.command()
def gauntlet() -> None:
    """Run the adversarial patch gauntlet against the governor (spec 24)."""
    configure(quiet=True)
    _settings()
    rejected = 0
    for attack in ATTACKS:
        verdict = review(before=attack.before, after=attack.after, path=attack.path)
        caught = [rule.rule_id for rule in verdict.rules_evaluated if not rule.passed]
        ok = not verdict.approved and attack.rule_id in caught
        rejected += ok
        mark = "REJECTED" if ok else "ESCAPED "
        typer.echo(f"{mark}  {attack.rule_id:<3} {attack.name:<38} {attack.description}")
    typer.echo(f"\n{rejected}/{len(ATTACKS)} attacks rejected by the rule that targets them")
    if rejected != len(ATTACKS):
        raise typer.Exit(1)


@app.command(name="eval")
def eval_cmd(
    arm: Annotated[str, typer.Option(help="A, B, C, or all")] = "C",
    cases: Annotated[str, typer.Option(help="case ids, or all")] = "all",
    runs: Annotated[int, typer.Option(help="capture budget per case")] = 20,
    probe_runs: Annotated[int, typer.Option(help="uninstrumented runs per case")] = 0,
    out: Annotated[Path, typer.Option(help="where to write results")] = Path("eval-results"),
) -> None:
    """Run the benchmark and produce every number the README claims."""
    configure()
    settings = _settings()
    corpus = load_cases(DEFAULT_CASES)
    if cases != "all":
        wanted = {item.strip().upper() for item in cases.split(",")}
        corpus = [case for case in corpus if case.case_id.upper() in wanted]
    if not corpus:
        typer.echo("no matching benchmark cases", err=True)
        raise typer.Exit(1)
    arms = ["A", "B", "C"] if arm.lower() == "all" else [arm.upper()]
    provider = _provider(settings)
    results = [
        run_arm(
            name,
            corpus,
            cwd=Path.cwd(),
            provider=provider,
            settings=settings,
            capture_runs=runs,
            probe_runs=probe_runs,
        )
        for name in arms
    ]
    store = _store(settings)
    for arm_result in results:
        for _case, incident in arm_result.results:
            store.save(incident)
    store.export(out / "incidents.json")
    markdown_path, json_path = write_report(results, out)
    typer.echo(markdown_path.read_text())
    typer.echo(f"written: {markdown_path} and {json_path}")


def _print_report(report: IncidentReport) -> None:
    banner = {
        "FIXED": "FIXED",
        "NEEDS_INVESTIGATION": "NEEDS INVESTIGATION",
        "ABSTAINED": "ABSTAINED",
    }[report.ui_state]
    typer.echo(f"{banner}  ({report.incident_id})")
    typer.echo(f"test    : {report.test_id}")
    typer.echo(f"flaky   : {report.natural_flake_rate:.0%} of captured runs")
    typer.echo(f"finding : {report.diagnosis.explanation}")
    if report.intent:
        typer.echo(f"intent  : {report.intent.transformation} ({report.intent.primitive})")
        typer.echo(f"why     : {report.intent.rationale}")
    if report.verdict:
        failed = [rule for rule in report.verdict.rules_evaluated if not rule.passed]
        typer.echo(
            f"governor: {len(report.verdict.rules_evaluated) - len(failed)}"
            f"/{len(report.verdict.rules_evaluated)} rules passed"
        )
        for rule in failed:
            typer.echo(f"          REJECTED {rule.rule_id}: {rule.detail}")
    if report.verification:
        result = report.verification
        typer.echo(f"tier    : {result.tier_reached}")
        if result.causally_proven:
            typer.echo(
                "proof   : forced ordering failed before the patch and passed after it, "
                "with the harness unchanged"
            )
        typer.echo(
            f"residual: {result.statistical_runs - result.statistical_failures}"
            f"/{result.statistical_runs} stable, "
            f"overhead {result.measured_overhead_ms:+g} ms"
        )
    if report.regression_test_path:
        typer.echo(f"guard   : {report.regression_test_path}")
    if report.unified_diff:
        typer.echo("\n" + report.unified_diff)


def main() -> None:
    """Entry point for the ``chronotrace`` console script."""
    try:
        app()
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
