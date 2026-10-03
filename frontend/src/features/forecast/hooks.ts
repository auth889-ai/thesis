import {useQuery} from "@tanstack/react-query";

import {api} from "@/lib/api";
import type {Dataset, Network, RoadForecast} from "./model";

const order = (x: Dataset) => (x.scientific ? -1 : x.user ? 0 : x.live ? 1 : 2);

export function useDatasets(uploads = true) {
  return useQuery({queryKey: ["predict", "datasets", uploads], queryFn: () => api.datasets(uploads) as Promise<{datasets: Dataset[]}>, select: (r) => r.datasets, staleTime: 60_000});
}

/** The whole-network forecast: every sensor and every mapped road at NOW / +15 / +30 / +60. */
export function useNetwork(ds: Dataset | null, asOf: string | number) {
  const mapped = !!ds && (!!ds.scientific || ds.id.startsWith("user:"));
  return useQuery({queryKey: ["forecast", "network", ds?.id, asOf], enabled: mapped, queryFn: () => api.forecastNetwork(ds!.id, asOf) as Promise<Network>, staleTime: 5 * 60_000});
}

export function useRoad(ds: string | undefined, node: string | null, asOf: string | number) {
  return useQuery({queryKey: ["forecast", "road", ds, node, asOf], enabled: !!ds && !!node, queryFn: () => api.forecastRoad(ds!, node!, asOf) as Promise<RoadForecast>, staleTime: 5 * 60_000});
}

export function useRegistry(scope: string | undefined) {
  return useQuery({queryKey: ["registry", scope], enabled: !!scope, queryFn: () => api.registry(scope!).catch(() => ({})) as Promise<any>, staleTime: 60_000});
}

export function useTrained() {
  return useQuery({queryKey: ["predict", "trained"], queryFn: () => api.trained().catch(() => ({trained: []})) as Promise<{trained: any[]}>, staleTime: 60_000});
}

export function useCloud() {
  return useQuery({queryKey: ["predict", "cloud"], queryFn: () => api.cloud().catch(() => ({available: false})) as Promise<{available: boolean}>, staleTime: Infinity});
}
