"""Science/branch/topic tree, loaded from the ``topic`` table."""

from scifind_lib.i18n import localise
from scifind_lib.util import request_cached, safe_json_dict


def load_tree(conn):
    """Nested topic tree rebuilt from ``topic`` rows ordered by position."""
    rows = conn.execute(
        "SELECT id, parent_id, name, name_genative, position FROM topic "
        "ORDER BY position"
    ).fetchall()
    nodes = {}
    for r in rows:
        translations = safe_json_dict(r["name"])
        if gen := safe_json_dict(r["name_genative"]).get("cs-cz"):
            translations.setdefault("cs-cz-gen", gen)
        nodes[r["id"]] = {"id": r["id"], "translations": translations,
                          "children": [], "_parent": r["parent_id"]}
    roots = []
    for node in nodes.values():
        parent = node.pop("_parent")
        (nodes[parent]["children"] if parent in nodes and parent != node["id"] else roots).append(node)
    return roots


def walk_tree(tree, visit):
    """Depth-first walk; visit(node) is called for each node."""
    for node in tree:
        visit(node)
        walk_tree(node.get("children") or [], visit)


def build_tree_indices(tree):
    """Single-pass indices: {id: node}, parent map, leaf-set and descendant-set per id."""
    id_to_node, parent, children_ids, leaf_map, desc_map = {}, {}, {}, {}, {}

    def visit(node, par=None):
        nid = node["id"]
        id_to_node[nid], parent[nid] = node, par
        kids = node.get("children") or []
        children_ids[nid] = [c["id"] for c in kids]
        leaves, descs = set(), {nid}
        for c in kids:
            visit(c, nid)
            leaves |= leaf_map[c["id"]]
            descs |= desc_map[c["id"]]
        leaf_map[nid] = leaves or {nid}
        desc_map[nid] = descs

    for root in tree or []:
        visit(root)
    return {"id_to_node": id_to_node, "parent": parent, "children": children_ids,
            "leaf": leaf_map, "descendant": desc_map, "order": list(id_to_node)}


def _norm_ids(ids):
    if not ids:
        return set()
    return {ids} if isinstance(ids, str) else set(ids)


def expand_selection(tree, ids, _indices=None):
    """Expand a set of tree-level ids to all descendant ids they cover."""
    ids = _norm_ids(ids)
    if not ids:
        return set()
    desc = (_indices or build_tree_indices(tree))["descendant"]
    return {d for nid in ids if nid in desc for d in desc[nid]}


def compress_selection(tree, ids, _indices=None):
    """Replace a set of ids with the minimal ancestor-covering set."""
    ids = _norm_ids(ids)
    if not ids:
        return set()
    idx = _indices or build_tree_indices(tree)
    desc, leaf = idx["descendant"], idx["leaf"]
    covered = set()
    for nid in ids:
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
    return out | (ids - set(desc))


def topic_name_map(tree, locale="en-us"):
    """Flat {id: localised name} for every node in the tree."""
    nodes = []
    walk_tree(tree, nodes.append)
    return {n["id"]: localise(n.get("translations") or {}, locale) for n in nodes}


def topic_name(topic_id, tree, locale="en-us"):
    if not topic_id:
        return None
    found = []

    def visit(node):
        if node["id"] == topic_id:
            found.append(localise(node.get("translations") or {}, locale))
    walk_tree(tree or [], visit)
    return found[0] if found else None


def topic_path(tree, topic, _indices=None, _parent_map=None):
    """Return the ids along the path to a topic, or None if not in the tree."""
    if _parent_map is None:
        _parent_map = _indices.get("parent") if _indices else None
    if _parent_map is None:
        _parent_map = (_indices or build_tree_indices(tree))["parent"]
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


def _topic_tree_order_uncached(conn):
    return {r["id"]: r["position"] for r in conn.execute("SELECT id, position FROM topic").fetchall()}


def topic_tree_order(conn):
    """{topic_id: position} over the science tree, from ``topic.position``."""
    return request_cached("_topic_tree_order", lambda: _topic_tree_order_uncached(conn))