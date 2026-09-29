import {useCallback, useState} from "react";

import {PhotoCard} from "@/components/PhotoCard";
import {Steps} from "@/components/Steps";
import {Card, ErrorNote} from "@/components/ui";
import {CommutePlanner} from "./CommutePlanner";
import {RouteCards} from "./RouteCards";
import {RouteMap} from "./RouteMap";
import {TransitCard} from "./TransitCard";
import {TripForm, type TripFields} from "./TripForm";
import {STAGES, useTripAnalysis} from "./useTripAnalysis";
import "./mobility.css";

/** MOBILITY: one trip → traffic now and at departure, the routes on the map, the recommendation, and "leave when?". */
export function MobilityPage() {
  const analysis = useTripAnalysis();
  const [fields, setFields] = useState<TripFields | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const onChange = useCallback((f: TripFields) => setFields(f), []);
  const r = analysis.data ?? null;
  return (
    <div className="stack">
      <Card title="Where to?" sub="traffic now, traffic at departure, the best route, and when to leave">
        <TripForm onSubmit={(req) => { setHighlight(null); analysis.mutate(req); }} busy={analysis.isPending} onChange={onChange} />
        {analysis.isPending && <div style={{marginTop: 10}}><Steps steps={STAGES} current={analysis.stage} /></div>}
        {analysis.error ? <div style={{marginTop: 10}}><ErrorNote error={analysis.error} /></div> : null}
      </Card>
      <div className={r ? "grid wide" : "stack compact-map"}>
        <Card title={r ? `${r.origin.label ?? "A"} → ${r.destination.label ?? "B"}` : "Your city"} sub={r ? `${r.routes.length} routes · horizon +${r.horizon_min} min` : "the routes are drawn here once a trip is analysed"}>
          <RouteMap result={r} highlight={highlight} />
        </Card>
        {r && <div className="stack"><Card title="By road" sub="now, at departure, and why one is recommended"><RouteCards r={r} onPick={setHighlight} /></Card>
          {fields && <TransitCard trip={{city: fields.city, origin: fields.origin, destination: fields.destination}} roadEtaS={r.current.eta_s} />}</div>}
      </div>
      {fields && <CommutePlanner trip={{city: fields.city, origin: fields.origin, destination: fields.destination}} />}
      <div className="phototiles">
        <PhotoCard photo="aerial" title="Ask the assistant" text={'"Be there by nine, remind me when to leave."'} to="/today" />
        <PhotoCard photo="metroCar" title="The city an hour ahead" text="Where congestion forms next, on the map." to="/city" />
      </div>
    </div>
  );
}
