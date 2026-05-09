import heapq
import math
from typing import List, Tuple, Callable

def discretize(val: float, step: int = 10) -> int:
    return int(round(val / step) * step)

def get_neighbors(node: Tuple[int, int], grid_max: int = 100, step: int = 10) -> List[Tuple[int, int]]:
    x, y = node
    neighbors = []
    if x - step >= 0: neighbors.append((x - step, y))
    if x + step <= grid_max: neighbors.append((x + step, y))
    if y - step >= 0: neighbors.append((x, y - step))
    if y + step <= grid_max: neighbors.append((x, y + step))
    return neighbors

def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def astar_path(
    start_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    cost_fn: Callable[[Tuple[int, int], Tuple[int, int]], float],
    grid_max: int = 100,
    step: int = 10
) -> List[Tuple[float, float]]:
    """
    Computes an A* path on a coarse grid.
    Returns a list of (x,y) waypoints from start_pos to target_pos.
    """
    start_node = (discretize(start_pos[0], step), discretize(start_pos[1], step))
    target_node = (discretize(target_pos[0], step), discretize(target_pos[1], step))

    # If already in the same discrete node, just move straight to target
    if start_node == target_node:
        return [target_pos]

    open_set = []
    heapq.heappush(open_set, (0, start_node))
    came_from = {}
    
    g_score = {start_node: 0.0}
    f_score = {start_node: heuristic(start_node, target_node)}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == target_node:
            # Reconstruct path
            path = [target_pos]
            while current in came_from:
                current = came_from[current]
                if current != start_node:
                    path.append((float(current[0]), float(current[1])))
            path.reverse()
            return path

        for neighbor in get_neighbors(current, grid_max, step):
            tentative_g_score = g_score[current] + cost_fn(current, neighbor)
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, target_node)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    # Fallback to straight line if no path
    return [target_pos]
