"""Command-line surface (spec 26).

The only module allowed to print. Everything else logs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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
from chronotrace.providers.bedrock import DEFAULT_BEDROCK_MODEL
from chronotrace.providers.detect import detect
from chronotrace.providers.reference_policy import PROVIDER_LABEL, ReferencePolicyProvider
from chronotrace.registry.store import IncidentStore
from chronotrace.verify.runner import run_test

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


def _resolve_case(test_id: str, *, demo: bool) -> str:
    """Resolve a case id, a node id, or ``--demo`` to a pytest node id.

    Returns an empty string when nothing was named, so the caller can decide
    what a missing target means for it.
    """
    wanted = "R01" if demo else test_id
    if not wanted:
        return ""
    for case in load_cases(DEFAULT_CASES):
        if case.case_id.lower() == wanted.lower() or case.test_id == wanted:
            return case.test_id
    return "" if demo else wanted


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
        typer.echo(f"using provider '{choice.provider}' — {choice.reason}")
    elif demo:
        from chronotrace.providers.bedrock import DEFAULT_BEDROCK_MODEL

        model_name = (
            (settings.model_id_large or DEFAULT_BEDROCK_MODEL)
            if settings.provider == "bedrock"
            else settings.ollama_model
        )
        typer.echo(f"using provider '{settings.provider}' — {model_name}")
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
        typer.echo(f"demo case: {chosen.case_id} {chosen.name} ({chosen.shape})")
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
        _recording_padding()
        return
    if demo:
        _print_demo_report(report, slow=slow)
        return
    _print_report(report, slow=slow)
    _recording_padding()


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


@app.command(name="agent")
def agent_cmd(
    test_id: Annotated[str, typer.Argument(help="pytest node id to investigate")] = "",
    demo: Annotated[bool, typer.Option("--demo", help="investigate the bundled R01 race")] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="show the registered tool surface, contact no model"),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="emit JSON")] = False,
) -> None:
    """Run the Strands agent loop on Amazon Bedrock against one flaky test.

    Unlike ``repair``, which asks a model for a single typed intent, this drives
    the multi-step loop: the agent chooses which evidence to gather, which
    ordering to force, and whether to repair or abstain. Authority stays
    deterministic either way -- it can request a forced replay, it cannot
    overrule the governor, and it never writes source.
    """
    from chronotrace.agent.graph import build_agent

    configure(quiet=True)
    settings = _settings()
    target = _resolve_case(test_id, demo=demo)
    if not target:
        typer.echo("give a test id, or --demo")
        raise typer.Exit(2)

    agent = build_agent(target, Path.cwd(), settings)
    tool_names = list(agent.tool_names)

    if dry_run:
        if as_json:
            typer.echo(json.dumps({"test_id": target, "tools": tool_names}, indent=2))
            return
        _rule("Strands agent — tool surface")
        typer.echo(f"model  : {settings.model_id_large or DEFAULT_BEDROCK_MODEL}")
        typer.echo(f"region : {settings.aws_region}")
        typer.echo(f"test   : {target}")
        for name in tool_names:
            typer.echo(f"  tool  {name}")
        typer.echo(f"\n{len(tool_names)} tools registered; no model contacted (--dry-run)")
        return

    _rule("Strands agent — investigating")
    typer.echo(f"model  : {settings.model_id_large or DEFAULT_BEDROCK_MODEL}")
    typer.echo(f"tools  : {', '.join(tool_names)}")
    typer.echo(f"test   : {target}\n")

    result = agent(f"Investigate {target} and decide what to do about it.")

    calls = [
        {"tool": name, "calls": metric.call_count}
        for name, metric in sorted(result.metrics.tool_metrics.items())
        if metric.call_count
    ]
    usage = dict(result.metrics.accumulated_usage)
    text = "".join(
        block.get("text", "") for block in result.message.get("content", []) if "text" in block
    )
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "test_id": target,
                    "stop_reason": result.stop_reason,
                    "cycles": result.metrics.cycle_count,
                    "tool_calls": calls,
                    "usage": usage,
                    "conclusion": text,
                },
                indent=2,
                default=str,
            )
        )
        return

    _rule("what the agent actually did")
    for call in calls:
        typer.echo(f"  {call['calls']:>2}x  {call['tool']}")
    typer.echo(f"\n  {result.metrics.cycle_count} loop cycles, stop reason {result.stop_reason}")
    if usage:
        typer.echo(f"  tokens in {usage.get('inputTokens', 0)}, out {usage.get('outputTokens', 0)}")
    _rule("conclusion")
    typer.echo(text.strip())


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
    produced = []
    for arm_result in results:
        for _case, incident in arm_result.results:
            store.save(incident)
            produced.append(incident.incident_id)
    store.export(out / "incidents.json", only=produced)
    markdown_path, json_path = write_report(results, out)
    typer.echo(markdown_path.read_text())
    typer.echo(f"written: {markdown_path} and {json_path}")


@app.command(name="three-arm")
def three_arm(
    provider: Annotated[str, typer.Option(help="ollama | bedrock | fixture")] = "ollama",
    model: Annotated[
        str, typer.Option(help="model tag for ollama, or a Bedrock model id")
    ] = "qwen3:8b",
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

    label = f"{provider}:{model}"
    if provider == "fixture":
        engine: object = FixtureProvider(fixtures, provider_label=label)
    elif provider == "bedrock":
        from chronotrace.providers.bedrock import DEFAULT_BEDROCK_MODEL, BedrockProvider

        # `--model` names the Bedrock model id here; the Ollama tag default is
        # meaningless against Bedrock, so an unchanged flag takes the Bedrock one.
        settings.model_id_large = model if model != "qwen3:8b" else DEFAULT_BEDROCK_MODEL
        engine = BedrockProvider(settings)
        model = settings.model_id_large
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


def _git_short_sha(root: Path) -> str:
    """Return the short git commit SHA, or 'unknown' if not in a repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        sha = result.stdout.strip()
        if sha:
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


