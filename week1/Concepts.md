# Week 1 — Ride-Hailing System Architecture

Personal study notes from Week 1 of the "build your own Uber" roadmap. Covers the service breakdown, the CAP theorem, the monolith-vs-microservices debate, and a short reflection on what stood out.

---

## 1. The Services, At a Glance

A ride-hailing platform isn't one program — it's a set of cooperating pieces, each with a narrow job. Here's the cast of characters from this week's architecture diagram:

| Service | Job | Talks to |
|---|---|---|
| **Rider App** | Lets a passenger sign up, request a ride, see a fare quote, watch the driver approach, and rate the trip afterward | Only the API Gateway — never a backend service directly |
| **Driver App** | Lets a driver go online/offline, broadcast location, and accept or decline ride requests | API Gateway + a WebSocket connection for live updates |
| **API Gateway** | The single front door for every client request — checks auth tokens, enforces rate limits, terminates SSL, and routes to the right internal service | Everything sits behind it; clients never see internal structure |
| **Dispatch / Matching Service** | The actual brain of the product: takes a ride request, finds nearby drivers, locks one down, and pushes the offer to them | Pricing, Redis, WebSocket layer, Postgres |
| **Pricing Service** | Works out the fare — base fee, distance, time, and a surge multiplier when demand is high | Redis (for live demand/supply numbers) |
| **Trip Service** | Owns the lifecycle of a single trip from "requested" through to "rated," and persists the final record | PostgreSQL |
| **Map / Routing Service** | Given two points, returns a route, an ETA, and a distance | Road graph data (PostGIS or an in-memory graph from OpenStreetMap) |
| **PostgreSQL** | The system of record — users, drivers, trips, payments, ratings | Everything that needs durability |
| **Redis** | The fast, in-memory layer doing several jobs at once: driver geolocation, online/offline flags, distributed locks, pub/sub fan-out for sockets, and surge counters | Dispatch, Pricing |

**One request, end to end:**

A rider asks for a ride → the gateway checks their token → Dispatch asks Pricing for a quote and asks Redis for the five nearest drivers → Dispatch takes a lock on one driver so two riders can't grab them at once → the driver gets notified over a WebSocket → once they accept, a trip record is created in Postgres and the state machine moves to "en route" → location updates stream to the rider in real time → on completion, Pricing computes the final fare and Postgres stores the closed-out trip.

**Vocabulary worth pinning down:**
- *Latency* — how long a single request takes to come back. Worth aiming under ~200ms for normal API calls and under ~100ms for live socket updates.
- *Throughput* — how many requests per second the system can absorb.
- *Availability* — the percentage of time the system is actually up; "five nines" means roughly five minutes of downtime a year.
- *Idempotency* — firing the same request twice should never double the effect. Non-negotiable for anything touching money or trip creation.
- *Eventual consistency* — every node gets to the same answer eventually, just not necessarily this millisecond.
- *TTL* — how long a cached value is allowed to live before it's considered stale.

---

## 2. CAP Theorem — Why You Can't Have It All

Originally put forward by Eric Brewer in 2000 and later proven formally by Gilbert and Lynch, the CAP theorem says a distributed system can only fully guarantee two of these three things at once:

- **Consistency** — every read gets the latest write, full stop. No server serves an old answer.
- **Availability** — every request gets *some* answer, even if a few nodes are down.
- **Partition Tolerance** — the system keeps functioning even when nodes can't talk to each other (dropped packets, severed links, the usual network chaos).

Here's the catch: in any real distributed deployment, network partitions are going to happen sooner or later — cables get cut, routers hiccup. So partition tolerance isn't really optional. The actual decision you're making is **CP or AP**:

- **CP systems** (Zookeeper, etcd, HBase) would rather throw an error than hand back a stale value.
- **AP systems** (Cassandra, DynamoDB, CouchDB) would rather hand back a slightly old value than refuse to answer.

### Mapping this onto the ride-hailing system

| Piece | CP or AP | Reasoning |
|---|---|---|
| PostgreSQL (trips, users, payments) | CP | A driver can't be double-booked and a rider can't be charged incorrectly — correctness beats uptime here |
| Redis (driver locations) | AP | A position that's 1–3 seconds stale is harmless; staying responsive matters more |
| Pricing Service | CP | The number shown to the rider has to match what actually gets charged |
| Driver online/offline flag | AP | A brief delay in reflecting status is fine; the system should never just stop responding |

