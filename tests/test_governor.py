"""One test per policy rule, driven by the adversarial gauntlet (spec 24).

The governor is the differentiator, so its test suite is adversarial by
construction: every attack is a patch that makes the test green while leaving
the race in place.
"""

import pytest

from chronotrace.govern.gate import RULES, review
from chronotrace.govern.gauntlet import ATTACKS


@pytest.mark.parametrize("attack", ATTACKS, ids=lambda a: f"{a.rule_id}-{a.name}")
def test_attack_is_rejected_by_its_own_rule(attack):
    verdict = review(before=attack.before, after=attack.after, path=attack.path)
    failed = {rule.rule_id for rule in verdict.rules_evaluated if not rule.passed}
    assert not verdict.approved, f"{attack.name} was approved"
    assert attack.rule_id in failed, f"{attack.name} was caught by {failed}, not {attack.rule_id}"


def test_every_rule_has_at_least_one_attack():
    """A rule with no attack against it is a rule nobody has tested."""
    covered = {attack.rule_id for attack in ATTACKS}
    uncovered = set(RULES) - covered - {"S2", "S4"}
    assert not uncovered, f"rules without an adversarial test: {sorted(uncovered)}"


def test_legitimate_synchronisation_patch_is_approved():
    before = (
        "import asyncio\n\n"
        "STORE = {}\n\n\n"
        "async def writer():\n"
        "    STORE['v'] = 1\n\n\n"
        "async def reader():\n"
        "    return STORE.get('v')\n"
    )
    after = (
        "import asyncio\n\n"
        "STORE = {}\n"
        "_gate = asyncio.Event()\n\n\n"
        "async def writer():\n"
        "    STORE['v'] = 1\n"
        "    _gate.set()\n\n\n"
        "async def reader():\n"
        "    await _gate.wait()\n"
        "    return STORE.get('v')\n"
    )
    verdict = review(before=before, after=after, path="tests/test_x.py")
    assert verdict.approved
    assert verdict.positive_check_passed
    assert not verdict.deadlock_cycle_detected


def test_production_scope_requires_opt_in():
    before = "async def f():\n    return 1\n"
    after = (
        "import asyncio\n\n_gate = asyncio.Event()\n\n\n"
        "async def f():\n    await _gate.wait()\n    return 1\n\n\n"
        "async def g():\n    _gate.set()\n"
    )
    blocked = review(before=before, after=after, path="app/service.py")
    assert blocked.scope_violation
    allowed = review(
        before=before, after=after, path="app/service.py", allow_production_repair=True
    )
    assert not allowed.scope_violation


def test_unparseable_patch_is_rejected_before_anything_else():
    verdict = review(before="x = 1\n", after="def broken(:\n", path="tests/test_x.py")
    assert not verdict.approved
    failed = {rule.rule_id for rule in verdict.rules_evaluated if not rule.passed}
    assert failed == {"S4"}


def test_preexisting_sleep_does_not_block_an_unrelated_repair():
    """Rules compare before and after: what is forbidden is the patch *adding* one."""
    before = (
        "import asyncio\n\n"
        "async def slow():\n"
        "    await asyncio.sleep(1)\n\n\n"
        "async def reader():\n"
        "    return 1\n"
    )
    after = (
        "import asyncio\n\n"
        "_gate = asyncio.Event()\n\n\n"
        "async def slow():\n"
        "    await asyncio.sleep(1)\n"
        "    _gate.set()\n\n\n"
        "async def reader():\n"
        "    await _gate.wait()\n"
        "    return 1\n"
    )
    assert review(before=before, after=after, path="tests/test_x.py").approved
