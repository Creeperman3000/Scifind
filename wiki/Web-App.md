# Web Application

Flask app in `webapp.py`, its templates with CSS and JS in `web/`.

```bash
python webapp.py          # http://localhost:5000 or provided URL
```

The DB is created automatically on first run if missing.

## Routes

| Route                               | Description                                          |
| ----------------------------------- | ---------------------------------------------------- |
| `/`                                 | Redirects to `/formulas`                             |
| `/formulas`                         | List of all formulas                                 |
| `/formula/<id>`                     | Formula details                                      |
| `/quantities`                       | List of all quantities                               |
| `/quantity/<id>`                    | Quantity details                                     |
| `/constant/<id>`                    | Constant details                                     |
| `/unit/<id>`                        | Unit details                                         |
| `/base-units`                       | Redirects to `/quantities?base_only=1` (base quantities)|
| `/search?q=<query>`                 | Search across formulas, quantities, units, constants |
| `/api/search-suggestions?q=<query>` | JSON autocomplete suggestions                        |
| `/api/quantities-filter`            | JSON quantity list for the filter chips              |
| `/create`                           | Formula SQL builder and equation parser              |
| `/export?format=<fmt>`              | Download DB as `xlsx`, `ods`, `sql`, or `csv` (see Export below) |

## Export

`/export?format=<fmt>` accepts `csv`, `xlsx`, `ods`, `sql` (default `csv`).
`format=csv` returns a multi-table ZIP archive (`scifind_csv.zip`), not a
single CSV file — use the CLI (`scifind_cli.py export --format csv`) for
plain CSV output to stdout, or `--format csvdir` for per-table files.
The chosen format is remembered in the `sf_export_format` cookie.
Export is rate-limited to 60 requests/minute per client (heaviest endpoint,
strictest tier). Page/API limits per client IP per minute: search, formulas,
quantities, filter-ids, selection-preview 300; suggestions, latex2unicode,
units-column and other light/cached endpoints 600; selection-share,
formula-parse, preview-render, build-sql 200. All 429 responses carry a
`Retry-After` header. Each `SCIFIND_RL_<KEY>` env var overrides one tier
(`SEARCH`, `SUGGEST`, `LATEX`, `UNITS_COLUMN`, `FORMULAS`, `QUANTITIES`,
`FILTER_IDS`, `SEL_PREVIEW`, `EXPORT`, `SHARE`, `CUSTOM`, `PREVIEW`,
`BUILD_SQL`, `LIGHT`).

The `/create` page uses AJAX endpoints (not meant to be called directly):
`POST /create/preview-render`, `POST /create/build-sql`,
`GET /create/token-sidebar`, `GET /create/breadcrumb`,
`GET /create/languages`.

## Query Parameters

### Filtering (`/formulas`, `/quantities`)

| Name        | Parameter                            | Description                                     |
| ----------- | ------------------------------------ | ----------------------------------------------- |
| Tree        | `topics=id1,id2,...`                 | Restrict to tree's nodes (children included)    |
| Difficulty  | `difficulty_min`, `difficulty_max`   | Difficulty range 1-10                           |
| Dimension   | `<dim>_eq`, `<dim>_geq`, `<dim>_leq` | Dimension exponent filter (M, L, T, I, Θ, N, J) |
|             | `dim_mode=and\|or`                   | Do all or any dimensions match                  |
| Quantity    | `qty=id1,id2`                        | Formulas containing these quantities            |
|             | `qty_mode=and\|or`                   | Require all or any quantities                   |
| Base only   | `base_only=1`                        | Only base quantities (`/quantities`)            |
| Sort        | `sort=<key>`                         | Sort order                                      |
| Exclude all | `exclude_all=1`                      | Empty result set (nothing selected)             |
| Selection view | `sel=<token>`, `show_selected=1`   | Selected-only view (single opaque share token) |

### Selection

The working selection set lives in the browsing URL itself: `?sel=` is the
single source of truth (in-memory store mirrors it). Every toggle, edit, or
custom add re-mints the token and `replaceState`s the address bar (debounced);
if a mint exceeds the token budget the change is reverted with an error, so
URL and state can never diverge. Copying the URL always shares the full
selection — no `localStorage`, no import step, no per-tab drift. Bulk adds
(select-all) pack the largest fitting prefix when the list exceeds the token
budget and say how many were added. `?sel=` propagates across SPA navigations including detail pages; a new filter query
keeps `?sel=` but exits the selected-only view. Select mode is session-scoped
UI state, never a URL parameter.

Explicit shares use one versioned token minted by `POST /api/selection-share`:

- `?sel=s2.<base64url(gzip(json))>` embeds the id lists **plus** modified
  formulas (`fo`), custom formulas (`cf`), quantity overrides (`qo`), and
  custom quantities (`cq`) as compact tokens (`["q", qid, sym?, nam?, label?]`,
  `["c", id]`, `["o", id]`, `["n", value]`) and display strings — the receiver
  renders the sender's edited content, not stale DB rows.
  Codec: `scifind_lib/selection.py`. The only budget is the token length
  (8000 chars); id counts are dynamic, not capped.
