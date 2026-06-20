# Week 4 — Spatial Indexing: Geohash, Quadtrees, R-Trees, and H3

Notes on how to actually find "the 5 nearest drivers" out of a million, without scanning every row on every request — geohash first, then where quadtrees and R-trees fit in, then why Uber moved to hexagons with H3, and a reflection on building this against a real latency target.

---

## 1. The Problem: You Can't Sort a Million Drivers on Every Request

The naive way to find nearby drivers looks something like this:

```sql
SELECT * FROM drivers
ORDER BY ST_Distance(location, rider_location)
LIMIT 5;
```

This computes the distance from the rider to **every single driver** before sorting any of them — an `O(N log N)` operation, run fresh on every single ride request. That falls apart the moment you're dealing with hundreds of thousands of drivers and thousands of requests per second.

The fix is the same idea every spatial index is built around: **pre-bucket drivers into spatial cells, and only search the cells near the rider.** Geohash, quadtrees/R-trees, and H3 are three different ways of drawing those cells.

---

## 2. Geohash: Bisect the World Into a String

### The Idea
A geohash encodes a lat/lng point into a short string by repeatedly cutting the world in half — alternating between longitude and latitude:

```
Step 1: Is the point in the East or West half of the world?   -> 1 bit
Step 2: Is the point in the North or South half?               -> 1 bit
Step 3: Subdivide again within that quadrant...                -> repeat
```

Every 5 bits map to one character from the alphabet `0123456789bcdefghjkmnpqrstuvwxyz`. Hyderabad's city centre (17.3850, 78.4867), for instance, encodes to something starting with `tedb3...`. Each extra character shrinks the cell by roughly a factor of 8:

| Geohash length | Approx. cell size |
|---|---|
| 1 | ~5,000 km |
| 3 | ~150 km |
| 5 | ~5 km |
| 7 | ~150 m |
| 9 | ~5 m |

### Why It's Useful
Geohashes have a convenient property: points that are physically close usually share a prefix.

```
Point A: tedb3xyz...
Point B: tedb3abc...
         └─┬─┘
   same prefix -> same ~5 km cell
```

So finding nearby drivers becomes an indexed string-prefix lookup instead of a distance calculation over the whole table:

1. Compute the rider's geohash at a chosen precision (5 characters ≈ 5 km cells).
2. Query: `SELECT * FROM drivers WHERE geohash LIKE 'tedb3%'`.
3. That's a fast, indexed prefix match, even across millions of rows.

### The Edge Case You Have to Handle
Two points can sit a few hundred metres apart and still get totally different geohashes, if they happen to fall on opposite sides of a high-level boundary:

```
Point A: u000   (just west of a major cell boundary)
Point B: ezzz   (just east of that boundary)
```

These could be 30 km apart in reality — or right next to each other across a line — and share **zero** common prefix characters either way. A query that only checks the rider's exact cell will silently miss drivers sitting just across that line.

**The fix:** always search the rider's cell plus its 8 neighbouring cells, never just the exact prefix:

```python
import geohash2 as geohash

code = geohash.encode(17.3850, 78.4867, precision=7)     # encode
lat, lon = geohash.decode('tedb3xy')                       # decode
neighbours = geohash.neighbors('tedb3xy')                  # the 8 surrounding cells
```

```sql
SELECT * FROM drivers
WHERE geohash IN ('tedb3', 'tedb1', 'tedb9', 'tedb2', ...) -- center + 8 neighbours
```

### Geohash, Summed Up
| | |
|---|---|
| Key idea | Recursively bisect lat/lng into a string; shared prefix ≈ proximity |
| Strength | Simple; works with plain string indexing in almost any database |
| Weakness | Boundary-straddling edge case; rectangular cells don't have uniform distance to all neighbours |
| Fix | Always query the center cell plus its 8 neighbours |

---

## 3. Quadtrees and R-Trees: Adapting to Where the Data Actually Is

Geohash always cuts space the same way regardless of where the data is. Quadtrees and R-trees take the opposite approach: they subdivide more where the data is denser.

