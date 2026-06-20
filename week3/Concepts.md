# Week 3 — A* Search and the Haversine Heuristic

Notes on why A* beats Dijkstra on a real road network, what makes a heuristic safe to use, the Haversine formula itself, and a reflection on running this against an actual city graph.

---

## 1. The Core Idea: Search With a Sense of Direction

Dijkstra explores a graph with no idea where the destination is. It just keeps expanding outward to whichever unvisited node is currently cheapest to reach — which means it spreads evenly in every direction, like a wave growing from a single point, including down roads that are obviously heading the wrong way.

A* fixes this by adding a sense of direction. It still uses a priority queue, exactly like Dijkstra, but it changes what goes into the priority:

| Algorithm | Priority of a node | Meaning |
|---|---|---|
| Dijkstra | `g(n)` | Actual cost from the start to `n` |
| A* | `f(n) = g(n) + h(n)` | Actual cost so far, **plus an estimate of what's left to the goal** |

- `g(n)` — the real, known cost from the start to node `n` (identical to what Dijkstra tracks).
- `h(n)` — the **heuristic**: a guess at how much further it is from `n` to the goal.
- `f(n)` — the total estimated cost of the cheapest path that passes through `n`.

Because `f(n)` factors in "how close does this look to the goal," A* naturally prioritizes nodes that are pointed in the right direction, and the search ends up shaped like a narrow corridor toward the destination instead of a circle around the start.

---

## 2. What Makes a Heuristic Trustworthy

Adding a heuristic only works if the heuristic plays by two rules.

### Admissible — never overestimate
`h(n)` must never claim the remaining distance is *more* than it actually is. If the true remaining distance from `n` to the goal is 5 km, `h(n)` has to be 5 km or less.

If a heuristic overestimates even once, it can quietly sabotage correctness: A* will treat a node on the actual shortest path as if it were more expensive than it really is, deprioritize it in favor of a route that only *looks* cheaper, and potentially finish with the wrong answer — without any way of knowing it got it wrong.

### Consistent (monotone) — a stronger, related guarantee
For every node `n` and neighbour `n'`:

```
h(n) ≤ cost(n, n') + h(n')
```

Consistency implies admissibility, and it buys you something extra: A* never has to reopen a node it's already finalized, which keeps the algorithm's behavior clean and predictable.

### Three Common Heuristics for Road-Like Graphs

**Euclidean (straight-line) distance**
```python
import math
def euclidean(node, goal):
    dx = node.x - goal.x
    dy = node.y - goal.y
    return math.sqrt(dx**2 + dy**2)
```
Admissible on a flat grid, but wrong for latitude/longitude — degrees aren't a fixed distance, so this badly misjudges real-world distance.

**Manhattan distance**
```python
def manhattan(node, goal):
    return abs(node.x - goal.x) + abs(node.y - goal.y)
```
Admissible only when movement is restricted to a grid of horizontal and vertical steps. Roads aren't laid out that way, so this doesn't apply here either.

**Haversine (great-circle) distance** — the one that actually fits this project, covered in full below.

---

## 3. The Haversine Formula

### Why Plain Euclidean Distance Doesn't Work Here
On a flat plane, distance is just `d = √((x2−x1)² + (y2−y1)²)`. But latitude and longitude are angles on a sphere, not flat coordinates — a degree of longitude is about 111 km wide at the equator and shrinks toward 0 km near the poles. Treating lat/lng like ordinary x/y coordinates gives a meaningless number.

### What It Actually Computes
Haversine gives the **great-circle distance**: the shortest path between two points along the curved surface of a sphere, accounting for the Earth's curvature rather than treating it as flat.

```
a = sin²(Δlat/2) + cos(lat1) · cos(lat2) · sin²(Δlon/2)
c = 2 · atan2(√a, √(1−a))
d = R · c
```

- `lat1, lon1` / `lat2, lon2` — the two points, in **radians**
- `Δlat = lat2 − lat1`, `Δlon = lon2 − lon1`
- `R = 6,371,000` m — Earth's mean radius
- `d` — the resulting distance, in metres

### Implementation
```python
import math

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance in metres between two lat/lng points (decimal degrees).
    Example: Hyderabad (17.3850, 78.4867) to Secunderabad (17.4416, 78.4983)
             -> roughly 6,400 metres
    """
    R = 6_371_000  # Earth's mean radius in metres
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
```

### Sanity Checks
```python
# Mumbai to Delhi (should be ~1,150 km)
print(haversine(19.0760, 72.8777, 28.6139, 77.2090) / 1000)
# -> ~1,149 km

# Same point twice (should be 0)
print(haversine(17.3850, 78.4867, 17.3850, 78.4867))
# -> 0.0
```

### Why This Is Admissible
Haversine gives the straight-line distance across the Earth's surface. A road can only ever be *longer* than that straight line — it has to bend, detour, follow terrain — never shorter. So:

```
haversine(node, goal) ≤ true_road_distance(node, goal)
```

always holds, which is exactly the admissibility condition A* needs.