- Opening `…?sel=<token>` (e.g. `/formulas?sel=…`) imports the set into the
  local store and cleans the address bar. `?sel=…&show_selected=1` renders the
  server-side selected-only list (`/formulas`, `/quantities`).
- The print dialog talks to `POST /api/selection-preview` with the same JSON
  payload (no URL length limits).
- Formula edits use `GET /api/formula-tokens?id=…` (prefill) and
  `POST /api/formula-parse` (equation + overwrites → latex + compact tokens);
  quantity edits use `GET /api/quantity-fields?id=…` (prefill).
- `GET|POST /api/selection-resolve?sel=…` decodes a token back to its payload.

### Sorting

`?sort=` accepts:

- `/formulas`: `id` (default), `name`, `diff_asc`, `diff_desc`, `topic_tree`, `topic_alpha`, `qty`
- `/quantities`: same except `qty`
- `/search`: `relevance` (default), plus all of the above

### Pagination (`/formulas`, `/quantities`, `/search`)

| Parameter   | Description                                                        |
| ----------- | ------------------------------------------------------------------ |
| `page`      | Page number, starting at 1 (default `1`)                           |
| `per_page`  | Items per page, 1–500 (default `100`)                              |

### Locale

`en-us` / `en-uk` / `cs-cz`.
Stored inside a session cookie.
Switchable via the settings menu.

### Dimensions Setting

Toggle how dimensions are shown via the settings menu (stored in the
`sf_dim_mode` cookie + session, not in the URL):

- **Dimensions** `dim` (default): M, L, T, I, Θ, N, J
- **Variables** `var`: m, l, t, i, T, n, Iᵥ
- **Units** `unit`: kg, m, s, A, K, mol, cd

URL `dim_mode` unambiguously means the dimension filter (`and|or`).

## Keyboard shortcuts

Press `?` anywhere (or Settings → Keyboard shortcuts) for the full in-app reference. Summary:

- Global: `/` / `Ctrl+K` search, `[` / `]` (`Ctrl+B` / `Ctrl+Shift+B`) sidebars, `g f` / `g q` / `g c` (`Alt+1` / `Alt+2`) switch views / create, `Esc` closes/clears/cancels a pending `g`/`f`/`c` prefix (5s hint pill).
- Filters (`f` prefix, list pages): `f q` quantity, `f Q` quantity AND/OR toggle, `f d` dimension picker (`m`/`l`/`t`/`i`/`h`/`n`/`j` or `1`–`7`; `e` prefix or `Shift` then `l`/`g`/`e` for ≤/≥/=; `f d f` fills empty dimensions with 0, `f d b` toggles base quantities), `f D` dimension AND/OR toggle, `f s` sort (`q`/`i`/`n`/`d`/`D`/`t`/`T`), `f r <digit>` min difficulty / `f R <digit>` max difficulty (`0` means `10`), `f t` tree walker (`1`–`9` drill, `Enter` toggles, `Esc` re-expands; `f t d` deselects all topics). Picker targets show blue key badges. Pure modifier presses (Shift, Ctrl, Alt, Meta, CapsLock) never cancel a pending prefix.
- Results & details: `j`/`k`/`↑`/`↓` move up/down (blue highlight), `h`/`l`/`←`/`→` move left/right, `Enter` opens, `Tab` focuses links, `m` loads more.
- Copy formula as (`c` prefix): `c l`/`c u`/`c p`/`c v` copy LaTeX/Unicode/PNG/SVG, `c s` formula SQL.
- Clear filter (`c` prefix): `c a` clear all, `c q`/`c d`/`c r`/`c t` clear one filter.
- Create: `g c` opens create, `Ctrl+Enter` continues to SQL, `e` focuses the equation field.

## Configuration

All optional environment variables:

| Variable                | Default                  | Description                                     |
| ----------------------- | ------------------------ | ----------------------------------------------- |
| `SCIFIND_DB`            | `scifind.db`             | Database path                                   |
| `SCIFIND_HOST`          | `127.0.0.1`              | Bind address (dev server)                       |
| `SCIFIND_PORT`          | `5000`                   | Port (dev server)                               |
| `SCIFIND_DEBUG`         | off                      | Flask debug mode (`1`/`true`/`yes`)             |
| `SCIFIND_SECRET_KEY`    | auto-generated           | Session secret, stored in `instance/secret_key` |
| `SCIFIND_MAX_UPLOAD_MB` | `1`                      | Max request body size in MB                     |
| `SCIFIND_COOKIE_SECURE` | off                      | Set `Secure` on session cookies (`1`/`true`/`yes`) |
| `SCIFIND_GITHUB_REPO`   | `Creeperman3000/Scifind` | Repo slug used for reporting issues |
| `SCIFIND_TRUST_PROXY`   | off                      | Trust `X-Forwarded-For` for rate-limit client IP (`1`/`true`/`yes`, only behind a known reverse proxy) |
| `SCIFIND_RL_MAX_BUCKETS` | `10000`                 | Max tracked rate-limit buckets |
| `SCIFIND_RL_<KEY>`      | see tiers above          | Per-tier per-minute limit override |
