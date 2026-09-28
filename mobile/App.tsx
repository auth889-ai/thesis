/**
 * TrafficTwin mobile — the same product as the web app on the same API, for a phone:
 *   Trip      where to? → ETA now and at departure, the recommended route, the honest data label
 *   Forecast  the sensor network's predicted state (Los Angeles benchmark data)
 *   Results   does smart routing help? — the current evidence, computed by the backend
 */
import {StatusBar} from "expo-status-bar";
import React, {useEffect, useState} from "react";
import {ActivityIndicator, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View} from "react-native";

import {API_URL, analyzeTrip, forecastNetwork, health, researchStatus, stressEvidence, type ForecastNetwork, type StressEvidence, type TripResult} from "./src/api/client";

type Tab = "trip" | "forecast" | "results";
const mins = (s: number | null | undefined) => (s == null ? "—" : `${(s / 60).toFixed(s < 600 ? 1 : 0)} min`);
const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(d)} %`);
const word = (label: string | null | undefined) => (label === "HELPED" ? "shorter" : label === "HURT" ? "longer" : "about the same");

export default function App() {
  const [tab, setTab] = useState<Tab>("trip");
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => { health().then(() => setOnline(true)).catch(() => setOnline(false)); }, []);
  return (
    <SafeAreaView style={s.app}>
      <StatusBar style="light" />
      <View style={s.header}>
        <Text style={s.brand}>TrafficTwin</Text>
        <Text style={s.sub}>forecast · route · V2X · SUMO</Text>
        <Text style={[s.dot, online === false && s.dotBad]}>{online == null ? "connecting…" : online ? `● API ${API_URL}` : `✕ API unreachable at ${API_URL}`}</Text>
      </View>
      <View style={s.tabs}>
        {(["trip", "forecast", "results"] as Tab[]).map((t) => (
          <Pressable key={t} onPress={() => setTab(t)} style={[s.tab, tab === t && s.tabOn]}><Text style={[s.tabText, tab === t && s.tabTextOn]}>{t === "trip" ? "Trip" : t === "forecast" ? "Forecast" : "Results"}</Text></Pressable>
        ))}
      </View>
      {tab === "trip" ? <TripScreen /> : tab === "forecast" ? <ForecastScreen /> : <ResultsScreen />}
    </SafeAreaView>
  );
}

function TripScreen() {
  const [city, setCity] = useState("Dhaka"); const [from, setFrom] = useState("Farmgate"); const [to, setTo] = useState("Shahbagh");
  const [stage, setStage] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null); const [r, setR] = useState<TripResult | null>(null);
  const run = async () => {
    setBusy(true); setErr(null); setR(null);
    try { setR(await analyzeTrip({city, origin: from, destination: to}, setStage)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); setStage(null); }
  };
  const h = r ? String(r.horizon_min) : "30";
  const rec = r?.routes.find((c) => c.recommended) ?? r?.routes[0];
  return (
    <ScrollView contentContainerStyle={s.body}>
      <Text style={s.h1}>Where to?</Text>
      <Text style={s.label}>CITY</Text><TextInput style={s.input} value={city} onChangeText={setCity} />
      <Text style={s.label}>FROM</Text><TextInput style={s.input} value={from} onChangeText={setFrom} />
      <Text style={s.label}>TO</Text><TextInput style={s.input} value={to} onChangeText={setTo} />
      <Pressable style={[s.button, busy && s.buttonBusy]} disabled={busy} onPress={run}><Text style={s.buttonText}>{busy ? (stage ?? "Working…") : "Forecast & route →"}</Text></Pressable>
      {busy && <ActivityIndicator style={{marginTop: 8}} />}
      {err && <Text style={s.error}>✕ {err}</Text>}
      {r && rec && (
        <View>
          <View style={s.cards}>
            <Card k={r.source.is_live ? "NOW · measured" : "NOW · last recorded"} v={mins(r.current.eta_s)} tag={r.current.congestion} />
            <Card k={`AT DEPARTURE · +${h} min · predicted`} v={mins(r.forecast.eta_s)} tag={`${r.forecast.risk} risk`} hi />
          </View>
          <Text style={s.decision}>Route {r.decision.recommended} — {r.decision.reason}{r.decision.saving_s > 60 ? ` (about ${Math.round(r.decision.saving_s / 60)} min saved)` : ""}</Text>
          {r.routes.map((c) => (
            <View key={c.key} style={[s.route, c.recommended && s.routeOn]}>
              <Text style={s.routeKey}>Route {c.key}{c.recommended ? " · recommended" : ""}</Text>
              <Text style={s.routeLine}>now {mins(c.eta_now_s)} · at +{h} min {mins(c.forecast[h]?.eta_s)} · {c.distance_m ? `${(c.distance_m / 1000).toFixed(1)} km` : ""} · {c.forecast[h]?.risk ?? "—"} risk{c.forecast[h]?.covered ? "" : " (no forecast on this route)"}</Text>
            </View>
          ))}
          <Text style={s.honest}>Forecast: {r.forecast.model ?? "none"} · {r.forecast.confidence}{"\n"}Traffic: {r.source.traffic}{"\n"}{r.source.is_live ? "" : "Minutes are uncalibrated (posted limits × recorded band); compare routes, not clocks."}</Text>
        </View>
      )}
    </ScrollView>
  );
}

function ForecastScreen() {
  const [n, setN] = useState<ForecastNetwork | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { forecastNetwork().then(setN).catch((e) => setErr((e as Error).message)); }, []);
  if (err) return <Text style={[s.body, s.error]}>✕ {err}</Text>;
  if (!n) return <ActivityIndicator style={{marginTop: 40}} />;
  const h = String(n.horizons?.includes(30) ? 30 : n.horizons?.[0] ?? 30);
  const rows = n.sensors.filter((x) => x.now_kmh != null && x.predicted?.[h] != null).map((x) => ({node: x.node, now: x.now_kmh as number, later: x.predicted![h] as number})).map((x) => ({...x, drop: x.later - x.now})).sort((a, b) => a.drop - b.drop);
  return (
    <ScrollView contentContainerStyle={s.body}>
      <Text style={s.h1}>Traffic forecast · {n.dataset}</Text>
      <Text style={s.honest}>Graph WaveNet on the 207-sensor Los Angeles benchmark (real detector data, held-out days). +{h} min ahead. {rows.filter((x) => x.drop <= -5).length} sensors predicted to slow by 5 km/h or more.</Text>
      {rows.slice(0, 12).map((x) => (
        <View key={x.node} style={s.route}><Text style={s.routeKey}>{x.node} · {x.drop <= -5 ? "slowing" : x.drop >= 5 ? "improving" : "steady"}</Text><Text style={s.routeLine}>{x.now.toFixed(0)} → {x.later.toFixed(0)} km/h ({x.drop > 0 ? "+" : ""}{x.drop.toFixed(0)})</Text></View>
      ))}
    </ScrollView>
  );
}

function ResultsScreen() {
  const [S, setS] = useState<StressEvidence | null>(null); const [G, setG] = useState<Record<string, {status: string}> | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { stressEvidence().then(setS).catch((e) => setErr((e as Error).message)); researchStatus().then((g) => setG(g.gates)).catch(() => setG({})); }, []);
  if (err) return <Text style={[s.body, s.error]}>✕ {err}</Text>;
  if (!S || !G) return <ActivityIndicator style={{marginTop: 40}} />;
  const A = S.scenarios.A?.eval; const arm = (name: string) => A?.arms.find((a) => a.arm === name);
  const oracle = arm("oracle_v2x")?.vs_reactive; const gw = arm("predictive_v2x"); const futureOk = G.FUTURE_INFORMATION_VALUE?.status === "ESTABLISHED"; const predOk = G.PREDICTIVE_TRAFFIC_BENEFIT?.status === "ESTABLISHED";
  return (
    <ScrollView contentContainerStyle={s.body}>
      <Text style={s.h1}>Does smart routing help?</Text>
      <Text style={s.hero}>{predOk ? `Yes — the AI forecast makes trips ${Math.abs(gw?.vs_baseline.mean_pct ?? 0).toFixed(1)} % shorter than no advice.` : futureOk ? `Knowing the future helps: a perfect view of the next hour cuts total travel time ${Math.abs(oracle?.mean_pct ?? 0).toFixed(1)} % against reactive routing. Today's AI forecast does not yet capture that gain.` : "Not yet — no information source beat reactive routing with confidence."}</Text>
      <View style={s.cards}>
        <Card k="Perfect knowledge of the future" v={pct(oracle?.mean_pct)} tag={`vs reactive · ${word(oracle?.label)}`} hi={oracle?.label === "HELPED"} />
        <Card k="AI forecast (Graph WaveNet)" v={pct(gw?.vs_reactive?.mean_pct)} tag={`vs reactive · ${word(gw?.vs_reactive?.label)}`} hi={gw?.vs_reactive?.label === "HELPED"} />
        <Card k="AI forecast vs no advice" v={pct(gw?.vs_baseline.mean_pct)} tag={word(gw?.vs_baseline.label)} />
      </View>
      <Text style={s.honest}>Simulation of a congested Los Angeles corridor, {A?.seeds?.length ?? 0} unseen days, identical start state in every world; only the routing advice changed. Controller status: {S.controller_status.status}. Every number is computed by the backend from run files.</Text>
      {Object.entries(G).map(([k, v]) => (<Text key={k} style={s.gate}>{k.replace(/_/g, " ")}: {v.status}</Text>))}
    </ScrollView>
  );
}

