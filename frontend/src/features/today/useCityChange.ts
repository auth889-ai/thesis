import {useEffect, useRef} from "react";

/**
 * Run `reset` when the person switches from one city to another, never when the city first becomes known. A trip belongs to one
 * city, but the city list arriving after the page opened is not a switch (QA 2026-10-07: a typed start and destination, or a place
 * sent from the search, were cleared when the city finished loading).
 */
export function useCityChange(cityId: string | undefined, reset: () => void) {
  const last = useRef<string | undefined>(cityId);
  const fn = useRef(reset); fn.current = reset;
  useEffect(() => {
    if (cityId && last.current && cityId !== last.current) fn.current();
    if (cityId) last.current = cityId;
  }, [cityId]);
}
