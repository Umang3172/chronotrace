"""Graph construction and ranking, including the properties they must always hold."""

from hypothesis import given, settings
from hypothesis import strategies as st

from chronotrace.capture.fingerprint import compute
from chronotrace.contracts import SpanRecord, TraceCapture
from chronotrace.diagnose.graph import build, is_test_scope, is_third_party
from chronotrace.diagnose.rank import candidates
from chronotrace.diagnose.slice import backward_slice


def _span(name, occurrence, start, *, resource=None, access=None, task="Task-1", parent=None):
    attributes = {"ct.qualname": name}
    if resource:
        attributes["ct.resource"] = resource
    if access:
        attributes["ct.access"] = access
    return SpanRecord(
        span_id=f"{name}{occurrence}",
        parent_span_id=parent,
        name=name,
        occurrence=occurrence,
        start_ns=start,
        end_ns=start + 10,
        task_name=task,
        source_file="tests/test_case.py",
        source_line=1,
        attributes=attributes,
    )


def _capture(outcome, spans, *, complete=True, failing_resource="s.v"):
    return TraceCapture(
        run_id=f"r{outcome}{len(spans)}",
        outcome=outcome,
        fingerprint=compute("tests/test_case.py::test_x"),
        spans=spans,
        complete=complete,
        failing_resource=failing_resource,
    )


def test_spans_with_the_same_name_are_not_collapsed():
    """D-3: name-keyed dicts silently drop every span but the last."""
    graph = build(
        _capture(
            "PASS",
            [
                _span("select", 0, 1, resource="db", access="read"),
                _span("select", 1, 2, resource="db", access="read"),
            ],
        )
    )
    assert sorted(graph.spans) == ["select#0", "select#1"]


def test_graph_has_all_three_edge_kinds():
    """D-2: resource edges alone leave the graph disconnected."""
    spans = [
        _span("outer", 0, 1, resource="s.v", access="write"),
        _span("inner", 0, 2, resource="s.v", access="read", parent="outer0"),
        _span("later", 0, 3, task="Task-1"),
    ]
    graph = build(_capture("PASS", spans))
    kinds = {kind for _, _, data in graph.graph.edges(data=True) for kind in data["kinds"]}
    assert kinds == {"parent_child", "program_order", "resource_access"}


def test_ranking_is_deterministic_across_repeated_calls():
    """D-5: nondeterministic output from a determinism tool is indefensible."""
    passing = [
        _capture(
            "PASS",
            [
                _span("w", 0, 1, resource="s.v", access="write"),
                _span("r", 0, 2, resource="s.v", access="read"),
            ],
        )
    ]
    failing = [
        _capture(
            "FAIL",
            [
                _span("r", 0, 1, resource="s.v", access="read"),
                _span("w", 0, 2, resource="s.v", access="write"),
            ],
        )
    ]
    sliced, _ = backward_slice([build(c) for c in failing + passing], "s.v")
    first = candidates(passing, failing, sliced)
    for _ in range(5):
        again = candidates(passing, failing, sliced)
        assert [c.failing_order for c in again] == [c.failing_order for c in first]


def test_absent_span_in_a_complete_run_orders_last():
    """The write that never happened is evidence, not missing data."""
    passing = [
        _capture(
            "PASS",
            [
                _span("w", 0, 1, resource="s.v", access="write"),
                _span("r", 0, 2, resource="s.v", access="read"),
            ],
        )
    ]
    failing = [_capture("FAIL", [_span("r", 0, 1, resource="s.v", access="read")])]
    sliced, _ = backward_slice([build(c) for c in failing + passing], "s.v")
    found = candidates(passing, failing, sliced)
    assert found and found[0].failing_order == ["r#0", "w#0"]
    assert found[0].ochiai_score == 1.0


def test_absent_span_in_an_incomplete_run_is_unknown_not_absent():
    """D4: a run that crashed before flushing says nothing about what did not run."""
    passing = [
        _capture(
            "PASS",
            [
                _span("w", 0, 1, resource="s.v", access="write"),
                _span("r", 0, 2, resource="s.v", access="read"),
            ],
        )
    ]
    failing = [_capture("FAIL", [_span("r", 0, 1, resource="s.v", access="read")], complete=False)]
    sliced, _ = backward_slice([build(c) for c in failing + passing], "s.v")
    assert candidates(passing, failing, sliced) == []


def test_scope_classification():
    assert is_test_scope("pkg/tests/test_a.py")
    assert is_test_scope("a/conftest.py")
    assert not is_test_scope("app/service.py")
    assert is_third_party("/x/.venv/lib/python3.11/site-packages/lib/a.py")
    assert not is_third_party("app/service.py")


@given(
    starts=st.lists(
        st.integers(min_value=0, max_value=10_000), min_size=1, max_size=12, unique=True
    )
)
@settings(max_examples=50, deadline=None)
def test_observed_order_graph_is_always_acyclic(starts):
    """Edges only ever run forwards in observed time, so a cycle is impossible."""
    import networkx as nx

    spans = [
        _span(f"op{index}", 0, start, resource="s.v", access="write")
        for index, start in enumerate(starts)
    ]
    graph = build(_capture("PASS", spans)).graph
    assert nx.is_directed_acyclic_graph(graph)
    assert not list(nx.selfloop_edges(graph))


@given(starts=st.lists(st.integers(min_value=0, max_value=1000), min_size=2, max_size=8))
@settings(max_examples=50, deadline=None)
def test_reachability_is_transitive(starts):
    spans = [
        _span(f"op{index}", 0, start, resource="s.v", access="read")
        for index, start in enumerate(starts)
    ]
    graph = build(_capture("PASS", spans))
    for left in graph.spans:
        for middle in graph.descendants[left]:
            assert graph.descendants[middle] <= graph.descendants[left]
