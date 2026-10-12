import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {best, FOUNDATION, HORIZONS, moveCost, ranked, siteRange, type ByModel, type Rq1} from "./rq1";

/**
 * RQ1, FORECASTING: baselines, zero-shot foundation models and our trained models on METR-LA and PEMS-BAY (mean ± sd over seeds) and
 * on Dhaka's recorded days; the unseen-city test; why Dhaka differs, measured from the data. Every number comes from
 * results/forecasting/rq1/summary.json; the sentences are built here from those numbers, in the app's language.
 */
export function ForecastTable() {
  const {t, lang} = useI18n();
  const q = useQuery({queryKey: ["forecasting-rq1"], queryFn: () => api.forecastingRq1() as Promise<Rq1>});
  if (!q.data) return null;
  const r = q.data;
  const name = (m: string) => r.names?.[m] ?? m.replace("_from_metr_la", ` (${t("lab.rq1.fromMetrLa")})`).replace("_trained_on_metr_la", ` (${t("lab.rq1.fromMetrLa")})`).replace("_trained_on_pems_bay", ` (${t("lab.rq1.atHome")})`);
  const n = (x: number | null | undefined, d = 2) => (x == null ? "–" : x.toLocaleString(lang, {maximumFractionDigits: d}));
  const cell = (c: ByModel[string][string] | undefined, k: "mae" | "rmse" | "mape_pct" = "mae") => (!c ? "–" : `${n(c[k] as number)}${(c as any)[`${k}_sd`] != null ? ` ± ${n((c as any)[`${k}_sd`])}` : ""}`);
  const table = (models: ByModel, extra = true) => <Table head={[t("lab.rq1.col.model"), ...HORIZONS.map((h) => t("lab.rq1.col.mae", {h})), ...(extra ? [t("lab.rq1.col.rmse60"), t("lab.rq1.col.mape60")] : [])]}
    rows={ranked(models).map(([m, v]) => [name(m), ...HORIZONS.map((h) => cell(v[h])), ...(extra ? [cell(v["60"], "rmse"), cell(v["60"], "mape_pct")] : [])])} />;
  const lab = r.lab ?? {}, dk = r.dhaka ?? {}, tr = r.unseen_city ?? {}, ch = r.character ?? {};
  const sites = ch.DhaTraX?.sites ?? {};
  return (
    <div data-story="research-forecasting">
      <Card title={<>{t("lab.rq1.title")} <Pill tone="info">{t("lab.rq1.badge")}</Pill></>} sub={t("lab.rq1.sub")}>
        {!r.available ? <p className="muted small">{t("lab.rq1.none")}</p> : <>
          <h4>{t("lab.rq1.finding")}</h4>
          <ul className="rs-list" data-story="rq1-finding">
            {Object.entries(lab).map(([ds, models]) => {
              const b = best(models, "60"), f = best(models, "60", FOUNDATION), p = models.persistence?.["60"]?.mae;
              return b && <li key={ds}>{t("lab.rq1.findLab", {city: t(`lab.rq1.city.${ds}`), ds, best: name(b.model), v: b.mae, p: p ?? 0, f: f ? name(f.model) : "–", fv: f?.mae ?? 0})}</li>;
            })}
            {dk.persistence && <li>{(() => { const o = Object.fromEntries(Object.entries(dk).filter(([m]) => m !== "persistence")); const v: Record<string, string | number> = {};
              for (const h of HORIZONS) { const b = best(o, h); v[`b${h}`] = b ? name(b.model) : "–"; v[`v${h}`] = b?.mae ?? "–"; v[`p${h}`] = dk.persistence[h]?.mae ?? "–"; }
              return t("lab.rq1.findDhaka", v); })()}</li>}
            {tr.xgboost_trained_on_metr_la && tr.xgboost_trained_on_pems_bay && <li>{t("lab.rq1.findUnseen", {moved: tr.xgboost_trained_on_metr_la["60"].mae, home: tr.xgboost_trained_on_pems_bay["60"].mae,
              cost: moveCost(tr.xgboost_trained_on_metr_la["60"].mae, tr.xgboost_trained_on_pems_bay["60"].mae)})}</li>}
          </ul>
          {ch["METR-LA"] && Object.keys(sites).length > 0 && <>
            <h4>{t("lab.rq1.why")}</h4>
            <p data-story="rq1-why">{(() => {
              const la = ch["METR-LA"], bay = ch["PEMS-BAY"], sv = Object.values(sites) as Record<string, number>[];
              const dkMoved = dk.xgboost_from_metr_la?.["60"]?.mae, dkP = dk.persistence?.["60"]?.mae;
              const trM = tr.xgboost_trained_on_metr_la?.["60"]?.mae, trH = tr.xgboost_trained_on_pems_bay?.["60"]?.mae;
              const g = lab["METR-LA"] ?? {}, b = best(Object.fromEntries(Object.entries(g).filter(([m]) => !FOUNDATION.includes(m) && !/^(historical|random|xgboost|persistence)/.test(m))), "60");
              return t("lab.rq1.whyText", {
                sg0: siteRange(sites, "stop_and_go_share", 100, 1)[0], sg1: siteRange(sites, "stop_and_go_share", 100, 1)[1],
                sgLa: Math.round(la.stop_and_go_share.median * 1000) / 10, sgBay: Math.round(bay.stop_and_go_share.median * 1000) / 10,
                cvMore: sv.filter((x) => x.cv > la.cv.median).length, n: sv.length, cvSites: Object.entries(sites).map(([k, v]: [string, any]) => `${k} ${n(v.cv)}`).join(", "),
                cvLa: la.cv.median, cvBay: bay.cv.median, aLess: sv.filter((x) => x.acf_12 < la.acf_12.median).length,
                a0: siteRange(sites, "acf_12")[0], a1: siteRange(sites, "acf_12")[1], aLa: la.acf_12.median, aBay: bay.acf_12.median,
                dkCost: dkMoved && dkP ? moveCost(dkMoved, dkP) : "–", cost: trM && trH ? moveCost(trM, trH) : "–",
                best: b ? name(b.model) : "–", bv: b?.mae ?? "–", pv: g.persistence?.["60"]?.mae ?? "–"});
            })()}</p>
          </>}
          {Object.entries(lab).map(([ds, models]) => <div key={ds} className="stack" style={{marginTop: 12}}>
            <div className="k">{t("lab.rq1.labTitle", {city: t(`lab.rq1.city.${ds}`), ds})}</div>{table(models)}
          </div>)}
          {Object.keys(dk).length > 0 && <div className="stack" style={{marginTop: 12}}>
            <div className="k">{t("lab.rq1.dhakaTitle")}</div>{table(dk, false)}
            <p className="muted small">{t("lab.rq1.noHa")}</p>
          </div>}
          {Object.keys(tr).length > 0 && <div className="stack" style={{marginTop: 12}}>
            <div className="k">{t("lab.rq1.unseenTitle")}</div>{table(tr, false)}
            <ul className="plain small muted">{Object.keys(r.cannot_transfer ?? {}).map((m) => <li key={m}>{m}: {t("lab.rq1.cannot")}</li>)}</ul>
          </div>}
          <div className="grid two" style={{marginTop: 12}}>{(r.figures ?? []).map((f) => { const file = f.split("/").pop()!; return <img key={f} src={api.forecastingRq1Figure(file)} alt={t(`lab.rq1.fig.${file.replace(".png", "")}`)} style={{width: "100%"}} />; })}</div>
          <details className="why"><summary>{t("lab.rq1.caveats")}</summary><ul className="plain small muted">{(r.caveats ?? []).map((c) => <li key={c}>{c}</li>)}</ul>
            <p className="muted small">{t("lab.ev.ownNames")}</p></details>
        </>}
      </Card>
    </div>
  );
}