function Card({k, v, tag, hi}: {k: string; v: string; tag?: string; hi?: boolean}) {
  return (<View style={[s.card, hi && s.cardHi]}><Text style={s.cardK}>{k}</Text><Text style={s.cardV}>{v}</Text>{tag ? <Text style={s.cardTag}>{tag}</Text> : null}</View>);
}

const s = StyleSheet.create({
  app: {flex: 1, backgroundColor: "#f6f4ee"}, header: {backgroundColor: "#16251f", padding: 16, paddingTop: 24}, brand: {color: "#8fd3bd", fontSize: 22, fontWeight: "800"}, sub: {color: "#9fb3aa", fontSize: 11, letterSpacing: 1.5, marginTop: 2},
  dot: {color: "#8fd3bd", fontSize: 11, marginTop: 8}, dotBad: {color: "#ff9a8a"},
  tabs: {flexDirection: "row", backgroundColor: "#16251f", paddingHorizontal: 8}, tab: {flex: 1, paddingVertical: 12, alignItems: "center", borderBottomWidth: 3, borderBottomColor: "transparent"}, tabOn: {borderBottomColor: "#8fd3bd"}, tabText: {color: "#9fb3aa", fontWeight: "700"}, tabTextOn: {color: "#fff"},
  body: {padding: 16, paddingBottom: 48}, h1: {fontSize: 22, fontWeight: "800", marginBottom: 8}, label: {fontSize: 11, fontWeight: "800", letterSpacing: 1, color: "#666", marginTop: 10}, input: {borderWidth: 1, borderColor: "#d8d3c6", borderRadius: 10, padding: 12, fontSize: 16, backgroundColor: "#fff", marginTop: 4},
  button: {backgroundColor: "#1f5a4a", borderRadius: 12, padding: 14, alignItems: "center", marginTop: 16}, buttonBusy: {opacity: 0.7}, buttonText: {color: "#fff", fontWeight: "800", fontSize: 16}, error: {color: "#a63d40", marginTop: 12},
  cards: {flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 16}, card: {flexGrow: 1, minWidth: "45%", backgroundColor: "#fff", borderRadius: 12, padding: 12, borderWidth: 1, borderColor: "#e6e1d4"}, cardHi: {borderColor: "#7b2d3b", backgroundColor: "#fbf3e8"},
  cardK: {fontSize: 10, fontWeight: "800", letterSpacing: 1, color: "#666"}, cardV: {fontSize: 26, fontWeight: "800", marginTop: 4}, cardTag: {fontSize: 12, color: "#3f7d3a", marginTop: 4},
  decision: {marginTop: 12, fontWeight: "700"}, route: {backgroundColor: "#fff", borderRadius: 10, padding: 12, marginTop: 8, borderWidth: 1, borderColor: "#e6e1d4"}, routeOn: {borderColor: "#4a5d23", borderWidth: 2}, routeKey: {fontWeight: "800"}, routeLine: {color: "#444", marginTop: 2, fontSize: 13},
  honest: {marginTop: 14, color: "#5b5750", fontSize: 12, lineHeight: 17}, hero: {fontSize: 17, fontWeight: "700", lineHeight: 24, marginTop: 4}, gate: {fontSize: 12, color: "#444", marginTop: 4},
});
