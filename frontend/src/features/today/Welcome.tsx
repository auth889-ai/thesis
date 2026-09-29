import {useState} from "react";

import {Button, Card, ErrorNote, Field} from "@/components/ui";
import {browserZone, locateMe, useProfile, useSaveProfile, type Profile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";

const hour = (p?: Profile) => new Date(p?.local_time ?? Date.now()).getHours();
export const greeting = (p?: Profile) => { const h = p ? new Date(p.local_time).getHours() : new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };

/** The first thing a new person sees: who they are, where they are, and how safe they want to be. Nothing is assumed. */
export function Welcome() {
  const profile = useProfile(USER_ID), save = useSaveProfile(USER_ID);
  const [name, setName] = useState(""), [city, setCity] = useState(""), [home, setHome] = useState(""), [work, setWork] = useState(""), [target, setTarget] = useState(0.8);
  const [pos, setPos] = useState<{lat: number; lng: number} | null>(null), [locating, setLocating] = useState(false), [locErr, setLocErr] = useState<string | null>(null);
  if (!profile.data || profile.data.exists) return null;
  const locate = async () => { setLocating(true); setLocErr(null); try { const r = await locateMe(); setCity(r.city); setPos({lat: r.lat, lng: r.lng}); } catch (e) { setLocErr((e as Error).message); } finally { setLocating(false); } };
  const submit = () => save.mutate({name: name.trim() || undefined, timezone: browserZone(), city: city.trim() || undefined, home: home.trim() || undefined, work: work.trim() || undefined, on_time_target: target, ...(pos ?? {})});
  return (
    <Card title="Welcome" sub={`your clock is read as ${browserZone()}; say where you live so every time and route is yours`}>
      <div className="grid two">
        <Field label="Your name"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="how should we greet you?" /></Field>
        <Field label="Your city"><div className="row"><input value={city} onChange={(e) => setCity(e.target.value)} placeholder="type it, or use your location" style={{flex: 1}} /><Button kind="ghost" onClick={locate} disabled={locating}>{locating ? "finding…" : "Use my location"}</Button></div></Field>
        <Field label="Home (a place name or address)"><input value={home} onChange={(e) => setHome(e.target.value)} placeholder="where your days start" /></Field>
        <Field label="Work or study (optional)"><input value={work} onChange={(e) => setWork(e.target.value)} placeholder="where you usually go" /></Field>
        <Field label="How sure do you want to be of arriving on time?"><select value={target} onChange={(e) => setTarget(Number(e.target.value))}><option value={0.8}>80 % (recommended)</option><option value={0.9}>90 %</option><option value={0.95}>95 %</option></select></Field>
      </div>
      {locErr && <p className="small bad">{locErr}</p>}
      {save.error ? <ErrorNote error={save.error} /> : null}
      <div className="row" style={{marginTop: 10}}><Button onClick={submit} disabled={save.isPending || !city.trim()}>{save.isPending ? "saving…" : "Start"}</Button><span className="muted small">Your location is used once to name the city; it is not tracked. Everything can be changed or erased on the You page.</span></div>
    </Card>
  );
}

export function Greeting() {
  const profile = useProfile(USER_ID);
  const p = profile.data;
  if (!p?.exists) return null;
  const when = new Date(p.local_time).toLocaleDateString([], {weekday: "short", month: "short", day: "numeric", timeZone: p.timezone});
  return <div className="greeting"><h2>{greeting(p)}{p.name ? `, ${p.name}` : ""} 👋</h2><p className="muted">Here is what is happening today in {p.city} · {when}{hour(p) < 6 ? " · it is early" : ""}</p></div>;
}