**Two things worth not getting wrong:**
1. "CA" isn't a real category at scale — drop partition tolerance and you've basically reduced yourself to a single node.
2. The CP/AP choice isn't made once for the whole system; it only really bites *during* a partition, and you make it per-component, not globally. As Martin Kleppmann puts it, the theorem is better treated as a conversation-starter than as a label you slap on an entire database.

*Further reading: Kleppmann's piece on why "CP/AP" labels are oversimplified (martin.kleppmann.com), and the original Gilbert & Lynch paper on ACM.*

---

## 3. Monolith vs. Microservices

### Monolith
Everything — rider logic, dispatch, pricing, trips, maps — lives in one codebase, one deployable, usually one database.

**Strengths:** simple to run locally, function calls instead of network calls, one thing to deploy, and transactions across the whole system are just normal ACID transactions.

**Weaknesses:** a bug in one module (say, Pricing) can take the whole app down with it; scaling means scaling everything even if only one piece is actually under load; and as the codebase grows, it gets harder to navigate and teams start colliding.

### Microservices
Each responsibility — rider, dispatch, pricing, trips, maps, driver — becomes its own deployable service with its own data store.

**Strengths:** services deploy and scale independently, a crash in one doesn't take down the others, and teams can own a service end to end.

**Weaknesses:** every internal call is now a network call that can be slow or fail outright; there's no free ACID transaction spanning multiple services anymore; and you now need real operational infrastructure — service discovery, distributed tracing, monitoring — just to know what's happening.

### The trade-off, side by side

| Factor | Monolith | Microservices |
|---|---|---|
| Team size it suits | Small teams (roughly under 8 engineers) | Larger orgs with multiple independent teams |
| Operational maturity needed | Low | High (k8s, service mesh, tracing) |
| Speed early on | Fast | Slower, due to infra overhead |
| Speed at scale | Tends to slow down as coupling grows | Stays fast because teams are decoupled |
| Debugging | Easy — one log stream | Hard — traces span several services |
| Testing | Straightforward integration tests | Needs contract testing and mocks |

### What this roadmap actually calls for
A **modular monolith that behaves like microservices on paper**: one codebase and one database, but cleanly separated folders/modules per service, each exposing the same REST-style interface it would have if it really were a separate service. That gives the conceptual benefits of the split without needing a Kubernetes cluster to learn from it. Splitting a module out into a genuine standalone service can come later, as a stretch goal.

**A useful real-world data point:** Uber itself started as a single Python/SQLAlchemy monolith. By 2014, at around 40 engineers, that monolith was visibly straining, and the 2015–2016 migration to microservices followed. By 2020 they had ballooned to 2,200+ microservices — which created its own coordination headaches, leading them toward a "domain-oriented" grouping of related services instead of treating every service as fully independent. The takeaway: start simple, and only add the complexity of microservices once you've actually outgrown the monolith — not before.

*Further reading: Martin Fowler's "Microservices" article and his "Microservice Premium" piece on when the split isn't worth it; Uber's own engineering blog on the migration.*

---

## 4. Reflection

**What surprised me most:** My first instinct was that a driver's location would just live in the main database with everything else. That fell apart once I did the math — a GPS ping every 2–4 seconds per driver adds up to thousands of writes a minute across the fleet. Postgres is built for durable records like trip history and payments, not for absorbing that kind of write-heavy churn. Redis is the better fit precisely because it's in-memory, understands geospatial queries natively, and doesn't flinch at that volume. The database doesn't need to know where a driver *is right now* — only where they *were* when a trip wrapped up.

**The hardest trade-off to reason through:** Applying CAP wasn't a single decision for the whole system — it's a decision made separately for each service. Payments and trip records need real consistency, so Postgres running in CP mode is worth the occasional slowdown. Driver location and surge pricing can tolerate a couple of seconds of staleness without anyone noticing, so those lean AP. The question that actually helps is: *if this particular piece of data is two seconds old, does the user even notice?* Answer that per service, not for the system as a whole.

**Still an open question:** Redis's geospatial query gives Dispatch a shortlist of nearby drivers, but it's not obvious how the final pick is made. Is it pure distance, or does it also weigh driver rating, route efficiency, or how likely a driver is to actually accept the offer? My guess is the later weeks on routing and optimization will answer this.

**Time spent this week:** 1–2 hours.
