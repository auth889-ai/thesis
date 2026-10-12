import {useMemo} from "react";

import {LineChart} from "@/components/LineChart";
import {useI18n} from "@/i18n";
import {chartDefaults, token} from "@/lib/chart";
import type {MeshRow} from "./mesh";

/** SIMULATED: delivery ratio per router, the mean over seeds as a bar and the min–max over seeds as a floating bar behind it. */
export function MeshFigure({rows}: {rows: MeshRow[]}) {
  const {t} = useI18n();
  const config = useMemo(() => {
    const d = chartDefaults();
    return {
      type: "bar" as const,
      data: {labels: rows.map((r) => r.name),
             datasets: [{label: t("mesh.figureRange"), data: rows.map((r) => (r.delivery_ratio ? [r.delivery_ratio.min, r.delivery_ratio.max] : [0, 0])), backgroundColor: "rgba(123,45,59,.18)", borderWidth: 0, barPercentage: 0.9, grouped: false},
                        {label: t("mesh.figureMean"), data: rows.map((r) => r.delivery_ratio?.mean ?? 0), backgroundColor: token("--caramel"), borderWidth: 0, barPercentage: 0.45, grouped: false}]},
      options: {...d, interaction: {mode: "index" as const, intersect: false},
                plugins: {...d.plugins, title: {display: true, text: t("mesh.figureTitle"), color: token("--ink-muted"), font: {size: 12}}},
                scales: {...d.scales, y: {...(d.scales as any).y, min: 0, max: 1, title: {display: true, text: t("mesh.delivery"), color: token("--ink-muted")}}}},
    };
  }, [rows, t]);
  return <LineChart config={config} height={220} />;
}
