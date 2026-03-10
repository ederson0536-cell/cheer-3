# Mulch Self Improver skill — robust docker-test
FROM node:20-alpine

# Bash needed for activator.sh, error-detector.sh, extract-skill.sh
RUN apk add --no-cache bash

WORKDIR /skill

COPY SKILL.md .
COPY hooks/openclaw/handler.js hooks/openclaw/
COPY scripts/ scripts/

RUN chmod +x scripts/*.sh scripts/benchmark/*.sh

# Default: robust test. Pass "benchmark" to run side-by-side vs baseline (Self Improving Agent — Rank #2 on ClawHub).
# (With "docker run image benchmark", benchmark is $0 when using -c.)
ENTRYPOINT ["/bin/sh", "-c", "if [ \"$0\" = 'benchmark' ]; then exec /skill/scripts/benchmark/run-benchmark.sh /skill; else exec /skill/scripts/docker-test.sh; fi"]
CMD []
