# Excel report exports

Inventory value history and the free inventory health checker offer Excel alongside
their existing CSV downloads. Snapshot leads use the same openpyxl reporting service
for their existing administrator-only Excel export. Purchase orders and other reports
already have formatted ExcelJS exports and retain that implementation. CSV import
templates remain CSV.

Each new workbook contains a summary with native editable Excel charts and a
filterable detail table with frozen headers, typed dates/numbers, currency labels,
and explicit missing-value handling. Formula-like identifiers are stored as literal
text, including leading-zero SKUs. Summary formulas recalculate when opened in Excel;
chart category caches preserve labels in spreadsheet previews.

`POST /exports/workbook.xlsx` is a stateless formatter for explicitly submitted
report results. It does not retrieve database records, fetch URLs, or persist inputs.
The public health checker still analyzes CSV locally. Its Excel button explains that
formatting sends results to Skubase; its CSV download stays local. Sample workbooks
are labeled in both their filename and summary. Existing protected lead endpoints
retain their authorization requirements.

The formatter accepts at most 1 MB, 365 history points or 1,000 health-check rows,
rejects malformed/nonfinite inputs, and permits two concurrent builds per process.
Busy responses return 503 and Retry-After; clients retain their CSV fallback. Responses
are marked no-store. No new dependencies or environment variables are required.

Verification:

- Backend: `python -m unittest tests.test_spreadsheet_exports -v`
- Frontend: `node --test tests/spreadsheet-export.test.cjs tests/inventory-health-check.test.cjs tests/report-export-financials.test.cjs`
- Frontend: `npm run typecheck` and `npm run build`

Workbook tests cover date/number preservation, unknown versus zero values, literal
identifiers, native chart references, empty lead data, bounded inputs, HTTP responses,
and release of concurrency permits after failures. Visual previews use synthetic data.
