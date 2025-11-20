FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
# Include user-local paths
ENV PATH="/home/dev/.local/bin:/home/dev/.claude/bin:/home/dev/.npm-global/bin:${PATH}"
# Set environment variables
ENV EDITOR=nano
ENV DEVCONTAINER=true

# Install essentials including firewall tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    aggregate \
    bash \
    ca-certificates \
    curl \
    dnsutils \
    git \
    iproute2 \
    iptables \
    ipset \
    jq \
    less \
    man-db \
    nano \
    net-tools \
    procps \
    psmisc \
    sudo \
 && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS system-wide via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user with passwordless sudo
RUN useradd -m dev && echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Allow dev user to run firewall script without password
RUN echo "dev ALL=(ALL) NOPASSWD: /usr/local/bin/init-firewall.sh" >> /etc/sudoers.d/firewall \
 && chmod 0440 /etc/sudoers.d/firewall

# Minimal modern prompt
RUN echo 'export PS1="\[\e[38;5;39m\]\u\[\e[0m\] \[\e[38;5;244m\](\w)\[\e[0m\] $ "' >> /home/dev/.bashrc

USER dev
WORKDIR /home/dev

# Configure npm to use local prefix
RUN npm config set prefix "/home/dev/.npm-global"

# Install uv (official method)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy scripts
COPY --chown=dev:dev entrypoint.sh /usr/local/bin/entrypoint
RUN sudo chmod +x /usr/local/bin/entrypoint

# Copy firewall initialization script
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN sudo chmod +x /usr/local/bin/init-firewall.sh

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["bash"]
