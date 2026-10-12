<template>
  <!-- TrafficTwin addition: Start on Headway's directions, our turn-by-turn on the chosen route -->
  <div v-if="!trip.active" class="tt-start">
    <q-btn
      data-tt="start"
      unelevated
      rounded
      color="primary"
      icon="navigation"
      :label="$t('tt.start')"
      :loading="trip.starting"
      :disable="!toPlace || trip.starting"
      @click="go(false)"
    />
    <q-btn
      data-tt="start-sim"
      flat
      dense
      no-caps
      size="sm"
      :label="$t('tt.try_simulated')"
      :disable="!toPlace || trip.starting"
      @click="go(true)"
    >
      <q-badge class="q-ml-xs" color="blue-grey-6">{{ $t('tt.simulated') }}</q-badge>
    </q-btn>
    <div v-if="trip.starting" class="text-caption">{{ $t('tt.starting') }}</div>
    <div v-if="trip.error" class="text-negative text-caption">
      {{ trip.error === 'no_city' ? $t('tt.no_city') : trip.error }}
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from 'vue';
import Place from 'src/models/Place';
import { map } from 'src/components/BaseMap.vue';
import { trip, startTrip, ourLang } from './tt';

export default defineComponent({
  name: 'TtStart',
  props: {
    fromPlace: { type: Object as PropType<Place>, required: false, default: undefined },
    toPlace: { type: Object as PropType<Place>, required: false, default: undefined },
    mode: { type: String, required: true },
    tripIndex: { type: Number, default: 0 },
  },
  setup() {
    return { trip };
  },
  methods: {
    async go(simulated: boolean) {
      if (!this.toPlace) return;
      const from = this.fromPlace?.point ?? map?.getCenter();
      if (!from) return;
      await startTrip({
        origin: { lat: from.lat, lon: from.lng },
        destination: { lat: this.toPlace.point.lat, lon: this.toPlace.point.lng },
        mode: this.mode,
        routeIndex: Math.max(0, this.tripIndex),
        simulated,
        lang: ourLang(this.$i18n.locale),
      });
    },
  },
});
</script>

<style lang="scss">
.tt-start {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
}
</style>
