import {Link} from "react-router-dom";

import {PhotoCard} from "@/components/PhotoCard";
import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {DayPlan} from "@/features/assistant/DayPlan";
import {useGoals} from "@/features/assistant/hooks";
import {STATUS_TONE, STATUS_WORDS} from "@/features/assistant/types";
import {Updates} from "@/features/assistant/Updates";
import {useFeed, useTwin} from "./hooks";
import {Risks} from "./Risks";
import {Stats} from "./Stats";
import {Ask} from "./Ask";
import {Cards} from "./Cards";
import {Greeting, Welcome} from "./Welcome";
import {Home} from "./Home";
import "@/features/assistant/assistant.css";

const ACTIVE = new Set(["planning", "running", "waiting_approval", "waiting_user"]);

/** TODAY: the home (the city in 3D, a trip, when to leave, alerts), then the day as one screen: numbers, timeline, risks and suggestions, active goals, updates. Everything is computed now. */
export function TodayPage() {
  const twin = useTwin(24), goals = useGoals(), feed = useFeed();
  const active = (goals.data?.goals ?? []).filter((g) => ACTIVE.has(g.status));
  return (
    <div className="stack today">
      <Home />
      <Welcome />
      <Ask />
      <Greeting />
      <Cards twin={twin.data} />
      <Stats twin={twin.data} goals={goals.data?.goals} feed={feed.data} />
      <Risks twin={twin.data} goals={goals.data?.goals} feed={feed.data} />
      <div className="grid wide">
        <div className="stack">
          <DayPlan />
        </div>
        <div className="stack">
          <Card title="Goals in progress" sub={active.length ? `${active.length} active` : "none active"} right={<Link to="/messages" className="chip">New goal</Link>}>
            {!goals.data ? <Loading /> : active.length ? <ul className="plain goals">{active.map((g) => <li key={g.id}><Link to={`/goals/${g.id}`}><Pill tone={STATUS_TONE[g.status]}>{STATUS_WORDS[g.status]}</Pill> {g.text}</Link> <span className="muted small">{ago(g.updated_utc)}</span></li>)}</ul> : <p className="muted small">Ask the agent for something and it appears here while it works.</p>}
          </Card>
          <Updates />
        </div>
      </div>
      <div className="phototiles">
        <PhotoCard photo="interchange" title="Plan a trip" text="Routes now and at departure, and the latest time you can leave." to="/map" />
        <PhotoCard photo="shibuya" title="The city an hour ahead" text="Every measured road at +15, +30 and +60 minutes." to="/city" />
        <PhotoCard photo="tokyoHighway" title="How it is tested" text="Simulation evidence, the models and every reference, for reviewers." to="/lab" />
      </div>
    </div>
  );
}
