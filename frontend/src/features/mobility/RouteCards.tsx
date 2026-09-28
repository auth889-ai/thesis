import {Pill, Provenance} from "@/components/ui";
import {km, mins} from "@/lib/format";
import type {TripResult} from "./types";

const risk = (p?: {covered: boolean; risk: string}) => (!p?.covered ? ["live estimate", "neutral"] : p.risk === "HIGH" ? ["heavy", "bad"] : p.risk === "MEDIUM" ? ["some congestion", "warn"] : ["flowing", "ok"]) as [string, "ok" | "warn" | "bad" | "neutral"];

/** Where the answer came from, in one plain sentence. */
export function provenanceWords(r: TripResult): string {
  const basis = r.source.traffic_basis ?? "";
  const when = (basis.match(/as of (\S+)/)?.[1] ?? "").replace("T", " ").slice(0, 16);
  const provider = r.source.routing === "amazon_location" ? "Amazon Location (HERE road data)" : r.source.routing === "google_routes" ? "Google Routes" : "the city's own road network";
  const traffic = r.source.is_live && r.source.traffic_coverage ? `live traffic from ${provider}` : basis.startsWith("RECORDED") ? `the last recorded traffic (${when}) on real roads from ${provider}` : "free-flow times (no live traffic coverage and no recorded traffic for this city yet)";
  const fd = r.forecast_decision ?? {};
  const forecast = r.forecastable ? `forecast by ${fd.label ?? fd.model ?? "the validated model"}` : "no forecast for this city yet, routes ranked on current traffic";
  return `Based on ${traffic}, ${forecast}.`;
}

/** Every candidate route: ETA now, ETA at departure, congestion, and why one is recommended. */
export function RouteCards({r, onPick}: {r: TripResult; onPick?: (index: number) => void}) {
  const h = String(r.horizon_min);
  const etaAt = (c: TripResult["routes"][number]) => (c.forecast[h]?.covered ? c.forecast[h].eta_s : c.eta_now_s);
  const rec = r.routes.find((c) => c.recommended) ?? r.routes[0];
  const best = etaAt(rec);
  return (
    <div className="stack">
      <div className="routecards">
        {r.routes.map((c) => {
          const [w, tone] = risk(c.forecast[h]); const eta = etaAt(c); const diff = eta - best;
          return (
            <div key={c.key} className={`routecard ${c.recommended ? "rec" : ""}`} onClick={() => onPick?.(c.index)}>
              <div className="rc-h"><b>Route {c.key}</b> <Pill tone={c.recommended ? "ok" : "neutral"}>{c.recommended ? "recommended" : c.key === r.current.route ? "fastest now" : "alternative"}</Pill></div>
              <div className="rc-grid"><div><div className="v">{mins(c.eta_now_s)}</div><div className="k">now</div></div><div><div className={`v ${c.recommended ? "good" : ""}`}>{mins(eta)}</div><div className="k">at departure (+{h} min)</div></div><div><div className="v">{km(c.distance_m)}</div><div className="k">distance</div></div></div>
              <div className="rc-foot"><Pill tone={tone}>{w}</Pill><span className={`small ${c.recommended ? "good" : diff > 30 ? "bad" : "muted"}`}>{c.recommended ? (r.decision.saving_s > 60 ? `saves about ${Math.round(r.decision.saving_s / 60)} min vs the fastest route now` : "best at departure") : diff > 30 ? `${Math.round(diff / 60)} min slower` : "about the same"}</span></div>
            </div>
          );
        })}
      </div>
      <div className="note ok"><b>Route {r.decision.recommended}</b> — {r.decision.reason}{r.decision.basis ? ` ${r.decision.basis}.` : ""}</div>
      <Provenance>{provenanceWords(r)}</Provenance>
    </div>
  );
}
