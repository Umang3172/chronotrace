"""Command-line surface (spec 26).

The only module allowed to print. Everything else logs.
"""

from __future__ import annotations

import json
import sys
import time
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
from chronotrace.providers.detect import detect
from chronotrace.providers.reference_policy import PROVIDER_LABEL, ReferencePolicyProvider
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
    if settings.provider == "ollama":
        return _ollama(settings)
    return ReferencePolicyProvider(fixtures_dir=settings.fixtures_dir)


def _ollama(settings: Settings, recorder: object = None) -> ModelProvider:
    from chronotrace.providers.ollama import OllamaProvider

    return OllamaProvider(
        host=settings.ollama_host,
        model=settings.ollama_model,
        temperature=settings.model_temperature,
        seed=settings.model_seed,
        max_tokens=settings.model_max_tokens,
        timeout_s=settings.model_timeout_s,
        recorder=recorder,  # type: ignore[arg-type]
    )


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
    demo_r14: Annotated[
        bool,
        typer.Option(
            "--demo-r14",
            help="run the R14 case and stop at the rejection: a patch the policy gate "
            "allows and forced replay refuses",
        ),
    ] = False,
    slow: Annotated[bool, typer.Option("--slow", help="pace the output for narration")] = False,
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
    demo = demo or demo_r14
    if demo and settings.provider == PROVIDER_LABEL:
        # The demo must show a model deciding, not the hand-written policy. Look
        # for a usable provider before refusing, and if there is none, say
        # exactly which command would produce one.
        choice = detect(settings)
        if not choice.usable:
            typer.echo(
                "The demo needs a language model, and none is available.\n\n"
                f"{choice.reason}.\n\n"
                "ChronoTrace will not run the demo on its reference policy: that is a\n"
                "hand-written decision procedure, not a model, so a demo it produced\n"
                "would show this repository deciding for itself.\n\n"
                f"{choice.remedy}",
                err=True,
            )
            raise typer.Exit(2)
        settings = _settings(
            provider=choice.provider, allow_production_repair=allow_production_repair
        )
        typer.echo(f"using provider '{choice.provider}' — {choice.reason}\n")
    if demo or not test_id:
        cases = load_cases(DEFAULT_CASES)
        if not cases:
            typer.echo("no benchmark cases found", err=True)
            raise typer.Exit(1)
        if demo_r14:
            chosen = next((case for case in cases if case.case_id == "R14"), None)
            if chosen is None:
                typer.echo("benchmark case R14 not found", err=True)
                raise typer.Exit(1)
        else:
            # The first demo leads with a repairable race, because the point
            # being demonstrated is the causal proof. The abstention cases are
            # reachable by naming them, and are shown by `chronotrace eval`.
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
    if demo_r14:
        _print_rejection_demo(report, slow=slow)
        return
    _print_report(report, slow=slow)


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
    typer.echo(f"post-patch unreachable   : {result.post_patch_forced_infeasible}")
    typer.echo(f"repair strength          : {result.repair_strength}")
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


@app.command(name="three-arm")
def three_arm(
    provider: Annotated[str, typer.Option(help="ollama | fixture")] = "ollama",
    model: Annotated[str, typer.Option(help="model tag for ollama")] = "qwen3:8b",
    runs: Annotated[int, typer.Option(help="capture budget per case")] = 20,
    cases: Annotated[str, typer.Option(help="case ids, or all")] = "all",
    out: Annotated[Path, typer.Option(help="results directory")] = Path("eval/results"),
    fixtures: Annotated[Path, typer.Option(help="call recording directory")] = Path(
        "fixtures/three_arm"
    ),
    arms: Annotated[str, typer.Option(help="which arms to run, e.g. C or A,B,C")] = "A,B,C",
    reuse_evidence: Annotated[
        bool,
        typer.Option(
            help="load the recorded traces and diagnoses instead of capturing afresh, "
            "so two models are compared on identical evidence"
        ),
    ] = False,
) -> None:
    """Run the three-arm baseline: code only, code plus traces, full ChronoTrace."""
    configure()
    settings = _settings(provider=provider, ollama_model=model)
    from chronotrace.eval.three_arm import run_sweep
    from chronotrace.eval.three_arm_report import write_results
    from chronotrace.providers.record import FixtureProvider, FixtureRecorder

    corpus = load_cases(DEFAULT_CASES)
    if cases != "all":
        wanted = {item.strip().upper() for item in cases.split(",")}
        corpus = [case for case in corpus if case.case_id.upper() in wanted]
    if not corpus:
        typer.echo("no matching benchmark cases", err=True)
        raise typer.Exit(1)

    label = f"ollama:{model}"
    if provider == "fixture":
        engine: object = FixtureProvider(fixtures, provider_label=label)
    else:
        engine = _ollama(settings, FixtureRecorder(fixtures))

    sweep = run_sweep(
        corpus,
        cwd=Path.cwd(),
        provider=engine,  # type: ignore[arg-type]
        settings=settings,
        capture_runs=runs,
        model_label=model,
        evidence_dir=fixtures / "evidence",
        replay=provider == "fixture" or reuse_evidence,
        arms=tuple(a.strip().upper() for a in arms.split(",") if a.strip()),
    )
    drift = getattr(engine, "prompt_drift", [])
    if drift:
        typer.echo(f"prompt drift on replay: {', '.join(sorted(set(drift)))}", err=True)
    json_path, markdown_path = write_results(sweep, out)
    typer.echo(markdown_path.read_text())
    typer.echo(f"\nwritten: {json_path} and {markdown_path}")


