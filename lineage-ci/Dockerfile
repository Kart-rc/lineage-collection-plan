FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/lineage
COPY pyproject.toml setup.py MANIFEST.in ./
COPY src ./src
COPY factory/parameters.yaml ./factory/parameters.yaml
COPY factory/specs ./factory/specs
COPY factory/work-packages/WP-29-model-assisted-extractor-for-opaque-units-with-a.md ./factory/work-packages/
RUN --mount=type=secret,id=registry_ca \
    if [ -f /run/secrets/registry_ca ]; then export PIP_CERT=/run/secrets/registry_ca; fi; \
    chmod -R a+rX factory && \
    pip install --no-cache-dir PyYAML==6.0.3 jsonschema==4.26.0 confluent-kafka==2.12.2 && pip install --no-cache-dir --no-deps .
ENV LINEAGE_REPO_ROOT=/opt/lineage
WORKDIR /repo
ENTRYPOINT ["lineage-ci"]
