#!/bin/bash
set -euo pipefail

# Track installation failures
FAILED_INSTALLS=()

# Error handling function
log_error() {
  local tool="$1"
  local message="$2"
  echo "ERROR [$tool] $message" >&2
  FAILED_INSTALLS+=("$tool")
}

# ============================================================================
# NETWORK MONITORING: Install mitmproxy CA certificate
# ============================================================================
if [ "${NETWORK_MONITORING:-false}" = "true" ]; then
  if [ -f "/tmp/mitmproxy-ca-cert.pem" ]; then
    echo "[mitmproxy] Installing CA certificate for HTTPS interception…"

    # Install certificate in system trust store
    sudo cp /tmp/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt
    sudo update-ca-certificates --fresh > /dev/null 2>&1

    # Set environment variables for tools that need explicit CA bundle
    export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
    export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

    # Persist CA bundle environment variables for shell sessions
    cat >> /home/dev/.bashrc << 'EOF'
# mitmproxy CA certificate (for HTTPS interception)
export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
EOF

    echo "[mitmproxy] ✓ CA certificate installed"
  else
    echo "[mitmproxy] WARNING: CA certificate not found, HTTPS may fail" >&2
  fi
fi

echo "========================================"
echo "Checking tools (install/update as needed)…"
echo "========================================"

# --- Claude Code (native installer) ---
if command -v claude >/dev/null 2>&1; then
  echo "[claude] Found at: $(command -v claude)"
  echo "[claude] Version: $(claude --version 2>/dev/null || echo 'unknown')"
  echo "[claude] Updating…"
  if ! claude update; then
    echo "[claude] Update failed, reinstalling…"
    if ! curl -fsSL https://claude.ai/install.sh | bash; then
      log_error "claude" "Reinstallation failed"
    fi
  fi
else
  echo "[claude] Installing via native installer…"
  if ! curl -fsSL https://claude.ai/install.sh | bash; then
    log_error "claude" "Installation failed"
  fi
fi

# --- uv (verify presence) ---
if ! command -v uv >/dev/null 2>&1; then
  echo "[uv] Installing…"
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
    log_error "uv" "Installation failed"
  fi
fi
if command -v uv >/dev/null 2>&1; then
  echo "[uv] Version: $(uv --version 2>/dev/null || echo 'unknown')"
else
  echo "[uv] Not available"
fi

# --- Codex CLI (OpenAI) ---
if ! command -v codex >/dev/null 2>&1; then
  echo "[codex] Installing '@openai/codex'…"
  if ! npm install -g @openai/codex; then
    log_error "codex" "npm installation failed"
  fi
else
  echo "[codex] Found: $(codex --version 2>/dev/null || echo 'version unknown')"
fi

# --- Gemini CLI (Google) ---
if ! command -v gemini >/dev/null 2>&1; then
  echo "[gemini] Installing '@google/gemini-cli'…"
  if ! npm install -g @google/gemini-cli; then
    log_error "gemini" "npm installation failed"
  fi
else
  echo "[gemini] Found: $(gemini --version 2>/dev/null || echo 'version unknown')"
fi

echo "========================================"
echo "Claude:  $(claude --version 2>/dev/null || echo 'not installed')"
echo "uv:      $(uv --version 2>/dev/null || echo 'not installed')"
echo "codex:   $(command -v codex >/dev/null 2>&1 && codex --version 2>/dev/null || echo 'not installed')"
echo "gemini:  $(command -v gemini >/dev/null 2>&1 && gemini --version 2>/dev/null || echo 'not installed')"
echo "========================================"

# Report installation failures
if [ ${#FAILED_INSTALLS[@]} -gt 0 ]; then
  echo ""
  echo "WARNING: The following installations failed:"
  for tool in "${FAILED_INSTALLS[@]}"; do
    echo "  - $tool"
  done
  echo ""
  echo "The container will continue, but some tools may not be available."
  echo "Check the logs above for specific error details."
  echo "========================================"
fi

# Execute provided command (default: bash)
exec "$@"
