"""Locale loading, localisation, and unit-word helpers."""

import json
import logging
import re

from scifind_lib.constants import _LOCALE_DIR

logger = logging.getLogger("scifind.i18n")


_locale_configs = {}


def _load_locale_config(locale):
    if locale not in _locale_configs:
        path = _LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f:
                _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError) as exc:
            logger.warning("locale %r: failed to load %s: %s", locale, path, exc)
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def load_locale_config(locale):
    """Return the parsed ``meta`` block for ``locale`` (empty dict on missing/malformed)."""
    return _load_locale_config(locale)


def localise(value, locale, default="en-us"):
    """Resolve a JSON i18n string, dict, or plain text to the active locale.

    Returns "" for None / empty / missing locale. Plain strings without a
    leading ``{`` are returned verbatim. Malformed JSON returns "".
    """
    if not value:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get(default) or ""
    s = value.strip()
    if not s.startswith("{"):
        return s
    try:
        d = json.loads(s)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("localise: bad JSON for locale %r: %s", locale, exc)
        return ""
    if isinstance(d, dict):
        return d.get(locale) or d.get(default) or ""
    logger.warning("localise: non-object JSON for locale %r", locale)
    return ""


def localise_english(value):
    return localise(value, "en-us")


def locale_unit_words(locale):
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


def _format_ordinal(n, locale="en-us"):
    suffix = _load_locale_config(locale).get("ordinalSuffix", "th")
    return f"{n}." if suffix == "." else f"{n}{suffix}"


def unit_exponent_word(exp, locale="en-us", denominator=False):
    """Return the natural-language word for a unit exponent."""
    words = locale_unit_words(locale)
    if exp == 1:
        return ""
    if exp == -1:
        return words.get("inverse", "inverse")
    if exp == 2:
        return words.get("squaredSpecial" if denominator else "squared", "squared")
    if exp == 3:
        return words.get("cubedSpecial" if denominator else "cubed", "cubed")
    if exp > 3:
        return f"{words.get('toThe', 'to the')} {_format_ordinal(exp, locale)}"
    return ""


def difficulty_to_stars(difficulty, max_dots=5):
    filled = min(int(difficulty or 0), max_dots)
    return "★" * filled + "☆" * (max_dots - filled)


def wrap_symbol_in_latex(symbol):
    r"""Wrap a plain-text identifier in \mathrm{...}; LaTeX passes through."""
    if not symbol:
        return ""
    trailing = symbol[-1] if symbol[-1].isspace() else ""
    s = symbol.strip()
    if not s:
        return s + trailing
    return f"\\mathrm{{{s}}}" + trailing
