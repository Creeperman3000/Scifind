"""Display helpers shared between the CLI and the web app."""
# Licensed under the LICENSE file in the project root.

from scifind_lib.constants import SUPERSCRIPT_DIGITS
from scifind_lib.tree import topic_name as _topic_name


def format_unit_str(default_unit_json):
    """Render a default_unit JSON list as a compact string like m·s⁻²."""
    from scifind_lib.units import parse_default_unit
    parts = parse_default_unit(default_unit_json)
    if not parts:
        return ""
    return "·".join(f"{uid}{str(exp).translate(SUPERSCRIPT_DIGITS)}"
                    for uid, exp in parts)


def group_by_topic(rows):
    """Group `rows` by their localised topic name, preserving insertion order."""
    by_topic = {}
    for row in rows:
        topic = _topic_name(row["topic_id"]) or "General"
        by_topic.setdefault(topic, []).append(row)
    return by_topic
