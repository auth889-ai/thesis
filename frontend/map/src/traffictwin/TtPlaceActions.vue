<template>
  <!-- TrafficTwin addition: the place card's actions — category, Directions, Start (our turn-by-turn from here), Share -->
  <div class="tt-place-actions" data-tt="place-actions">
    <div v-if="category" class="tt-category" data-tt="category">{{ category }}</div>
    <div class="tt-actions-row">
      <q-btn class="tt-primary" unelevated color="primary" icon="directions" :label="$t('tt.directions')" data-tt="directions" @click="directions" />
      <q-btn class="tt-secondary" unelevated icon="navigation" :label="$t('tt.start')" :loading="trip.starting" data-tt="card-start" @click="start" />
      <q-btn class="tt-secondary" unelevated icon="share" :label="$t('tt.share')" data-tt="share" @click="share" />
    </div>
    <div v-if="note" class="tt-note">{{ note }}</div>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';
import Place from 'src/models/Place';
import { trip, startTrip, ourLang } from './tt';

const CATS = ['hospital', 'clinic', 'doctors', 'pharmacy', 'school', 'university', 'college', 'restaurant', 'cafe', 'bank', 'atm', 'bus_stop', 'bus_station',
  'place_of_worship', 'police', 'fire_station', 'fuel', 'marketplace', 'supermarket', 'hotel', 'park', 'station'];

export default defineComponent({
  name: 'TtPlaceActions',
  props: { place: { type: Object as PropType<Place>, required: true } },
  setup() {
    return { trip };
  },
  data: () => ({ category: '', note: '' }),
  watch: {
    place: { immediate: true, handler: 'loadCategory' },
  },
  methods: {
    async loadCategory() {
      this.category = '';
      const gid = this.place.id.gid;
      if (!gid) return;
      try {
        const r = await fetch(`/pelias/v1/place?ids=${encodeURIComponent(gid)}`);
        const p = (await r.json()).features?.[0]?.properties ?? {};
        const raw: string | undefined = p.category?.[0] ?? (p.addendum ? undefined : undefined);
        if (!raw) return;
        if (CATS.includes(raw)) this.category = this.$t(`tt.cat.${raw}`);
        else if (!this.$i18n.locale.startsWith('bn')) this.category = raw.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
      } catch {
        /* no category: the card shows none */
      }
    },
    here(): Promise<{ lat: number; lon: number } | null> {
      return new Promise((resolve) => {
        if (!navigator.geolocation) return resolve(null);
        navigator.geolocation.getCurrentPosition(
          (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
          () => resolve(null),
          { timeout: 4000, maximumAge: 120_000 },
        );
      });
    },
    async directions() {
      const me = await this.here();
      const from = me ? encodeURIComponent(`${me.lat},${me.lon}`) : '_';
      this.$router.push(`/directions/car/${this.place.urlEncodedId()}/${from}`);
    },
    async start() {
      this.note = '';
      const me = await this.here();
      if (!me) {
        this.note = this.$t('tt.start_needs_location');
        return this.directions();
      }
      await startTrip({
        origin: me,
        destination: { lat: this.place.point.lat, lon: this.place.point.lng },
        mode: 'car',
        routeIndex: 0,
        simulated: false,
        lang: ourLang(this.$i18n.locale),
      });
      if (trip.error === 'no_city') this.note = this.$t('tt.no_city');
    },
    async share() {
      const url = location.href;
      try {
        if (navigator.share) await navigator.share({ title: document.title, url });
        else {
          await navigator.clipboard.writeText(url);
          this.note = this.$t('tt.link_copied');
        }
      } catch {
        /* the person closed the share sheet */
      }
    },
  },
});
</script>

<style lang="scss">
.tt-place-actions {
  padding: 0 16px 8px;
}
.tt-category {
  color: var(--tt-ink-muted);
  font-size: 14px;
  margin: -8px 0 12px;
}
.tt-actions-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.tt-note {
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--tt-ink-muted);
}
</style>
