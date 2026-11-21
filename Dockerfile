# Telegram Business Assistant Bot - Dockerfile for Railway/Render
# Build: docker build --build-arg CLAUDE_VERSION=1.0.58 --build-arg AI_PROVIDER=claude -t tg-business-assistant .
# The CLAUDE_VERSION should match the version verified locally with --check-claude
# AI_PROVIDER: "claude" (installs Claude CLI) or "openrouter" (skips CLI install, smaller image)

FROM python:3.12-slim

# Build args must be declared inside the build stage to be usable in RUN.
ARG CLAUDE_VERSION=1.0.58
ARG AI_PROVIDER=claude

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    PYTHONPATH="/app" \
    PATH="/root/.local/bin:${PATH}"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI only if using claude provider
RUN if [ "$AI_PROVIDER" = "claude" ]; then \
    curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_VERSION}" \
    && claude --version; \
    else echo "Skipping Claude CLI installation (AI_PROVIDER=$AI_PROVIDER)"; fi

# Set working directory
WORKDIR /app

# Install Python dependencies first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the flat repository into a proper Python package.
# Internal imports and relative imports use the assistant.* namespace.
COPY . /app/assistant/
WORKDIR /app/assistant

# Render Web Services also need the port served by bot.py (/health).
EXPOSE 10000

CMD ["python", "-m", "assistant.bot", "--settings-from-env"]