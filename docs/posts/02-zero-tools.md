# A Strands agent with zero tools answers exactly like one with eight

*Second in a series on building ChronoTrace, an agent that repairs
concurrency-induced flaky tests, for the Agents for Humans hackathon.*

I shipped an agent loop, wrote a README section describing its eight tools, and
recorded a demo video narrating what they do. Then I checked, and the agent had
never held a single one.

This is a short post about a failure mode with no symptom, because I think it is
the most likely way for a Strands project to be quietly broken.

## The setup

ChronoTrace investigates a flaky asyncio test. The agent's job is to decide
what evidence to gather and whether the evidence supports a repair at all, so it
gets a tool surface bound to one incident:

```python
class AgentTools:
    def capture_traces(self, runs: int = 20) -> dict[str, Any]:
        """Run the test repeatedly and gather a comparable pass/fail trace pair.

        Args:
            runs: Maximum runs to spend.
        """
        ...

    def force_replay(self, order: list[str], runs: int = 5) -> dict[str, Any]:
        """Force one ordering and report what happened."""
        ...
```

Eight of those, handed to the agent:

```python
return Agent(
    model=BedrockModel(model_id=model_id, region_name=region),
    system_prompt=SYSTEM_PROMPT,
    tools=[
        tools.capture_traces,
        tools.trace_slice,
        tools.compare_orderings,
        tools.force_replay,
        tools.source_context,
        tools.diagnose_now,
        tools.check_patch,
        tools.run_once,
    ],
)
```

Type hints on every argument. Google-style docstrings with an `Args:` block, so
the schema has descriptions. Primitive JSON in and out, because an AgentCore
runtime will happily serialize a rich object into a fallback string and blow
past its payload limit.

It looks right. It is not right.

## The symptom

There isn't one.

```
>>> agent = build_agent(test_id, cwd, settings)
>>> agent.tool_names
[]
```

Zero. The SDK logs one line per tool at construction:

```
tool=<bound method AgentTools.capture_traces of ...> | unrecognized tool specification
```

...and then carries on and builds the agent. No exception. No warning that
survives to the caller. And crucially, **the agent still works** — it still
takes the prompt, still reasons, still returns a well-formed answer about the
flaky test. A model with no tools is not a model that errors. It is a model that
talks.

The missing piece is the `@tool` decorator. Without it, a bound method is just a
callable, and the SDK has no schema to send:

```python
from strands import tool


class AgentTools:
    @tool
    def capture_traces(self, runs: int = 20) -> dict[str, Any]: ...
```

That is the entire fix. `@tool` works fine on instance methods — `self` is
excluded from the generated input schema, and the method stays directly callable
from ordinary Python, so nothing else in the codebase changes:

```
>>> tools.capture_traces.tool_spec["inputSchema"]["json"]
{'properties': {'runs': {'default': 20,
                         'description': 'Maximum runs to spend.',
                         'type': 'integer'}},
 'type': 'object'}
```

## Why nothing caught it

Every mechanism I had was blind to it, and I think this generalises.

**Tests didn't.** The agent module was in my coverage `omit` list, on the
reasonable-sounding grounds that it needs credentials. Tool *registration* needs
no credentials at all — it happens entirely locally, before a single byte goes
to Bedrock. I had excluded the one part that was cheap to test.

**The type checker didn't.** `Agent(tools=[...])` takes a permissive type. A
bound method satisfies it.

**The demo didn't.** This is the one that should worry you. My end-to-end path
never called the agent — it used a single-shot `converse` with a forced tool
choice, which is a perfectly good design and *not an agent loop*. The
Strands code sat there, imported by nothing, described in the README, narrated in
the video. `grep -r build_agent` returned only its own definition.

**Reading the output didn't.** When I finally ran the loop, the model produced a
fluent, plausible paragraph about the flaky test. If I had been checking whether
the answer *looked* right rather than whether the tools *ran*, I would have
shipped it.

## What I'd assert instead

The registration is the thing to test, because it is the thing that fails
silently:

```python
@pytest.mark.parametrize("name", TOOL_NAMES)
def test_every_tool_carries_a_spec(tools, name):
    """An undecorated method has no spec, and Strands drops it without erroring."""
    spec = getattr(getattr(tools, name), "tool_spec", None)
    assert spec is not None, f"{name} would be dropped as an unrecognized tool"


def test_build_agent_registers_every_tool():
    """The whole point: the agent ends up holding all eight, not zero."""
    agent = build_agent(TEST_ID, Path(), Settings(aws_region="us-east-1"))
    assert sorted(agent.tool_names) == sorted(TOOL_NAMES)
```

No credentials, no network, runs in two seconds. And a CLI flag so a reviewer can
check it without an AWS account at all:

```
$ chronotrace agent --demo --dry-run
model  : amazon.nova-pro-v1:0
  tool  capture_traces
  tool  trace_slice
  tool  compare_orderings
  tool  force_replay
  tool  source_context
  tool  diagnose_now
  tool  check_patch
  tool  run_once

8 tools registered; no model contacted (--dry-run)
```

## The second half of the bug

With the tools registered, Nova Pro ran the loop properly: captured traces,
sliced back from the failed assertion, ranked the orderings that differed, forced
the top candidate and got a failure rate of 1.0 — a sufficient condition for the
failure, established rather than guessed. Then it said:

> *"I cannot propose a repair intent for this issue due to the constraints on the
> types of transformations allowed."*

It was right. My system prompt listed what was **forbidden** — sleeps, retries,
timeout inflation, weakened assertions, skips — and never once named what was
**permitted**. There was also no tool that emitted a repair. The loop could
investigate and could ask the governor about source it had no way to produce.

Two things fixed it. A `propose_repair` tool that takes a typed intent, applies
it deterministically, runs it past the policy gate and verifies it by forced
replay. And a prompt that names the two transformations that actually repair
something, plus a sentence I should not have needed to write:

> Do not abstain merely because the forbidden repairs are forbidden.

Nova Pro now closes the loop, including correcting itself when the validator
rejects an incomplete intent:

```
Tool #4: force_replay      → forced failure rate 1.0
Tool #5: propose_repair    → rejected: primitive missing
Tool #6: propose_repair    → governor 15/15, tier FORCED_HARMLESS

7 loop cycles, 18,665 input / 777 output tokens
```

That rejection-and-retry is a better demonstration of an agent loop than a clean
first attempt would have been.

## The general shape

Both halves are the same mistake. An agent that cannot act still produces
output, and output is what I was looking at. If the only thing you check is
whether the answer reads well, an agent with no tools and an agent with no
permission to use them are indistinguishable from an agent that is working.

Assert the capability, not the paragraph.

---

ChronoTrace is MIT-licensed: <https://github.com/Umang3172/chronotrace>