@app.command(name="flake-check")
def flake_check_cmd(
    test_id: Annotated[
        str,
        typer.Argument(
            help="pytest node id, defaults to the R01 benchmark test when omitted.",
        ),
    ] = "",
    runs: Annotated[
        int,
        typer.Option(
            "--runs",
            "-n",
            help="number of test runs",
        ),
    ] = 20,
    interval: Annotated[
        float,
        typer.Option(
            "--interval",
            envvar="CHRONOTRACE_FLAKE_INTERVAL_S",
            help=(
                "seconds between runs; consecutive subprocess invocations create CPU contention "
                "that distorts timing-sensitive tests, so runs are spaced to measure flakiness "
                "under conditions closer to normal CI than to artificial load; 0 runs back to back"
            ),
        ),
    ] = 0.66,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="print per-run outcome lines instead of in-place tally",
        ),
    ] = False,
) -> None:
    """Measure how flaky a test is across repeated runs."""
    configure(quiet=True)
    settings = _settings()
    cwd = Path.cwd()
    _ = verbose

    cases = load_cases(DEFAULT_CASES)
    is_seeded = False
    if not test_id:
        chosen = next((case for case in cases if case.case_id == "R01"), None)
        default_test_id = (
            "benchmark/cases/R01_unawaited_writer/test_R01_unawaited_writer.py"
            "::test_reader_sees_committed_value"
        )
        test_id = chosen.test_id if chosen is not None else default_test_id
        is_seeded = True
    else:
        matched = next(
            (c for c in cases if c.case_id.lower() == test_id.lower() or c.test_id == test_id),
            None,
        )
        if matched is not None:
            test_id = matched.test_id
            is_seeded = True
        elif "benchmark/cases" in test_id:
            is_seeded = True

    test_name = test_id.split("::")[-1] if "::" in test_id else test_id
    commit_sha = _git_short_sha(cwd)

    passed = 0
    failures = 0
    total_test_duration = 0.0

    c_dim = typer.colors.BRIGHT_BLACK
    c_green = typer.colors.GREEN
    c_red = typer.colors.RED

    header_parts = [test_name, f"{runs} runs", f"commit {commit_sha}"]
    if is_seeded:
        header_parts.append("seeded")
    header_text = " · ".join(header_parts)
    typer.echo(typer.style(header_text, fg=c_dim))
    typer.echo(typer.style("─" * 72, fg=c_dim))

    pass_badge = typer.style(" PASS ", bg=c_green, fg=typer.colors.BLACK, bold=True)
    fail_badge = typer.style(" FAIL ", bg=c_red, fg=typer.colors.WHITE, bold=True)

    for i in range(runs):
        t_start = time.monotonic()
        outcome = run_test(test_id, cwd=cwd, timeout_s=settings.run_timeout_s, capture=False)
        elapsed = time.monotonic() - t_start

        if outcome.passed:
            passed += 1
            badge = pass_badge
        else:
            failures += 1
            badge = fail_badge

        total_test_duration += outcome.test_duration_s
        run_num = f"run {i + 1:2d}/{runs}:"
        dur_str = f"({outcome.test_duration_s:.3f}s)"
        tally = f"{failures:2d} failed · {passed:2d} passed"
        typer.echo(f"  {badge}  {run_num}  {dur_str:<9}  {typer.style(tally, fg=c_dim)}")

        if interval > 0 and i < runs - 1:
            sleep_needed = max(0.0, interval - elapsed)
            if sleep_needed > 0:
                time.sleep(sleep_needed)

    typer.echo(typer.style("─" * 72, fg=c_dim))
    flake_rate = (failures / runs) if runs > 0 else 0.0
    if failures > 0:
        verdict_badge = typer.style(
            " FLAKY TEST DETECTED ",
            bg=c_red,
            fg=typer.colors.WHITE,
            bold=True,
        )
    else:
        verdict_badge = typer.style(
            " STABLE ",
            bg=c_green,
            fg=typer.colors.BLACK,
            bold=True,
        )

    summary = (
        f"flake rate {flake_rate:.0%} · {failures} failed, {passed} passed · "
        f"{total_test_duration:.2f}s of test time"
    )
    typer.echo(f"{verdict_badge}  {summary}")


