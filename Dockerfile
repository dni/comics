# Stage 1: build the SolidJS frontend into static assets (frontend/dist).
# Kept separate so the runtime stage never needs Node at all.
# pinned by digest, not just tag - a mutable tag is one registry/upstream
# compromise away from a poisoned image baked into every deployer's build.
# Update deliberately: `docker pull node:22-slim`, then swap in the new
# Digest it reports (likewise for python:3.12-slim and uv:latest below).
FROM node:22-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# Stage 2: install Python dependencies into a venv. Kept separate from the
# runtime stage so that if a future dependency ever needs a C toolchain to
# build, only this stage grows, not the shipped image.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS builder

COPY --from=ghcr.io/astral-sh/uv:latest@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /usr/local/bin/uv

WORKDIR /app
COPY requirements.txt ./
RUN uv venv .venv && uv pip install -p .venv --no-cache -r requirements.txt


# Stage 3: runtime - no uv, no npm, no compilers. Just the venv and frontend
# build from the stages above, the app's own source, and ImageMagick (the
# import pipeline shells out to `magick`/`convert` - see
# comics_importer/imagemagick.py).
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends imagemagick \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY backend/ ./backend/
COPY comics_importer/ ./comics_importer/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PATH="/app/.venv/bin:${PATH}"
ENV FRONTEND_DIST=/app/frontend/dist

# catalog.db, library/, and import/ all live under here - see the Makefile's
# `run` target, which bind-mounts a host ./data directory to this path so
# the catalog and images survive container restarts/upgrades
ENV DB_PATH=/app/data/catalog.db
ENV LIBRARY_DIR=/app/data/library
ENV IMPORT_DIR=/app/data/import

# overridable at `docker run -e PORT=...` - with --network host (see the
# Makefile's `run` target) there's no docker -p mapping to remap a port
# with, so the app itself must listen on whatever port the host expects
ENV PORT=8000
EXPOSE 8000

# runtime settings (ANTHROPIC_API_KEY, etc. - see .env.example) are read
# from real environment variables, passed with `docker run --env-file .env`;
# no file needs copying in

# non-root by default - limits what a future RCE in this app gains to this
# UID's own permissions, not root on the container. /app/data is created and
# chowned here as a fallback for a plain `docker run` with no bind mount;
# `make run`'s local dev flow overrides this UID at `docker run` time
# (--user, matching the host's own) so its bind-mounted ./data keeps working
# regardless of what's baked in here.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/data && chown -R app:app /app
USER app

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
