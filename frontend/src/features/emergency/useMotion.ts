import {useCallback, useEffect, useReducer, useRef, useState} from "react";

import {api} from "@/lib/api";
import {INITIAL, isJolt, magnitudeG, reduce, type Sample} from "./sos";

type MotionEventCtor = typeof DeviceMotionEvent & {requestPermission?: () => Promise<"granted" | "denied">};

/**
 * The phone's motion sensor (DeviceMotion, accelerationIncludingGravity) behind the SOS state machine: listens only while armed,
 * asks iOS for permission, and can replay a synthetic trace through the same rule at its own rate for a laptop or the thesis.
 */
export function useMotion() {
  const [state, dispatch] = useReducer(reduce, INITIAL);
  const [support, setSupport] = useState<"unknown" | "yes" | "no" | "denied">("unknown");
  const replay = useRef<number | null>(null);
  const buf = useRef<{t: number; g: number}[]>([]);                  // the last 10 s the rule read, for the live graph (MotionGraph)
  const [recent, setRecent] = useState<{t: number; g: number}[]>([]);
  const keep = (t: number, g: number) => { buf.current.push({t, g}); while (buf.current.length && t - buf.current[0].t > 10) buf.current.shift(); };
  useEffect(() => {                                   // redraw the graph ten times a second while armed
    if (state.phase !== "armed" && state.phase !== "countdown") return;
    const id = window.setInterval(() => setRecent([...buf.current]), 100);
    return () => window.clearInterval(id);
  }, [state.phase]);
  const stopReplay = () => { if (replay.current != null) { window.clearInterval(replay.current); replay.current = null; } };
  useEffect(() => { setSupport(typeof window !== "undefined" && "DeviceMotionEvent" in window ? "yes" : "no"); }, []);
  useEffect(() => {                                   // the sensor, only while armed on it
    if (state.phase !== "armed" || state.source !== "sensor" || support !== "yes") return;
    const on = (e: DeviceMotionEvent) => {
      const a = e.accelerationIncludingGravity;
      if (!a || a.x == null || a.y == null || a.z == null) return;
      const s: Sample = {t: e.timeStamp / 1000, ax: a.x, ay: a.y, az: a.z};
      const g = magnitudeG(s.ax, s.ay, s.az);
      keep(s.t, g);
      if (isJolt(s)) dispatch({type: "jolt", g: Math.round(g * 100) / 100, source: "sensor"}); else dispatch({type: "sample", g});
    };
    window.addEventListener("devicemotion", on);
    return () => window.removeEventListener("devicemotion", on);
  }, [state.phase, state.source, support]);
  useEffect(() => {                                   // the countdown
    if (state.phase !== "countdown") return;
    const t = window.setInterval(() => dispatch({type: "tick"}), 1000);
    return () => window.clearInterval(t);
  }, [state.phase]);
  useEffect(() => () => stopReplay(), []);
  const arm = useCallback(async () => {
    const ctor = (window as any).DeviceMotionEvent as MotionEventCtor | undefined;
    if (ctor?.requestPermission) {
      try { if ((await ctor.requestPermission()) !== "granted") { setSupport("denied"); return; } } catch { setSupport("denied"); return; }
    }
    buf.current = [];
    dispatch({type: "arm", source: "sensor"});
  }, []);
  const replayTrace = useCallback(async (kind: string) => {
    stopReplay();
    const tr = (await api.sosTrace(kind)) as {samples: Sample[]; rate_hz: number};
    buf.current = [];
    dispatch({type: "arm", source: `synthetic:${kind}`});
    let i = 0;
    const started = Date.now();
    replay.current = window.setInterval(() => {
      const due = Math.min(tr.samples.length, Math.floor(((Date.now() - started) / 1000) * tr.rate_hz));   // the trace runs on the clock, whatever the timer's rate (a background tab throttles it)
      const chunk = tr.samples.slice(i, due);
      i = due;
      for (const s of chunk) {
        const g = magnitudeG(s.ax, s.ay, s.az);
        keep((started / 1000) + s.t, g);
        if (isJolt(s)) { dispatch({type: "jolt", g: Math.round(g * 100) / 100, source: `synthetic:${kind}`}); stopReplay(); return; }
        dispatch({type: "sample", g});
      }
      if (i >= tr.samples.length) stopReplay();
    }, 100);
  }, []);
  const disarm = useCallback(() => { stopReplay(); dispatch({type: "disarm"}); }, []);
  return {state, support, recent, arm, disarm, replayTrace, cancel: () => dispatch({type: "cancel"}), reset: () => { stopReplay(); dispatch({type: "reset"}); }};
}
