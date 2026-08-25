# Scifind

A physics formula database with a CLI tool and web app.

## Quick Start

Go [here](https://scifind.onrender.com/quantities) to use the website.

If you want to host it yourself, you can do that by running the following:

```bash
git clone https://github.com/Creeperman3000/Scifind.git
cd Scifind
pip install -r requirements.txt
python scifind_cli.py init        # for CLI only
python webapp.py                  # for webapp too
```

## Project Structure

| Path               | Purpose                       |
| ------------------ | ----------------------------- |
| `scifind_cli.py`   | CLI entry point               |
| `scifind_lib/`     | Library package               |
| `webapp.py`        | Flask webapp                  |
| `web/`             | Jinja2 templates, CSS, and JS |
| `scifind.db`       | Database                      |
| `schema.sql`       | Database schema               |
| `seed.sql`         | Seed data                     |
| `tree.json`        | Science/branch/topic tree     |
| `locales/`         | Locale JSON files             |
| `wiki/`            | Documentation                 |
| `requirements.txt` | Dependencies                  |

## Docs

See the [wiki](wiki/Home.md) to learn more.
