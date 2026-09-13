# Scifind

A physics formula database with a CLI tool and web app.

## Quick Start

Click [here](https://scifind.onrender.com/quantities) to use the website.

If you want to host it yourself, you can do that by running the following:

```bash
git clone https://github.com/Creeperman3000/Scifind.git
cd Scifind
pip install -r requirements.txt
python scifind_cli.py init        # CLI
python webapp.py                  # webapp
```

## Project Structure

| Path               | Purpose                       |
| ------------------ | ----------------------------- |
| `scifind_cli.py`   | CLI entry point               |
| `scifind_lib/`     | Library package               |
| `webapp.py`        | Flask webapp                  |
| `web/`             | Jinja2 templates, CSS, and JS |
| `schema.sql`       | Database schema               |
| `seed.sql`         | Seed data                     |
| `tree.json`        | Topic-tree seed source (runtime data lives in the `topic` table) |
| `locales/`         | Locale JSON files             |
| `wiki/`            | Documentation                 |
| `requirements.txt` | Dependencies                  |

See the [wiki](wiki/Home.md) to learn more.
