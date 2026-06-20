"""
Week 4 Deliverable — Nearby Drivers Service
=============================================
Given a rider's lat/lng, return the 5 closest drivers in under 50ms.

Pick ONE of:
  (a) Geohash prefix matching (center cell + 8 neighbours), or
  (b) H3 k-ring lookup

You may lean on Redis's GEOSEARCH command OR roll your own geohash/H3
bucketing logic — either is fine. The point of the exercise is to understand
WHY this is fast, not to re-derive Redis's internals.

Rules:
  - Seed and query at least 10,000 drivers (see starter/seed_drivers.py)
  - Benchmark the query and report the timing
  - Explain (in REFLECTION.md) which approach you picked and why
"""

import os
import sys
import json
import math
import time

sys.path.insert(0, "../starter")


# ── Haversine distance (carried over from Week 3) ─────────────────────────────
# Needed at the end of every strategy to rank the shortlisted candidates exactly.

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    EARTH_RADIUS_KM = 6371

    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    chord = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(chord), math.sqrt(1 - chord))


# ── Strategy 1: Redis GEOSEARCH ────────────────────────────────────────────────

def query_drivers_via_redis(rider_lat: float, rider_lng: float, top_n: int = 5) -> list:
    """
    Delegate the nearest-neighbour search to Redis's geospatial sorted-set
    index, so the heavy lifting happens inside Redis rather than in Python.

        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        results = r.geosearch(
            "drivers:geo",
            longitude=rider_lng, latitude=rider_lat,
            radius=10, unit="km",
            count=top_n, sort="ASC",
            withdist=True
        )
        # -> [(driver_id, distance_km), ...]
    """
    import redis  # local import: keep this optional for folks without redis-py

    client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    return client.geosearch(
        "drivers:geo",            # geo key populated by seed_drivers.py
        longitude=rider_lng,
        latitude=rider_lat,
        radius=15,                 # wide enough net to comfortably cover top_n
        unit="km",
        count=top_n,
        sort="ASC",
        withdist=True,
    )


# ── Strategy 2: H3 k-ring lookup ───────────────────────────────────────────────

# Built lazily on first call and reused across every subsequent query in the run.
_h3_cell_index: dict = {}


def query_drivers_via_h3(rider_lat: float, rider_lng: float, drivers: dict,
                          top_n: int = 5, resolution: int = 7) -> list:
    """
    Bucket every driver into its H3 cell, then only scan the rider's cell
    plus its immediate ring of neighbours.

      1. Find the rider's H3 cell at `resolution`
      2. Pull the k-ring of neighbouring cells (k=1, widen to k=2 if thin)
      3. Bucket all drivers by H3 cell (built once, not per query)
      4. Collect every driver sitting in one of those cells
      5. Rank the collected candidates by exact Haversine distance

        import h3
        rider_cell = h3.latlng_to_cell(rider_lat, rider_lng, resolution)
        ring = h3.grid_disk(rider_cell, 1)
    """
    import h3

    global _h3_cell_index

    # Step 3 — build the bucket index once and cache it for the rest of the run.
    if not _h3_cell_index:
        bucket = {}
        for driver_id, location in drivers.items():
            cell_id = h3.latlng_to_cell(location["lat"], location["lng"], resolution)
            bucket.setdefault(cell_id, []).append((driver_id, location))
        _h3_cell_index = bucket

    # Step 1 — locate the rider within the same grid.
    rider_cell = h3.latlng_to_cell(rider_lat, rider_lng, resolution)

    # Step 2 — start with the tight 1-ring (7 cells: center + 6 neighbours).
    ring_radius = 1
    nearby_cells = h3.grid_disk(rider_cell, ring_radius)

    # Step 4 — pull every driver bucketed under one of those cells.
    shortlist = []
    for cell_id in nearby_cells:
        shortlist.extend(_h3_cell_index.get(cell_id, []))

    # Widen the search if the 1-ring didn't surface enough candidates.
    if len(shortlist) < top_n:
        nearby_cells = h3.grid_disk(rider_cell, 2)
        shortlist = []
        for cell_id in nearby_cells:
            shortlist.extend(_h3_cell_index.get(cell_id, []))

    # Step 5 — exact distance ranking over the (small) shortlist only.
    ranked = [
        (driver_id, haversine(rider_lat, rider_lng, location["lat"], location["lng"]))
        for driver_id, location in shortlist
    ]
    ranked.sort(key=lambda pair: pair[1])
    return ranked[:top_n]


