"""Science/branch/topic tree loaded from tree.json."""

import json

from scifind_lib.constants import TREE_PATH
from scifind_lib.i18n import localise

_TREE_CACHE = {}


def load_tree():
    if "tree" not in _TREE_CACHE:
        try:
            with open(TREE_PATH, encoding="utf-8") as f:
                _TREE_CACHE["tree"] = json.load(f).get("sciences", [])
        except (OSError, ValueError):
            _TREE_CACHE["tree"] = []
    return _TREE_CACHE["tree"]


def walk_tree(tree, visit):
    """Depth-first walk; visit(node) is called for each node."""
    for root in tree:
        visit(root)
        for child in (root.get("children") or []):
            walk_tree([child], visit)


def leaf_ids(node):
    if not node.get("children"):
        return {node["id"]}
    leaves = set()
    for child in node["children"]:
        leaves |= leaf_ids(child)
    return leaves


def descendant_ids(node):
    ids = {node["id"]}
    for child in (node.get("children") or []):
        ids |= descendant_ids(child)
    return ids


def expand_selection(tree, ids):
    """Expand a set of tree-level ids to all leaf ids they cover."""
    idset = set(ids)
    covered = set()

    def _expand_node(node):
        if node["id"] in idset:
            covered.update(descendant_ids(node))

    walk_tree(tree, _expand_node)
    return covered


def compress_selection(tree, ids):
    """Replace a set of leaf ids with the minimal ancestor-covering set."""
    idset = set(ids)
    covered_leaves = set()

    def visit_collect(node):
        if node["id"] in idset:
            covered_leaves.update(leaf_ids(node))

    walk_tree(tree, visit_collect)

    out = set()

    def visit_collapse(roots):
        for node in roots:
            if leaf_ids(node) <= covered_leaves:
                out.add(node["id"])
                continue
            visit_collapse(node.get("children") or [])

    visit_collapse(tree)
    return out


def all_tree_ids(tree):
    out = set()
    walk_tree(tree, lambda n: out.add(n["id"]))
    return out


def topic_name_map(tree, locale="en-us"):
    """Flat {id: localised name} for every node in the tree."""
    out = {}

    def _name_node(node):
        out[node["id"]] = localise(node.get("translations") or {}, locale)
    walk_tree(tree, _name_node)
    return out


def topic_name(topic_id, tree=None, locale="en-us"):
    if not topic_id:
        return None
    if tree is None:
        tree = load_tree()
    name_map = topic_name_map(tree, locale)
    if topic_id in name_map:
        return name_map[topic_id]
    return topic_id.replace("_", " ").title()


def topic_path(tree, topic):
    """Return the ids along the path to a topic, or None if not in the tree."""
    def _path_node(node, ancestors=()):
        if node["id"] == topic:
            return ancestors + (topic,)
        for child in (node.get("children") or []):
            result = _path_node(child, ancestors + (node["id"],))
            if result:
                return result
    for root in tree:
        if result := _path_node(root):
            return result
    return None


def topic_tree_order():
    """{topic_id: depth-first index} over the science tree."""
    tree = load_tree()
    order = {}
    counter = [0]

    def _order_node(node):
        order[node["id"]] = counter[0]
        counter[0] += 1
        for child in (node.get("children") or []):
            _order_node(child)

    for root in tree:
        _order_node(root)
    return order