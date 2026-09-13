"""Science/branch/topic tree, loaded from the ``topic`` table."""

import json

from scifind_lib.i18n import localise


def _parse_json_dict(text):
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def load_tree(conn):
    """Nested topic tree rebuilt from ``topic`` rows ordered by position."""
    rows = conn.execute(
        "SELECT id, parent_id, name, name_genative, position FROM topic "
        "ORDER BY position"
    ).fetchall()
    nodes = {}
    for r in rows:
        translations = _parse_json_dict(r["name"])
        if gen_val := _parse_json_dict(r["name_genative"]).get("cs-cz"):
            translations.setdefault("cs-cz-gen", gen_val)
        nodes[r["id"]] = {
            "id": r["id"], "translations": translations, "children": [],
            "_parent": r["parent_id"],
        }
    roots = []
    for node in nodes.values():
        parent = node.pop("_parent")
        if parent and parent in nodes:
            nodes[parent]["children"].append(node)
        else:
            roots.append(node)
    return roots


def walk_tree(tree, visit):
    """Depth-first walk; visit(node) is called for each node."""
    for node in tree:
        visit(node)
        walk_tree(node.get("children") or [], visit)


def leaf_ids(node):
    if not node.get("children"):
        return {node["id"]}
    return set().union(*(leaf_ids(c) for c in node["children"]))


def descendant_ids(node):
    ids = {node["id"]}
    for child in (node.get("children") or []):
        ids |= descendant_ids(child)
    return ids


def expand_selection(tree, ids):
    """Expand a set of tree-level ids to all leaf ids they cover."""
    idset, covered = set(ids), set()

    def _expand(node):
        if node["id"] in idset:
            covered.update(descendant_ids(node))

    walk_tree(tree, _expand)
    return covered


def compress_selection(tree, ids):
    """Replace a set of leaf ids with the minimal ancestor-covering set."""
    idset, covered, out = set(ids), set(), set()

    def _collect(node):
        if node["id"] in idset:
            covered.update(leaf_ids(node))

    walk_tree(tree, _collect)

    def _collapse(nodes):
        for node in nodes:
            if leaf_ids(node) <= covered:
                out.add(node["id"])
            else:
                _collapse(node.get("children") or [])

    _collapse(tree)
    return out


def all_tree_ids(tree):
    out = set()
    walk_tree(tree, lambda n: out.add(n["id"]))
    return out


def topic_name_map(tree, locale="en-us"):
    """Flat {id: localised name} for every node in the tree."""
    nodes = []
    walk_tree(tree, nodes.append)
    return {n["id"]: localise(n.get("translations") or {}, locale) for n in nodes}


def topic_name(topic_id, tree, locale="en-us"):
    if not topic_id:
        return None
    return topic_name_map(tree, locale).get(topic_id, topic_id.replace("_", " ").title())


def topic_path(tree, topic):
    """Return the ids along the path to a topic, or None if not in the tree."""
    for node in tree:
        if node["id"] == topic:
            return (topic,)
        if result := topic_path(node.get("children") or [], topic):
            return (node["id"],) + result
    return None


def topic_tree_order(conn):
    """{topic_id: position} over the science tree, from ``topic.position``."""
    return {r["id"]: r["position"]
            for r in conn.execute("SELECT id, position FROM topic").fetchall()}