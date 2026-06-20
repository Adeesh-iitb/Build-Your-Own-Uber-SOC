import heapq
import math


def great_circle_distance(lat_a, lon_a, lat_b, lon_b):
    """Return spherical distance (metres) between two coordinates."""

    earth_radius = 6371000

    lat_a = math.radians(lat_a)
    lat_b = math.radians(lat_b)

    d_lat = lat_b - lat_a
    d_lon = math.radians(lon_b - lon_a)

    term = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_a)
        * math.cos(lat_b)
        * math.sin(d_lon / 2) ** 2
    )

    angle = 2 * math.atan2(math.sqrt(term), math.sqrt(1 - term))

    return earth_radius * angle


def reconstruct_route(parent_map, start, goal):
    """Rebuild route from predecessor information."""

    route = [goal]
    node = goal

    while node != start:
        node = parent_map.get(node)

        if node is None:
            return []

        route.append(node)

    route.reverse()
    return route


def astar_search(graph, start, goal):
    """A* shortest-path search."""

    goal_lat = graph.nodes[goal]["y"]
    goal_lon = graph.nodes[goal]["x"]

    frontier = []

    initial_h = great_circle_distance(
        graph.nodes[start]["y"],
        graph.nodes[start]["x"],
        goal_lat,
        goal_lon,
    )

    heapq.heappush(frontier, (initial_h, 0.0, start))

    cost_so_far = {start: 0.0}
    predecessor = {}

    explored = 0

    while frontier:

        estimated_total, current_cost, current = heapq.heappop(frontier)

        if current_cost > cost_so_far.get(current, float("inf")):
            continue

        explored += 1

        if current == goal:
            break

        for nxt in graph.successors(current):

            segment = min(
                edge["length"]
                for edge in graph[current][nxt].values()
            )

            candidate_cost = current_cost + segment

            if candidate_cost < cost_so_far.get(nxt, float("inf")):

                cost_so_far[nxt] = candidate_cost
                predecessor[nxt] = current

                heuristic = great_circle_distance(
                    graph.nodes[nxt]["y"],
                    graph.nodes[nxt]["x"],
                    goal_lat,
                    goal_lon,
                )

                priority = candidate_cost + heuristic

                heapq.heappush(
                    frontier,
                    (priority, candidate_cost, nxt),
                )

    final_route = reconstruct_route(predecessor, start, goal)

    return (
        final_route,
        cost_so_far.get(goal, float("inf")),
        explored,
    )


def dijkstra_search(graph, start, goal):
    """Classic Dijkstra shortest-path algorithm."""

    queue = [(0.0, start)]

    best_distance = {start: 0.0}
    predecessor = {}

    explored = 0

    while queue:

        current_distance, node = heapq.heappop(queue)

        if current_distance > best_distance.get(node, float("inf")):
            continue

        explored += 1

        if node == goal:
            break

        for neighbour in graph.successors(node):

            edge_length = min(
                edge["length"]
                for edge in graph[node][neighbour].values()
            )

            candidate = current_distance + edge_length

            if candidate < best_distance.get(neighbour, float("inf")):

                best_distance[neighbour] = candidate
                predecessor[neighbour] = node

                heapq.heappush(
                    queue,
                    (candidate, neighbour),
                )

    route = reconstruct_route(predecessor, start, goal)

    return (
        route,
        best_distance.get(goal, float("inf")),
        explored,
    )
