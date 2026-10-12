import {Loading} from "@/components/ui";
import {useCity} from "@/lib/city";
import {SosCard} from "@/features/emergency/SosCard";
import {NavigateCard} from "./NavigateCard";
import {NearestCard} from "./NearestCard";
import "./home.css";

/**
 * HOME, focused (owner, 2026-10-08): three things a person needs on the road, large and plain: crash SOS, the nearest hospital from
 * here, and navigation. Everything else is behind "More", unchanged.
 */
export function FocusHome() {
  const {city} = useCity();
  if (!city) return <Loading />;
  return (
    <div className="focus-home" data-story="focus-home">
      <SosCard city={city} compact />
      <NearestCard city={city} />
      <NavigateCard city={city} />
    </div>
  );
}
