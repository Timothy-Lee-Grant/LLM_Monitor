#!/usr/bin/env bash
# Recovery for the OpenWebUI WEBUI_AUTH=false auto-provision race.
#
# Background: when WEBUI_AUTH=false, OpenWebUI's own backend (routers/auths.py,
# signin()) auto-creates an admin@localhost account on first use via a
# check-then-act sequence (get_user_by_email -> has_users -> signup_handler)
# that isn't guarded by a lock or a unique constraint. If a few requests land
# concurrently on first boot (e.g. more than one browser tab open to the page),
# each can pass the check before any of them commit, producing several
# admin@localhost rows that all land on role=pending — with no admin account
# left to approve any of them from the Admin Panel.
#
# This is an upstream OpenWebUI bug (see
# Documentation/AI_Implementation_Plans/002, Finding 2) — it lives in the
# vendored image, not in this repo, so it can't be fixed here. This script
# is the idempotent workaround: it inspects the running container's SQLite
# db and, if it finds the stuck state (zero admins, one or more pending
# admin@localhost rows), promotes the oldest such row to admin and removes
# the rest. Safe to run any time; it's a no-op if an admin already exists.
#
# Usage:
#   bash scripts/fix_openwebui_admin.sh

set -uo pipefail

CONTAINER="openwebui"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "FAIL: container '$CONTAINER' is not running"
    exit 1
fi

docker exec "$CONTAINER" python3 -c "
import sqlite3

conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()

cur.execute(\"SELECT id, role, created_at FROM user WHERE email = 'admin@localhost' ORDER BY created_at ASC\")
rows = cur.fetchall()

if not rows:
    print('No admin@localhost account found yet - nothing to do.')
elif any(role == 'admin' for _, role, _ in rows):
    print(f'OK: admin@localhost already has role=admin ({len(rows)} row(s) total) - no-op.')
else:
    keep_id = rows[0][0]
    cur.execute(\"UPDATE user SET role = 'admin' WHERE id = ?\", (keep_id,))
    cur.execute(\"DELETE FROM user WHERE email = 'admin@localhost' AND id != ?\", (keep_id,))
    deleted_user = cur.rowcount
    cur.execute(\"DELETE FROM auth WHERE email = 'admin@localhost' AND id != ?\", (keep_id,))
    deleted_auth = cur.rowcount
    conn.commit()
    print(f'FIXED: promoted {keep_id} to admin; removed {deleted_user} duplicate user row(s) and {deleted_auth} duplicate auth row(s).')
"
