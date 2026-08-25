# Scifind

Scifind is a physics formula database with a web app and a CLI tool.
Formulas are stored as a list of [RPN](https://en.wikipedia.org/wiki/Reverse_Polish_notation) tokens in a normalized
SQLite schema. Features include:

- [LaTeX](https://en.wikipedia.org/wiki/LaTeX) rendering
- [i18n](https://en.wikipedia.org/wiki/Internationalization_and_localization) language support
- dimensional analysis
- export to CSV, XLSX, ODS, SQL.

## Pages

- **[CLI Tool](CLI):** command-line tool
- **[Web App](Web-App):** routes and filtering
- **[Database](Database):** schema and seed data specs
- **[Development](Development):** setup and testing

## Tech Stack

| Component | Tech |
|-----------|------|
| Backend   | Python 3 + Flask (gunicorn for production) |
| Database  | SQLite |
| Rendering | KaTeX + Lucide icons via CDN |
| Export    | CSV, XLSX (openpyxl), ODS (odfpy), SQL |
| Frontend  | Vanilla JS, no framework |
