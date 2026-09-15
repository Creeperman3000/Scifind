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
| `/base-units`                       | Redirects to `/quantities?is_dim=1` (base quantities)|
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
Export is rate-limited to 6 requests/minute per client.

The `/create` page uses AJAX endpoints (not meant to be called directly):
`POST /create/preview-render`, `POST /create/build-sql`,
`GET /create/token-sidebar`, `GET /create/breadcrumb`,
`GET /create/languages`.

## Query Parameters

### Filtering (`/formulas`, `/quantities`)

| Name        | Parameter                            | Description                                     |
| ----------- | ------------------------------------ | ----------------------------------------------- |
| Tree        | `ids=id1,id2,...`                    | Restrict to tree's nodes (children included)    |
| Difficulty  | `diff_min`, `diff_max`               | Difficulty range 1-10                           |
| Dimension   | `<dim>_eq`, `<dim>_geq`, `<dim>_leq` | Dimension exponent filter (M, L, T, I, Θ, N, J) |
|             | `dim_mode=and\|or`                   | Do all or any dimensions match\*                |
| Quantity    | `qty=id1,id2`                        | Formulas containing these quantities            |
|             | `qty_mode=and\|or`                   | Require all or any quantities\*                 |
| Sort        | `sort=<key>`                         | Sort order                                      |
| Exclude all | `exclude_all=1`                      | Empty result set (nothing selected)             |

\* - Shared parameter

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
| `all=1`     | Show everything on one page (also `per_page=all` or `per_page=0`)   |

### Locale

`en-us` / `en-uk` / `cs-cz`.
Stored inside a session cookie.
Switchable via the settings menu.

### Dimensions Setting

Toggle how dimensions are shown: `?dim_mode=<setting>`

- **Dimensions** `dim` (default): M, L, T, I, Θ, N, J
- **Variables** `var`: m, l, t, i, T, n, Iᵥ
- **Units** `unit`: kg, m, s, A, K, mol, cd

## Keyboard shortcuts

Press `?` anywhere (or Settings → Keyboard shortcuts) for the full in-app reference. Summary:

- Global: `/` / `Ctrl+K` search, `[` / `]` (`Ctrl+B` / `Ctrl+Shift+B`) sidebars, `g f` / `g q` (`Alt+1` / `Alt+2`) switch views, `Esc` closes/clears/cancels a pending `g`/`f`/`c` prefix (5s hint pill).
- Filters (`f` prefix, list pages): `f q` quantity, `f d` dimension picker (`m`/`l`/`t`/`i`/`h`/`n`/`j` or `1`–`7`; `e` prefix or `Shift` then `l`/`g`/`e` for ≤/≥/=; `f d f` fills empty dimensions with 0, `f d b` toggles base quantities), `f s` sort (`q`/`i`/`n`/`d`/`D`/`t`/`T`), `f r` difficulty, `f t` tree walker (`1`–`9` drill, `Enter` toggles, `Esc` re-expands; `f t d` deselects all topics). Picker targets show blue key badges.
- Results & details: `j`/`k`/`↑`/`↓` move up/down (blue highlight), `h`/`l`/`←`/`→` move left/right, `Enter` opens, `Tab` focuses links, `m` loads more.
- Copy formula as (`c` prefix): `c l`/`c u`/`c p`/`c v` copy LaTeX/Unicode/PNG/SVG, `c s` formula SQL.
- Clear filter (`c` prefix): `c a` clear all, `c q`/`c d`/`c r`/`c t` clear one filter.
- Create: `Ctrl+Enter` continues to SQL, `e` focuses the equation field.

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
