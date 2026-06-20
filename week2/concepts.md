# Week 2 — Shortest Paths and Graph Representations

Notes on Dijkstra's algorithm, how to actually store a graph in memory, and how this ties back into the Map/Routing service from Week 1's architecture.

---

## 1. Graph Representations — Pick This Before You Pick an Algorithm

Before running any graph algorithm, you need to decide how the graph itself lives in memory. There are two standard options.

### Adjacency List
Each node keeps a list of the neighbours it connects to, along with the edge weight.

```python
# Undirected, weighted graph with 4 nodes
graph = {
    0: [(1, 4), (2, 1)],   # node 0 connects to node 1 (weight 4) and node 2 (weight 1)
    1: [(0, 4), (3, 1)],
    2: [(0, 1), (3, 5)],
    3: [(1, 1), (2, 5)],
}
```

- Space: `O(V + E)`
- Checking if edge `(u, v)` exists: `O(degree(u))`
- Iterating over the neighbours of `u`: `O(degree(u))`

Best when the graph is **sparse** — far fewer edges than `V²`. Road networks and social graphs both fall into this category, and it's the default choice for almost every graph algorithm.

### Adjacency Matrix
A `V × V` grid where `matrix[u][v]` holds the weight of the edge from `u` to `v` (or `0`/`∞` when no edge exists).

```python
INF = float('inf')
# Same 4-node graph as above
matrix = [
    #  0    1    2    3
    [  0,   4,   1, INF],  # node 0
    [  4,   0, INF,   1],  # node 1
    [  1, INF,   0,   5],  # node 2
    [INF,   1,   5,   0],  # node 3
]
```

- Space: `O(V²)`
- Checking if edge `(u, v)` exists: `O(1)`
- Iterating over the neighbours of `u`: `O(V)` — you have to scan the whole row

Best when the graph is **dense**, or when you specifically need constant-time edge lookups. Also the natural choice for Floyd–Warshall, which needs all-pairs shortest paths anyway.

### Side by Side

| Operation | Adjacency List | Adjacency Matrix |
|---|---|---|
| Space | O(V + E) | O(V²) |
| Add edge | O(1) | O(1) |
| Remove edge | O(degree) | O(1) |
| Check if edge exists | O(degree) | O(1) |
| Get all neighbours | O(degree) | O(V) |
| Best suited for | Sparse graphs | Dense graphs |

### Why It Matters Here
Road networks are about as sparse as graphs get — a typical intersection has 3 or 4 connecting roads, not thousands. That makes the adjacency list the obvious pick for any routing work.

Mumbai's road graph, pulled from OpenStreetMap, has roughly 200,000 nodes and 500,000 edges:
- Adjacency list → around 700,000 entries total.
- Adjacency matrix → `200,000²` = **40 billion entries**, which simply isn't usable.

### BFS vs DFS, Quickly
| | BFS | DFS |
|---|---|---|
| Data structure | Queue | Stack (or recursion) |
| Finds shortest path? | Yes, for unweighted graphs | No |
| Memory usage | Higher — holds the whole frontier | Lower |
| Good for | Shortest path, level-order traversal | Cycle detection, topological sort, connected components |
| Time complexity | O(V + E) | O(V + E) |

The thing to remember: BFS only gives you the shortest path in terms of *number of edges*. As soon as edges have different weights, you need something else — which is exactly where Dijkstra comes in.

---

## 2. Dijkstra's Algorithm

### The Problem
Given a weighted graph and a single source node, find the shortest distance from that source to every other node in the graph.

### Example Graph

```
        4
   0 ———————— 1
   |           |
 1 |           | 1
   |           |
   2 ———————— 3
        5
```

Edges: `0→1` (weight 4), `0→2` (weight 1), `1→3` (weight 1), `2→3` (weight 5)

### The Algorithm, in Plain English
1. Set the distance to the source as `0`, and everything else as `∞`.
2. Push the source onto a min-heap with priority `0`.
3. While the heap isn't empty:
   - Pop the node with the smallest known distance.
   - If it's already been visited, skip it.
   - Otherwise, mark it visited.
   - For every unvisited neighbour: if `current_distance + edge_weight` beats their currently known distance, update it and push the neighbour onto the heap.

### Walking Through It (source = node 0)

**Start:**

| Node | Distance | Visited |
|---|---|---|
| 0 | **0** | No |
| 1 | ∞ | No |
| 2 | ∞ | No |
| 3 | ∞ | No |

Heap: `[(0, node_0)]`

**Pop node 0 (distance 0).** Check its neighbours:
- Node 1: `0 + 4 = 4 < ∞` → update to 4, push `(4, node_1)`
- Node 2: `0 + 1 = 1 < ∞` → update to 1, push `(1, node_2)`

| Node | Distance | Visited |
|---|---|---|
| 0 | 0 | Yes |
| 1 | **4** | No |
| 2 | **1** | No |
| 3 | ∞ | No |

