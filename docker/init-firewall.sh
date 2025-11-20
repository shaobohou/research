#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting firewall initialization...${NC}"

# Function to validate CIDR notation
is_valid_cidr() {
    local cidr=$1
    if [[ $cidr =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$ ]]; then
        return 0
    fi
    return 1
}

# Function to validate IP address
is_valid_ip() {
    local ip=$1
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        return 0
    fi
    return 1
}

# Preserve Docker DNS rules
echo -e "${YELLOW}Preserving Docker DNS rules...${NC}"
DOCKER_DNS_RULES=$(iptables-save | grep 'docker.*53' || true)

# Flush existing rules
echo -e "${YELLOW}Flushing existing iptables rules...${NC}"
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Restore Docker DNS rules
if [ -n "$DOCKER_DNS_RULES" ]; then
    echo -e "${YELLOW}Restoring Docker DNS rules...${NC}"
    echo "$DOCKER_DNS_RULES" | iptables-restore -n || true
fi

# Create ipset for allowed domains
echo -e "${YELLOW}Creating ipset for allowed domains...${NC}"
ipset destroy allowed-domains 2>/dev/null || true
ipset create allowed-domains hash:net

# Allow localhost
echo -e "${YELLOW}Allowing localhost...${NC}"
ipset add allowed-domains 127.0.0.0/8

# Allow host network (typically 172.17.0.0/16 for Docker)
HOST_SUBNET=$(ip route | grep default | awk '{print $3}' | cut -d. -f1-3).0/24
if is_valid_cidr "$HOST_SUBNET"; then
    echo -e "${YELLOW}Allowing host subnet: $HOST_SUBNET${NC}"
    ipset add allowed-domains "$HOST_SUBNET"
fi

# Fetch GitHub IP ranges
echo -e "${YELLOW}Fetching GitHub IP ranges...${NC}"
GITHUB_IPS=$(curl -s https://api.github.com/meta | jq -r '.git[],.web[],.api[]' | sort -u)
for ip in $GITHUB_IPS; do
    if is_valid_cidr "$ip"; then
        ipset add allowed-domains "$ip" 2>/dev/null || true
    fi
done

# Resolve and add specific domains
DOMAINS=(
    "registry.npmjs.org"
    "api.anthropic.com"
    "console.anthropic.com"
    "sentry.io"
    "update.code.visualstudio.com"
    "vscode.download.prss.microsoft.com"
    "marketplace.visualstudio.com"
    "pypi.org"
    "files.pythonhosted.org"
)

echo -e "${YELLOW}Resolving and adding domain IPs...${NC}"
for domain in "${DOMAINS[@]}"; do
    echo -e "  Resolving $domain..."
    IPS=$(dig +short "$domain" A | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)
    for ip in $IPS; do
        if is_valid_ip "$ip"; then
            ipset add allowed-domains "$ip/32" 2>/dev/null || true
        fi
    done
done

# Set default policies
echo -e "${YELLOW}Setting default firewall policies...${NC}"
iptables -P INPUT ACCEPT
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow established and related connections
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow DNS queries
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow SSH
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT

# Allow traffic to allowed domains
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# Log dropped packets (optional, for debugging)
# iptables -A OUTPUT -j LOG --log-prefix "FIREWALL-DROP: " --log-level 4

# Drop everything else
iptables -A OUTPUT -j DROP

echo -e "${GREEN}Firewall rules applied successfully!${NC}"

# Validation tests
echo -e "${YELLOW}Running validation tests...${NC}"

# Test 1: GitHub should be accessible
if curl -s --connect-timeout 5 https://api.github.com >/dev/null 2>&1; then
    echo -e "${GREEN}✓ GitHub API is accessible${NC}"
else
    echo -e "${RED}✗ GitHub API is NOT accessible${NC}"
fi

# Test 2: example.com should NOT be accessible
if curl -s --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo -e "${RED}✗ example.com is accessible (should be blocked)${NC}"
else
    echo -e "${GREEN}✓ example.com is blocked (as expected)${NC}"
fi

echo -e "${GREEN}Firewall initialization complete!${NC}"
