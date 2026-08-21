"""Locale loading, localisation, and unit-word helpers."""
# Licensed under the LICENSE file in the project root.

import html
import re
from pathlib import Path

from scifind_lib.constants import _LOCALE_DIR


_locale_configs = {}


def _load_locale_config(locale):
    if locale not in _locale_configs:
        path = _LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f:
                import json
                _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError):
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def localise(value, locale, default="en-us"):
    """Resolve a JSON i18n string, dict, or plain text to the active locale."""
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get(default) or ""
    s = value.strip()
    if not s.startswith("{"):
        return s
    try:
        import json
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        d = None
    if isinstance(d, dict):
        return d.get(locale) or d.get(default) or s
    # Recover the first quoted value from malformed seed JSON instead of throwing.
    if d is None and s.endswith("}"):
        _, _, raw = s[s.find("{") + 1 : s.rfind("}")].partition(":")
        raw = raw.strip()
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def localise_english(value):
    return localise(value, "en-us")


def locale_words(locale):
    config = _load_locale_config(locale)
    return config.get("unitWords", _load_locale_config("en-us").get("unitWords", {}))


def locale_quantities_special(locale):
    return _load_locale_config(locale).get("quantitiesSpecial", [])


def locale_accusative_names(locale):
    return _load_locale_config(locale).get("accusativeNames", {})


def locale_sibilants(locale):
    return _load_locale_config(locale).get(
        "sibilants", {"chars": [], "preposition": {"suffix": ""}}
    )


def _ordinal(n, locale="en-us"):
    suffix = _load_locale_config(locale).get("ordinalSuffix", "th")
    return f"{n}." if suffix == "." else f"{n}{suffix}"


def exponent_word(exp, locale="en-us", denominator=False):
    """Return the natural-language word for a unit exponent."""
    words = locale_words(locale)
    if exp == 1:
        return ""
    if exp == -1:
        return words.get("inverse", "inverse")
    if exp == 2:
        return words.get("squaredSpecial" if denominator else "squared", "squared")
    if exp == 3:
        return words.get("cubedSpecial" if denominator else "cubed", "cubed")
    if exp > 3:
        return f"{words.get('toThe', 'to the')} {_ordinal(exp, locale)}"
    return ""


def difficulty_to_stars(difficulty, max_dots=5):
    filled = min(int(difficulty or 0), max_dots)
    return "★" * filled + "☆" * (max_dots - filled)


def render_symbol(symbol):
    r"""Wrap a plain-text identifier in \mathrm{...}; LaTeX passes through."""
    if not symbol:
        return ""
    s = symbol.strip()
    if not s or "\\" in s:
        return s
    return re.sub(r"[A-Za-z]+", lambda m: f"\\mathrm{{{m.group(0)}}}", s.replace("_", "\\_"))
