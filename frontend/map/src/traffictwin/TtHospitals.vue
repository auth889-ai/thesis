<template>
  <!-- TrafficTwin addition: nearest hospitals as Headway places (each opens Headway's own card, with Directions), pinned on the map -->
  <div class="tt-hospitals">
    <q-chip data-tt="hospitals" clickable icon="local_hospital" class="tt-chip-hospital" @click="toggle">
      {{ $t('tt.hospitals') }}
    </q-chip>
  </div>
  <transition name="tt-slide">
    <div v-if="open" class="tt-hospital-sheet" data-tt="hospital-list">
      <div class="tt-sheet-head">
        <div>
          <div class="tt-sheet-title">{{ $t('tt.hospitals_title') }}</div>
          <div class="tt-sheet-sub">{{ fromMap ? $t('tt.hospitals_from_map') : $t('tt.hospitals_from_you') }}</div>
        </div>
        <q-btn flat round dense icon="close" :aria-label="$t('tt.close')" @click="close" />
      </div>
      <q-toggle v-model="live" dense :label="$t('tt.reach.live')" data-tt="reach-live-toggle" class="tt-reach-toggle" @update:model-value="liveChanged" />
      <div v-if="live" class="tt-sheet-sub tt-reach-hint">{{ $t('tt.reach.tap') }}</div>
      <div v-if="reach && !reach.available" class="tt-empty" data-tt="reach-live-failed">{{ $t('tt.reach.failed') }}</div>
      <div v-if="reach && reach.available" class="tt-reach-card" data-tt="reach-live">
        <div><b>{{ $t('tt.reach.computed', { s: fmt(reach.computed_s ?? 0) }) }}</b> <q-badge color="blue-8">{{ $t('tt.reach.badge') }}</q-badge></div>
        <div v-if="summary">{{ summary.minutes == null ? $t('tt.reach.noRoute', { name: summary.name }) : $t('tt.reach.nearestIn', { name: summary.name, min: fmt(summary.minutes) }) }}</div>
        <div class="tt-sheet-sub">{{ $t('tt.reach.legend') }} · {{ $t('tt.reach.speeds') }}</div>
        <div v-if="reach.thesis" class="tt-sheet-sub">{{ $t('tt.reach.thesis', { a: fmt(reach.thesis.map_pct['10'] ?? 0), b: fmt(reach.thesis.map_pct['20'] ?? 0), c: fmt(reach.thesis.map_pct['30'] ?? 0) }) }}</div>
      </div>
      <q-linear-progress v-if="loading" indeterminate color="secondary" />
      <div v-if="!loading && !items.length" class="tt-empty">{{ $t('tt.hospitals_none') }}</div>
      <q-list>
        <q-item v-for="(h, i) in items" :key="h.osm_id" clickable class="tt-hospital" @click="openPlace(h)">
          <q-item-section avatar>
            <div class="tt-pin-n">{{ fmt(i + 1) }}</div>
          </q-item-section>
          <q-item-section>
            <q-item-label class="tt-h-name">{{ h.name === 'Hospital (unnamed)' ? $t('tt.unnamed_hospital') : h.name.split(',')[0] }}</q-item-label>
            <q-item-label caption>
              {{ $t('tt.minutes_away', { min: fmt(Math.max(1, Math.round(h.time_s / 60))) }) }} · {{ km(h.distance_m) }}
            </q-item-label>
          </q-item-section>
          <q-item-section side><q-icon name="chevron_right" /></q-item-section>
        </q-item>
      </q-list>
    </div>
  </transition>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import * as maplibregl from 'maplibre-gl';
import { map } from 'src/components/BaseMap.vue';
import { cityAt } from './tt';
import { reachBounds, reachFeatures, reachSummary, type LiveReach } from './ttReach';

type Hospital = { osm_id: string; name: string; lat: number; lon: number; time_s: number; distance_m: number };
let pins: maplibregl.Marker[] = []; // the map's markers: not reactive state
let tapPin: maplibregl.Marker | null = null;
const REACH = 'tt-reach';
let onTap: ((e: maplibregl.MapMouseEvent) => void) | null = null;

export default defineComponent({
  name: 'TtHospitals',
  data: () => ({ open: false, loading: false, items: [] as Hospital[], fromMap: false, live: false, reach: null as LiveReach | null }),
  computed: { summary() { return this.reach ? reachSummary(this.reach) : null; } },
  beforeUnmount() {
    this.clearPins();
    this.liveChanged(false);
  },
  methods: {
    bn(): boolean {
      return this.$i18n.locale.startsWith('bn');
    },
    fmt(n: number): string {
      return n.toLocaleString(this.bn() ? 'bn-BD' : 'en-US', { maximumFractionDigits: 1, useGrouping: false });
    },
    km(m: number): string {
      return this.$t('tt.km', { km: this.fmt(Math.round(m / 100) / 10) });
    },
    here(): Promise<{ lat: number; lng: number; fromMap: boolean }> {
      return new Promise((resolve) => {
        const fallback = () => {
          const c = map?.getCenter();
          resolve({ lat: c?.lat ?? 0, lng: c?.lng ?? 0, fromMap: true });
        };
        if (!navigator.geolocation) return fallback();
        navigator.geolocation.getCurrentPosition(
          (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, fromMap: false }),
          fallback,
          { timeout: 5000, maximumAge: 60_000 },
        );
      });
    },
    clearPins() {
      for (const p of pins) p.remove();
      pins = [];
    },
    drawPins() {
      this.clearPins();
      if (!map || !this.items.length) return;
      const bounds = new maplibregl.LngLatBounds();
      this.items.forEach((h, i) => {
        const el = document.createElement('div');
        el.className = 'tt-map-pin';
        el.textContent = this.fmt(i + 1);
        el.onclick = () => this.openPlace(h);
        pins.push(new maplibregl.Marker({ element: el }).setLngLat([h.lon, h.lat]).addTo(map!));
        bounds.extend([h.lon, h.lat]);
      });
      map.fitBounds(bounds, { padding: { top: 120, bottom: 340, left: 40, right: 40 }, maxZoom: 15, duration: 600 });
    },
    close() {
      this.open = false;
      this.clearPins();
      this.liveChanged(false);
      this.live = false;
    },
    /** Live reach (step K, off by default): while on, a tap on the map asks the server for the nearest hospitals and their 10/20/30-minute
     *  polygons, computed now by the city's routing server (Valhalla isochrones), and draws them. Off: the layers and the handler go. */
    liveChanged(on: boolean) {
      if (!map) return;
      if (on && !onTap) {
        onTap = (e) => void this.tapped(e.lngLat.lat, e.lngLat.lng);
        map.on('click', onTap);
      }
      if (!on) {
        if (onTap) map.off('click', onTap);
        onTap = null;
        for (const id of [REACH + '-fill', REACH + '-line']) if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(REACH)) map.removeSource(REACH);
        tapPin?.remove(); tapPin = null;
        this.reach = null;
      }
    },
    async tapped(lat: number, lng: number) {
      if (!map) return;
      this.loading = true;
      try {
        const city = await cityAt(lat, lng);
        if (!city.available || !city.city_id) { this.reach = { available: false }; return; }
        const j: LiveReach = await fetch(`/api/emergency/reach/${encodeURIComponent(city.city_id)}/live?lat=${lat}&lon=${lng}&k=3`)
          .then((r) => (r.ok ? r.json() : { available: false })).catch(() => ({ available: false }));
        this.reach = j;
        if (!j.available || !j.hospitals) return;
        this.fromMap = true;
        this.items = j.hospitals.map((h) => ({ osm_id: h.osm_id, name: h.name, lat: h.lat, lon: h.lon, time_s: h.time_s, distance_m: h.distance_m }));
        this.drawPins();
        const features = reachFeatures(j.hospitals);
        const data = { type: 'FeatureCollection', features } as GeoJSON.FeatureCollection;
        const src = map.getSource(REACH) as { setData?: (d: unknown) => void } | undefined;
        if (src?.setData) src.setData(data);
        else {
          map.addSource(REACH, { type: 'geojson', data });
          map.addLayer({ id: REACH + '-fill', type: 'fill', source: REACH, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.28 } });
          map.addLayer({ id: REACH + '-line', type: 'line', source: REACH, paint: { 'line-color': ['get', 'color'], 'line-width': 1.5 } });
        }
        tapPin?.remove();
        tapPin = new maplibregl.Marker({ color: '#1f4e9c' }).setLngLat([lng, lat]).addTo(map);
        const b = reachBounds(features);
        if (b) map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: { top: 100, bottom: 340, left: 40, right: 40 }, maxZoom: 14, duration: 600 });
      } finally {
        this.loading = false;
      }
    },
    async toggle() {
      if (this.open) return this.close();
      this.open = true;
      this.loading = true;
      try {
        const p = await this.here();
        this.fromMap = p.fromMap;
        const city = await cityAt(p.lat, p.lng);
        if (!city.available || !city.city_id) {
          this.items = [];
          return;
        }
        const r = await fetch(`/api/emergency/reach/${encodeURIComponent(city.city_id)}/nearest?lat=${p.lat}&lon=${p.lng}&k=5`);
        const j = r.ok ? await r.json() : {};
        this.items = j.available ? j.nearest ?? [] : [];
        this.drawPins();
      } finally {
        this.loading = false;
      }
    },
    openPlace(h: Hospital) {
      this.close();
      this.$router.push(`/place/${encodeURIComponent(`openstreetmap:venue:${h.osm_id}`)}`);
    },
  },
});
</script>

