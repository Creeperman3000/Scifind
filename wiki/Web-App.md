# Web Application

Flask web app at `webapp.py`. Run with `python webapp.py` and open `http://localhost:5000`.

## Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to `/formulas` |
| `/formulas` | All formulas (default landing) |
| `/quantities` | All quantities |
| `/formula/<id>` | Formula detail with LaTeX, variables, conditions, relations |
| `/quantity/<id>` | Quantity detail with dimensions and units |
| `/unit/<id>` | Unit detail |
| `/search?q=<query>` | Full-text search |
| `/base-units` | Redirect to `/quantities?is_dim=1` (backward-compat; filter uses `formula_item` dimension rows) |
| `/export?format=<fmt>` | Download database export (csv, xlsx, ods) |

## Features

### Filtering
- **Science/Branch/Subbranch/Topic** — Checkboxes in right sidebar. URL params: `science=id1,id2`, `branch=id1`, `subbranch=id1`, `topic=id1`
- **Difficulty** — Range slider. Params: `diff_min`, `diff_max`
- **Dimension** — Dimension filter dropdowns for each SI base dimension
- **Quantity** — Filter formulas by which quantities they contain
- **Base quantities** — Button to filter SI base quantities (filter uses `formula_item` dimension rows)

### Locale Toggle
en-US / en-UK via settings menu. Priority: `?locale=` query param > session cookie > `Accept-Language` header > `en-us`.

### Dimension Mode
Toggle between variable mode (default) and unit mode for formula dimension display. Params: `?dim_mode=var|unit`, stored in session.

### Copy Formula
From the formula detail page: copy as LaTeX, Unicode (via CDN `unicodeit`), or image (via CDN `html-to-image` to PNG).

### Data Management
Export formulas/quantities/units as CSV (zipped), XLSX, or ODS.

## Templates

| File | Purpose |
|------|---------|
| `base.html` | Layout with topbar, sidebars, settings, theme |
| `formula.html` | Formula detail |
| `formulas.html` | Formula listing |
| `quantity.html` | Quantity detail |
| `quantities.html` | Quantity listing |
| `unit.html` | Unit detail |
| `search.html` | Search results |
| `index.html` | Homepage (SI base units landing) |
