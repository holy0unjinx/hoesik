#!/bin/sh
set -eu
git config --global --add safe.directory /repo || true
exec python3 /usr/local/bin/schedule.py
