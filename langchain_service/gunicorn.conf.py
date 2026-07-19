"""Gunicorn config (auto-loaded from cwd). Plan 002 Step 4.

One job: when a worker dies, tell prometheus_client's multiprocess machinery
so the dead worker's mmap files get marked and its gauge/counter state isn't
reported forever. Without this, worker restarts slowly pollute /metrics.
"""

from prometheus_client import multiprocess


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
