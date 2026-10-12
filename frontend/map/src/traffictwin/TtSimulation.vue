<template>
  <!-- TrafficTwin addition: the thesis's simulations run from the map (POST /api/live/{kind}), computed now on this server, labelled SIMULATION -->
  <div class="tt-sim">
    <q-chip data-tt="simulation" clickable icon="science" class="tt-chip-sim" @click="open = !open">{{ $t('tt.sim.chip') }}</q-chip>
  </div>
  <transition name="tt-slide">
    <div v-if="open" class="tt-hospital-sheet tt-sim-sheet" data-tt="sim-sheet">
      <div class="tt-sheet-head">
        <div>
          <div class="tt-sheet-title">{{ $t('tt.sim.title') }} <q-badge color="deep-orange">{{ $t('tt.sim.badge') }}</q-badge></div>
          <div class="tt-sheet-sub">{{ $t('tt.sim.sub') }}</div>
        </div>
        <q-btn flat round dense icon="close" :aria-label="$t('tt.close')" @click="close" />
      </div>
      <q-tabs v-model="kind" dense align="left" no-caps :disable="running">
        <q-tab v-for="k in kinds" :key="k" :name="k" :label="$t('tt.sim.kind.' + k)" :data-tt="'sim-tab-' + k" />
      </q-tabs>
      <div class="tt-sim-form">
        <q-select v-if="kind === 'v2x' || kind === 'sos'" v-model="p.tech" dense outlined emit-value map-options :options="techs" :label="$t('tt.sim.tech')" />
        <div v-if="kind === 'v2x' || kind === 'sos'">{{ $t('tt.sim.share', { pct: Math.round(p.share * 100) }) }}<q-slider v-model="p.share" :min="0" :max="1" :step="0.25" markers dense /></div>
        <q-select v-if="kind === 'mesh'" v-model="p.protocol" dense outlined emit-value map-options :options="protocols" :label="$t('tt.sim.protocol')" />
        <q-input v-if="kind === 'mesh'" v-model.number="p.phones" type="number" dense outlined :min="2" :max="17" :label="$t('tt.sim.phones')" />
        <q-input v-if="kind === 'mesh'" v-model.number="p.range" type="number" dense outlined :min="1" :max="200" :label="$t('tt.sim.range')" />
        <q-select v-if="kind === 'v2x' || kind === 'signals'" v-model="p.level" dense outlined emit-value map-options :options="levels" :label="$t('tt.sim.level')" />
        <q-input v-model.number="p.seed" type="number" dense outlined :min="1" :label="$t('tt.sim.seed')" />
        <q-btn v-if="!running" unelevated color="primary" icon="play_arrow" :label="$t('tt.sim.run')" data-tt="sim-run" @click="run" />
        <q-btn v-else outline color="negative" icon="stop" :label="$t('tt.sim.stop')" data-tt="sim-stop" @click="stop" />
      </div>
      <div class="tt-sim-thesis">{{ $t('tt.sim.thesis.' + kind) }}</div>
      <div v-if="job" class="tt-sim-live" data-tt="sim-live">
        <div class="tt-sheet-sub">{{ statusLine }}</div>
        <div v-if="last && last.counts" class="tt-sim-counts">
          <span v-for="(v, k) in last.counts" :key="k"><b>{{ v }}</b> {{ $t('tt.sim.count.' + k) }}</span>
        </div>
        <div v-if="kind === 'signals' && last" class="tt-sim-counts">
          <span><b>{{ last.fixed?.halting ?? '–' }}</b> {{ $t('tt.sim.haltFixed') }}</span><span><b>{{ last.rl?.halting ?? '–' }}</b> {{ $t('tt.sim.haltRl') }}</span>
        </div>
        <div v-if="error" class="tt-empty">{{ error }}</div>
      </div>
      <div v-if="result" class="tt-fc-card" data-tt="sim-result">
        <div v-for="(line, i) in resultLines" :key="i">{{ line }}</div>
        <q-badge :color="/^REPRODUCED/.test(result.check_text) ? 'positive' : /^DIFFERENT/.test(result.check_text) ? 'negative' : 'grey-7'" class="q-mt-xs" data-tt="sim-check">{{ result.check_text }}</q-badge>
        <div><a href="/app/lab/evidence" class="tt-howknow">{{ $t('tt.fc.how') }}</a></div>
      </div>
    </div>
  </transition>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { map } from 'src/components/BaseMap.vue';
import { frameBounds, frameFeatures, type Frame } from './ttSim';

const SRC = 'tt-sim';
const DEFAULTS: Record<string, Record<string, unknown>> = {
  v2x: { tech: 'its_g5', share: 1, seed: 11, level: 'dhaka' }, sos: { tech: 'its_g5', share: 0.5, seed: 11 },
  mesh: { protocol: 'prophet', phones: 17, range: 10, seed: 1 }, signals: { level: 'dhaka', seed: 11 },
};
let timer: number | undefined;

