"""THE WORKER — goals run in the background, one runner per goal, and survive a restart.

The API only records what the person asked and returns; a daemon thread advances the goal through the orchestrator
while the page polls. Ownership is a lease row (goal, lease id, worker, until) renewed while the goal runs, so two
processes never advance the same goal (the claim-and-heartbeat design of CopilotKit/openmuse `engine/worker.ts`,
read in Phase 1 and re-implemented here). After a restart, a goal left `running` whose lease has lapsed is
recovered: its in-flight call is marked interrupted (tahodev/openmuse marks pending work interrupted on restart
rather than pretending it completed) and the goal is queued again, so the model sees the interruption and continues.
A cancel request is a flag the loop checks between steps. A reaper pass runs at startup and every HEARTBEAT_S:
a lease held by a process on this host that no longer exists counts as lapsed at once; any other lease lapses when
its renewal stops, so a goal is never stranded for longer than one lease."""
from __future__ import annotations

import os
import socket
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.agent import audit, orchestrator, store
from app.agent.models import AuditEntry, Goal, GoalStatus, now_iso

LEASE_S = 120                                   # a lease not renewed within this many seconds is lapsed
HEARTBEAT_S = 30
ACTIVE = (GoalStatus.PLANNING, GoalStatus.RUNNING)
WORKER = f"{socket.gethostname()}:{os.getpid()}"
_threads: dict[str, threading.Thread] = {}
_lock = threading.Lock()
_reaper: threading.Thread | None = None


def _dead_here(worker: str) -> bool:
    """A lease's holder is a process on this host that is gone: the lease is void whatever its clock says."""
    host, _, pid = worker.rpartition(":")
    if host != socket.gethostname() or not pid.isdigit() or int(pid) == os.getpid():
        return False
    try:
        os.kill(int(pid), 0); return False
    except ProcessLookupError:
        return True
    except PermissionError:
        return False


def _until(seconds: int = LEASE_S) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def enqueue(goal_id: str, llm_factory: Callable[[], object]) -> bool:
    """Claim the goal and run it on a background thread. False when another live runner holds it."""
    holder = store.lease_holder(goal_id)
    if holder and _dead_here(holder["worker"]):
        store.release_lease(goal_id, holder["lease_id"])
    lease = store.claim_lease(goal_id, WORKER, _until())
    if not lease:
        return False
    t = threading.Thread(target=_run, args=(goal_id, lease, llm_factory), name=f"goal-{goal_id}", daemon=True)
    with _lock:
        _threads[goal_id] = t
    t.start()
    return True


def _run(goal_id: str, lease: str, llm_factory) -> None:
    goal = store.load_goal(goal_id)
    if not goal:
        store.release_lease(goal_id, lease); return
    stop = threading.Event()
    beat = threading.Thread(target=_heartbeat, args=(goal_id, lease, stop), daemon=True); beat.start()
    try:
        orchestrator.run(goal, llm_factory(), stop=lambda: store.cancel_requested(goal_id))
    except Exception as exc:                                        # noqa: BLE001 - the goal records the real failure
        goal = store.load_goal(goal_id) or goal
        goal.status = GoalStatus.FAILED; goal.summary = f"{type(exc).__name__}: {str(exc)[:300]}"
        audit.write(AuditEntry(user_id=goal.user_id, goal_id=goal.id, kind="error", detail={"reason": goal.summary}))
        store.save_goal(goal)
    finally:
        stop.set(); store.release_lease(goal_id, lease)
        with _lock:
            _threads.pop(goal_id, None)


def _heartbeat(goal_id: str, lease: str, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_S):
        if not store.renew_lease(goal_id, lease, _until()):
            return                                                  # the lease was taken over; this runner's writes stop mattering


def wait(goal_id: str, timeout_s: float = 60.0) -> Goal | None:
    """Block until the goal's runner finishes (tests and the MCP path); the goal as stored afterwards."""
    with _lock:
        t = _threads.get(goal_id)
    if t:
        t.join(timeout_s)
    return store.load_goal(goal_id)


def cancel(goal_id: str) -> Goal | None:
    """Ask a running goal to stop at its next step; a paused goal is cancelled at once."""
    goal = store.load_goal(goal_id)
    if not goal or goal.status in (GoalStatus.DONE, GoalStatus.FAILED, GoalStatus.CANCELLED):
        return goal
    store.request_cancel(goal_id)
    if goal.status not in ACTIVE:                                   # waiting for the person: nothing is running, finish it here
        goal.status = GoalStatus.CANCELLED; goal.summary = "stopped by you"
        audit.write(AuditEntry(user_id=goal.user_id, goal_id=goal.id, kind="cancel", detail={"while": "paused"}))
        store.save_goal(goal)
    return goal


def resume_interrupted(llm_factory: Callable[[], object]) -> list[str]:
    """After a restart: every active goal whose lease lapsed gets its in-flight call marked interrupted and is queued again."""
    resumed = []
    for goal_id in store.active_goals(tuple(s.value for s in ACTIVE)):
        holder = store.lease_holder(goal_id)
        if holder and store.lease_alive(goal_id) and not _dead_here(holder["worker"]):
            continue
        goal = store.load_goal(goal_id)
        if not goal:
            continue
        for s in goal.steps:
            c = s.call
            if c and c.started_utc and not c.finished_utc and c.result is None and c.error is None:
                c.error = "interrupted by a restart before it finished; the result is unknown — check before repeating anything that leaves your space"
                c.finished_utc = now_iso()
        audit.write(AuditEntry(user_id=goal.user_id, goal_id=goal.id, kind="interrupted", detail={"by": "restart", "worker": WORKER}))
        store.save_goal(goal)
        if enqueue(goal_id, llm_factory):
            resumed.append(goal_id)
    return resumed


def start(llm_factory: Callable[[], object]) -> None:
    """One recovery pass now, then a reaper every HEARTBEAT_S so a stranded goal waits at most one lease."""
    global _reaper
    if _reaper and _reaper.is_alive():
        return
    def loop():
        while True:
            try:
                resumed = resume_interrupted(llm_factory)
                if resumed:
                    print(f"[agent] resumed {len(resumed)} interrupted goal(s): {', '.join(resumed)}")
                store.purge_lapsed_leases()
            except Exception as exc:                                # noqa: BLE001 - the reaper must outlive one bad pass
                print(f"[agent] recovery pass failed: {exc}")
            threading.Event().wait(HEARTBEAT_S)
    _reaper = threading.Thread(target=loop, name="goal-reaper", daemon=True); _reaper.start()


def state() -> dict:
    with _lock:
        running = sorted(_threads)
    return {"worker": WORKER, "running": running, "leases": [l | {"alive": l["until_utc"] > now_iso() and not _dead_here(l["worker"])} for l in store.list_leases()]}
