"""Graph-search utilities used by the agents.

The city grid is treated as an implicit graph: nodes are walkable cells,
edges connect 4-neighbours. BFS provides unweighted shortest paths and a
multi-target variant for "go to nearest X" behaviours; A* offers a
heuristic-guided alternative using Manhattan distance.
"""

from collections import deque
import heapq


_NEIGHBOUR_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def neighbours(pos, walkable):
    """Yield walkable 4-connected neighbours of ``pos``.

    ``walkable`` is a predicate ``(x, y) -> bool`` indicating whether a
    cell can be entered.
    """
    x, y = pos
    for dx, dy in _NEIGHBOUR_OFFSETS:
        nxt = (x + dx, y + dy)
        if walkable(nxt):
            yield nxt


def bfs_shortest_path(start, goal, walkable):
    """Return the shortest path from ``start`` to ``goal`` as a list of cells.

    The returned path includes both endpoints. Returns ``None`` if no path
    exists under the given ``walkable`` predicate.
    """
    if start == goal:
        return [start]

    frontier = deque([start])
    came_from = {start: None}

    while frontier:
        current = frontier.popleft()
        for nxt in neighbours(current, walkable):
            if nxt in came_from:
                continue
            came_from[nxt] = current
            if nxt == goal:
                path = [nxt]
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                path.reverse()
                return path
            frontier.append(nxt)
    return None


def bfs_nearest(start, targets, walkable):
    """Return ``(target, path)`` for the closest cell in ``targets``.

    A single multi-source BFS is cheaper than running BFS once per target
    when several candidates exist (e.g. nearest waste or nearest bin).
    """
    target_set = set(targets)
    if not target_set:
        return None, None
    if start in target_set:
        return start, [start]

    frontier = deque([start])
    came_from = {start: None}

    while frontier:
        current = frontier.popleft()
        for nxt in neighbours(current, walkable):
            if nxt in came_from:
                continue
            came_from[nxt] = current
            if nxt in target_set:
                path = [nxt]
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                path.reverse()
                return nxt, path
            frontier.append(nxt)
    return None, None


def manhattan(a, b):
    """Manhattan distance, an admissible heuristic on a 4-connected grid."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_path(start, goal, walkable):
    """A* shortest path from ``start`` to ``goal`` using Manhattan heuristic.

    Returns the same shape of path as :func:`bfs_shortest_path`, or
    ``None`` when no path exists.
    """
    if start == goal:
        return [start]

    open_heap = []
    counter = 0
    heapq.heappush(open_heap, (manhattan(start, goal), counter, start))

    came_from = {start: None}
    g_score = {start: 0}

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current == goal:
            path = [current]
            while came_from[path[-1]] is not None:
                path.append(came_from[path[-1]])
            path.reverse()
            return path

        for nxt in neighbours(current, walkable):
            tentative_g = g_score[current] + 1
            if tentative_g >= g_score.get(nxt, float("inf")):
                continue
            came_from[nxt] = current
            g_score[nxt] = tentative_g
            f_score = tentative_g + manhattan(nxt, goal)
            counter += 1
            heapq.heappush(open_heap, (f_score, counter, nxt))
    return None
