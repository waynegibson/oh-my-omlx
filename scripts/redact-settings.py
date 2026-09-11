#!/usr/bin/env python3
"""git clean filter for base/settings.json: strip credentials before they reach the index.

Wired up via .gitattributes (filter=redact-secrets) and, per clone:
    git config filter.redact-secrets.clean 'python3 scripts/redact-settings.py'
    git config filter.redact-secrets.required true
The working copy is untouched; only the committed blob is redacted. The server
regenerates auth.secret_key on first start when it is null.
"""
import json
import sys

raw = sys.stdin.read()
data = json.loads(raw)
auth = data.get("auth")
if isinstance(auth, dict):
    for field in ("api_key", "secret_key"):
        if field in auth:
            auth[field] = None
sys.stdout.write(json.dumps(data, indent=2) + ("\n" if raw.endswith("\n") else ""))
