import {useQueryClient} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {useDatasets} from "./hooks";
import type {Dataset} from "./model";

/** The chosen dataset (default: the scientific one), the moment (latest or a held-out index), and a refresh after training or upload. */
export function useDataset() {
  const qc = useQueryClient();
  const datasets = useDatasets();
  const [dsId, setDsId] = useState<string | null>(null);
  const ds: Dataset | null = datasets.data?.find((d) => d.id === dsId) ?? datasets.data?.find((d) => d.scientific) ?? datasets.data?.[0] ?? null;
  const [mode, setMode] = useState<"latest" | "replay">("latest");
  const [moment, setMoment] = useState<string>("");
  useEffect(() => { setMode("latest"); setMoment(""); }, [dsId]);
  const asOf = mode === "latest" || !moment ? "latest" : moment;
  const refresh = () => { qc.invalidateQueries({queryKey: ["predict"]}); qc.invalidateQueries({queryKey: ["forecast"]}); qc.invalidateQueries({queryKey: ["registry"]}); };
  return {datasets, ds, dsId, setDsId, mode, setMode, moment, setMoment, asOf, refresh};
}

export function DatasetSelect({datasets, value, onChange}: {datasets: Dataset[]; value: string; onChange: (id: string) => void}) {
  return <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Dataset">{datasets.map((x) => <option key={x.id} value={x.id}>{x.name.split(" —")[0]}{x.user ? "" : x.live ? " · live" : " · benchmark"}</option>)}</select>;
}
