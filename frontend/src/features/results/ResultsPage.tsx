import {useQuery} from "@tanstack/react-query";

import {Card, Loading, Pill, Table} from "@/components/ui";
import {api, type Json} from "@/lib/api";
import {ci, pct} from "@/lib/format";
import {useI18n} from "@/i18n";
import {AmbulanceTable} from "./AmbulanceTable";
import {AmbulanceRq2} from "./AmbulanceRq2";
import {ForecastTable} from "./ForecastTable";
import {ReachTable} from "./ReachTable";
import {SosTable} from "./SosTable";
import {PrefetchTable} from "./PrefetchTable";
import {MeshTable} from "@/features/emergency/MeshTable";
import {arm, gateOk, gateStatus, verdict, wl, type Arm, type Gate} from "./verdict";
import "./results.css";

const tone = (l?: string | null) => (l === "HELPED" ? "ok" : l === "HURT" ? "bad" : "warn");

/** RESULTS: "does smart routing help?" computed from the congested Scenario A/B experiment and the research gates. */
export function ResultsPage() {
  const {t, lang} = useI18n();
  const word = (l?: string | null) => t(`lab.ev.word.${l === "HELPED" || l === "HURT" ? l : "other"}`);
  const S = useQuery({queryKey: ["stress"], queryFn: () => api.stress()});
  const G = useQuery({queryKey: ["research", "status"], queryFn: () => api.researchStatus().catch((): Json => ({gates: {}}))});
  if (S.isError) return <div className="note bad">{t("lab.ev.unavailable", {why: (S.error as Error).message})}</div>;
  if (!S.data || !G.data) return <Loading what={t("lab.ev.loading")} />;
  const s = S.data; if (!s.available) return <div className="note warn"><b>{t("lab.ev.none")}</b></div>;
  const A = s.scenarios.A ?? {}, B = s.scenarios.B ?? {}, evalA = A.eval ?? {}, evalB = B.eval ?? {};
  const gates: Record<string, Gate> = G.data.gates ?? {};
  const v = verdict(gates, evalA, t);
  const oracle = arm(evalA, "oracle_v2x"), gwnet = arm(evalA, "predictive_v2x"), random = arm(evalA, "random_v2x");
  const oVr = oracle.vs_reactive ?? {}, gVr = gwnet.vs_reactive ?? {}, gVb = gwnet.vs_baseline ?? {};
  const predOk = gateStatus(gates, "PREDICTIVE_TRAFFIC_BENEFIT") === "ESTABLISHED";
  const sweep: any = Object.values(s.sweeps ?? {}).find((x: any) => x.od_rule === "arterial") ?? Object.values(s.sweeps ?? {})[0];
  const seedsA = (evalA.seeds ?? []).length;
  return (
    <div className="stack">
      <section className={`rs-hero ${v.kind}`}>
        <div className="k">{t("lab.ev.kicker")}</div>
        <h2>{v.text} <b>{v.strong}</b></h2>
        <p>{t("lab.ev.measured")} {seedsA ? t("lab.ev.unseenDays", {n: seedsA}) : ""}</p>
      </section>
      <div className="grid three">
        {([[t("lab.ev.arm.oracle"), oVr, t("lab.ev.arm.oracleSub")], [t("lab.ev.arm.forecast"), gVr, t("lab.ev.arm.forecastSub")], [t("lab.ev.arm.forecastNone"), gVb, ""]] as [string, any, string][]).map(([name, st, sub]) => (
          <div key={name} className={`card rs-card ${st.label === "HELPED" ? "good" : ""}`}><div className="rs-big">{pct(st.mean_pct)}</div><div className="rs-name">{name}</div><div className="muted small">{sub}{sub ? " · " : ""}{word(st.label)} · {ci(st)}</div></div>
        ))}
      </div>
      <Card title={t("lab.ev.today")} right={<Pill tone={predOk ? "ok" : "warn"}>{predOk ? t("lab.ev.benefit") : t("lab.ev.noBenefit")}</Pill>}>
        <p>{predOk ? t("lab.ev.todayYes") : t("lab.ev.todayNo", {gVr: pct(gVr.mean_pct), gVrWord: word(gVr.label), gVb: pct(gVb.mean_pct), gVbWord: word(gVb.label), rnd: pct(random.vs_reactive?.mean_pct), rndWord: word(random.vs_reactive?.label)})}</p>
        <p className="muted">{t("lab.ev.why")}</p>
      </Card>
      <Card title={t("lab.ev.sources")}>
        {lang !== "en" && <p className="muted small" data-story="own-names">{t("lab.ev.ownNames")}</p>}
        <ArmsTable sc={evalA} title={t("lab.ev.scenarioA", {text: A.text ?? t("lab.ev.peak")})} />
        <ArmsTable sc={evalB} title={t("lab.ev.scenarioB", {text: B.text ?? t("lab.ev.incident")})} />
      </Card>
      <div className="grid two">
        <Card title={t("lab.ev.means")}><ul className="rs-list">
          {[1, 2, 3].map((i) => <li key={i}><b>{t(`lab.ev.means${i}Lead`)}</b> {t(`lab.ev.means${i}`)}</li>)}</ul></Card>
        <Card title={t("lab.ev.how")}><ul className="rs-list">
          <li>{t("lab.ev.how1")}{sweep ? <> {t("lab.ev.chosen", {scale: sweep.chosen_scale, gate: sweep.gate})}</> : null}</li>
          {[2, 3, 4].map((i) => <li key={i}>{t(`lab.ev.how${i}`)}</li>)}</ul></Card>
      </div>
      {sweep && <Card title={t("lab.ev.congested")} sub={t("lab.ev.congestedSub")}>
        <Table head={["demand", "vehicles", "arrived", "lost", "tti", "meanTrip", "stable", "congested"].map((c) => t(`lab.ev.col.${c}`))} rows={sweep.points.map((p: any) => [<span className={p.scale === sweep.chosen_scale ? "good" : ""}>{p.scale}{p.scale === sweep.chosen_scale ? t("lab.ev.chosenMark") : ""}</span>, Math.round(p.vehicles_loaded), `${(p.arrival_share * 100).toFixed(0)} %`, `${(p.teleport_rate * 100).toFixed(2)} %`, p.tti ?? t("lab.ev.reference"), Math.round(p.mean_travel_time_s), t(p.STABLE ? "lab.ev.yes" : "lab.ev.no"), t(p.CONGESTED ? "lab.ev.yes" : "lab.ev.no")])} />
      </Card>}
      <Card title={t("lab.ev.status")} sub={t("lab.ev.statusSub", {files: Object.keys(G.data.generated_from ?? {}).join(", ")})}>
        <div className="rs-gates">{Object.entries(gates).map(([k, g]) => <div key={k} className={`rs-gate ${gateOk(g.status ?? "") ? "ok" : "no"}`}><b>{k.replace(/_/g, " ")}</b>{g.status}<br /><small className="muted">{g.scope ?? g.reason ?? g.note ?? g.detail ?? ""}</small></div>)}</div>
      </Card>
      <ForecastTable />
      <AmbulanceTable />
      <AmbulanceRq2 />
      <ReachTable />
      <SosTable />
      <PrefetchTable />
      <MeshTable />
      <details className="why"><summary>{t("lab.ev.details")}</summary>
        <p className="muted small">{t("lab.ev.controller")} <b>{s.controller_status?.status}</b> (arm {s.controller_status?.arm}, seeds {JSON.stringify(s.controller_status?.seeds ?? [])}): {s.controller_status?.rule ?? ""}</p>
        <p className="muted small">{t("lab.ev.devGates")} A <b>{A.dev?.oracle_gate?.status}</b> ({pct(A.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} {ci(A.dev?.oracle_gate?.oracle_vs_reactive)}), B <b>{B.dev?.oracle_gate?.status}</b> ({pct(B.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} {ci(B.dev?.oracle_gate?.oracle_vs_reactive)}). {t("lab.ev.evalGates")} A <b>{evalA.oracle_gate?.status}</b>, B <b>{evalB.oracle_gate?.status}</b>.</p>
        <p className="muted small">{t("lab.ev.report")} <code>{s.report}</code>. {t("lab.ev.lowLoad")} <code>{s.low_load_negative_result ?? "–"}</code>.</p>
      </details>
    </div>
  );
}

function ArmsTable({sc, title}: {sc: any; title: string}) {
  const {t} = useI18n();
  const label = (l?: string | null) => t(`lab.ev.label.${l === "HELPED" || l === "HURT" ? l : "other"}`);
  const arms: Arm[] = sc.arms ?? [];
  return (
    <div className="stack" style={{marginTop: 12}}>
      <div className="k">{title}</div>
      <Table head={["source", "vsNone", "vsReactive", "reroutes"].map((c) => t(`lab.ev.col.${c}`))} rows={arms.length ? arms.map((a) => [a.label,
        <>{pct(a.vs_baseline?.mean_pct, 2)} <Pill tone={tone(a.vs_baseline?.label)}>{label(a.vs_baseline?.label)}</Pill><br /><small className="muted">{ci(a.vs_baseline)} · W/L/T {wl(a.vs_baseline)}</small></>,
        a.vs_reactive ? <>{pct(a.vs_reactive.mean_pct, 2)} <Pill tone={tone(a.vs_reactive.label)}>{label(a.vs_reactive.label)}</Pill><br /><small className="muted">{ci(a.vs_reactive)} · W/L/T {wl(a.vs_reactive)}</small></> : "–", a.reroutes ?? "–"]) : [[<span className="muted">{t("lab.ev.notRun")}</span>, "", "", ""]]} />
      <p className="muted small">{sc.seeds ? <>{t("lab.ev.seeds", {n: sc.seeds.length, seeds: JSON.stringify(sc.seeds)})} · {t("lab.ev.identical")} <b>{String(sc.fork_identical)}</b></> : null}{sc.oracle_gate ? <> · {t("lab.ev.oracleGate")} <b>{sc.oracle_gate.status}</b></> : null}{sc.run_dir ? <> · <code>{sc.run_dir}</code></> : null}</p>
    </div>
  );
}
