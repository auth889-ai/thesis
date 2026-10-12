import {useQuery} from "@tanstack/react-query";

import {PlainResult} from "@/components/PlainResult";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {ambulanceSentence, type Rq2Plain} from "./ambulanceSentence";

/** SIMULATED: the ambulance alert in one plain sentence, from RQ2's summary, with "How we know" to the RQ2 card. Only for the city RQ2 ran on;
 * any other city gets "no result" rather than Dhaka's numbers (CLAUDE.md, city-agnostic rules 4 and 5). */
export function AmbulancePlain({cityId, cityName}: {cityId: string; cityName: string}) {
  const {t} = useI18n();
  const q = useQuery({queryKey: ["emergency-rq2"], queryFn: () => api.emergencyRq2() as Promise<{available: boolean; city_id?: string; plain?: Rq2Plain | null}>});
  if (q.isPending) return null;
  const p = q.data?.available && q.data.city_id === cityId ? q.data.plain : null;          // a failed request also says "no result", never a blank card
  if (!p) return <p className="muted">{t("emergency.noResult", {city: cityName})}</p>;
  return <PlainResult kind="simulated" to="/lab/evidence#rq2">{ambulanceSentence(p, t)}</PlainResult>;
}
