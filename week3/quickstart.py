"""
road_network_demo.py
--------------------

Small demonstration of working with OpenStreetMap road data
through the OSMnx package.

Features:
    • Downloads a drivable road network
    • Displays graph statistics
    • Examines sample vertices and edges
    • Finds the closest graph node to a coordinate
    • Produces a visualization of the network

Requirements:
    pip install osmnx matplotlib
"""

from pathlib import Path

import matplotlib.pyplot as plt
import osmnx as ox


CITY_NAME = "Hyderabad, India"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def download_network(place_name: str):
    """Retrieve a road graph from OpenStreetMap."""
    print(f"Fetching road network for {place_name}...")
    print("First download may take a little while.\n")

    return ox.graph_from_place(
        place_name,
        network_type="drive"
    )


def show_graph_summary(graph):
    """Display basic information about the graph."""

    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    print("GRAPH SUMMARY")
    print("-" * 40)
    print(f"Intersections : {node_count:,}")
    print(f"Road Segments : {edge_count:,}")


def inspect_sample_node(graph):
    """Print details from one graph node."""

    node_id = next(iter(graph.nodes))
    info = graph.nodes[node_id]

    print("\nEXAMPLE NODE")
    print("-" * 40)
    print(f"Node ID   : {node_id}")
    print(f"Latitude  : {info['y']}")
    print(f"Longitude : {info['x']}")


def inspect_sample_edge(graph):
    """Print details from one graph edge."""

    start, end, attributes = next(iter(graph.edges(data=True)))

    print("\nEXAMPLE EDGE")
    print("-" * 40)
    print(f"From      : {start}")
    print(f"To        : {end}")
    print(f"Length    : {attributes.get('length', 'Unknown')} m")
    print(f"Road Name : {attributes.get('name', 'Unnamed')}")


def find_closest_intersection(graph, latitude, longitude):
    """Locate nearest graph node."""

    node = ox.nearest_nodes(
        graph,
        X=longitude,
        Y=latitude
    )

    print("\nNEAREST NODE SEARCH")
    print("-" * 40)
    print(f"Coordinate : ({latitude}, {longitude})")
    print(f"Closest ID : {node}")

    return node


def save_network_plot(graph):
    """Generate and save a graph visualization."""

    print("\nGenerating graph visualization...")

    figure, axes = ox.plot_graph(
        graph,
        node_size=2,
        edge_linewidth=0.5,
        show=False,
        close=False
    )

    output_file = OUTPUT_DIR / "city_roads.png"

    figure.savefig(
        output_file,
        dpi=120,
        bbox_inches="tight"
    )

    plt.close(figure)

    print(f"Image saved to: {output_file}")


def main():

    road_graph = download_network(CITY_NAME)

    show_graph_summary(road_graph)

    inspect_sample_node(road_graph)

    inspect_sample_edge(road_graph)

    test_latitude = 17.3850
    test_longitude = 78.4867

    find_closest_intersection(
        road_graph,
        test_latitude,
        test_longitude
    )

    save_network_plot(road_graph)

    print("\nUseful Notes")
    print("-" * 40)
    print("• Graph type: NetworkX MultiDiGraph")
    print("• Latitude  -> graph.nodes[node]['y']")
    print("• Longitude -> graph.nodes[node]['x']")
    print("• Road length stored in edge['length']")
    print("• Use ox.nearest_nodes() to snap coordinates")
    print("• G.successors(node) returns outgoing neighbours")
    print("• Parallel roads may exist between two nodes")


if __name__ == "__main__":
    main()
