"""Science/branch/topic tree, loaded from the ``topic`` table."""

import json

from scifind_lib.db import process_cached
from scifind_lib.i18n import localise


def _parse_json_dict(text):
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@process_cached("topic_tree")
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


def build_tree_indices(tree):
    """Single-pass indices: {id: node}, parent map, leaf-set and descendant-set per id."""
    id_to_node, parent, children_ids = {}, {}, {}
    order = []

    def visit(node, par=None):
        nid = node["id"]
        id_to_node[nid] = node
        parent[nid] = par
        kids = node.get("children") or []
        children_ids[nid] = [c["id"] for c in kids]
        order.append(nid)
        for c in kids:
            visit(c, nid)

    for root in tree or []:
        visit(root, None)
    # Post-order leaf/descendant sets (each node's set built once).
    leaf_map, desc_map = {}, {}
    for nid in reversed(order):
        kids = children_ids.get(nid, [])
        if not kids:
            leaf_map[nid] = {nid}
            desc_map[nid] = {nid}
        else:
            ls, ds = set(), {nid}
            for k in kids:
                ls |= leaf_map[k]
                ds |= desc_map[k]
            leaf_map[nid] = ls
            desc_map[nid] = ds
    return {
        "id_to_node": id_to_node,
        "parent": parent,
        "children": children_ids,
        "leaf": leaf_map,
        "descendant": desc_map,
        "order": order,
    }


def _idx(tree, given=None):
    return given or build_tree_indices(tree)


def expand_selection(tree, ids, _indices=None):
    """Expand a set of tree-level ids to all descendant ids they cover."""
    if not ids:
        return set()
    desc = _idx(tree, _indices)["descendant"]
    covered = set()
    for nid in set(ids):
        if nid in desc:
            covered |= desc[nid]
    return covered


def compress_selection(tree, ids, _indices=None):
    """Replace a set of ids with the minimal ancestor-covering set."""
    if not ids:
        return set()
    idx = _idx(tree, _indices)
    desc, leaf = idx["descendant"], idx["leaf"]
    covered = set()
    for nid in set(ids):
        covered |= leaf.get(nid, {nid}) if nid in desc else {nid}
    out = set()

    def _collapse(nodes):
        for node in nodes:
            nid = node["id"]
            if leaf.get(nid, {nid}) <= covered:
                out.add(nid)
            else:
                _collapse(node.get("children") or [])

    _collapse(tree or [])
    return out


def topic_parent_map(tree, _indices=None):
    """{topic_id: parent_id or None} for the whole tree."""
    return dict(_idx(tree, _indices)["parent"])


def topic_name_map(tree, locale="en-us"):
    """Flat {id: localised name} for every node in the tree."""
    nodes = []
    walk_tree(tree, nodes.append)
    return {n["id"]: localise(n.get("translations") or {}, locale) for n in nodes}


def topic_name(topic_id, tree, locale="en-us"):
    if not topic_id:
        return None
    return topic_name_map(tree, locale).get(topic_id, topic_id.replace("_", " ").title())


def topic_path(tree, topic, _indices=None, _parent_map=None):
    """Return the ids along the path to a topic, or None if not in the tree."""
    if _parent_map is None and _indices is not None:
        _parent_map = _indices.get("parent")
    if _parent_map is not None:
        if topic not in _parent_map:
            return None
        path, seen, cur = [topic], {topic}, _parent_map.get(topic)
        while cur is not None:
            if cur in seen:
                return None
            seen.add(cur)
            path.append(cur)
            cur = _parent_map.get(cur)
        return tuple(reversed(path))
    for node in tree:
        if node["id"] == topic:
            return (topic,)
        if result := topic_path(node.get("children") or [], topic):
            return (node["id"],) + result
    return None


@process_cached("topic_tree_order")
def _topic_tree_order_uncached(conn):
    return {r["id"]: r["position"] for r in conn.execute("SELECT id, position FROM topic").fetchall()}


def topic_tree_order(conn):
    """{topic_id: position} over the science tree, from ``topic.position``."""
    return dict(_topic_tree_order_uncached(conn))