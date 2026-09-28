import {useMutation, useQuery} from "@tanstack/react-query";
import {useRef, useState} from "react";

import {api, pollJob} from "@/lib/api";
import type {TripJob, TripResult} from "./types";

export const STAGES = ["Finding the places", "Reading traffic", "Forecasting", "Comparing routes"];
const stageIndex = (s = "") => (/Resolving|Loading/.test(s) ? 0 : /Fetching|Validating/.test(s) ? 1 : /checkpoint|inference/i.test(s) ? 2 : 3);

export type TripRequest = {city: string; origin: string; destination: string; departure?: string | null; departure_local?: string | null; model?: string; horizon_min?: number};

/** Start an analysis job and follow it to the end. The stage index drives the progress row. */
export function useTripAnalysis() {
  const [stage, setStage] = useState(0);
  const dead = useRef({dead: false});
  const m = useMutation({
    mutationFn: async (req: TripRequest): Promise<TripResult> => {
      setStage(0);
      const {job} = await api.analyzeStart({horizon_min: 30, model: "auto", ...req});
      const final = await pollJob<TripJob>(() => api.analyzeStatus(job) as Promise<TripJob>, {every: 700, active: ["queued", "running"], signal: dead.current, onTick: (s) => setStage(stageIndex(s.stage))});
      if (final.status !== "done" || !final.result) throw new Error((final.error || "analysis failed").replace(/^\w+Error: /, ""));
      return final.result;
    },
  });
  return {...m, stage};
}

export function usePlaces(city: string, search: string) {
  return useQuery({queryKey: ["places", city, search], queryFn: () => api.places(city, search) as Promise<{places: {label: string}[]}>, staleTime: 60_000});
}

export function useCities() {
  return useQuery({queryKey: ["cities"], queryFn: () => api.cities() as Promise<{cities: {id: string; label: string; dataset?: string}[]}>, staleTime: Infinity});
}

export function useModels(city: string) {
  return useQuery({queryKey: ["models", city], queryFn: () => api.models(city) as Promise<any>, staleTime: 60_000});
}
