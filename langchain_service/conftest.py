"""Shared pytest fixtures (plan 001 Step 9).

Lives at the service root (not in tests/) deliberately: pytest adds a
conftest.py's directory to sys.path, which is what makes `import app...`
resolve no matter where pytest is invoked from.
"""

import os

# Before any app import: tests are mock-mode by definition (no containers),
# and observability is force-disabled so spans/callbacks are true no-ops
# regardless of what the developer's shell environment says.
os.environ["LLM_MODE"] = "mock"
os.environ["OBSERVABILITY_ENABLED"] = "false"

import pytest

from app.api.FlaskServer import create_app


@pytest.fixture()
def client():
    """A fresh Flask test client per test — the application-factory payoff."""
    app = create_app()
    return app.test_client()
