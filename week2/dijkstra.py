import heapq
import os
import sys

# Configure import path
base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base_dir)
sys.path.insert(0, os.path.join(project_root, "starter"))

from graph import GRAPH, SOURCE, EXPECTED_DISTANCES  # type: ignore


def shortest_paths(network: dict, start: int):
    """
    Compute shortest paths from a start node using Dijkstra's algorithm.
    """

    cost = {vertex: float("inf") for vertex in network}
    parent = {vertex: None for vertex in network}

    cost[start] = 0
    pq = [(0, start)]

    while pq:
        current_cost, vertex = heapq.heappop(pq)

        # Ignore outdated entries
        if current_cost > cost[vertex]:
            continue

        for nxt, edge_cost in network[vertex]:
            candidate = current_cost + edge_cost

            if candidate < cost[nxt]:
                cost[nxt] = candidate
                parent[nxt] = vertex
                heapq.heappush(pq, (candidate, nxt))

    return cost, parent


def build_route(parent: dict, start: int, destination: int):
    """
    Reconstruct route from start to destination.
    """

    route = []
    node = destination

    while node is not None:
        route.append(node)
        node = parent.get(node)

    route.reverse()

    return route if route and route[0] == start else []


def display_results(distances: dict, parents: dict):
    print(f"\nStarting Node: {SOURCE}")
    print("=" * 50)

    for node_id in sorted(GRAPH):
        route = build_route(parents, SOURCE, node_id)

        print(
            f"Target {node_id:<2} | "
            f"Distance = {distances[node_id]:<4} | "
            f"Route = {route}"
        )

    print("=" * 50)

    passed = True
    for node, expected in EXPECTED_DISTANCES.items():
        if distances[node] != expected:
            passed = False
            break

    print("Verification:", "PASS" if passed else "FAIL")


def main():
    dist, parent = shortest_paths(GRAPH, SOURCE)
    display_results(dist, parent)


if __name__ == "__main__":
    main()
