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
| `/unit/<id>`                        | Unit details                                         |
| `/search?q=<query>`                 | Search                                               |
| `/api/search-suggestions?q=<query>` | JSON autocomplete suggestions                        |
| `/create`                           | Formula SQL builder and equation parser              |
| `/export?format=<fmt>`              | Download DB as  `csv` (zipped), `xlsx`, `ods`, `sql` |

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

### Locale

`en-us` / `en-uk` / `cs-cz`.
Stored inside a session cookie.
Switchable via the settings menu.

### Dimensions Setting

Toggle how dimensions are shown: `?dim_mode=<setting>`

- **Dimensions** `dim` (default): M, L, T, I, Θ, N, J
- **Variables** `var`: m, l, t, i, T, n, Iᵥ
- **Units** `unit` (units): kg, m, s, A, K, mol, cd

## Configuration

All optional environment variables:

| Variable                | Default                  | Description                                     |
| ----------------------- | ------------------------ | ----------------------------------------------- |
| `SCIFIND_DB`            | `scifind.db`             | Database path                                   |
| `SCIFIND_HOST`          | `127.0.0.1`              | Bind address (dev server)                       |
| `SCIFIND_PORT`          | `5000`                   | Port (dev server)                               |
| `SCIFIND_DEBUG`         | off                      | Flask debug mode (`1`/`true`/`yes`)             |
| `SCIFIND_SECRET_KEY`    | auto-generated           | Session secret, stored in `instance/secret_key` |
| `SCIFIND_MAX_UPLOAD_MB` | `32`                     | Max request body size                           |
| `SCIFIND_GITHUB_REPO`   | `Creeperman3000/Scifind` | Repo slug used for new-locale issue links       |