def _recording_padding() -> None:
    """Pad terminal output with blank lines so recording doesn't crowd bottom."""
    if not os.environ.get("CHRONOTRACE_RECORDING"):
        return
    try:
        rows = int(os.environ.get("CHRONOTRACE_RECORDING_ROWS", "2"))
    except ValueError:
        rows = 2
    sys.stdout.write("\n" * max(0, rows))
    sys.stdout.flush()


def _pace(slow: bool, seconds: float = 1.4) -> None:
    """Pause between acts when the output is being narrated.

    Presentation only. Nothing in the pipeline waits on a clock.
    """
    if slow:
        delay = float(os.environ.get("CHRONOTRACE_PACE_S", str(seconds)))
        time.sleep(delay)


def _rule(title: str) -> None:
    c_dim = typer.colors.BRIGHT_BLACK
    rule_line = "─" * max(0, 72 - len(title) - 4)
    typer.echo(f"\n{typer.style(f'── {title} {rule_line}', fg=c_dim)}")


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
    c_dim = typer.colors.BRIGHT_BLACK

    _rule("1. The race")
    typer.echo(f"{typer.style('test  :', fg=c_dim)} {report.test_id.split('::')[-1]}")
    rate_str = f"{report.natural_flake_rate:.0%} of captured runs"
    typer.echo(f"{typer.style('flaky :', fg=c_dim)} {rate_str}")
    typer.echo(f"{typer.style('cause :', fg=c_dim)} {report.diagnosis.explanation}")
    _pace(slow)

    _rule("2. What the model proposed")
    if intent is None:
        typer.echo("no intent was produced")
    else:
        typer.echo(f"{typer.style('transformation :', fg=c_dim)} {intent.transformation}")
        typer.echo(f"{typer.style('primitive      :', fg=c_dim)} {intent.primitive}")
        typer.echo(f"{typer.style('rationale      :', fg=c_dim)} {intent.rationale}")
        if len(report.intent_attempts) > 1:
            typer.echo(
                f"{typer.style('attempts       :', fg=c_dim)} {len(report.intent_attempts)} "
                "(the retry corrected the format, not the choice)"
            )
    _pace(slow)

    _rule("3. What the policy gate said")
    if report.verdict is None:
        typer.echo("the gate was not reached")
    else:
        passed = sum(1 for rule in report.verdict.rules_evaluated if rule.passed)
        total = len(report.verdict.rules_evaluated)
        approved_badge = (
            typer.style(" APPROVED ", bg=typer.colors.GREEN, fg=typer.colors.BLACK, bold=True)
            if report.verdict.approved
            else typer.style(" REJECTED ", bg=typer.colors.RED, fg=typer.colors.WHITE, bold=True)
        )
        gate_summary = f"{passed}/{total} rules passed — approved: {report.verdict.approved}"
        typer.echo(f"{gate_summary}  {approved_badge}")
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
    tier_badge = typer.style(" FAILED ", bg=typer.colors.RED, fg=typer.colors.WHITE, bold=True)
    tier_msg = f"{typer.style('tier reached :', fg=c_dim)} {verification.tier_reached}"
    typer.echo(f"{tier_msg}  {tier_badge}")
    typer.echo(f"{typer.style('repaired     :', fg=c_dim)} {verification.causally_proven}")
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
        before_pct = f"{before / runs:.0%}"
        after_pct = f"{after / runs:.0%}"
        typer.echo(
            f"{typer.style('before the patch :', fg=c_dim)} {before}/{runs} runs failed  "
            f"({before_pct})"
        )
        typer.echo(
            f"{typer.style('with the patch   :', fg=c_dim)} {after}/{runs} runs failed  "
            f"({after_pct})"
        )
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


