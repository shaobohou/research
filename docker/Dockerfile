FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# One source of truth for user-local binary dirs
ENV LOCAL_BINS="/home/dev/.npm-global/bin:/home/dev/.local/bin:/home/dev/.claude/bin"
ENV PATH="${LOCAL_BINS}:${PATH}"

# Install essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    iproute2 \
    less \
    man-db \
    net-tools \
    procps \
    psmisc \
    sudo \
    tmux \
 && rm -rf /var/lib/apt/lists/*

# Install Node.js LTS system-wide via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && chmod 644 /usr/share/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user with passwordless sudo
RUN useradd -m dev && echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER dev
WORKDIR /home/dev

# tmux: always use bash as the default shell/command
RUN printf '%s\n' \
  'set-option -g default-shell /bin/bash' \
  'set-option -g default-command "bash"' \
  'set -g default-terminal "screen-256color"' \
  > /home/dev/.tmux.conf

# Make login shells source .bashrc, and re-export PATH from single source
RUN echo 'if [ -f ~/.bashrc ]; then . ~/.bashrc; fi' > /home/dev/.bash_profile \
 && echo 'export PATH="$LOCAL_BINS:$PATH"' >> /home/dev/.bashrc \
 && echo 'export PS1="\[\e[38;5;39m\]\u\[\e[0m\] \[\e[38;5;244m\](\w)\[\e[0m\] $ "' >> /home/dev/.bashrc

# Configure npm to use local prefix
RUN npm config set prefix "/home/dev/.npm-global"

# Install uv (official method)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy entrypoint
COPY --chown=dev:dev entrypoint.sh /usr/local/bin/entrypoint
RUN sudo chmod +x /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["bash"]
