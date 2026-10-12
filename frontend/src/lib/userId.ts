/** The device's own pseudonymous id (no account): made once, kept in this browser. Free of React, so the map app can use it. */
export function stableUserId(): string {
  try {
    const k = "tt.user"; const cur = localStorage.getItem(k);
    if (cur) return cur;
    const id = "p_" + (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "").slice(0, 16) : Math.random().toString(36).slice(2, 18));
    localStorage.setItem(k, id); return id;
  } catch { return "p_local"; }
}

