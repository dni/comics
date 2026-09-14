# Comics Catalog

A self-hosted comic book cataloging app. Drop scans/photos into an import
folder (or upload from the browser), and it uses ImageMagick to clean up and
optimize each image and Claude's vision API to identify series, issue, year,
publisher, condition, and an estimated numeric grade — then renames, organizes,
and catalogs the result in a local SQLite database.

## Features

- Drag-and-drop or folder-based import, with automatic crop/rotate suggestions
  you can fine-tune by hand
- AI-assisted metadata identification (series, issue, year, publisher,
  condition, numeric grade) via Claude, with a reclassify action if it got
  something wrong
- Duplicate-copy detection (same series/issue already in your catalog)
- Failed-import queue with retry
- CSV export and full backup download
- Optional "for sale" flagging with a public listing page and eBay sold-listing
  lookup / suggested listing text
- Single-admin session auth (set up on first launch)

## Local development

Requires [ImageMagick](https://imagemagick.org/) on `PATH`, Python 3.12+,
[`uv`](https://github.com/astral-sh/uv), and Node.js for the frontend.

```sh
make install            # creates .venv, installs backend deps
make frontend-install    # npm ci in frontend/
cp .env.example .env     # set ANTHROPIC_API_KEY

make dev                 # backend on :8000
make dev-frontend         # Vite dev server on :5173 (proxies API to :8000)
```

Run tests with:

```sh
make test
```

## Docker

A prebuilt image is published to Docker Hub as `dni256/comics`.

```sh
docker build --pull -t dni256/comics .    # or: make build
```

Run it with the data directory (SQLite DB, library, import folder) bind-mounted
to the host so it persists across container restarts/upgrades:

```sh
mkdir -p data/library data/import
touch data/catalog.db

docker run --restart always -d --name comics \
  --network host \
  --user "$(id -u):$(id -g)" \
  -e PORT=8000 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  dni256/comics
```

The app will be available at `http://localhost:8000`. On first launch it
prompts you to create the admin username/password.

Equivalently, `make run` does the same thing (stopping/removing any existing
`comics` container first).