### How Accurate Is It, Really?
Haversine assumes a perfectly round Earth, but the Earth is slightly oblate — a bit wider at the equator than pole to pole. That introduces up to roughly 0.5% error over very long distances. For anything city-scale (well under 100 km), this is negligible. Production-grade systems needing higher precision use the **Vincenty formula**, which accounts for the ellipsoid shape — but Haversine is more than good enough for routing within a city.

### Where OSMnx Already Has This
OSMnx stores coordinates per node and computes edge lengths automatically:
- `G.nodes[node_id]['y']` → latitude
- `G.nodes[node_id]['x']` → longitude
- `G.edges[u, v, 0]['length']` → edge length in metres, which OSMnx already derives internally using Haversine.

---

## 4. A* vs. Dijkstra: How Much Does the Heuristic Actually Save?

Picture the shape of each search on a road network:

```
Dijkstra: explores a full circle, radius = distance to goal
A*:       explores a narrow corridor, roughly pointed at the goal
```

Typical savings on a city-scale routing query:
- Dijkstra: ends up exploring **40–60%** of the graph.
- A* with Haversine: ends up exploring only **5–15%** of the graph.

### My Own Result on a Real City Query
| Algorithm | Nodes explored |
|---|---|
| A* (Haversine heuristic) | 2,530 |
| Dijkstra | 28,556 |
| **Reduction** | **91%** |

That's a far bigger saving than the typical range above, which says more about this particular query (likely a fairly direct point-to-point route, where Dijkstra wastes a lot of effort exploring in every other direction) than about a flaw in either algorithm — both still return the exact same shortest path.

---

## 5. Beyond A*: What Production Routing Engines Actually Do

### Bidirectional A* (conceptual)
Run A* outward from the source *and* backward from the goal at the same time, and stop as soon as the two search frontiers meet in the middle. This roughly halves the search space again on top of what A* already saves, and it's part of how systems like Google Maps and Apple Maps handle long-distance routes.

### Contraction Hierarchies (conceptual)
A precomputation trick used by real routing engines (OSRM, Valhalla, GraphHopper):
1. **Preprocess once:** rank every node by "importance," strip out the less important ones, and insert shortcut edges that still preserve true distances.
2. **Query fast:** run a bidirectional search, but only across the upper, important layers of the hierarchy.

The preprocessing step can take hours, but it only has to run once — after that, queries on continent-scale graphs return in milliseconds. This is roughly how Uber's actual routing works at production scale. Not something to implement here, but worth knowing it's the reason "real" routing feels instant.

---

## 6. Reflection

**How many nodes did A* explore vs. Dijkstra on my city query?**
A* explored 2,530 nodes; Dijkstra explored 28,556 — about a 91% reduction.

**Why did A* explore so many fewer nodes, in my own words?**
Dijkstra has no concept of "toward the goal" — it just keeps grabbing whatever unvisited node is currently cheapest, which means it expands evenly in every direction at once, including down roads heading the wrong way entirely. A* adds the Haversine distance as a heuristic, so every node also gets scored on how close it looks to the destination in a straight line. That tilts the search toward nodes that are actually making progress, which keeps it confined to a tight corridor toward the goal instead of fanning out across the whole map.

**What would happen if the heuristic overestimated the true distance?**
It would break admissibility. If `h(n)` claims a node is farther from the goal than it actually is, A* might wrongly deprioritize a node that's actually on the optimal path, because it looks artificially expensive compared to some other route. The algorithm could then settle on a path that isn't actually the shortest one — and worse, it would have no way of detecting that it had gotten the wrong answer.

**What is the Haversine formula actually calculating?**
The great-circle distance — the shortest possible path between two points along the curved surface of a sphere, rather than a flat straight line. It works directly off latitude and longitude in radians and accounts for the Earth's curvature, which is the whole reason it works correctly for lat/lng coordinates while ordinary Euclidean distance doesn't.

**What surprised me about the OSMnx road graph?**
Mostly just the scale — even a fairly small, localized area turns into thousands of nodes and directed edges once you actually load it. I also didn't expect how much real infrastructure detail comes through automatically: multi-lane junctions, street names, and strict one-way restrictions are all captured because OSMnx represents the graph as a `MultiDiGraph`, and those one-way edges genuinely change which routes are even legal, not just which ones are fastest.

**How does this connect to the ride-hailing system from Week 1?**
This is the actual engine behind the Map/Routing service from the Week 1 architecture. Every time a rider requests a trip, this is what computes the real driving distance and ETA — and that output feeds directly into Pricing (to calculate the fare) and Dispatch (to decide which driver actually makes sense to assign).

**Time spent this week:** 1 hour

**Self-assessment**

| Topic | Rating (1–5) |
|---|---|
| A* algorithm — could implement from memory | 5 |
| Admissible heuristic — understand the requirement | 5 |
| Haversine formula — understand what it computes | 5 |
| OSMnx — comfortable loading a graph and querying it | 5 |
| Bidirectional A* / contraction hierarchies — conceptual understanding | 4 |
