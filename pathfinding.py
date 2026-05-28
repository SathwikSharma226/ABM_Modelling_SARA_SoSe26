from collections import deque # double ended queue, efficient for FIFO operations, used in BFS
import heapq # used for priority queue in A* implementation

_NEIGHBOUR_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def neighbours(pos, walkable): # walkable is a function that takes a position and returns True if it's walkable and False if not
    """Yield walkable 4-connected neighbours of pos.
    walkable is a predicate (x, y) -> bool indicating whether a cell can be entered.
    """
    x, y = pos
    for dx, dy in _NEIGHBOUR_OFFSETS:
        nxt = (x + dx, y + dy)
        if walkable(nxt):
            yield nxt # yield is more efficient than return. It  returns a generator that produces values one at a time, more efficient in large grids.


def bfs_shortest_path(start, goal, walkable):
    """Return the shortest path from start to goal as a list of cells.

    The returned path includes both endpoints. Returns None if no path exists under the given walkable predicate.
    """
    frontier = deque([start]) # queue of cells to explore, initialized with the starting cell. deque used for efficient pops from the left (FIFO order).
    came_from = {start: None} # record the cell we came from to reach a given cell. used to reconstruct the path once we reach the goal.

    while frontier:
        current = frontier.popleft() # remove the oldest queued cell, ensuring breadth-first exploration
        for nxt in neighbours(current, walkable): # visit each walkable neighbour
            if nxt in came_from:
                continue # skip already visited
            came_from[nxt] = current # if next cell is new, record where we came from to reach it
            if nxt == goal:
                path = [nxt] # if nxt is goal, reconstruct path
                while came_from[path[-1]] is not None:
                    path.append(came_from[path[-1]])
                path.reverse() # reverse the path to get it from start to goal, since we built it backwards from the goal.
                return path
            frontier.append(nxt) # add new cell to explore queue
    return None


def bfs_nearest(start, targets, walkable):
    """Return (target, path) for the closest cell in targets.

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
                path.reverse() # reverse the path to get it from start to goal, since we built it backwards from the goal.
                return nxt, path
            frontier.append(nxt)
    return None, None


def manhattan(a, b):
    """Manhattan distance, an admissible heuristic on a 4-connected grid."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar_path(start, goal, walkable):
    """A* shortest path from start to goal using Manhattan heuristic.
    Returns the same shape of path as :func:`bfs_shortest_path`, or None when no path exists.
    """
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
            path.reverse() # reverse the path to get it from start to goal, since we built it backwards from the goal.
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