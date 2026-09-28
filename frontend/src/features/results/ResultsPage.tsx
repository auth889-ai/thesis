import {useQuery} from "@tanstack/react-query";

import {Card, Loading, Pill, Table} from "@/components/ui";
import {api, type Json} from "@/lib/api";
import {ci, label, pct, word} from "@/lib/format";
import {arm, gateOk, gateStatus, verdict, wl, type Arm, type Gate} from "./verdict";
import "./results.css";

const tone = (l?: string | null) => (l === "HELPED" ? "ok" : l === "HURT" ? "bad" : "warn");

/** RESULTS: "does smart routing help?" computed from the congested Scenario A/B experiment and the research gates. */
export function ResultsPage() {
  const S = useQuery({queryKey: ["stress"], queryFn: () => api.stress()});
  const G = useQuery({queryKey: ["research", "status"], queryFn: () => api.researchStatus().catch((): Json => ({gates: {}}))});
  if (S.isError) return <div className="note bad">Results unavailable: {(S.error as Error).message}</div>;
  if (!S.data || !G.data) return <Loading what="loading the test results" />;
  const s = S.data; if (!s.available) return <div className="note warn"><b>No congested-scenario test has been run yet.</b></div>;
  const A = s.scenarios.A ?? {}, B = s.scenarios.B ?? {}, evalA = A.eval ?? {}, evalB = B.eval ?? {};
  const gates: Record<string, Gate> = G.data.gates ?? {};
  const v = verdict(gates, evalA);
  const oracle = arm(evalA, "oracle_v2x"), gwnet = arm(evalA, "predictive_v2x"), random = arm(evalA, "random_v2x");
  const oVr = oracle.vs_reactive ?? {}, gVr = gwnet.vs_reactive ?? {}, gVb = gwnet.vs_baseline ?? {};
  const predOk = gateStatus(gates, "PREDICTIVE_TRAFFIC_BENEFIT") === "ESTABLISHED";
  const sweep: any = Object.values(s.sweeps ?? {}).find((x: any) => x.od_rule === "arterial") ?? Object.values(s.sweeps ?? {})[0];
  const seedsA = (evalA.seeds ?? []).length;
  return (
    <div className="stack">
      <section className={`rs-hero ${v.kind}`}>
        <div className="k">Does smart routing help?</div>
        <h2>{v.text} <b>{v.strong}</b></h2>
        <p>Measured in a traffic simulation of a congested Los Angeles corridor (real road network, real detector data feeding the forecast) with the same vehicles and journeys in every world. Only the routing advice changed. {seedsA ? `${seedsA} unseen random days.` : ""}</p>
      </section>
      <div className="grid three">
        {([["Perfect knowledge of the future", oVr, "total travel time vs reactive routing"], ["The AI forecast (Graph WaveNet)", gVr, "vs reactive routing"], ["The AI forecast vs no advice", gVb, ""]] as [string, any, string][]).map(([name, st, sub]) => (
          <div key={name} className={`card rs-card ${st.label === "HELPED" ? "good" : ""}`}><div className="rs-big">{pct(st.mean_pct)}</div><div className="rs-name">{name}</div><div className="muted small">{sub}{sub ? " · " : ""}{word(st.label)} · {ci(st)}</div></div>
        ))}
      </div>
      <Card title="What the AI forecast does today" right={<Pill tone={predOk ? "ok" : "warn"}>{predOk ? "traffic benefit established" : "no measurable benefit yet"}</Pill>}>
        <p>{predOk ? "The learned forecast beats both no advice and reactive routing on unseen days." : <>The Graph WaveNet forecast is validated on real Los Angeles detector data (it beats "traffic stays the same"), and routing on it is <b>{pct(gVr.mean_pct)}</b> against reactive routing ({word(gVr.label)}). But against <b>no advice at all</b> it is <b>{pct(gVb.mean_pct)}</b> ({word(gVb.label)}), and a <b>shuffled</b> forecast used as a control scores <b>{pct(random.vs_reactive?.mean_pct)}</b> vs reactive ({word(random.vs_reactive?.label)}). So the gain over reactive routing comes from the disciplined V2X advice pipeline, not yet from forecast skill. We say so rather than round it up.</>}</p>
        <p className="muted">Why perfect information helps and the forecast does not yet: the forecast prices only the roads with sensors; the perfect-information arm prices every road. Covering more roads is the next step.</p>
      </Card>
      <Card title="Every information source, unseen days">
        <ArmsTable sc={evalA} title={`Scenario A · ${A.text ?? "forecastable peak"}`} />
        <ArmsTable sc={evalB} title={`Scenario B · ${B.text ?? "unexpected incident"}`} />
      </Card>
      <div className="grid two">
        <Card title="What this means for you"><ul className="rs-list">
          <li><b>Route advice</b> only changes your route when the predicted saving is worth it, and only for a budgeted share of drivers per round — the discipline that beat reactive routing here.</li>
          <li><b>The AI forecast</b> steers advice only where a model has been validated on that city's own road data; elsewhere routes follow current traffic.</li>
          <li><b>In Dhaka</b> the app routes on the project's own road network with the last recorded traffic when no live provider is available, and says so on screen.</li></ul></Card>
        <Card title="How we tested it"><ul className="rs-list">
          <li>Demand was raised on a real Los Angeles corridor until the roads were congested but stable (rule frozen before any result: travel-time index ≥ 1.3, standing jams, ≤ 1 % lost vehicles).{sweep ? <> Chosen level: <b>{sweep.chosen_scale}×</b> ({sweep.gate}).</> : null}</li>
          <li>Every world started from one saved simulation state. First the perfect-information arm had to beat reactive routing; only then were the learned forecasts tested.</li>
          <li>Only 30 % of drivers are connected, as in real life; messages travel through a simulated V2X channel with latency, loss and expiry.</li>
          <li>A result counts only when it held across all unseen days (paired 95 % confidence interval), never on a lucky one. A shuffled forecast runs as a negative control.</li></ul></Card>
      </div>
      {sweep && <Card title="How congested was the test" sub="demand is synthetic (scaled random trips on the real road network); the METR-LA data carries no traffic counts, so it is never called real traffic">
        <Table head={["demand ×", "vehicles", "arrived", "lost (teleports)", "travel-time index", "mean trip s", "stable", "congested"]} rows={sweep.points.map((p: any) => [<span className={p.scale === sweep.chosen_scale ? "good" : ""}>{p.scale}{p.scale === sweep.chosen_scale ? " ← chosen" : ""}</span>, Math.round(p.vehicles_loaded), `${(p.arrival_share * 100).toFixed(0)} %`, `${(p.teleport_rate * 100).toFixed(2)} %`, p.tti ?? "1 (reference)", Math.round(p.mean_travel_time_s), p.STABLE ? "yes" : "no", p.CONGESTED ? "yes" : "no"])} />
      </Card>}
      <Card title="Computed research status" sub={`computed by the backend from run files (${Object.keys(G.data.generated_from ?? {}).join(", ")}); no page or document may set a status by hand`}>
        <div className="rs-gates">{Object.entries(gates).map(([k, g]) => <div key={k} className={`rs-gate ${gateOk(g.status ?? "") ? "ok" : "no"}`}><b>{k.replace(/_/g, " ")}</b>{g.status}<br /><small className="muted">{g.scope ?? g.reason ?? g.note ?? g.detail ?? ""}</small></div>)}</div>
      </Card>
      <details className="why"><summary>Details for reviewers</summary>
        <p className="muted small">Controller status <b>{s.controller_status?.status}</b> (arm {s.controller_status?.arm}, seeds {JSON.stringify(s.controller_status?.seeds ?? [])}): {s.controller_status?.rule ?? ""}</p>
        <p className="muted small">Development-seed oracle gates: A <b>{A.dev?.oracle_gate?.status}</b> ({pct(A.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} {ci(A.dev?.oracle_gate?.oracle_vs_reactive)}), B <b>{B.dev?.oracle_gate?.status}</b> ({pct(B.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} {ci(B.dev?.oracle_gate?.oracle_vs_reactive)}). Evaluation-seed gates: A <b>{evalA.oracle_gate?.status}</b>, B <b>{evalB.oracle_gate?.status}</b>.</p>
        <p className="muted small">Full report: <code>{s.report}</code>. The earlier low-load experiment is kept as a negative result: <code>{s.low_load_negative_result ?? "–"}</code>.</p>
      </details>
    </div>
  );
}

function ArmsTable({sc, title}: {sc: any; title: string}) {
  const arms: Arm[] = sc.arms ?? [];
  return (
    <div className="stack" style={{marginTop: 12}}>
      <div className="k">{title}</div>
      <Table head={["information source", "vs no advice", "vs reactive routing", "reroutes"]} rows={arms.length ? arms.map((a) => [a.label,
        <>{pct(a.vs_baseline?.mean_pct, 2)} <Pill tone={tone(a.vs_baseline?.label)}>{label(a.vs_baseline?.label)}</Pill><br /><small className="muted">{ci(a.vs_baseline)} · W/L/T {wl(a.vs_baseline)}</small></>,
        a.vs_reactive ? <>{pct(a.vs_reactive.mean_pct, 2)} <Pill tone={tone(a.vs_reactive.label)}>{label(a.vs_reactive.label)}</Pill><br /><small className="muted">{ci(a.vs_reactive)} · W/L/T {wl(a.vs_reactive)}</small></> : "–", a.reroutes ?? "–"]) : [[<span className="muted">not run</span>, "", "", ""]]} />
      <p className="muted small">{sc.seeds ? <>{sc.seeds.length} unseen seeds {JSON.stringify(sc.seeds)} · identical start state across arms: <b>{String(sc.fork_identical)}</b></> : null}{sc.oracle_gate ? <> · oracle-headroom gate <b>{sc.oracle_gate.status}</b></> : null}{sc.run_dir ? <> · <code>{sc.run_dir}</code></> : null}</p>
    </div>
  );
}