# ── Strategy 3: Geohash prefix matching ────────────────────────────────────────

_geohash_bucket_index: dict = {}


def query_drivers_via_geohash(rider_lat: float, rider_lng: float, drivers: dict,
                               top_n: int = 5, precision: int = 5) -> list:
    """
    Bucket drivers by geohash prefix, then scan only the rider's cell and
    its 8 surrounding cells.

      1. Encode the rider's position at `precision`
      2. Look up the 8 neighbouring prefixes
      3. Bucket all drivers by geohash prefix (built once)
      4. Collect drivers whose prefix matches the center cell or a neighbour
      5. Rank the collected candidates by exact Haversine distance
    """
    import geohash2 as geohash

    global _geohash_bucket_index

    # Step 3 — build the prefix bucket once, reused on every subsequent call.
    if not _geohash_bucket_index:
        bucket = {}
        for driver_id, location in drivers.items():
            prefix = geohash.encode(location["lat"], location["lng"], precision)
            bucket.setdefault(prefix, []).append((driver_id, location))
        _geohash_bucket_index = bucket

    # Step 1 — rider's own cell prefix.
    rider_prefix = geohash.encode(rider_lat, rider_lng, precision)

    # Step 2 — the 8 adjacent prefixes, guarding against either API spelling.
    if hasattr(geohash, "neighbors"):
        adjacent_prefixes = geohash.neighbors(rider_prefix)
    else:
        adjacent_prefixes = geohash.neighbours(rider_prefix)

    cells_to_scan = [rider_prefix] + adjacent_prefixes

    # Step 4 — gather every driver bucketed under one of those 9 prefixes.
    shortlist = []
    for prefix in cells_to_scan:
        shortlist.extend(_geohash_bucket_index.get(prefix, []))

    # Step 5 — exact distance ranking over the shortlist only.
    ranked = [
        (driver_id, haversine(rider_lat, rider_lng, location["lat"], location["lng"]))
        for driver_id, location in shortlist
    ]
    ranked.sort(key=lambda pair: pair[1])
    return ranked[:top_n]


# ── Benchmark harness ──────────────────────────────────────────────────────────

def time_it(fn, *args, repeats: int = 100, **kwargs):
    """Call `fn` `repeats` times and return (last_result, avg_latency_ms)."""
    samples = []
    output = None

    for _ in range(repeats):
        t0 = time.perf_counter()
        output = fn(*args, **kwargs)
        samples.append((time.perf_counter() - t0) * 1000)

    return output, sum(samples) / len(samples)


def main():
    rider_lat, rider_lng = 17.3850, 78.4867  # Hyderabad city centre

    print(f"Rider location: ({rider_lat}, {rider_lng})\n")
    print("Querying 5 nearest drivers...\n")

    results, avg_latency_ms = None, None

    # Prefer a live Redis instance if one happens to be running and seeded.
    try:
        import redis
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        if client.exists("drivers:geo"):
            results, avg_latency_ms = time_it(query_drivers_via_redis, rider_lat, rider_lng)
            print("Strategy: Redis GEOSEARCH")
    except Exception:
        results, avg_latency_ms = None, None

    # Otherwise fall back to an in-memory index built from the local seed file.
    if not results:
        fallback_path = "../drivers_fallback.json"
        if os.path.exists(fallback_path):
            with open(fallback_path) as f:
                drivers = json.load(f)

            try:
                import h3
                results, avg_latency_ms = time_it(query_drivers_via_h3, rider_lat, rider_lng, drivers)
                print("Strategy: In-memory H3 grid")
            except ImportError:
                results, avg_latency_ms = time_it(query_drivers_via_geohash, rider_lat, rider_lng, drivers)
                print("Strategy: In-memory geohash prefix matching")

    if results:
        for rank, (driver_id, distance_km) in enumerate(results, start=1):
            print(f"{rank}. {driver_id}  →  {distance_km:.2f} km")

        within_budget = "✅" if avg_latency_ms < 50 else "❌"
        print(f"\nQuery time: {avg_latency_ms:.2f} ms  {within_budget} (target: under 50ms)")
    else:
        print("Not implemented yet — fill in one of the query_drivers_via_* functions above.")


if __name__ == "__main__":
    main()
