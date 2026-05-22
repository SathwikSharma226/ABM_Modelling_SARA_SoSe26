"""
pathfinding.py
--------------
Graph-search utilities used by the agents.

The lecture explicitly asks us to "use graph search algorithms where it
makes sense". We use:

* Breadth-First Search (BFS) for unweighted shortest paths in the city
  grid (used by transporters and cleaners to walk along streets).
* A simple A* implementation for goal-directed search with a heuristic
  (Manhattan distance), used when a heuristic offers a clear speed-up.

The graph is implicit: nodes are walkable grid cells, edges connect
4-neighbours (no diagonal movement) when both cells are walkable.
"""

from collections import deque  # deque -> O(1) popleft for the BFS frontier
import heapq  # heapq -> priority queue used by A*


# 4-connected neighbourhood offsets (no diagonals so paths follow streets)
_NEIGHBOUR_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def neighbours(pos, walkable):
    """Yield walkable 4-connected neighbours of ``pos``.

    Parameters
    ----------
    pos : tuple[int, int]
        Current cell as (x, y).
    walkable : Callable[[tuple[int, int]], bool]
        Predicate returning True if a cell can be entered.
    """
    # Iterate over the four cardinal offsets and test each candidate cell.
    x, y = pos
    for dx, dy in _NEIGHBOUR_OFFSETS:
        nxt = (x + dx, y + dy)
        # Only yield neighbours the predicate considers walkable.
        if walkable(nxt):
            yield nxt


def bfs_shortest_path(start, goal, walkable):
    """Return the shortest path from ``start`` to ``goal`` as a list of cells.

    Returns ``None`` if no path exists. The returned path *includes* the
    start and goal cells.
    """
    # Trivial case: already at the goal -> empty walk.
    if start == goal:
        return [start]

    # Standard BFS: queue of cells to visit, plus a parent map for backtracking.
    frontier = deque([start])
    came_from = {start: None}

    while frontier:
        current = frontier.popleft()  # FIFO ensures shortest hop count
        # Expand current node's walkable neighbours.
        for nxt in neighbours(current, walkable):
            if nxt in came_from:
                continue  # already discovered -> skip to avoid re-processing
            came_from[nxt] = current
            if nxt == goal:
                # Reconstruct the path by walking back through parents.
                path = [nxt]
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                path.reverse()  # was built goal -> start, flip it
                return path
            frontier.append(nxt)

    # Goal unreachable from start under the current ``walkable`` predicate.
    return None


def bfs_nearest(start, targets, walkable):
    """Return (target, path) for the *closest* cell in ``targets`` from ``start``.

    Useful for "go to nearest waste / nearest bin" behaviours. Performs a
    single multi-target BFS instead of running BFS once per target.
    """
    # Convert to a set for O(1) membership checks during expansion.
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
                # Reconstruct the path back to ``start``.
                path = [nxt]
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                path.reverse()
                return nxt, path
            frontier.append(nxt)

    # No target reachable.
    return None, None


def manhattan(a, b):
    """Manhattan distance heuristic used by A*."""
    # |dx| + |dy| is admissible on a 4-connected grid with unit costs.
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_path(start, goal, walkable):
    """A* shortest path (Manhattan heuristic) from start to goal.

    Returns the same shape of path as ``bfs_shortest_path``.
    """
    if start == goal:
        return [start]

    # Each entry on the open set: (f_score, tie_breaker, position).
    # The tie_breaker keeps heap ordering deterministic when f-scores tie.
    open_heap = []
    counter = 0
    heapq.heappush(open_heap, (manhattan(start, goal), counter, start))

    came_from = {start: None}
    g_score = {start: 0}  # cost so far from start to a cell

    while open_heap:
        _, _, current = heapq.heappop(open_heap)

        if current == goal:
            # Found the goal: reconstruct path via the parent map.
            path = [current]
            while came_from[path[-1]] is not None:
                path.append(came_from[path[-1]])
            path.reverse()
            return path

        for nxt in neighbours(current, walkable):
            tentative_g = g_score[current] + 1  # unit edge cost on grid
            # Skip neighbours we've already reached via a cheaper path.
            if tentative_g >= g_score.get(nxt, float("inf")):
                continue
            came_from[nxt] = current
            g_score[nxt] = tentative_g
            f_score = tentative_g + manhattan(nxt, goal)
            counter += 1
            heapq.heappush(open_heap, (f_score, counter, nxt))

    # No path found.
    return None