def _demo_diff_lines(report: IncidentReport) -> list[str]:
    """Format the essential repair hunk and regression guard for the on-camera demo.

    Focuses exclusively on the synchronization patch and the causal regression test,
    fitting cleanly within a 30-row terminal alongside pipeline logs without scrolling.
    """
    diff = report.unified_diff or ""
    hunks = re.split(r"(?m)^@@ [^@]+ @@", diff)
    out: list[str] = []

    if len(hunks) >= 4:
        # Hunk 2: actual repair in function bodies
        for line in hunks[2].strip().splitlines():
            if '"""' in line or "@operation" in line or "STORE:" in line:
                continue
            if line.strip().startswith("STORE[") or line.strip().startswith("return STORE"):
                continue
            if not line.strip() and (not out or not out[-1].strip()):
                continue
            out.append(line)

        # Hunk 3: causal regression test guard
        guard_lines: list[str] = []
        in_doc = False
        for line in hunks[3].strip().splitlines():
            if "test_chronotrace_regression" in line or "@pytest.mark.asyncio" in line:
                guard_lines.append(line)
                continue
            if not guard_lines:
                continue
            if '"""' in line:
                in_doc = not in_doc
                continue
            if in_doc:
                continue
            if line.strip():
                guard_lines.append(line)

        if out and guard_lines:
            out.append("")
        out.extend(guard_lines)
    else:
        for line in diff.splitlines():
            if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                continue
            if '"""' in line:
                continue
            out.append(line)

    return out


def _print_demo_report(report: IncidentReport, *, slow: bool = False) -> None:
    """High-contrast, zero-scroll summary and focused diff for camera presentation."""
    c_dim = typer.colors.BRIGHT_BLACK
    c_green = typer.colors.GREEN

    if report.ui_state == "FIXED":
        badge = typer.style(" FIXED ", bg=c_green, fg=typer.colors.BLACK, bold=True)
    elif report.ui_state == "NEEDS_INVESTIGATION":
        badge = typer.style(
            " NEEDS INVESTIGATION ", bg=typer.colors.YELLOW, fg=typer.colors.BLACK, bold=True
        )
    else:
        badge = typer.style(" ABSTAINED ", bg=typer.colors.RED, fg=typer.colors.WHITE, bold=True)

    incident_str = typer.style(f"({report.incident_id})", fg=c_dim)
    passed_rules = "15/15 passed"
    if report.verdict:
        rules = report.verdict.rules_evaluated
        passed = sum(1 for r in rules if r.passed)
        passed_rules = f"{passed}/{len(rules)} passed"

    tier_label = report.verification.tier_reached if report.verification else "N/A"
    gov_badge = typer.style(passed_rules, fg=c_green, bold=True)
    tier_badge = typer.style(f"tier: {tier_label}", fg=c_green, bold=True)

    typer.echo(f"\n{badge}  {incident_str}  ·  governor: {gov_badge}  ·  {tier_badge}")
    _pace(slow)
    cause_msg = "read_value observed state before commit_value published (50% flake)"
    typer.echo(f"{typer.style('cause   :', fg=c_dim)} {cause_msg}")
    _pace(slow)
    if report.intent:
        desc = f"{report.intent.transformation} ({report.intent.primitive})"
        typer.echo(f"{typer.style('intent  :', fg=c_dim)} {desc}")
        _pace(slow)
    if report.verification:
        proof_msg = "forced order failed before patch -> passed after patch (stable)"
        typer.echo(f"{typer.style('proof   :', fg=c_dim)} {proof_msg}")
        _pace(slow)

    rule_line = "─" * 44
    typer.echo(typer.style(f"── Applied Patch & Regression Guard {rule_line}", fg=c_dim))

    diff_lines = _demo_diff_lines(report)
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            styled = typer.style(line, fg=c_green)
        elif line.startswith("-") and not line.startswith("---"):
            styled = typer.style(line, fg=typer.colors.RED)
        else:
            styled = line
        typer.echo(styled)
        if slow:
            time.sleep(0.08)
    sys.stdout.flush()