### Quadtrees (Conceptual)
A quadtree recursively splits 2D space into four quadrants, but only subdivides further in the quadrants that actually need it:

```
┌─────┬─────┐
│ NW  │ NE  │
├─────┼─────┤
│ SW  │ SE  │   <- SW has lots of points, so it gets subdivided further
└─────┴─────┘

┌─────┬─────┐
│ NW  │ NE  │
├──┬──┼─────┤
│NW│NE│     │
├──┼──┤ SE  │
│SW│SE│     │
└──┴──┴─────┘
```

**Strength:** adapts naturally to data density — sparse regions stay coarse, dense regions get fine-grained. **Weakness:** because cells are different sizes, "is point A within X km of point B" is harder to reason about uniformly, and the structure is more involved to implement and query than a flat hash.

### R-Trees (Conceptual)
An R-tree is built the other way round — bottom-up from the data rather than top-down by fixed subdivision. It groups nearby objects into bounding rectangles, then groups those rectangles into larger bounding rectangles, recursively:

```
Leaf level:    [Driver A] [Driver B] [Driver C] [Driver D]
                    └─────┬─────┘         └─────┬─────┘
Level 1:          [Bounding Box 1]      [Bounding Box 2]
                            └──────┬──────┘
Root:                  [Bounding Box covering all]
```

**Where this actually shows up:** this is exactly what's running under the hood of `ST_DWithin`, `ST_Distance`, and PostGIS's other spatial queries. Creating a `GIST` index on a `geometry` column in PostgreSQL is, in effect, building an R-tree.

---

## 4. H3: Why Uber Moved to Hexagons

Uber built H3 to get past two problems they kept running into with geohash-style square grids at very high volume (millions of driver pings per second).

### Problem 1 — Squares Don't Have Equal Neighbours
```
┌───┬───┬───┐
│ NW│ N │ NE│   <- diagonal neighbours (NW, NE, SW, SE)
├───┼───┼───┤      are √2 times farther than edge neighbours (N, S, E, W)
│ W │ X │ E │
├───┼───┼───┤
│ SW│ S │ SE│
└───┴───┴───┘
```
This makes "give me everything within radius R" inconsistent — some of the cells you'd grab are meaningfully closer than others, purely because of grid geometry, not actual distance.

