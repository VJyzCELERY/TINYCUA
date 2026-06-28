FROM python:3.12-slim

ARG HERMES_VERSION=0.17.0

# Install system deps for hermes environment probing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir hermes-agent==${HERMES_VERSION}

# Install Node.js so hermes doesn't probe/install on every run
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create judge user
RUN useradd -m -s /bin/bash judge

# Copy judge profile (plain — no custom skills, no tooling)
COPY src/experiment/judge/profiles/judge /home/judge/.hermes/profiles/judge

# Own everything to judge user
RUN chown -R judge:judge /home/judge

USER judge
WORKDIR /home/judge

# Set judge as default profile
RUN hermes profile use judge

CMD ["hermes", "-p", "judge", "-z", "Ready to judge."]
