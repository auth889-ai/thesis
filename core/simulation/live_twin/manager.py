"""Live twins on this server: one per visitor, at most MAX_RUNNING simulations at once (twins plus the site's single map live job or
3D City run), each stopped after IDLE_S without a viewer. On the hosted app each also stops after HOSTED_WALL_S of real time, and
starts are limited per visitor per day (backend/app/platform/ratelimit.py)."""
from __future__ import annotations

import os
import threading
import time

from core.simulation.live_twin.session import Refused, Session

MAX_RUNNING = 3
IDLE_S = 60
HOSTED_WALL_S = 600


def hosted() -> bool:
    return os.environ.get("TRAFFICTWIN_HOSTED") == "1"


def others_running() -> int:
    """The site's other simulations: a map live job (core/simulation/live_jobs) and the 3D City run."""
    from core.simulation.live_jobs import runner
    from core.simulation.twin.live import runtime as twin
    n = int(runner.busy())
    n += int(twin.live_sim.state(with_vehicles=False).get("status") in ("starting", "running", "paused"))
    return n


class Manager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()
        self._reaper = None

    def alive(self) -> list[Session]:
        return [s for s in self.sessions.values() if s.status in ("starting", "warming", "running")]

    def start(self, city_id: str, visitor: str, speed: float = 8.0, technology: str = "its_g5") -> tuple[Session, bool]:
        """(session, created). A visitor who already has a running twin gets it back (one per visitor)."""
        with self.lock:
            mine = [s for s in self.alive() if s.visitor == visitor]
            if mine:
                return mine[0], False
            if len(self.alive()) + others_running() >= MAX_RUNNING:
                raise Refused(f"this server is running {MAX_RUNNING} simulations already; try again in a few minutes", "full", n=MAX_RUNNING)
            s = Session(city_id, visitor, speed=speed, technology=technology, hosted_wall_s=HOSTED_WALL_S if hosted() else None)
            self.sessions[s.id] = s
            s.start()
            self._ensure_reaper()
            return s, True

    def get(self, sid: str) -> Session | None:
        return self.sessions.get(sid)

    def _ensure_reaper(self) -> None:
        if self._reaper and self._reaper.is_alive():
            return
        self._reaper = threading.Thread(target=self._reap, daemon=True, name="live-twin-reaper")
        self._reaper.start()

    def reap_once(self, now: float | None = None) -> bool:
        """Stop twins with no viewer for IDLE_S; forget stopped ones after ten minutes. True while any twin is still alive."""
        now = time.time() if now is None else now
        with self.lock:
            for s in self.alive():
                if now - s.last_seen > IDLE_S:
                    s.say(f"stopped: no viewer for {IDLE_S} s", "idle", s=IDLE_S)
                    s.stop()
            for sid, s in list(self.sessions.items()):
                if s.status in ("stopped", "failed") and now - s.last_seen > 600:
                    self.sessions.pop(sid)
            return bool(self.alive())

    def _reap(self) -> None:
        while True:
            time.sleep(5)
            if not self.reap_once():
                self._reaper = None
                return


MANAGER = Manager()
