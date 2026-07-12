# Scifind Wiki

Scifind is a structured physics formula database with a CLI tool and Flask
web application. Formulas are stored in a normalized SQL schema with full
LaTeX rendering, i18n (`en-us` / `en-uk` / `cs-cz`), dimension analysis, and
multiple export formats (CSV, XLSX, ODS). The web app can be deployed to
Cloudflare Workers via the edgekit bundler.

## Pages

- **[CLI Tool](CLI)** — Command-line interface reference
- **[Web App](Web-App)** — Flask web application features and routes
- **[Database](Database)** — Schema and seed data specification
- **[Development](Development)** — Setup, contributing, Workers deployment

## Tech Stack

| Component | Tech |
|-----------|------|
| Backend | Python 3.13 + Flask |
| Database | SQLite |
| Rendering | KaTeX via CDN |
| Export | CSV, XLSX (openpyxl), ODS (odfpy) |
| Frontend | Vanilla JS, no framework |
| Workers | Cloudflare Python Workers via edgekit |
