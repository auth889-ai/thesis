# third_party/

Adapters for official research repositories — **never** copies of them.

Rules: upstream is fetched at a pinned SHA into the execution environment and
never committed here; an adapter only translates between upstream's API and a
`dhakaflow` Protocol, then registers itself via `common.registry`; heavy
imports stay inside factory functions. Per-lab pins live in each lab's
`upstream/UPSTREAM_LOCK.yaml` (see paper_labs/01_sumo_foundation/upstream/).
Empty until Lab 04.
