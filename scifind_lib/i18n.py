"""Locale loading, localisation, and unit-word helpers."""

import json
import logging

from scifind_lib.constants import LOCALE_DIR
from scifind_lib.util import safe_json_dict

logger = logging.getLogger("scifind.i18n")


_locale_configs = {}


def load_locale_config(locale):
    """Return the parsed ``meta`` block for ``locale`` (empty dict on missing/malformed)."""
    if locale not in _locale_configs:
        path = LOCALE_DIR / f"{locale}.json"
        try:
            with open(path, encoding="utf-8") as f: _locale_configs[locale] = json.load(f).get("meta", {})
        except (OSError, ValueError) as exc:
            logger.warning("locale %r: failed to load %s: %s", locale, path, exc)
            _locale_configs[locale] = {}
    return _locale_configs[locale]


def locale_chain(locale):
    chain, seen = [], set()
    while locale and locale not in seen:
        seen.add(locale)
        chain.append(locale)
        locale = load_locale_config(locale).get("fallback")
    return chain


def localise(value, locale):
    if not value: return ""
    if isinstance(value, dict): translations = value
    else:
        stripped = value.strip()
        if not stripped.startswith("{"): return stripped
        translations = safe_json_dict(stripped, default="")
        if not translations:
            return stripped
    for code in locale_chain(locale):
        if translations.get(code): return translations[code]
    return ""


def _chain_get(locale, key):
    for code in locale_chain(locale):
        if value := load_locale_config(code).get(key):
            return value
    return None


def locale_unit_words(locale):
    return _chain_get(locale, "unitWords") or {}


def locale_sibilants(locale):
    return _chain_get(locale, "sibilants") or {"chars": [], "preposition": {"suffix": ""}}


def unit_exponent_word(exp, locale="en-us", denominator=False):
    words = locale_unit_words(locale)
    if exp in (1, 0): return ""
    if exp == -1: return words.get("inverse") or ""
    if exp in (2, 3):
        base = "squared" if exp == 2 else "cubed"
        return words.get(base + "Special" if denominator else base) or ""
    suffix = _chain_get(locale, "ordinalSuffix")
    if suffix is None:
        suffix = ""
    ordinal = f"{exp}." if suffix == "." else f"{exp}{suffix}"
    return f"{words.get('toThe') or ''} {ordinal}".strip()


def difficulty_to_stars(difficulty, max_dots=5):
    filled = min(int(difficulty or 0), max_dots)
    return "★" * filled + "☆" * (max_dots - filled)


def wrap_symbol_in_latex(symbol):
    r"""Wrap a plain-text identifier in \mathrm{...}; LaTeX passes through."""
    if not symbol: return ""
    trailing = symbol[-1] if symbol[-1].isspace() else ""
    stripped = symbol.strip()
    if not stripped or (stripped.startswith("\\mathrm{") and stripped.endswith("}")):
        return stripped + trailing
    return f"\\mathrm{{{stripped}}}" + trailing


def with_subscript(sym, label):
    """Append a subscript unless the symbol already carries one."""
    if not label or "_" in sym: return sym
    label = str(label)
    return f"{sym}_{label}" if len(label) == 1 else f"{sym}_{{{label}}}"
