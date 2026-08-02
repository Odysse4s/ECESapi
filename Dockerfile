# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
# Install build deps into a virtual-env so we can copy it cleanly.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir .

COPY . .
RUN /opt/venv/bin/pip install --no-cache-dir .


# ── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="Odysseas Avdikos"
LABEL description="ECES API — Ephemeral Code Execution Sandbox"

# The API process itself does NOT need root, but it DOES need access to
# the Docker socket (mounted as a volume) so we run as root inside this
# container.  The *sandbox* containers run as uid 1000.
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY . .

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
