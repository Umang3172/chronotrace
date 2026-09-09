"""AgentCore Runtime entrypoint shim.

AgentCore invokes a decorated callable inside a `BedrockAgentCoreApp`, while this
repository's entrypoint is the plain function `chronotrace.agent.graph:handler`
named in `chronotrace/agent/deploy/agentcore.yaml`. This module is the adapter
between those two shapes and nothing more: it forwards the payload unchanged and
returns what the handler returns. There is no fallback path and no canned data —
if the handler raises inside the runtime, the invocation fails, which is the
honest result.

It lives at the repository root rather than beside `agentcore.yaml` because the
runtime launches the entrypoint as a script (`python agentcore_entry.py`), so the
file's own directory is what lands on `sys.path`. At the root that directory is
the bundle root, which is what makes `import chronotrace` and the agent's pytest
subprocesses against `benchmark/cases/` resolve at all.

`cwd` defaults to that same root rather than `"."`, because the agent's tools
shell out to pytest and the runtime's working directory is not guaranteed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp

from chronotrace.agent.graph import handler

BUNDLE_ROOT = Path(__file__).resolve().parent

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """Forward an AgentCore invocation to the real handler, unmodified."""
    payload.setdefault("cwd", str(BUNDLE_ROOT))
    return handler(payload)


if __name__ == "__main__":
    app.run()
