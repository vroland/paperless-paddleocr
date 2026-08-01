# Paperless PaddleOCR

Paperless-ngx parser plugin that delegates PDF and image OCR to a separately
deployed PaddleOCR-VL service. It sends supported documents to the service's
`/layout-parsing` endpoint and returns normalized text for Paperless search.
The plugin does not bundle or run OCR models itself.

## Components

- **Paperless-ngx** imports, stores, and indexes documents, then selects this
  parser for supported PDFs and images.
- **paperless-paddleocr** sends the document to PaddleOCR-VL and converts its
  layout-parsing response into searchable text.
- **PaddleOCR-VL service** runs separately and must expose a reachable
  `/layout-parsing` HTTP endpoint. Configure its URL with
  `PAPERLESS_PADDLEOCR_URL`; it owns the OCR model and any service-specific
  configuration.

## Local development

The development stack runs Paperless with SQLite and Valkey locally. It
requires a reachable PaddleOCR-VL service; set `PAPERLESS_PADDLEOCR_URL` in
`dev/.env` before starting the stack.

1. Copy the local configuration and set `PAPERLESS_TAG` to the image version
   deployed in production.

   ```bash
   cp dev/.env.example dev/.env
   ```

2. Start the isolated development stack.

   ```bash
   make dev-up
   ```

3. Open `http://127.0.0.1:8000` and sign in with the credentials in
   `dev/.env`.

4. Place a synthetic fixture in `dev/consume/`. Paperless consumes it locally
   and the parser submits it to the remote PaddleOCR service.

5. Restart Paperless after changing parser code. The package is installed in
   the image, while the source directory is bind-mounted for live edits, so no
   image rebuild is required.

   ```bash
   make dev-restart
   ```

Use `make dev-reset` to remove only local development volumes. It does not
touch production Paperless data or the remote OCR services.

## Tests

```bash
uv sync --group dev
uv run ruff format --check .
uv run ruff check .
uv run mypy --show-error-codes --warn-unused-configs src/
uv run pytest -q
```

Tests must not contact a real PaddleOCR service. Real-service checks are
manual and should use synthetic fixtures only.

## Paperless API checks

The optional `paperless` dependency group installs the actual Paperless-ngx
`v3.0.4` source and its dependencies. It is intentionally separate from the
ordinary test group because Paperless has a large dependency set.

```bash
uv sync --group paperless
uv run --group paperless python -c "import documents, paperless; print(paperless.__file__)"
make paperless-test
```
