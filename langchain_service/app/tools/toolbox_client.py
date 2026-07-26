"""ToolBox (MCP) discovery client — plan 003 Step 2.

The ToolBox is a separate .NET MCP server (sibling repo) reachable only on
the compose network at TOOLBOX_URL (http://toolbox:8080/mcp — the path is
/mcp, not /; hitting / yields an empty tool list, see the plan-003
troubleshooting table).

Design notes (from the Tool_Box walkthrough doc + Stage 2 discussion):

- MultiServerMCPClient is stateless per invocation: every tool call opens a
  fresh MCP session, executes, and cleans up. Nothing is shared, so this is
  safe under gunicorn's multi-process model — no locks, no connection pool
  to manage.
- Discovery is EAGER (Stage 2 A3): called once at pipeline construction.
  If the toolbox is unreachable the service fails at startup — consistent
  with how pgvector is treated (depends_on: service_healthy makes this
  visible in compose ordering, not as a mid-request surprise).
- Adding a toolset to Tool_Box requires zero changes here: whatever the
  server advertises is whatever the agent gets. That's the payoff being
  purchased by this integration.

Finding recorded during Step 2 (pre-answers Stage 2 A2): the adapter builds
StructuredTool instances with ONLY `coroutine=` set (no sync `func=`), so
the tools are async-only. Sync `graph.invoke()` through a ToolNode would
raise; the graph-tools pipeline (Step 3) must therefore run via `ainvoke`.
"""

import asyncio
import os

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


def build_toolbox_client() -> MultiServerMCPClient:
    """Client configured from the environment.

    os.environ[...] (not .get) on purpose: a missing TOOLBOX_URL is a
    deployment error and must fail loudly at startup with a KeyError —
    a silent default would "work" until the first tool call, mid-request.
    """
    return MultiServerMCPClient(
        {
            "toolbox": {
                # Key must be exactly "streamable_http" (verified against
                # langchain-mcp-adapters 0.3.0 sessions.py Literal) — a
                # typo here fails at session time, not construction time.
                "transport": "streamable_http",
                "url": os.environ["TOOLBOX_URL"],
            }
        }
    )


def discover_tools() -> list[BaseTool]:
    """Synchronous startup-time wrapper around the async discovery call.

    asyncio.run() is safe HERE because this runs once at module-import /
    pipeline-construction time, where no event loop exists yet. It would
    NOT be safe inside an async request path (asyncio.run() refuses to
    nest inside a running loop) — request-time execution is Step 3's
    concern, handled with `ainvoke` there.
    """
    return asyncio.run(build_toolbox_client().get_tools())