<style lang="scss">
.tt-hospitals {
  margin-top: 10px;
}
.tt-chip-hospital {
  background: #fde8e4 !important;
  color: #a83a2f !important;
}
.tt-hospital-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  max-height: 46vh;
  overflow-y: auto;
  background: var(--tt-cream);
  color: var(--tt-ink);
  border-radius: 22px 22px 0 0;
  box-shadow: 0 -10px 30px -12px rgba(74, 38, 32, 0.45);
  padding: 10px 10px calc(10px + env(safe-area-inset-bottom));
  @media screen and (min-width: 800px) {
    left: 16px;
    right: auto;
    width: 400px;
    bottom: 16px;
    border-radius: 22px;
  }
}
.tt-sheet-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 6px 8px 8px 10px;
}
.tt-sheet-title {
  font-family: var(--tt-display);
  font-size: 19px;
  font-weight: 700;
}
.tt-sheet-sub {
  font-size: 12.5px;
  color: var(--tt-ink-muted);
}
.tt-reach-toggle { margin: 0 6px; }
.tt-reach-hint { padding: 0 12px 6px; }
.tt-reach-card { margin: 4px 10px 8px; padding: 8px 10px; border-radius: 12px; background: #e9f0fb; font-size: 13.5px; display: grid; gap: 3px; }
.tt-empty {
  padding: 12px;
  color: var(--tt-ink-muted);
}
.tt-h-name {
  font-weight: 600;
}
.tt-pin-n,
.tt-map-pin {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: #a83a2f;
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}
.tt-map-pin {
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  cursor: pointer;
}
.tt-slide-enter-active,
.tt-slide-leave-active {
  transition: transform 0.22s ease, opacity 0.22s ease;
}
.tt-slide-enter-from,
.tt-slide-leave-to {
  transform: translateY(30px);
  opacity: 0;
}
</style>
