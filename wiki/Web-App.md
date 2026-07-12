# Web Application

Flask web app at `webapp.py`. Run with `python webapp.py` and open
`http://localhost:5000`.

## Routes

| Route | Description |
|-------|-------------|
| `/` | Redirects to `/formulas` |
| `/formulas` | All formulas (default landing) |
| `/quantities` | All quantities |
| `/formula/<id>` | Formula detail with LaTeX, variables, relations |
| `/quantity/<id>` | Quantity detail with dimensions and units |
| `/unit/<id>` | Unit detail |
| `/search?q=<query>` | Substring search |
| `/api/search-suggestions?q=<query>` | JSON suggestions for autocomplete |
| `/base-units` | Redirect to `/quantities?is_dim=1` |
| `/export?format=<fmt>` | Download database export (csv, xlsx, ods) |

## Features

### Filtering
- **Science/Branch/Topic** — Checkboxes in right sidebar. URL param: `ids=id1,id2,…`
- **Difficulty** — Range slider. Params: `diff_min`, `diff_max`
- **Dimension** — Per-dimension operator filter (eq / ≥ / ≤). Params: `<symbol>_eq`, `<symbol>_geq`, `<symbol>_leq`. Combine with `dim_mode=and|or`.
- **Quantity** — Filter formulas by which quantities they contain. Params: `qty=id1,id2`. Combine with `qty_mode=and|or` (or `fml_mode` on `/formulas`).
- **Base quantities** — `is_dim=1` filter on `/quantities` shows only SI base quantities.

### Locale Toggle
`en-us` / `en-uk` / `cs-cz` via settings menu. Priority: `?locale=` query
param > session cookie > `Accept-Language` header > `en-us`.

### Dimension Mode
Toggle between dimension (default), variable, and unit display. Param:
`?dim_mode=dim|var|unit`, stored in session.

### Data Management
Export formulas/quantities/units as CSV (zipped directory), XLSX, or ODS.

## Templates

| File              | Purpose                                       |
| ----------------- | --------------------------------------------- |
| `base.html`       | Layout with topbar, sidebars, settings, theme |
| `formula.html`    | Formula detail                                |
| `formulas.html`   | Formula listing                               |
| `quantity.html`   | Quantity detail                               |
| `quantities.html` | Quantity listing                              |
| `unit.html`       | Unit detail                                   |
| `search.html`     | Search results                                |
