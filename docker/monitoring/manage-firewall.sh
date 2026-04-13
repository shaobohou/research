#!/usr/bin/env bash
set -euo pipefail

#
# Interactive Network Firewall Management
#
# Use this script to:
# - View network access statistics
# - Add/remove firewall rules
# - Import/export rule configurations
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "${1:-}" = "--stats" ]; then
  # Just show stats
  uv run "$SCRIPT_DIR/network-monitor.py" --stats
else
  # Interactive management
  uv run "$SCRIPT_DIR/network-monitor.py" --manage
fi
