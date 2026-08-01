# Paperless PaddleOCR

Paperless-ngx parser plugin that delegates PDF and image OCR to a separately
deployed PaddleOCR-VL service. It sends OCRmyPDF-rendered page images to the
service's `/layout-parsing` endpoint, returns normalized text for Paperless
search, and produces searchable PDF/PDF-A archives. The plugin does not bundle
or run OCR models itself.

## Components

- **Paperless-ngx** imports, stores, and indexes documents, then selects this
  parser for supported PDFs and images.
- **paperless-paddleocr** stages image inputs as PDFs, sends one rendered page
  image at a time to PaddleOCR-VL, and uses the same normalized response for
  searchable text and the archive text layer.
- **PaddleOCR-VL service** runs separately and must expose a reachable
  `/layout-parsing` HTTP endpoint. Configure its URL with
  `PAPERLESS_PADDLEOCR_URL`; it owns the OCR model and any service-specific
  configuration.

## Native-text PDFs

For PDFs with any extractable native text, the plugin declines parser selection
and lets Paperless use its normal PDF parser and archive policy. Scanned PDFs
and JPEG, PNG, and TIFF images continue to use PaddleOCR-VL. Mixed native-text
and scanned PDFs are deliberately delegated rather than partially re-OCRed.

## Archives

The plugin creates PDF/PDF-A archives using Paperless's configured output type
and color conversion settings. JPEG, PNG, and every frame of a TIFF are first
wrapped as a PDF, so alpha PNGs, missing DPI metadata, and multipage TIFFs are
supported without a visible-page raster replacement.

PaddleOCR-VL is the only recognizer. OCRmyPDF 17.4.2 still requires Tesseract
to be installed for preflight, but Tesseract recognition is never selected.

Paddle's current response contains block geometry but not documented line or
word geometry. Archives therefore have searchable and copyable text with
coarse placement; selection rectangles and copy order can be approximate for
multiline blocks, tables, and vertical text. If any page has invalid geometry,
the plugin retains the complete Paddle text but omits the archive rather than
publish a partial text layer.

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