@app.command(name="replay-check")
def replay_check(
    live: Annotated[Path, typer.Option(help="results JSON from the model-backed run")],
    replay: Annotated[Path, typer.Option(help="results JSON from the fixture replay")],
) -> None:
    """Confirm a fixture replay reproduces the model-derived numbers exactly."""
    configure(quiet=True)
    from chronotrace.eval.replay_check import compare

    comparison = compare(live, replay)
    typer.echo(comparison.render())
    if not comparison.model_derived_identical:
        raise typer.Exit(1)


def _pace(slow: bool, seconds: float = 1.4) -> None:
    """Pause between acts when the output is being narrated.

    Presentation only. Nothing in the pipeline waits on a clock.
    """
    if slow:
        time.sleep(seconds)


def _rule(title: str) -> None:
    typer.echo(f"\n{title}\n{'-' * len(title)}")


def _print_rejection_demo(report: IncidentReport, *, slow: bool = False) -> None:
    """Walk through a patch the policy gate allows and forced replay refuses.

    R14's assertion depends on a task *finishing*, not on one write landing, so
    an injected event is the wrong repair even though the operations look like
    the read-after-write shape that selects it. Nothing about the patch violates
    policy. The gate passes it and the experiment rejects it, which is the whole
    argument for having an experiment.
    """
    verification = report.verification
    intent = report.intent

    _rule("1. The race")
    typer.echo(f"test  : {report.test_id.split('::')[-1]}")
    typer.echo(f"flaky : {report.natural_flake_rate:.0%} of captured runs")
    typer.echo(f"cause : {report.diagnosis.explanation}")
    _pace(slow)

    _rule("2. What the model proposed")
    if intent is None:
        typer.echo("no intent was produced")
    else:
        typer.echo(f"transformation : {intent.transformation}")
        typer.echo(f"primitive      : {intent.primitive}")
        typer.echo(f"rationale      : {intent.rationale}")
        if len(report.intent_attempts) > 1:
            typer.echo(
                f"attempts       : {len(report.intent_attempts)} "
                "(the retry corrected the format, not the choice)"
            )
    _pace(slow)

    _rule("3. What the policy gate said")
    if report.verdict is None:
        typer.echo("the gate was not reached")
    else:
        passed = sum(1 for rule in report.verdict.rules_evaluated if rule.passed)
        total = len(report.verdict.rules_evaluated)
        typer.echo(f"{passed}/{total} rules passed — approved: {report.verdict.approved}")
        typer.echo(
            "No sleep, no retry, no timeout change, no weakened assertion. This patch\n"
            "breaks no policy. The problem with it is judgement, not policy, and a\n"
            "policy checker cannot see judgement."
        )
    _pace(slow)

    _rule("4. What forced replay said")
    if verification is None:
        typer.echo("verification did not run")
        return
    typer.echo(f"tier reached : {verification.tier_reached}")
    typer.echo(f"repaired     : {verification.causally_proven}")
    typer.echo(
        "The ordering failed before the patch and still failed after it, so the\n"
        "patch did not defeat the interleaving it was chosen to defeat."
    )
    _pace(slow)

    _rule("5. What a rerun-based gate would have concluded")
    runs = verification.statistical_runs
    after = verification.statistical_failures
    before = verification.pre_patch_natural_failures
    if runs:
        typer.echo(f"before the patch : {before}/{runs} runs failed  ({before / runs:.0%})")
        typer.echo(f"with the patch   : {after}/{runs} runs failed  ({after / runs:.0%})")
        # The sentence has to follow the measurement. The residual is noisy: this
        # patch has measured anywhere from 45% to 75% across runs against a
        # pre-patch rate of 70-80%, so sometimes it looks like an improvement and
        # sometimes it does not. Claiming the favourable reading on a run that
        # produced the other one would be exactly the kind of thing this project
        # exists to refuse.
        if after < before:
            typer.echo(
                f"\nflake rate {before / runs:.0%} before, {after / runs:.0%} with this "
                "patch — a rerun-based gate would accept this."
            )
            typer.echo(
                "\nThe test used to fail most of the time and now fails less often.\n"
                "Every rerun-based signal reads that as an improvement."
            )
        else:
            typer.echo(
                f"\nflake rate {before / runs:.0%} before, {after / runs:.0%} with this "
                "patch — on this run it did not even get rarer."
            )
            typer.echo(
                "\nOn other runs this same patch has measured 45% against 80% before,\n"
                "which a rerun-based gate would have accepted. That is the problem\n"
                "with rerun-based gates: the signal is noisy enough that the same\n"
                "wrong patch passes or fails depending on the day."
            )
    typer.echo(
        "\nForcing the ordering is what separates 'fixed the race' from 'made it\n"
        "rarer', and unlike the rerun count it gives the same answer every time."
    )
    _pace(slow)

    _rule("What the correct repair was")
    typer.echo(
        "Await the task handle the test already holds, before the assertion. Both\n"
        "unconstrained baseline arms wrote exactly that. ChronoTrace did not: the\n"
        "operations look like a read-after-write on a shared resource, which is the\n"
        "condition that selects an event, and the model matched the shape rather\n"
        "than what the assertion depends on.\n\n"
        "The verification layer caught it. That is the claim being demonstrated."
    )


def _print_report(report: IncidentReport, *, slow: bool = False) -> None:
    banner = {
        "FIXED": "FIXED",
        "NEEDS_INVESTIGATION": "NEEDS INVESTIGATION",
        "ABSTAINED": "ABSTAINED",
    }[report.ui_state]
    typer.echo(f"{banner}  ({report.incident_id})")
    typer.echo(f"test    : {report.test_id}")
    typer.echo(f"flaky   : {report.natural_flake_rate:.0%} of captured runs")
    _pace(slow)
    typer.echo(f"finding : {report.diagnosis.explanation}")
    _pace(slow)
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
        _pace(slow)
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