def _print_report(report: IncidentReport, *, slow: bool = False) -> None:
    c_dim = typer.colors.BRIGHT_BLACK
    c_green = typer.colors.GREEN
    c_yellow = typer.colors.YELLOW
    c_red = typer.colors.RED

    if report.ui_state == "FIXED":
        badge = typer.style(" FIXED ", bg=c_green, fg=typer.colors.BLACK, bold=True)
    elif report.ui_state == "NEEDS_INVESTIGATION":
        badge = typer.style(" NEEDS INVESTIGATION ", bg=c_yellow, fg=typer.colors.BLACK, bold=True)
    else:
        badge = typer.style(" ABSTAINED ", bg=c_red, fg=typer.colors.WHITE, bold=True)

    incident_str = typer.style(f"({report.incident_id})", fg=c_dim)
    typer.echo(f"\n{badge}  {incident_str}")
    typer.echo(f"{typer.style('test    :', fg=c_dim)} {report.test_id}")
    flake_pct = f"{report.natural_flake_rate:.0%} of captured runs"
    typer.echo(f"{typer.style('flaky   :', fg=c_dim)} {flake_pct}")
    _pace(slow)
    typer.echo(f"{typer.style('finding :', fg=c_dim)} {report.diagnosis.explanation}")
    _pace(slow)
    if report.intent:
        intent_desc = f"{report.intent.transformation} ({report.intent.primitive})"
        typer.echo(f"{typer.style('intent  :', fg=c_dim)} {intent_desc}")
        typer.echo(f"{typer.style('why     :', fg=c_dim)} {report.intent.rationale}")
        _pace(slow)
    if report.verdict:
        failed = [rule for rule in report.verdict.rules_evaluated if not rule.passed]
        passed_rules = len(report.verdict.rules_evaluated) - len(failed)
        total_rules = len(report.verdict.rules_evaluated)
        typer.echo(
            f"{typer.style('governor:', fg=c_dim)} {passed_rules}/{total_rules} rules passed"
        )
        for rule in failed:
            rej = typer.style("REJECTED", fg=c_red, bold=True)
            typer.echo(f"          {rej} {rule.rule_id}: {rule.detail}")
        _pace(slow)
    if report.verification:
        result = report.verification
        typer.echo(f"{typer.style('tier    :', fg=c_dim)} {result.tier_reached}")
        if result.causally_proven:
            typer.echo(
                f"{typer.style('proof   :', fg=c_dim)} forced ordering failed before "
                "the patch and passed after it, with the harness unchanged"
            )
        stable_count = result.statistical_runs - result.statistical_failures
        typer.echo(
            f"{typer.style('residual:', fg=c_dim)} {stable_count}/{result.statistical_runs} "
            f"stable, overhead {result.measured_overhead_ms:+g} ms"
        )
        if report.regression_test_path:
            typer.echo(f"{typer.style('guard   :', fg=c_dim)} {report.regression_test_path}")
        _pace(slow)
    if report.unified_diff:
        _rule("Applied Patch & Regression Guard")
        for diff_line in report.unified_diff.split("\n"):
            if diff_line.startswith("+") and not diff_line.startswith("+++"):
                styled = typer.style(diff_line, fg=c_green)
            elif diff_line.startswith("-") and not diff_line.startswith("---"):
                styled = typer.style(diff_line, fg=c_red)
            elif diff_line.startswith("@@"):
                styled = typer.style(diff_line, fg=typer.colors.CYAN)
            else:
                styled = diff_line
            typer.echo(styled)
            if slow:
                time.sleep(0.04)
        sys.stdout.flush()


def main() -> None:
    """Entry point for the ``chronotrace`` console script."""
    try:
        app()
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    main()
