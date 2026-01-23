from collections import defaultdict, deque


def build_dag(actions):
    nodes = {a.derived_id: a for a in actions}
    incoming = {a.derived_id: set(a.depends_on) for a in actions}
    outgoing = defaultdict(set)

    for action in actions:
        for dep in action.depends_on:
            outgoing[dep].add(action.derived_id)

    return nodes, incoming, outgoing


def topo_sort(actions):
    nodes, incoming, outgoing = build_dag(actions)

    ready = deque(
        node for node, deps in incoming.items() if not deps
    )

    order = []

    while ready:
        node = ready.popleft()
        order.append(node)

        for downstream in outgoing[node]:
            incoming[downstream].remove(node)
            if not incoming[downstream]:
                ready.append(downstream)

    if len(order) != len(nodes):
        remaining = set(nodes) - set(order)
        raise ValueError(f"Cycle detected involving: {remaining}")

    return order


def compute_execution_levels(actions):
    nodes = {a.derived_id: a for a in actions}
    incoming = {a.derived_id: set(a.depends_on) for a in actions}
    outgoing = defaultdict(set)

    for a in actions:
        for dep in a.depends_on:
            outgoing[dep].add(a.derived_id)

    levels = []
    remaining = set(nodes.keys())

    while remaining:
        ready = sorted(
            n for n in remaining if not incoming[n]
        )

        if not ready:
            raise ValueError(f"Cycle detected involving {remaining}")

        levels.append(ready)

        for n in ready:
            remaining.remove(n)
            for downstream in outgoing[n]:
                incoming[downstream].remove(n)

    return levels
