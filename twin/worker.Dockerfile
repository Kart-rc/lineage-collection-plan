FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
WORKDIR /app
COPY requirements.lock pyproject.toml setup.py MANIFEST.in ./
RUN --mount=type=secret,id=registry_ca \
    if [ -f /run/secrets/registry_ca ]; then export PIP_CERT=/run/secrets/registry_ca; fi; \
    pip install --no-cache-dir -r requirements.lock
COPY src ./src
COPY factory/parameters.yaml ./factory/parameters.yaml
COPY factory/specs ./factory/specs
COPY fixtures/otel-demo-3.1.0/aliases.json ./fixtures/otel-demo-3.1.0/aliases.json
COPY code/observed_edges.py ./code/observed_edges.py
RUN --mount=type=secret,id=registry_ca \
    if [ -f /run/secrets/registry_ca ]; then export PIP_CERT=/run/secrets/registry_ca; fi; \
    pip install --no-cache-dir --no-deps . \
    && chmod -R a+rX /app \
    && useradd --uid 1000 --create-home lineage \
    && mkdir /archive /snapshot-archive && chown lineage:lineage /archive /snapshot-archive
ENV LINEAGE_REPO_ROOT=/app
USER lineage
ENTRYPOINT ["python", "-m", "lineage.pipeline"]
