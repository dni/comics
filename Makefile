.PHONY: all install frontend-install dev dev-frontend test build run redeploy

IMAGE_NAME = dni256/comics
CONTAINER_NAME = comics
PORT = 8000
GIT_VERSION := $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)

install:
	uv venv .venv
	uv pip install -p .venv -r requirements.txt

frontend-install:
	cd frontend && npm ci

test:
	.venv/bin/python -m unittest discover -s tests

# runs against the same relative ./catalog.db, ./library, ./import used
# throughout local development - the frontend is served separately by the
# Vite dev server (see dev-frontend), not by this process
dev:
	.venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port $(PORT)

dev-frontend:
	cd frontend && npm run dev

build:
	docker build --pull --build-arg GIT_VERSION=$(GIT_VERSION) -t $(IMAGE_NAME) .

ENV_FILE := $(wildcard .env)

run:
	@echo "Restarting container..."
	docker stop $(CONTAINER_NAME) 2>/dev/null || true
	docker rm $(CONTAINER_NAME) 2>/dev/null || true
	mkdir -p data/library data/import
	touch data/catalog.db
	# the whole data/ dir is bind-mounted, not just catalog.db - sqlite needs
	# to create its rollback-journal/WAL companion files in the *same
	# directory* as the db file, and --user (below) only guarantees this
	# host dir is writable by that UID, not /app itself (owned by the
	# image's own baked-in non-root user, whichever UID that happens to
	# be - see Dockerfile). DB_PATH/LIBRARY_DIR/IMPORT_DIR (baked into the
	# image's env) point the app at this mount instead of its defaults.
	docker run --restart always -d --name $(CONTAINER_NAME) \
		--network host \
		--user $(shell id -u):$(shell id -g) \
		-e PORT=$(PORT) \
		$(if $(ENV_FILE),--env-file $(ENV_FILE),) \
		-v $(PWD)/data:/app/data \
		$(IMAGE_NAME)
	@echo "Container $(CONTAINER_NAME) is running at http://localhost:$(PORT)"

# `run` alone reuses whatever image is already tagged locally - it will NOT
# pick up new code on its own. Use this after pulling/making changes so you
# don't end up staring at a stale build wondering why nothing changed.
redeploy: build run
