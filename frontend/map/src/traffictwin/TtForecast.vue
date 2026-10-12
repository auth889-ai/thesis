<template>
  <!-- TrafficTwin addition: the forecast layer (GET /api/forecast-layer/{city}): recorded speeds, a model's forecast where it has one,
       its measured error in plain words, and "best time to leave" only where the API says the model has skill -->
  <div class="tt-forecast">
    <q-chip data-tt="forecast" clickable icon="speed" class="tt-chip-forecast" @click="toggle">{{ $t('tt.fc.chip') }}</q-chip>
  </div>
  <transition name="tt-slide">
    <div v-if="open" class="tt-hospital-sheet" data-tt="forecast-sheet">
      <div class="tt-sheet-head">
        <div class="tt-sheet-title">{{ $t('tt.fc.title') }}</div>
        <q-btn flat round dense icon="close" :aria-label="$t('tt.close')" @click="close" />
      </div>
      <q-linear-progress v-if="loading" indeterminate color="secondary" />
      <div v-else-if="!d || !d.available" class="tt-empty" data-tt="forecast-none">{{ $t('tt.fc.none') }}</div>
      <div v-else class="tt-fc-body">
        <q-btn-toggle v-if="views.length > 1" v-model="view" dense unelevated toggle-color="primary" :options="views.map((v) => ({ label: v === '0' ? $t('tt.fc.now') : $t('tt.fc.plus', { min: fmt(+v) }), value: v }))" @update:model-value="draw" />
        <p data-tt="forecast-label">
          <span v-if="d.kind === 'replay'">{{ $t('tt.fc.replay', { day: day(d.recorded_at), time: clock(d.recorded_at) }) }}</span>
          <span v-else>{{ $t('tt.fc.recorded_day') }}</span>
          <q-badge :color="view === '0' ? 'teal' : 'deep-purple'" class="q-ml-xs">{{ view === '0' ? $t('tt.fc.tag_recorded') : $t('tt.fc.tag_forecast') }}</q-badge>
        </p>
        <div class="tt-fc-small" data-tt="forecast-legend">{{ $t('tt.fc.legend') }}</div>
        <ul v-if="d.kind === 'recorded_day'" class="tt-fc-list">
          <li v-for="p in d.points" :key="p.id">{{ p.now == null ? $t('tt.fc.site_none', { site: p.id, day: day(p.day) }) : $t('tt.fc.site', { site: p.id, v: fmt(p.now), u: unit(), day: day(p.day) }) }}</li>
        </ul>
        <div class="tt-fc-card" data-tt="forecast-card">
          <div class="tt-sheet-sub">{{ $t('tt.fc.card') }}</div>
          <template v-if="d.kind === 'replay'">
            <div v-for="h in ['15', '30', '60']" :key="h">{{ $t('tt.fc.err', { min: fmt(+h), m: err(d.card.horizons[h].mae), p: err(d.card.horizons[h].no_change_mae), u: unit() }) }}</div>
            <div class="tt-fc-small">{{ $t('tt.fc.where_replay', { model: d.card.model, n: fmt(d.points.length) }) }}</div>
          </template>
          <template v-else>
            <div v-for="(c, site) in d.card.sites" :key="site">{{ $t('tt.fc.site_err', { site, m15: err(c['15'].mae), p15: err(c['15'].no_change_mae), m60: err(c['60'].mae), p60: err(c['60'].no_change_mae), u: unit() }) }}</div>
            <div class="tt-fc-small">{{ $t('tt.fc.where_day') }}</div>
          </template>
        </div>
        <p data-tt="forecast-best" class="tt-fc-best">
          <template v-if="d.best_time">{{ d.best_time.clear ? $t('tt.fc.best_in', { min: fmt(d.best_time.leave_in_min) }) : $t('tt.fc.best_now') }}</template>
          <template v-else>{{ (d as any).best_time_reason === 'few_sensors' ? $t('tt.fc.best_few') : $t('tt.fc.best_none') }}</template>
        </p>
        <a href="/app/lab/evidence" class="tt-howknow">{{ $t('tt.fc.how') }}</a>
      </div>
    </div>
  </transition>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { map } from 'src/components/BaseMap.vue';
