/**
 * Live connection over Server-Sent Events.
 *
 * The point of this file is the failure path. A dashboard that silently freezes on stale numbers
 * when its stream dies is the clearest sign of a toy, so this tracks connection state explicitly
 * and publishes it: `connected`, `reconnecting`, `offline`. EventSource retries on its own (the
 * server sends a `retry:` hint); this adds a watchdog for the case where the socket stays open but
 * data stops arriving, which EventSource does not detect.
 */
const STALE_AFTER_MS = 30_000;

class LiveStream extends EventTarget {
  constructor(path = "/api/stream") {
    super();
    this.path = path;
    this.status = "offline";
    this.lastMessageAt = 0;
    this.source = null;
  }

  start() {
    this.#connect();
    this.watchdog = setInterval(() => {
      if (this.status === "connected" && Date.now() - this.lastMessageAt > STALE_AFTER_MS) {
        this.#setStatus("reconnecting");     // socket open but silent: force a fresh connection
        this.source?.close();
        this.#connect();
      }
    }, 5_000);
  }

  stop() {
    clearInterval(this.watchdog);
    this.source?.close();
    this.#setStatus("offline");
  }

  #connect() {
    this.source = new EventSource(this.path);
    this.source.addEventListener("open", () => this.#setStatus("connected"));
    this.source.addEventListener("update", (e) => {
      this.lastMessageAt = Date.now();
      this.#setStatus("connected");
      this.dispatchEvent(new CustomEvent("pulse", {detail: JSON.parse(e.data)}));
    });
    this.source.addEventListener("error", () => this.#setStatus("reconnecting"));
  }

  #setStatus(s) {
    if (s === this.status) return;
    this.status = s;
    this.dispatchEvent(new CustomEvent("status", {detail: s}));
  }
}

export const stream = new LiveStream();
