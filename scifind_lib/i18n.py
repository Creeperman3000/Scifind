"""Locale loading, localisation, and unit-word helpers."""

import json
import logging

from scifind_lib.constants import LOCALE_DIR

logger = logging.getLogger("scifind.i18n")


_locale_configs = {}


def load_locale_config(locale):
    """Return the parsed ``meta`` block for ``locale`` (empty dict on missing/malformed)."""
    if locale not in _locale_configs:
        path = LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f:
                _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError) as exc:
            logger.warning("locale %r: failed to load %s: %s", locale, path, exc)
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def localise(value, locale, default="en-us"):
    """Resolve a JSON i18n string, dict, or plain text to the active locale."""
    if not value:
        return ""
    if isinstance(value, dict):
        d = value
    else:
        s = value.strip()
        if not s.startswith("{"):
            return s
        try:
            d = json.loads(s)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("localise: bad JSON for locale %r: %s", locale, exc)
            return ""
        if not isinstance(d, dict):
            logger.warning("localise: non-object JSON for locale %r", locale)
            return ""
    return d.get(locale) or d.get(default) or ""


def localise_english(value):
    return localise(value, "en-us")


def locale_unit_words(locale):
    config = load_locale_config(locale)
    return config.get("unitWords", load_locale_config("en-us").get("unitWords", {}))


def locale_quantities_special(locale):
    return load_locale_config(locale).get("quantitiesSpecial", [])


def locale_accusative_names(locale):
    return load_locale_config(locale).get("accusativeNames", {})


def locale_sibilants(locale):
    return load_locale_config(locale).get("sibilants", {"chars": [], "preposition": {"suffix": ""}})


def _format_ordinal(n, locale="en-us"):
    suffix = load_locale_config(locale).get("ordinalSuffix", "th")
    return f"{n}." if suffix == "." else f"{n}{suffix}"


def unit_exponent_word(exp, locale="en-us", denominator=False):
    """Return the natural-language word for a unit exponent."""
    words = locale_unit_words(locale)
    if exp == 1:
        return ""
    if exp == -1:
        return words.get("inverse", "inverse")
    if exp in (2, 3):
        base = "squared" if exp == 2 else "cubed"
        return words.get(base + "Special" if denominator else base, base)
    return f"{words.get('toThe', 'to the')} {_format_ordinal(exp, locale)}" if exp > 3 else ""


def difficulty_to_stars(difficulty, max_dots=5):
    filled = min(int(difficulty or 0), max_dots)
    return "★" * filled + "☆" * (max_dots - filled)


def wrap_symbol_in_latex(symbol):
    r"""Wrap a plain-text identifier in \mathrm{...}; LaTeX passes through."""
    if not symbol:
        return ""
    trailing = symbol[-1] if symbol[-1].isspace() else ""
    s = symbol.strip()
    if not s or (s.startswith("\\mathrm{") and s.endswith("}")):
        return s + trailing
    return f"\\mathrm{{{s}}}" + trailing


def with_subscript(sym, label):
    """Append a subscript unless the symbol already carries one."""
    if not label or "_" in sym:
        return sym
    label = str(label)
    return f"{sym}_{label}" if len(label) == 1 else f"{sym}_{{{label}}}"
