FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
# Include user-local paths
ENV PATH="/home/dev/.local/bin:/home/dev/.claude/bin:/home/dev/.npm-global/bin:${PATH}"

# Install essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo curl git bash ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS system-wide via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user with passwordless sudo
RUN useradd -m dev && echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Minimal modern prompt
RUN echo 'export PS1="\[\e[38;5;39m\]\u\[\e[0m\] \[\e[38;5;244m\](\w)\[\e[0m\] $ "' >> /home/dev/.bashrc

USER dev
WORKDIR /home/dev

# Configure npm to use local prefix
RUN npm config set prefix "/home/dev/.npm-global"

# Install uv (official method)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy entrypoint
COPY --chown=dev:dev entrypoint.sh /usr/local/bin/entrypoint
RUN sudo chmod +x /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["bash"]
