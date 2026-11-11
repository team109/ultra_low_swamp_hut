from ultra_low_hut import ROOT

"""Independent adjacent-chunk decoration policies and their result summary."""

import json
import hashlib
from itertools import product
from pathlib import Path

APPROACHES = ("center", "north", "east", "south", "west")
LOADING_POLICY = "adjacent-3x3-v1"
STANDARD_VERIFICATION_MODES = ("on", "off")
VERIFICATION_MODES = STANDARD_VERIFICATION_MODES
_CENTER = ((0, 0), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
_NORTH = ((0, -1), (-1, -1), (1, -1), (0, 0), (-1, 0), (1, 0), (0, 1), (-1, 1), (1, 1))


def _rotate(order, turns):
    result = []
    for x, z in order:
        for _ in range(turns):
            x, z = -z, x
        result.append([x, z])
    return result


def legacy_feature_spec():
    return dict(id="features-3x3-v1", orders=[dict(id=a, offsets=_rotate(_CENTER if a == "center" else _NORTH,
                                                                         0 if a == "center" else APPROACHES.index(a)-1))
                                          for a in APPROACHES])


def order_fingerprint(orders):
    return hashlib.sha256(json.dumps(orders, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# Letter positions follow the displayed three-by-three grid, north at the top.
CHUNK_LETTERS = {letter: (i % 3 - 1, i // 3 - 1)
                 for i, letter in enumerate("ABCDEFGHI")}
NEIGHBOR_LETTERS = "BCFIHGDA"
STRUCTURED_SWAP_FAMILIES = (
    ("BCFIHGDA", ("FI", "HG", "DA")),
    ("BCFIHGDA", ("CF", "IH")),
    ("BCFIHGDA", ("GD", "AB")),
    ("BCFIHGDA", ("BC", "FI", "DA")),
    ("ABCFIHGD", ("BC", "FI", "DA")),
)


def _letter_symmetries(order):
    letters = {position: letter for letter, position in CHUNK_LETTERS.items()}
    for reflected in (False, True):
        for turns in range(4):
            transformed = []
            for letter in order:
                x, z = CHUNK_LETTERS[letter]
                if reflected:
                    x = -x
                for _ in range(turns):
                    x, z = -z, x
                transformed.append(letters[x, z])
            yield "".join(transformed)


def structured_neighbor_orders():
    """Generate the ring and five complete independent-swap families."""
    orders = set()
    for direction in (NEIGHBOR_LETTERS, NEIGHBOR_LETTERS[::-1]):
        orders.update(direction[i:] + direction[:i] for i in range(8))
    for base, pairs in STRUCTURED_SWAP_FAMILIES:
        for enabled in product((False, True), repeat=len(pairs)):
            permutation = {letter: letter for letter in base}
            for pair, swap in zip(pairs, enabled):
                if swap:
                    permutation[pair[0]], permutation[pair[1]] = pair[1], pair[0]
            order = "".join(permutation[letter] for letter in base)
            orders.update(_letter_symmetries(order))
    return tuple(sorted(orders))


def generate_structured_order_spec():
    """Generate the ring/swap families when creating a new editable list."""
    orders = []
    for neighbors in structured_neighbor_orders():
        for index in range(9):
            name = neighbors[:index] + "E" + neighbors[index:]
            orders.append(dict(id=name, offsets=[list(CHUNK_LETTERS[c]) for c in name]))
    return _structured_spec(orders)


def _structured_spec(orders):
    orders.sort(key=lambda order: order["id"])
    fingerprint = order_fingerprint(orders)
    return dict(schema="hut-loading-orders-v1",
                id="features-selected-3x3-v2-" + fingerprint[:12],
                orders_sha256=fingerprint, symmetry="D4",
                objective="ring-and-independent-swaps-all-center-positions",
                neighbor_orders=len({tuple(tuple(p) for p in o['offsets'] if p != [0, 0]) for o in orders}),
                distinct_prefixes=len(center_prefixes(dict(orders=orders))), orders=orders)


def structured_order_spec(path=None):
    """Load the editable direction list used by prefix measurement plans."""
    path = Path(path) if path is not None else ROOT / 'config/verification/loading-orders.txt'
    offsets = dict(N=(0, -1), NE=(1, -1), E=(1, 0), SE=(1, 1),
                   S=(0, 1), SW=(-1, 1), W=(-1, 0), NW=(-1, -1), C=(0, 0))
    letters = {value: key for key, value in CHUNK_LETTERS.items()}
    orders, seen = [], set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        tokens = line.partition('#')[0].split()
        if not tokens:
            continue
        if len(tokens) != 9 or set(tokens) != set(offsets):
            raise ValueError(f'{path}:{number}: each order must contain N NE E SE S SW W NW C once')
        name = ''.join(letters[offsets[token]] for token in tokens)
        if name in seen:
            raise ValueError(f'{path}:{number}: repeated order')
        seen.add(name)
        orders.append(dict(id=name, offsets=[list(offsets[token]) for token in tokens]))
    if not orders:
        raise ValueError('Loading-order list is empty: ' + str(path))
    return _structured_spec(orders)


def center_prefixes(spec):
    """Distinct neighbor prefixes before E, in depth-first lexical order.

    Indices use north, northeast, east, southeast, south, southwest, west,
    northwest. Each returned tuple describes one center-decoration result.
    """
    indices = {CHUNK_LETTERS[c]: i for i, c in enumerate(NEIGHBOR_LETTERS)}
    prefixes = set()
    for order in spec["orders"]:
        prefix = []
        for offset in order["offsets"]:
            if tuple(offset) == (0, 0):
                prefixes.add(tuple(prefix))
                break
            prefix.append(indices[tuple(offset)])
        else:
            raise ValueError("Loading order lacks the center chunk")
    return tuple(sorted(prefixes))


def load_order_spec(path=None):
    path = Path(path) if path is not None else ROOT / "config/verification/loading-orders.txt"
    if path.suffix == ".txt":
        return structured_order_spec(path)
    if not path.exists():
        raise FileNotFoundError("Loading-order specification is missing: " + str(path))
    spec = json.loads(path.read_text())
    if spec.get('orders_file'):
        expanded = structured_order_spec(path.parent / spec['orders_file'])
        if any(key in spec and spec[key] != expanded[key] for key in ('id', 'orders_sha256')):
            raise ValueError('Loading-order manifest does not match its direction list')
        spec = dict(spec, **expanded)
    if spec.get("schema") != "hut-loading-orders-v1" or not isinstance(spec.get("id"), str) or not spec["id"] or not spec.get("orders"):
        raise ValueError("Invalid loading-order specification")
    fingerprint = order_fingerprint(spec["orders"])
    if spec.get("orders_sha256") != fingerprint or spec["id"] != "features-selected-3x3-v2-" + fingerprint[:12]:
        raise ValueError("Loading-order identity must match its recipe fingerprint")
    seen = set()
    for order in spec["orders"]:
        name = order.get("id")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Invalid or repeated loading-order ID")
        seen.add(name)
        offsets = order["offsets"]
        if len(offsets) != 9 or any(len(p) != 2 or any(type(v) is not int for v in p) for p in offsets) or set(map(tuple, offsets)) != {(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1)}:
            raise ValueError("Loading orders must permute all nine adjacent offsets")
    return spec


def normalize_verification_mode(value):
    """Read legacy saved modes while emitting on/off in current records."""
    mode = {"none": "off", "full": "on"}.get(value, value)
    if mode not in VERIFICATION_MODES:
        raise ValueError("Verification mode must be on or off")
    return mode


def get_order_spec(profile="on", path=None):
    """Read the editable order list for enabled vanilla verification."""
    if normalize_verification_mode(profile) != "on":
        raise ValueError("Loading-order profile must be on")
    return load_order_spec(path)


def order_work(spec):
    """Count measurements and trie edges without assuming prefix closure."""
    prefixes = center_prefixes(spec)
    trie_edges = {prefix[:end] for prefix in prefixes for end in range(1, len(prefix) + 1)}
    return dict(orders=len(spec["orders"]), prefixes=len(prefixes),
                neighbor_steps=len(trie_edges), center_steps=len(prefixes),
                shared_steps=len(trie_edges) + len(prefixes))


ORDER_SPEC = load_order_spec()
FEATURES_POLICY = ORDER_SPEC["id"]
LOADING_FIELDS = (
    "loading_policy", "min_hpos", "min_hpos_approaches",
    "loading_order_affected", "loading_order_heights",
)


def summarize_loading_orders(results, *, spec=None):
    if not results:
        raise ValueError("Verification requires every configured loading order")
    heights = {}
    reference = next(iter(results.values()))
    policy = reference.get("loading_policy")
    if spec is None and policy == FEATURES_POLICY:
        spec = ORDER_SPEC
    if spec is not None:
        if policy != spec["id"]:
            raise ValueError("Verification uses a different loading-order specification")
        approaches = tuple(order["id"] for order in spec["orders"])
        expected_orders = {order["id"]: order["offsets"] for order in spec["orders"]}
    elif policy in (LOADING_POLICY, "features-3x3-v1"):
        approaches = APPROACHES
        expected_orders = {order["id"]: order["offsets"] for order in legacy_feature_spec()["orders"]}
    else:
        raise ValueError("Unknown chunk ordering policy")
    if set(results) != set(approaches):
        raise ValueError("Verification requires every configured loading order")
    for approach in approaches:
        result = results[approach]
        if "error" in result:
            raise RuntimeError(f"{approach} verification failed: {result['error']}")
        if result.get("loading_policy") != policy:
            raise ValueError("Cannot mix generation policies in loading-order verification")
        if result.get("world_reused"):
            raise ValueError("Loading approaches require independent world contexts")
        if result.get("approach") != approach:
            raise ValueError("Verifier returned the wrong loading approach")
        if policy != LOADING_POLICY:
            if result.get("generation_status") != "FEATURES":
                raise ValueError("FEATURES verification requires completed FEATURES generation")
            if result.get("actual_decoration_order") != result.get("requested_chunk_order") or not result.get("actual_decoration_order"):
                raise ValueError("Decoration order did not match the requested order")
            expected = [[result["x"] // 16 + dx, result["z"] // 16 + dz] for dx, dz in expected_orders[approach]]
            if result["requested_chunk_order"] != expected:
                raise ValueError("Observed decoration did not execute the configured policy")
        for field in ("seed", "x", "z", "version", "controlled", "world_type", "biome", "force_biome"):
            if result.get(field) != reference.get(field):
                raise ValueError("Loading-order response mismatch: " + field)
        values = result["heights"]
        if any(type(h) is not int for h in values):
            raise ValueError("Verifier returned a non-integer height")
        heights[approach] = sorted(set(values))
    minimum = min((h for values in heights.values() for h in values), default=None)
    return dict(
        loading_policy=policy,
        min_hpos=minimum,
        min_hpos_approaches=[a for a in approaches if minimum in heights[a]],
        loading_order_affected=len({tuple(h) for h in heights.values()}) > 1,
        loading_order_heights=heights,
    )


def aggregate_loading_orders(results, *, spec=None):
    summary = summarize_loading_orders(results, spec=spec)
    result = dict(results.get("center", next(iter(results.values()))))
    for field in ("hut_pieces", "before_hut_calls", "requested_chunk_order", "actual_decoration_order", "approach", "profile", "block_digest", "terrain"):
        result.pop(field, None)
    result.update(summary)
    result["heights"] = [] if summary["min_hpos"] is None else [summary["min_hpos"]]
    result["loading_orders"] = results
    result["seconds"] = sum(r["seconds"] for r in results.values())
    return result