import { cityAt } from './tt';
import { layerViews, speedColour } from './ttPure';

const SRC = 'tt-forecast';
type Pt = { id: string; lat: number; lon: number; now: number | null; day?: string; [h: string]: number | string | null | undefined };
type Layer = { available: boolean; kind: string; units: string; recorded_at?: string; points: Pt[]; horizons_min: number[];
  card: Record<string, any>; best_time: { leave_in_min: number; clear: boolean } | null }; // eslint-disable-line @typescript-eslint/no-explicit-any

export default defineComponent({
  name: 'TtForecast',
  data: () => ({ open: false, loading: false, d: null as Layer | null, view: '0' }),
  computed: {
    views(): string[] {
      return this.d?.available ? layerViews(this.d.kind, this.d.horizons_min ?? []) : ['0'];
    },
  },
  beforeUnmount() {
    this.clear();
  },
  methods: {
    loc(): string {
      return this.$i18n.locale.startsWith('bn') ? 'bn-BD' : 'en-US';
    },
    fmt(n: number): string {
      return Number(n).toLocaleString(this.loc(), { maximumFractionDigits: 1, useGrouping: false });
    },
    err(n: number): string {
      return Number(n).toLocaleString(this.loc(), { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });
    },
    unit(): string {
      return this.d?.units === 'mph' ? this.$t('tt.fc.mph') : this.$t('tt.fc.kmh');
    },
    day(iso?: string): string {
      return iso ? new Date(iso.slice(0, 10) + 'T12:00:00').toLocaleDateString(this.loc(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : '';
    },
    clock(iso?: string): string {
      return iso ? Number(iso.slice(11, 13)).toLocaleString(this.loc(), { minimumIntegerDigits: 2 }) + ':' + Number(iso.slice(14, 16)).toLocaleString(this.loc(), { minimumIntegerDigits: 2 }) : '';
    },
    clear() {
      if (!map) return;
      if (map.getLayer(SRC)) map.removeLayer(SRC);
      if (map.getSource(SRC)) map.removeSource(SRC);
    },
    draw() {
      if (!map || !this.d?.available) return;
      this.clear();
      const key = this.view === '0' ? 'now' : this.view;
      const vals = this.d.points.map((p) => p[key] as number | null | undefined).filter((v): v is number => v != null);
      const top = vals.length ? Math.max(...vals) : 0;
      const features = this.d.points.map((p) => ({ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [p.lon, p.lat] },
        properties: { c: speedColour(p[key] as number | null | undefined, top) } }));
      map.addSource(SRC, { type: 'geojson', data: { type: 'FeatureCollection', features } });
      map.addLayer({ id: SRC, type: 'circle', source: SRC, paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 3, 14, 8], 'circle-color': ['get', 'c'],
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1 } });
    },
    close() {
      this.open = false;
      this.clear();
    },
    async toggle() {
      if (this.open) return this.close();
      this.open = true;
      this.loading = true;
      this.view = '0';
      try {
        const c = map?.getCenter();
        const city = c ? await cityAt(c.lat, c.lng) : { available: false };
        if (!city.available || !city.city_id) {
          this.d = null;
          return;
        }
        const b = map!.getBounds();
        const r = await fetch(`/api/forecast-layer/${encodeURIComponent(city.city_id)}?bbox=${[b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(',')}`);
        this.d = r.ok ? await r.json() : null;
        this.draw();
      } finally {
        this.loading = false;
      }
    },
  },
});
</script>

<style lang="scss">
.tt-forecast { margin-top: 6px; }
.tt-chip-forecast { background: #e6f0ff !important; color: #1f4f9a !important; }
.tt-fc-body { padding: 4px 16px 16px; }
.tt-fc-list { margin: 4px 0 8px; padding-left: 18px; }
.tt-fc-card { background: #f6f7fb; border-radius: 10px; padding: 8px 12px; margin: 6px 0; font-size: 13px; }
.tt-fc-small { opacity: 0.65; font-size: 11px; margin-top: 4px; }
.tt-fc-best { font-weight: 600; margin: 8px 0 4px; }
.tt-howknow { font-size: 13px; }
</style>
