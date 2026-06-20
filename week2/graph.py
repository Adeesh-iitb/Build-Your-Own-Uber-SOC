# graph_data.py

"""
Weighted graph used for shortest path experiments.

Each dictionary key represents a vertex.
The corresponding list contains tuples of the form:

    (adjacent_vertex, edge_cost)

The graph is undirected, therefore every edge appears
in the adjacency lists of both connected vertices.
"""

NETWORK = {

    0: [(1, 4), (7, 8)],

    1: [
        (0, 4),
        (2, 8),
        (7, 11)
    ],

    2: [
        (1, 8),
        (3, 7),
        (5, 4),
        (8, 2)
    ],

    3: [
        (2, 7),
        (4, 9),
        (5, 14)
    ],

    4: [
        (3, 9),
        (5, 10)
    ],

    5: [
        (2, 4),
        (3, 14),
        (4, 10),
        (6, 2)
    ],

    6: [
        (5, 2),
        (7, 1),
        (8, 6)
    ],

    7: [
        (0, 8),
        (1, 11),
        (6, 1),
        (8, 7)
    ],

    8: [
        (2, 2),
        (6, 6),
        (7, 7)
    ]
}

START_VERTEX = 0

# Reference distances from START_VERTEX
REFERENCE_DISTANCES = {
    0: 0,
    1: 4,
    2: 12,
    3: 19,
    4: 21,
    5: 11,
    6: 9,
    7: 8,
    8: 14,
}
