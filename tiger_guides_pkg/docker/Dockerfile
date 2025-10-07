# -----------------------------------------------------------------------------
# Stage 1 — Build the off-target C binary
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/tiger_guides
COPY c/offtarget/ c/offtarget/
RUN cd c/offtarget \
    && gcc -O3 -Wall -Wextra -o offtarget_search search.c \
    && mkdir -p /opt/tiger_guides/bin \
    && cp offtarget_search /opt/tiger_guides/bin/offtarget_search \
    && chmod +x /opt/tiger_guides/bin/offtarget_search

# -----------------------------------------------------------------------------
# Stage 2 — Package install & runtime image
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      libbz2-dev \
      liblzma-dev \
      zlib1g-dev \
      curl \
      unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/tiger_guides/bin/offtarget_search /usr/local/bin/offtarget_search

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY c/offtarget/ c/offtarget/
COPY docker/entrypoint.sh /entrypoint.sh

RUN pip install --upgrade pip \
    && pip install . \
    && rm -rf /root/.cache/pip

RUN useradd --create-home --shell /bin/bash tiger \
    && mkdir -p /work /references \
    && chown tiger:tiger /work /references

WORKDIR /work
USER tiger

ENV TIGER_GUIDES_REFERENCE_DIR=/references
ENV PATH="/home/tiger/.local/bin:${PATH}"

# Pre-populate smoke-test outputs (soft failure tolerated)
RUN tiger-guides smoke || true

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tiger-guides", "smoke"]