export default defineComponent({
  name: 'TtSimulation',
  data: () => ({ open: false, kind: 'v2x', kinds: ['v2x', 'sos', 'mesh', 'signals'], p: { ...DEFAULTS.v2x } as Record<string, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
    job: null as string | null, status: '', message: '', next: 0, last: null as Frame | null, result: null as Frame | null, error: '', fitted: false }),
  computed: {
    running(): boolean { return this.status === 'running' || this.status === 'starting'; },
    techs() { return [['its_g5', 'ITS-G5 (802.11p)'], ['c_v2x', 'C-V2X'], ['cellular_4g', '4G']].map(([value, label]) => ({ value, label })); },
    protocols() { return [['epidemic', 'Epidemic'], ['spray_and_wait', 'Spray and Wait'], ['prophet', 'PRoPHET']].map(([value, label]) => ({ value, label })); },
    levels() { return ['dhaka', 'x0.5', 'x1', 'x2', 'x3', 'x4'].map((v) => ({ value: v, label: v === 'dhaka' ? this.$t('tt.sim.levelDhaka') : v })); },
    statusLine(): string { return `${this.$t('tt.sim.status.' + (this.status || 'starting'))}${this.message ? ' · ' + this.message : ''}`; },
    resultLines(): string[] { return this.result ? linesFor(this.kind, this.result, (k: string, v?: Record<string, unknown>) => String(this.$t(k, v ?? {}))) : []; },
  },
  watch: { kind(k: string) { this.p = { ...DEFAULTS[k] }; this.reset(); } },
  beforeUnmount() { window.clearInterval(timer); this.clear(); },
  methods: {
    reset() { this.job = null; this.status = ''; this.message = ''; this.next = 0; this.last = null; this.result = null; this.error = ''; this.fitted = false; this.clear(); },
    close() { this.open = false; if (!this.running) this.clear(); },
    clear() {
      if (!map) return;
      for (const id of [SRC + '-line', SRC + '-pt']) if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(SRC)) map.removeSource(SRC);
    },
    draw(f: Frame | null) {
      if (!map) return;
      const features = frameFeatures(this.kind, f);
      const data = { type: 'FeatureCollection', features } as GeoJSON.FeatureCollection;
      const src = map.getSource(SRC) as { setData?: (d: unknown) => void } | undefined;
      if (src?.setData) src.setData(data);
      else {
        map.addSource(SRC, { type: 'geojson', data });
        map.addLayer({ id: SRC + '-line', type: 'line', source: SRC, filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': ['get', 'color'], 'line-width': 2.5 } });
        map.addLayer({ id: SRC + '-pt', type: 'circle', source: SRC, filter: ['==', ['geometry-type'], 'Point'],
          paint: { 'circle-color': ['get', 'color'], 'circle-radius': ['get', 'size'], 'circle-stroke-color': '#333', 'circle-stroke-width': 1 } });
      }
      const b = !this.fitted && frameBounds(features);
      if (b) { map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 80, maxZoom: 16, duration: 600 }); this.fitted = true; }
    },
    async run() {
      this.reset();
      const r = await fetch(`/api/live/${this.kind}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.p) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { this.status = 'failed'; this.error = j.detail || j.error || `HTTP ${r.status}`; this.job = 'none'; return; }
      this.job = j.job; this.status = 'starting';
      timer = window.setInterval(() => void this.poll(), 250);
    },
    async poll() {
      if (!this.job) return;
      const d = await fetch(`/api/live/jobs/${this.job}?since=${this.next}`).then((r) => r.json()).catch(() => null);
      if (!d) return;
      this.status = d.status; this.message = d.message; this.next = d.next;
      const shown = (d.frames as Frame[]).filter((f) => f.t != null);
      if (shown.length) { this.last = shown[shown.length - 1] ?? null; this.draw(this.last); }
      if (!this.running) { window.clearInterval(timer); this.result = d.result; if (d.status === 'failed') this.error = d.message; }
    },
    async stop() { if (this.job) await fetch(`/api/live/jobs/${this.job}/stop`, { method: 'POST' }); },
  },
});

/** The result card's sentences, every number from the job's result. */
function linesFor(kind: string, r: Frame, t: (k: string, v?: Record<string, unknown>) => string): string[] {
  if (kind === 'v2x') return [t('tt.sim.res.v2x', { a: r.no_alert_s, b: r.alert_s, pct: r.saved_pct }), t('tt.sim.res.msgs', { s: r.messages?.sent, d: r.messages?.delivered, al: r.alerted, g: r.junctions_green })];
  if (kind === 'sos') { const w = r.with_warning, n = r.without_warning; return [t('tt.sim.res.sos', { w: w.warned, r: w.rerouted, d: r.delivery_in_range }), t('tt.sim.res.sos2', { aw: w.affected_arrived, an: n.affected_arrived, n: w.affected })]; }
  if (kind === 'mesh') return [t('tt.sim.res.mesh', { pct: (100 * r.delivery_ratio).toFixed(1), d: r.delay_s ? r.delay_s.toFixed(0) : '–', c: r.copies?.toFixed(2) })];
  return [t('tt.sim.res.sig', { fa: r.fixed?.travel_time_s, ra: r.rl?.travel_time_s, fq: r.fixed?.queue_at_signals, rq: r.rl?.queue_at_signals, fh: r.fixed?.total_vehicle_hours, rh: r.rl?.total_vehicle_hours })];
}
</script>

<style lang="scss">
.tt-sim { margin-top: 6px; }
.tt-chip-sim { background: #fff1e6 !important; color: #b2490e !important; }
.tt-sim-sheet { max-height: 70vh; overflow-y: auto; }
.tt-sim-form { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; padding: 8px 16px; align-items: center; }
.tt-sim-thesis { font-size: 12px; opacity: 0.75; padding: 0 16px 6px; }
.tt-sim-live { padding: 4px 16px; }
.tt-sim-counts { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; margin: 4px 0; }
.tt-sim-sheet .tt-fc-card { margin: 6px 16px 16px; }
</style>
