import {useEffect, useState} from "react";

import {LineChart} from "@/components/LineChart";
import {useT} from "@/i18n";
import {chartDefaults, nowLine, PALETTE} from "@/lib/chart";

type Sensor = {index: number; id: string};
type Info = {available: boolean; reason?: string; models: string[]; sensors: Sensor[]; test_from: string; test_to: string; units: string};
type Run = {ok: boolean; error?: string; model: string; at: string; split: string; units: string; sensor: Sensor;
  history: {times: string[]; speed: number[]}; future: {times: string[]; recorded: number[]; forecast: number[]; no_change: number[]};
  errors: {model: Record<string, number | null>; no_change: Record<string, number | null>}; rq1_check: {file: string; window: number; max_abs_diff_mph: number; equal: boolean} | null};

/** LAB · MODEL LAB: pick a sensor, a moment and a model; Run computes the forecast now with RQ1's own code (POST /api/model-lab/run). */
export function ModelLabPage() {
  const t = useT();
  const [info, setInfo] = useState<Info | null>(null);
  const [sensor, setSensor] = useState(0);
  const [at, setAt] = useState("2012-06-07T14:30");
  const [model, setModel] = useState("D2STGNN");
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [took, setTook] = useState<number | null>(null);
  useEffect(() => { fetch("/api/model-lab/sensors").then((r) => r.json()).then(setInfo).catch(() => setInfo({available: false} as Info)); }, []);

  const go = async () => {
    setBusy(true); const t0 = performance.now();
    try {
      const r = await fetch("/api/model-lab/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({sensor, at, model})});
      setRun(await r.json());
    } finally { setTook((performance.now() - t0) / 1000); setBusy(false); }
  };
  if (!info) return <p>{t("modelLab.loading")}</p>;
  if (!info.available) return <div className="note warn" data-story="model-lab-none">{t("modelLab.none")} {info.reason}</div>;

  return (
    <div className="model-lab" data-story="model-lab">
      <p>{t("modelLab.intro")}</p>
      <div className="row" style={{display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end"}}>
        <label>{t("modelLab.sensor")}<br />
          <select value={sensor} onChange={(e) => setSensor(+e.target.value)} data-tt="lab-sensor">
            {info.sensors.map((s) => <option key={s.index} value={s.index}>{s.index} · {s.id}</option>)}
          </select></label>
        <label>{t("modelLab.at")}<br />
          <input type="datetime-local" step={300} value={at} onChange={(e) => setAt(e.target.value)} data-tt="lab-at" /></label>
        <label>{t("modelLab.model")}<br />
          <select value={model} onChange={(e) => setModel(e.target.value)} data-tt="lab-model">
            {info.models.map((m) => <option key={m} value={m}>{m === "persistence" ? t("modelLab.noChange") : m}</option>)}
          </select></label>
        <button className="btn primary" onClick={go} disabled={busy} data-tt="lab-run">{busy ? t("modelLab.running") : t("modelLab.run")}</button>
      </div>
      <p className="muted">{t("modelLab.testWindow", {from: info.test_from, to: info.test_to})}</p>
      {run && !run.ok && <div className="note warn">{run.error}</div>}
      {run?.ok && <Result run={run} took={took} />}
    </div>
  );
}

function Result({run, took}: {run: Run; took: number | null}) {
  const t = useT();
  const h = run.history, f = run.future, n = h.times.length;
  const labels = [...h.times, ...f.times].map((s) => s.slice(11));
  const pad = (xs: number[]) => [...new Array(n - 1).fill(null), h.speed[n - 1], ...xs];
  const base = chartDefaults();
  const ds = (label: string, data: (number | null)[], color: string, dash: number[] = []) => ({label, data, borderColor: color, backgroundColor: color, pointRadius: 2, borderWidth: 2, borderDash: dash, tension: 0.2});
  const config: any = {type: "line", data: {labels, datasets: [
    ds(t("modelLab.history"), [...h.speed, ...new Array(f.times.length).fill(null)], PALETTE.history),
    ds(t("modelLab.recorded"), pad(f.recorded), PALETTE.ink),
    ds(run.model === "persistence" ? t("modelLab.noChange") : run.model, pad(f.forecast), PALETTE.model),
    ds(t("modelLab.noChange"), pad(f.no_change), PALETTE.persistence, [4, 4])]},
    plugins: [nowLine], options: {...base, plugins: {...base.plugins, nowline: {index: n - 1, label: run.at.slice(11)}},
      scales: {...base.scales, y: {...(base.scales as any).y, title: {display: true, text: run.units}}}}};
  const e = run.errors, c = run.rq1_check;
  return (
    <div data-tt="lab-result">
      <p><b>{t("modelLab.computed", {model: run.model, sensor: run.sensor.id, at: run.at.replace("T", " "), s: took?.toFixed(1) ?? "?"})}</b> <span className="pill">{t("modelLab.tag")}</span></p>
      <p className="muted">{run.split}</p>
      <LineChart config={config} height={300} />
      <table className="table"><thead><tr><th></th><th>15 min</th><th>30 min</th><th>60 min</th></tr></thead><tbody>
        <tr><td>{run.model}</td>{["15", "30", "60"].map((k) => <td key={k}>{e.model[k] ?? "—"}</td>)}</tr>
        <tr><td>{t("modelLab.noChange")}</td>{["15", "30", "60"].map((k) => <td key={k}>{e.no_change[k] ?? "—"}</td>)}</tr>
      </tbody></table>
      <p className="muted">{t("modelLab.oneWindow")}</p>
      <p data-tt="lab-check">{c ? t(c.equal ? "modelLab.checkSame" : "modelLab.checkDiff", {file: c.file, w: c.window, d: c.max_abs_diff_mph.toExponential(1)}) : t("modelLab.checkNew")}</p>
    </div>
  );
}