**The hexagon fix:**
```
      ___
     /   \
 ___/  N  \___
/   \     /   \
| NW |  X  | NE |
\___/     \___/
    \  S  /
     \___/
```
Every hexagon has exactly 6 neighbours, and all 6 are the same distance from the center. That makes a radius search (H3's `k-ring`, now called `grid_disk`) mathematically uniform — there's no diagonal-vs-edge distortion to correct for.

### Problem 2 — Boundary-Straddling
This is the same edge case geohash has: two nearby points can land in very different cells if they straddle a boundary. H3 doesn't make boundaries disappear — no tiling of space can — but it makes handling them trivial: always query the center cell plus its ring of neighbours, and because hexagons are symmetric, that ring looks the same in every direction, with no special-casing needed.

### H3 Resolution Levels
H3 has 16 resolution levels, from 0 (coarsest) to 15 (finest):

| Resolution | Approx. hexagon edge length | Use case |
|---|---|---|
| 0 | ~1,107 km | Continent-level analysis |
| 5 | ~8.5 km | City-level demand heatmaps |
| 7 | ~1.2 km | Neighbourhood-level driver search |
| 9 | ~0.17 km | Street-level matching |
| 15 | ~0.5 m | Building footprint |

For "find nearby drivers," resolution 7–8 is generally the sweet spot — fine enough to be meaningful, coarse enough that you're not scanning dozens of cells to get a usable candidate list.

### Looking Up Nearby Cells with k-ring
```python
import h3

center = h3.latlng_to_cell(17.3850, 78.4867, 7)   # resolution 7
ring = h3.grid_disk(center, 1)                     # center + 1 ring of neighbours (7 cells total)
```
To find nearby drivers in practice: compute each driver's H3 cell at resolution 7, group drivers by that cell, then for any rider look up `grid_disk(rider_cell, k=1)` and pull every driver sitting in those cells.

---

## 5. All Three, Side by Side

| | Geohash | Quadtree / R-tree | H3 |
|---|---|---|---|
| Cell shape | Rectangle | Rectangle (variable size) | Hexagon |
| Neighbour distances | Unequal (diagonal vs. edge) | N/A — irregular | Equal — all 6 neighbours equidistant |
| Adapts to data density | No — fixed grid | Yes | No — fixed grid, but multi-resolution |
| Used by | Redis `GEO` commands | PostGIS (`GIST` index) | Uber, Lyft, and most ride-hailing/delivery platforms |
| Best for | Simple proximity search, easy to index in any DB | General-purpose spatial queries | High-volume radius search needing uniform symmetry |

---

## 6. Reflection

**Which approach did I use, and why?**
I went with the in-memory H3 grid (Option B). The deciding factor was the equidistant-neighbour property — every hexagon's 6 neighbours sit at exactly the same distance from its center, so a `k-ring`/`grid_disk` radius search behaves consistently in every direction. Geohash's rectangular cells don't give you that; the diagonal neighbours are always farther away than the edge ones, which makes "within radius R" a slightly fuzzier guarantee.

**What was the measured query time?**
1.34 ms average, over 100 runs — comfortably inside the under-50ms target.

**Why does bucketing beat scanning all drivers, in my own words?**
Scanning every driver means computing a real distance calculation for each one, for every single request, with no index to skip past anyone — that's a full `O(N)` pass before you've even sorted anything. Bucketing flips this around: drivers get sorted into cells ahead of time, so a request only has to look at the handful of cells actually near the rider and can ignore the rest of the city outright. The win isn't that the math per driver got cheaper — it's that you stop doing the math for drivers that were never going to be candidates anyway.

**Describe the boundary edge case in my own words.**
Two drivers standing right next to each other in real life can still end up in completely different cells if they happen to fall on opposite sides of a grid line — whether that's a geohash prefix boundary or an H3 cell edge. If a query only checks the rider's exact cell, it'll miss a driver who's genuinely close by but technically one cell over. The fix is the same in both systems: always check the rider's cell plus its immediate ring of neighbours, never just an exact match.

**Why does Uber use hexagons instead of squares for H3?**
Because a square's diagonal neighbours are about 1.41× (√2) farther from the center than its edge neighbours, which makes radius searches inconsistent — some "neighbouring" cells are noticeably closer than others purely due to grid shape, not real distance. A hexagon has exactly 6 neighbours and all 6 sit at the same distance from the center, so a radius search expands evenly in every direction with no geometric distortion to account for.

**What resolution did I choose, and why?**
Resolution 7, with an edge length of roughly 1.2 km. That's small enough to keep a `k=1` or `k=2` disk search meaningfully local — you're not sweeping in drivers from across town — but large enough that a single ring still has enough candidate drivers in it before the final Haversine sort kicks in to pick the closest ones.

**How does this connect to the Dispatch service from Week 1?**
This is exactly the layer the Dispatch/Matching Service depends on to find candidates quickly. It also reinforces something from Week 1's reflection: driver location updates arrive every few seconds per driver, which is far too high a write volume for PostgreSQL to absorb directly. That traffic needs to live in something built for it — Redis or an in-memory H3 grid — so the core transactional tables (trips, payments, users) never get put under that kind of write pressure.

**Time spent this week:** 4 hours

**Self-assessment**

| Topic | Rating (1–5) |
|---|---|
| Geohash encoding and prefix search | 5 |
| The boundary-straddling edge case and its fix | 5 |
| Quadtrees / R-trees — conceptual understanding | 5 |
| H3 hexagons — why they're used and how k-ring works | 5 |
| Could explain "why not just scan all drivers" to a non-technical person | 5 |
