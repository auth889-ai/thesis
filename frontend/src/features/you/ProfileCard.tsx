import {useEffect, useState} from "react";

import {Button, Card, ErrorNote, Field} from "@/components/ui";
import {browserZone, locateMe, useProfile, useSaveProfile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";

/** Who you are and where you live, as the server holds it; every field editable; the source shown when nothing is set. */
export function ProfileCard() {
  const profile = useProfile(USER_ID), save = useSaveProfile(USER_ID);
  const [f, setF] = useState({name: "", timezone: browserZone(), city: "", home: "", work: "", on_time_target: 0.8});
  useEffect(() => { const p = profile.data; if (p) setF({name: p.name ?? "", timezone: p.timezone, city: p.exists ? p.city : "", home: p.home ?? "", work: p.work ?? "", on_time_target: p.on_time_target}); }, [profile.data]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((c) => ({...c, [k]: k === "on_time_target" ? Number(e.target.value) : e.target.value}));
  const locate = async () => { try { const r = await locateMe(); setF((c) => ({...c, city: r.city})); save.mutate({lat: r.lat, lng: r.lng, city: r.city}); } catch (e) { alert((e as Error).message); } };
  return (
    <Card title="Who and where" sub={profile.data?.source === "person" ? `as you set it · local time ${new Date(profile.data.local_time).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", timeZone: profile.data.timezone})}` : "not set yet: the deployment's defaults are being used"}>
      <div className="grid two">
        <Field label="Name"><input value={f.name} onChange={set("name")} /></Field>
        <Field label="Timezone"><input value={f.timezone} onChange={set("timezone")} placeholder="Asia/Dhaka" /></Field>
        <Field label="City"><div className="row"><input value={f.city} onChange={set("city")} style={{flex: 1}} /><Button kind="ghost" onClick={locate}>Use my location</Button></div></Field>
        <Field label="On-time target"><select value={f.on_time_target} onChange={set("on_time_target")}><option value={0.8}>80 %</option><option value={0.9}>90 %</option><option value={0.95}>95 %</option></select></Field>
        <Field label="Home"><input value={f.home} onChange={set("home")} /></Field>
        <Field label="Work or study"><input value={f.work} onChange={set("work")} /></Field>
      </div>
      {save.error ? <ErrorNote error={save.error} /> : null}
      <div className="row" style={{marginTop: 10}}><Button onClick={() => save.mutate({...f, name: f.name || undefined, home: f.home || undefined, work: f.work || undefined, city: f.city || undefined})} disabled={save.isPending}>{save.isPending ? "saving…" : "Save"}</Button><span className="muted small">id {USER_ID}</span></div>
    </Card>
  );
}
