#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "flask>=3.0.0",
#     "flask-cors>=4.0.0",
# ]
# ///

"""
Web-based UI for Network Firewall Management

Provides a browser-based interface for:
- Real-time network request monitoring
- Interactive rule management
- Statistics and analytics
- Live activity feed
"""

import json
import threading
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Configuration
CONFIG_FILE = Path.home() / "docker-agent-data" / "network-rules.json"
LOG_FILE = Path.home() / "docker-agent-data" / "network-access.log"
WEB_PORT = 8081

app = Flask(__name__)
CORS(app)

# In-memory cache
cache = {"rules": {}, "stats": defaultdict(int), "recent_requests": [], "last_update": None}
cache_lock = threading.Lock()


def load_rules() -> Dict[str, str]:
    """Load rules from config file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rules: {e}")
            return {}
    return {}


def save_rules(rules: Dict[str, str]) -> bool:
    """Save rules to config file"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(rules, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving rules: {e}")
        return False


def parse_log_line(line: str) -> Optional[Dict]:
    """Parse a log line into structured data"""
    try:
        parts = line.strip().split(" | ")
        if len(parts) >= 4:
            return {
                "timestamp": parts[0],
                "decision": parts[1].strip(),
                "method": parts[2].strip(),
                "url": parts[3].strip(),
            }
    except Exception:
        pass
    return None


def load_recent_logs(limit: int = 100) -> List[Dict]:
    """Load recent requests from log file"""
    if not LOG_FILE.exists():
        return []

    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()

        # Get last N lines
        recent_lines = lines[-limit:] if len(lines) > limit else lines

        # Parse each line
        requests = []
        for line in reversed(recent_lines):
            parsed = parse_log_line(line)
            if parsed:
                requests.append(parsed)

        return requests
    except Exception as e:
        print(f"Error loading logs: {e}")
        return []


def calculate_stats() -> Dict:
    """Calculate statistics from log file"""
    stats = defaultdict(int)

    if not LOG_FILE.exists():
        return dict(stats)

    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                parsed = parse_log_line(line)
                if parsed:
                    stats["total"] += 1
                    stats[parsed["decision"].lower()] += 1
    except Exception as e:
        print(f"Error calculating stats: {e}")

    return dict(stats)


def update_cache():
    """Update in-memory cache from files"""
    with cache_lock:
        cache["rules"] = load_rules()
        cache["stats"] = calculate_stats()
        cache["recent_requests"] = load_recent_logs(100)
        cache["last_update"] = datetime.now().isoformat()


# Background thread to update cache periodically
def cache_updater():
    """Background thread to refresh cache"""
    while True:
        try:
            update_cache()
        except Exception as e:
            print(f"Cache update error: {e}")
        time.sleep(2)  # Update every 2 seconds


# Start background updater
updater_thread = threading.Thread(target=cache_updater, daemon=True)
updater_thread.start()


# API Routes


@app.route("/")
def index():
    """Serve the main UI"""
    return send_from_directory(".", "web-ui.html")


@app.route("/api/rules", methods=["GET"])
def get_rules():
    """Get all firewall rules"""
    with cache_lock:
        return jsonify({"rules": cache["rules"], "count": len(cache["rules"]), "last_update": cache["last_update"]})


@app.route("/api/rules", methods=["POST"])
def add_rule():
    """Add or update a firewall rule"""
    data = request.json
    target = data.get("target")
    action = data.get("action")

    if not target or not action:
        return jsonify({"error": "Missing target or action"}), 400

    if action not in ["allow", "deny", "allow-domain", "deny-domain"]:
        return jsonify({"error": "Invalid action"}), 400

    with cache_lock:
        rules = cache["rules"].copy()
        rules[target] = action

        if save_rules(rules):
            cache["rules"] = rules
            return jsonify({"success": True, "target": target, "action": action})
        else:
            return jsonify({"error": "Failed to save rules"}), 500


@app.route("/api/rules/<path:target>", methods=["DELETE"])
def delete_rule(target):
    """Delete a firewall rule"""
    with cache_lock:
        rules = cache["rules"].copy()

        if target in rules:
            del rules[target]
            if save_rules(rules):
                cache["rules"] = rules
                return jsonify({"success": True, "target": target})
            else:
                return jsonify({"error": "Failed to save rules"}), 500
        else:
            return jsonify({"error": "Rule not found"}), 404


@app.route("/api/rules/clear", methods=["POST"])
def clear_rules():
    """Clear all firewall rules"""
    with cache_lock:
        if save_rules({}):
            cache["rules"] = {}
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to clear rules"}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get network access statistics"""
    with cache_lock:
        return jsonify({"stats": cache["stats"], "last_update": cache["last_update"]})


@app.route("/api/requests", methods=["GET"])
def get_requests():
    """Get recent network requests"""
    limit = request.args.get("limit", 100, type=int)

    with cache_lock:
        return jsonify(
            {
                "requests": cache["recent_requests"][:limit],
                "count": len(cache["recent_requests"]),
                "last_update": cache["last_update"],
            }
        )


@app.route("/api/stream", methods=["GET"])
def stream_updates():
    """Server-Sent Events stream for live updates"""

    def generate():
        last_count = 0
        while True:
            with cache_lock:
                current_count = len(cache["recent_requests"])
                if current_count != last_count:
                    data = {
                        "requests": cache["recent_requests"][:10],
                        "stats": cache["stats"],
                        "timestamp": cache["last_update"],
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_count = current_count
            time.sleep(1)

    return app.response_class(
        generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.route("/api/export", methods=["GET"])
def export_rules():
    """Export rules as JSON"""
    with cache_lock:
        return jsonify(cache["rules"])


@app.route("/api/import", methods=["POST"])
def import_rules():
    """Import rules from JSON"""
    data = request.json

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid format, expected JSON object"}), 400

    # Validate all actions
    for target, action in data.items():
        if action not in ["allow", "deny", "allow-domain", "deny-domain"]:
            return jsonify({"error": f"Invalid action for {target}: {action}"}), 400

    with cache_lock:
        if save_rules(data):
            cache["rules"] = data
            return jsonify({"success": True, "count": len(data)})
        else:
            return jsonify({"error": "Failed to save rules"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "proxy_running": True,  # TODO: Actually check if proxy is running
            "rules_count": len(cache["rules"]),
            "timestamp": datetime.now().isoformat(),
        }
    )


if __name__ == "__main__":
    print("=" * 80)
    print("Network Firewall Web UI")
    print("=" * 80)
    print(f"Starting web server on http://0.0.0.0:{WEB_PORT}")
    print(f"Rules file: {CONFIG_FILE}")
    print(f"Log file: {LOG_FILE}")
    print()
    print(f"Open in browser: http://localhost:{WEB_PORT}")
    print("=" * 80)
    print()

    # Initial cache load
    update_cache()

    # Run Flask app
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False, threaded=True)
