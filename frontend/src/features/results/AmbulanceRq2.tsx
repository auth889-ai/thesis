import {useQuery} from "@tanstack/react-query";
import {useEffect} from "react";
import {useLocation} from "react-router-dom";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {DHAKA, dhakaLabel, dhakaRow, helpLevels, medianByLevel, relation, signalsBeat, type Rq2} from "./rq2";

/**
 * RQ2, THE AMBULANCE ALERT, HOW FAR IT HELPS: time saved against the siren-only run of the same seed and density, over traffic density
 * and the share of vehicles that receive the alert; Q-learning signals (sumo-rl) as a stronger signal baseline; why, from the free
 * space ahead of the ambulance and the queues at its signals. Every number comes from results/emergency/dhaka/rq2/summary.json.
 */
export function AmbulanceRq2() {
  const {t, lang} = useI18n();
  const q = useQuery({queryKey: ["emergency-rq2"], queryFn: () => api.emergencyRq2() as Promise<Rq2>});
  const {hash} = useLocation();
  useEffect(() => { if (hash === "#rq2" && q.data) document.getElementById("rq2")?.scrollIntoView({block: "start"}); }, [hash, q.data]);   // "How we know" from the everyday pages
  if (!q.data) return null;
  const r = q.data;
  const n = (x: number | null | undefined, d = 1) => (x == null ? "–" : x.toLocaleString(lang, {maximumFractionDigits: d}));
  const dl = r.dhaka_level, dk = dhakaRow(r), dLab = dhakaLabel(dl);
  const levels: (number | string)[] = [...(r.ladder ?? []).map((l) => l.scale), ...(dk ? [DHAKA] : [])];
  const head = (l: number | string) => (l === DHAKA ? t(`lab.rq2.dhakaCol.${dLab}`, {scale: dl?.scale ?? 0}) : `x${l}`);
  const iqr = (c?: {saved_s_median: number; saved_s_q25?: number; saved_s_q75?: number}) => c ? t("lab.rq2.medIqr", {m: n(c.saved_s_median), lo: n(c.saved_s_q25), hi: n(c.saved_s_q75)}) : "";
  const med = medianByLevel(r);
  const rel = (c: Parameters<typeof relation>[0]) => t(`lab.rq2.rel.${relation(c) ?? "none"}`);
  const yy = r.why?.saved_vs_yield_share, bb = r.why?.saved_vs_siren_blocked_s;
  const fw = Object.values(r.why?.free_width_by_scale ?? {}), sb = signalsBeat(r);
  const wd = r.why_dhaka, sd = r.v1_record?.slowdown, ql = r.qlearning_dhaka, mw = r.makeway?.current;
  const ovnCell = (c: {saved_s_median: number; saved_s_q25: number; saved_s_q75: number; slower_runs: number; seeds: number} | null) =>
    c ? t("lab.rq2.ovnCell", {m: n(c.saved_s_median), lo: n(c.saved_s_q25), hi: n(c.saved_s_q75), slow: c.slower_runs, runs: c.seeds}) : "–";
  const lvName = (lv: string) => (lv === DHAKA ? t(`lab.rq2.dhakaCol.${dLab ?? "dhaka"}`, {scale: dl?.scale ?? 0}) : `x${lv}`);
  const byNum = (x: string, y: string) => (x === DHAKA ? 1e9 : +x) - (y === DHAKA ? 1e9 : +y);       // JavaScript lists "1" before "0.5": sort by value, the Dhaka level last
  const whole = (k: "slower_runs" | "seeds") => ["alert", "alert_preemption"].flatMap((a) => Object.values(r.saved?.[a] ?? {}).flatMap((by) =>
    Object.entries(by).filter(([lv]) => lv !== DHAKA).map(([, c]) => c))).reduce((x, c) => x + c[k], 0);            // the whole network, as the backend's "backfire" finding
  const w = r.why?.saved_vs_free_width, qq = r.why?.saved_vs_queue;
  return (
    <div data-story="research-ambulance-rq2" id="rq2">
      <Card title={<>{t("lab.rq2.title")} <Pill tone="info">{t("plain.tag.simulated")}</Pill></>} sub={t("lab.rq2.sub")}>
        {!r.available ? <p className="muted small">{t("lab.rq2.none")}</p> : <>
          <h4>{t("lab.rq1.finding")}</h4>
          <ul className="rs-list" data-story="rq2-finding">
            {med.length > 0 && <li>{t("lab.rq2.findDensity", {list: med.map((m) => t("lab.rq2.atLevel", {s: m.s, p: m.p, scale: m.scale})).join("; ")})}</li>}
            {Object.values(r.saved?.alert ?? {}).length > 0 && <li>{t("lab.rq2.findSlower", {worse: whole("slower_runs"), runs: whole("seeds")})}</li>}
            {dk && dl && <li data-story="rq2-dhaka">{t(`lab.rq2.findCorridor.${dLab}`, {sim: n(dl.INT_density_median), rec: n(dl.recorded.density_median), scale: dl.scale ?? 0,
              alert: iqr(dk.alert), seeds: dk.alert?.seeds ?? 0, slower: dk.alert?.slower_runs ?? 0})}
              {dk.pre && ` ${t("lab.rq2.findCorridorPre", {v: iqr(dk.pre)})}`}{dk.rl && ` ${t("lab.rq2.findCorridorRl", {v: iqr(dk.rl)})}`}
              {` ${t("lab.rq2.findCorridorFlow", {flow: n(dl.INT_entered_per_hour_median, 0), rec: n(dl.recorded.flow_veh_h_median, 0)})}`}</li>}
            {(() => { const h = helpLevels(r); return <li>{h.yes.length ? t("lab.rq2.findHelpAt", {pct: r.help_pct ?? 10, list: h.yes.map((x) => t("lab.rq2.fromShare", {scale: x.scale, share: n(x.share * 100, 0)})).join(", ")})
              + (h.no.length ? ` ${t("lab.rq2.findHelpNot", {list: h.no.map((x) => `x${x}`).join(", ")})}` : "") : t("lab.rq2.findHelpNone", {pct: r.help_pct ?? 10})}</li>; })()}
            {r.saved?.rl_signals?.["0"] && <li>{t("lab.rq2.findRl", {list: Object.entries(r.saved.rl_signals["0"]).filter(([k]) => k !== DHAKA).sort(([a], [b]) => +a - +b).map(([k, v]) => `${n(v.saved_s_median)} s (x${k})`).join(", ")})}</li>}
            {r.dhaka_anchor && <li>{r.dhaka_anchor.reached_before_gridlock ? t("lab.rq2.findDhakaReached", {rec: r.dhaka_anchor.recorded_veh_km, scale: r.dhaka_anchor.closest_scale ?? 0, sim: r.dhaka_anchor.closest_simulated_veh_km ?? 0})
              : t("lab.rq2.findDhakaNot", {rec: r.dhaka_anchor.recorded_veh_km, sim: r.dhaka_anchor.closest_simulated_veh_km ?? 0})}</li>}
          </ul>
          {mw?.version === 2 && <p data-story="rq2-makeway">{t("lab.rq2.makeway", {d: mw.distance_m ?? 0})}</p>}
          {w?.rho != null && <><h4>{t("lab.rq1.why")}</h4>
            <p data-story="rq2-why">{t("lab.rq2.whyText", {wRel: rel(w), rho: w.rho, lo: w.ci95?.[0] ?? 0, hi: w.ci95?.[1] ?? 0, runs: w.n, qRel: rel(qq), qrho: qq?.rho ?? 0, qlo: qq?.ci95?.[0] ?? 0, qhi: qq?.ci95?.[1] ?? 0})}
              {yy?.rho != null && ` ${t("lab.rq2.whyYield", {yRel: rel(yy), rho: yy.rho, lo: yy.ci95?.[0] ?? 0, hi: yy.ci95?.[1] ?? 0})}`}
              {bb?.rho != null && ` ${t("lab.rq2.whyBlocked", {bRel: rel(bb), rho: bb.rho, lo: bb.ci95?.[0] ?? 0, hi: bb.ci95?.[1] ?? 0})}`}
              {fw.length > 0 && ` ${t("lab.rq2.whyRoom", {lo: Math.min(...fw), hi: Math.max(...fw)})}`}
              {sb.of > 0 && ` ${t("lab.rq2.whySignals", {beats: sb.beats, of: sb.of})}`}</p></>}
          {wd?.saved_vs_free_width?.rho != null && <p data-story="rq2-why-dhaka">{t("lab.rq2.whyDhaka", {wRel: rel(wd.saved_vs_free_width), rho: wd.saved_vs_free_width.rho, runs: wd.saved_vs_free_width.n,
            lo: wd.saved_vs_free_width.ci95?.[0] ?? 0, hi: wd.saved_vs_free_width.ci95?.[1] ?? 0, qRel: rel(wd.saved_vs_queue), qrho: wd.saved_vs_queue?.rho ?? 0,
            bRel: rel(wd.saved_vs_siren_blocked_s), brho: wd.saved_vs_siren_blocked_s?.rho ?? 0, blocked: n(wd.siren_blocked_s_median), fw: n(wd.free_width_m_mean, 2)})}</p>}
          {ql && <p data-story="rq2-qlearning">{t("lab.rq2.qlearning", {seeds: ql.seeds.length, stood: n(ql.totals.rl_signals?.stood_s, 0), siren: n(ql.totals.no_alert?.stood_s, 0),
            near: n((ql.totals.rl_signals?.stood_s ?? 0) - (ql.totals.rl_signals?.by_light["no light within 100 m ahead"] ?? 0), 0), green: n(ql.next_light_rl.green, 0),
            red: n(ql.next_light_rl.red, 0), none: n(ql.next_light_rl.none_ahead, 0), head: n(ql.queue_head_rl.median_vehicles_to_head ?? 0, 0)})}</p>}
          {sd && (() => { const c = sd.causes_in_slower_runs, v = sd.variants, a = sd.arms.alert;
            return <p data-story="rq2-v1-record" className="muted">{t("lab.rq2.v1Label")} {t("lab.rq2.dhakaCause", {slow: c.slower_seeds.length, runs: a.runs, stood: n(c.seconds_stood, 0), share: n(c.lane_end_share * 100, 0),
              rest: n(100 - Math.round(c.lane_end_share * 100), 0), sMed: n(v.strategic?.median_s), sLo: n(v.strategic?.q25_s), sHi: n(v.strategic?.q75_s), sRuns: v.strategic?.runs ?? 0,
              sSlow: v.strategic?.slower_runs ?? 0, sCrash: v.strategic?.crashed ?? 0, nMed: n(v.near50?.median_s), nLo: n(v.near50?.q25_s), nHi: n(v.near50?.q75_s),
              nSlow: v.near50?.slower_runs ?? 0, nRuns: v.near50?.runs ?? 0, jMed: n(v.nojunction?.median_s)})}</p>; })()}
          {r.density_gap && <p data-story="rq2-gap">{t("lab.rq2.gap", r.density_gap.numbers)}
            {r.density_gap.numbers.corridor_veh_km != null && ` ${t("lab.rq2.gapCorridor", {...r.density_gap.numbers, q25: dl?.recorded.density_q25 ?? 0, q75: dl?.recorded.density_q75 ?? 0})}`}</p>}
          <div className="k" style={{marginTop: 12}}>{t("lab.rq2.tableTitle")}</div>
          <Table head={[t("lab.rq2.col.arm"), t("lab.rq2.col.share"), ...levels.map(head)]}
            rows={Object.entries(r.saved ?? {}).flatMap(([arm, byShare]) => Object.entries(byShare).sort(([a], [b]) => +a - +b).map(([share, byLv]) => [t(`lab.rq2.arm.${arm}`), `${n(+share * 100, 0)} %`,
              ...levels.map((l) => { const c = byLv[String(l)]; return c ? `${n(c.saved_s_median)} s (${n(c.saved_pct_median)} %)` : "–"; })]))} />
          {r.old_vs_new && <><div className="k" style={{marginTop: 12}}>{t("lab.rq2.ovnTitle")}</div>
            <Table head={[t("lab.rq2.col.arm"), t("lab.rq2.col.share"), t("lab.rq2.col.demand"), t("lab.rq2.ovnV1"), t("lab.rq2.ovnV2")]}
              rows={Object.entries(r.old_vs_new).flatMap(([arm, byShare]) => Object.entries(byShare).sort(([x], [y]) => +x - +y).flatMap(([share, byLv]) =>
                Object.entries(byLv).sort(([x], [y]) => byNum(x, y)).map(([lv, c]) => [t(`lab.rq2.arm.${arm}`), `${n(+share * 100, 0)} %`, lvName(lv), ovnCell(c.v1), ovnCell(c.v2)])))} /></>}
          <div className="k" style={{marginTop: 12}}>{t("lab.rq2.ladderTitle")}</div>
          <Table head={[t("lab.rq2.col.demand"), t("lab.rq2.col.vehicles"), t("lab.rq2.col.density"), t("lab.rq2.col.siren"), t("lab.rq2.col.gridlock")]}
            rows={[...(r.ladder ?? []).map((l) => [`x${l.scale}`, n(l.vehicles, 0), n(l.section_density_veh_km, 2), n(l.no_alert_travel_s), l.gridlock ? t("lab.ev.yes") : t("lab.ev.no")]),
              ...(dl?.reached ? [[head(DHAKA), "–", `${n(dl.INT_density_median, 2)} (${t("lab.rq2.recordedShort", {rec: n(dl.recorded.density_median)})})`, "–", "–"]] : [])]} />
          <div className="grid two" style={{marginTop: 12}}>{(r.figures ?? []).map((f) => { const file = f.split("/").pop()!; return <img key={f} src={api.emergencyRq2Figure(file)} alt={t(`lab.rq2.fig.${file.replace(".png", "")}`)} style={{width: "100%"}} />; })}</div>
          <details className="why"><summary>{t("lab.rq1.caveats")}</summary><ul className="plain small muted">{(r.caveats ?? []).map((c) => <li key={c}>{c}</li>)}</ul>
            <p className="muted small">{t("lab.ev.ownNames")}</p></details>
        </>}
      </Card>
    </div>
  );
}