Heap: `[(1, node_2), (4, node_1)]`

**Pop node 2 (distance 1).** Check its neighbours:
- Node 0: already visited, skip.
- Node 3: `1 + 5 = 6 < ∞` → update to 6, push `(6, node_3)`

| Node | Distance | Visited |
|---|---|---|
| 0 | 0 | Yes |
| 1 | 4 | No |
| 2 | 1 | Yes |
| 3 | **6** | No |

Heap: `[(4, node_1), (6, node_3)]`

**Pop node 1 (distance 4).** Check its neighbours:
- Node 0: already visited, skip.
- Node 3: `4 + 1 = 5 < 6` → **update to 5**, push `(5, node_3)`

| Node | Distance | Visited |
|---|---|---|
| 0 | 0 | Yes |
| 1 | 4 | Yes |
| 2 | 1 | Yes |
| 3 | **5** | No |

Heap: `[(5, node_3), (6, node_3)]` — note the stale `(6, node_3)` entry is still sitting in there.

**Pop node 3 (distance 5).** Mark it visited. No unvisited neighbours left to check.

Heap: `[(6, node_3)]`

**Pop `(6, node_3)`.** Node 3 is already visited, so this entry is just discarded. The heap is now empty — we're done.

### Final Answer

| Node | Shortest distance from node 0 | Path |
|---|---|---|
| 0 | 0 | `[0]` |
| 1 | 4 | `[0, 1]` |
| 2 | 1 | `[0, 2]` |
| 3 | 5 | `[0, 1, 3]` — not `[0, 2, 3]`, which would cost 6 |

### Why Bother With a Min-Heap?

Without one, finding the unvisited node with the smallest distance means scanning every node each iteration — `O(V)` per iteration, `O(V²)` overall. A min-heap keeps the smallest value sitting right at the top, so each pop only costs `O(log V)`, bringing the total down to `O((V + E) log V)`.

That difference isn't academic. For a road network with 200,000 nodes and 500,000 edges:
- Naive scan: `200,000²` ≈ **40 billion operations**.
- With a heap: `(200,000 + 500,000) × log(200,000)` ≈ **12 million operations**.

### Where Dijkstra Breaks Down

Dijkstra relies on one core assumption: once a node is popped off the heap and marked visited, its distance is final and will never improve. That assumption falls apart if a negative-weight edge could later open up a shorter path back to a node that's already been finalized.

The fix is **Bellman-Ford**, which relaxes every edge `V - 1` times and works correctly even with negative weights — at the cost of `O(V × E)` time, which is considerably slower. For our case this isn't a real concern: road network edge weights are distances or travel times, which are always non-negative, so Dijkstra is the right tool here.

---

## 3. Reflection

**Did the implementation pass on the first try?**
Not quite — it passed the basic cases right away, but I had a bug in how I was reconstructing the path that only showed up on the test with a tie between two routes of different lengths. Once I fixed how I was tracking "previous node," everything passed cleanly.

**Hardest part to implement?**
Path reconstruction, more than the core algorithm itself. The actual traversal — pop, relax neighbours, push — is fairly mechanical once you trust the heap. What took more care was walking backward from the destination using a dictionary of "previous node" pointers, handling the case where a node has no predecessor (the source itself), and then reversing the list so it reads source-to-target instead of target-to-source.

**Why does Dijkstra need a min-heap, in my own words?**
Every iteration, the algorithm needs to grab the unvisited node that's currently closest to the source. Without a heap, that means checking every single node's distance each time — an `O(V)` scan, every iteration, which adds up to `O(V²)` total. A min-heap keeps the smallest distance sitting at the top at all times, so grabbing it costs only `O(log V)`. On a graph with hundreds of thousands of nodes, that's the difference between something that finishes instantly and something that doesn't finish at all.

**Why does Dijkstra break on negative edges?**
It's a greedy algorithm — the moment a node is popped and marked visited, Dijkstra treats its distance as locked in for good. If a negative edge shows up later in the graph, it could offer a cheaper route back to a node that's already been "finalized," but Dijkstra has no mechanism to go back and check that, since it never revisits a node once it's marked done. The result is a distance that's wrong, and the algorithm has no way of knowing it's wrong.

**How does this connect to the ride-hailing project?**
This is exactly what the Map/Routing service from Week 1 needs to do under the hood. The road network maps naturally onto a graph — intersections as nodes, road segments as edges weighted by travel time — and Dijkstra (or a close variant of it) is what computes the actual route and ETA once Dispatch has matched a driver to a rider.

**Time spent this week:** 3 hours

**Self-assessment**

| Topic | Rating (1–5) |
|---|---|
| Adjacency list vs. matrix — know when to use each | 5 |
| BFS and DFS — could implement from memory | 5 |
| Dijkstra — could implement from memory | 5 |
| Min-heap / `heapq` — understand how it works | 5 |
| Time complexity `O((V+E) log V)` — understand the derivation | 5 |
