import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {useState} from "react";

import {Button, Card, ErrorNote, Loading} from "@/components/ui";
import {get, postForm} from "@/lib/api";
import {USER_ID} from "./types";

type Feed = {events: {id: string; title: string; start_utc: string; location: string}[]; calendars: {id: string; name: string; url: string; imported_utc: string; events: number}[]};

/** Bring your calendar in from any iCalendar link or file (Google, Outlook, Apple and university calendars all export one). Events with a place get a departure plan. */
export function CalendarImport() {
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const q = useQuery({queryKey: ["calendar"], queryFn: () => get<Feed>(`/api/calendar/events?user_id=${USER_ID}&hours=168`)});
  const imp = useMutation({
    mutationFn: () => { const f = new FormData(); f.set("user_id", USER_ID); if (file) f.set("file", file); else f.set("url", url); return postForm("/api/calendar/import", f); },
    onSuccess: () => { setUrl(""); setFile(null); qc.invalidateQueries({queryKey: ["calendar"]}); qc.invalidateQueries({queryKey: ["plan"]}); },
  });
  return (
    <Card title="Your calendar" sub={q.data?.calendars.length ? `${q.data.calendars.length} calendar${q.data.calendars.length > 1 ? "s" : ""} linked · ${q.data.events.length} events this week` : "link a calendar and every event with a place gets a leave-by time"}>
      <div className="row">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="iCalendar link (webcal:// or https://…ics)" aria-label="Calendar link" style={{flex: 1, minWidth: 220}} />
        <label className="btn ghost small">{file ? file.name : "or an .ics file"}<input type="file" accept=".ics,text/calendar" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <Button onClick={() => imp.mutate()} disabled={imp.isPending || (!url && !file)}>{imp.isPending ? "importing…" : "Import"}</Button>
      </div>
      {imp.error ? <ErrorNote error={imp.error} /> : null}
      {imp.data ? <p className="good small">Imported {String((imp.data as {imported: number}).imported)} events.</p> : null}
      {!q.data ? <Loading /> : q.data.events.length > 0 && <ul className="plain" style={{marginTop: 8}}>{q.data.events.slice(0, 6).map((e) => <li key={e.id}>{e.title} <span className="muted small">{new Date(e.start_utc).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"})}{e.location ? ` · ${e.location}` : ""}</span></li>)}</ul>}
    </Card>
  );
}
