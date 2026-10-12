<template>
  <!-- TrafficTwin addition: the trip screen — Ferrostar's turn banner on top (its own), the map, and this one sheet with the crash SOS -->
  <div v-if="trip.active" class="tt-trip" data-tt="trip">
    <div class="tt-sheet">
      <q-btn
        data-tt="sos"
        class="tt-sos"
        round
        unelevated
        color="negative"
        size="lg"
        :label="$t('tt.sos')"
        @click="press"
      />
      <div v-if="trip.alerts.length" class="tt-alerts">
        <div v-for="a in trip.alerts" :key="a.id" class="tt-alert" :data-tt="`alert-${a.kind}`">
          <q-icon :name="a.kind === 'ambulance' ? 'emergency' : 'traffic'" size="18px" />
          <span class="tt-alert-text">{{ a.text }}</span>
          <q-badge rounded class="tt-tag">{{ $t(`tt.tag.${a.stamp}`) }}</q-badge>
          <a href="/app/lab/evidence">{{ $t('tt.how_we_know') }}</a>
        </div>
      </div>

      <div class="tt-head">
        <div>
          <div class="tt-eta" data-tt="eta">{{ eta }}</div>
          <div class="tt-sub" data-tt="progress">
            {{ progress }}
            <q-badge rounded :class="trip.simulated ? 'tt-tag' : 'tt-tag tt-live'">
              {{ trip.simulated ? $t('tt.simulated_speed', { x: 8 }) : $t('tt.live') }}
            </q-badge>
          </div>
        </div>
        <q-btn data-tt="end" round unelevated color="negative" icon="close" :aria-label="$t('tt.end')" @click="end">
          <q-tooltip>{{ $t('tt.end') }}</q-tooltip>
        </q-btn>
      </div>

      <div v-if="trip.done" class="tt-arrived"><q-icon name="flag" /> {{ $t('tt.arrived') }}</div>
      <div v-else-if="trip.lines.length" class="tt-line" data-tt="line" @click="showAll = !showAll">
        <q-icon name="record_voice_over" size="20px" />
        <span>{{ trip.lines[0] }}</span>
        <q-icon v-if="trip.lines.length > 1" :name="showAll ? 'expand_less' : 'expand_more'" />
      </div>
      <ul v-if="showAll && trip.lines.length > 1" class="tt-lines">
        <li v-for="(l, i) in trip.lines.slice(1)" :key="i">{{ l }}</li>
      </ul>

      <div class="tt-notes">
        <span v-if="trip.savedMb != null" data-tt="saved"><q-icon name="offline_pin" /> {{ $t('tt.saved_mb', { mb: fmt(trip.savedMb) }) }}</span>
        <span v-else-if="trip.saveFailed" data-tt="saved"><q-icon name="cloud_off" /> {{ $t('tt.saved_failed') }}</span>
        <span v-if="!trip.sos.supported && isPhone && trip.sos.sensor === 'off'" data-tt="sos-state"><q-icon name="sensors_off" /> {{ $t('tt.sos_needs_sensor') }}</span>
        <q-btn v-if="trip.sos.sensor !== 'granted'" dense outline no-caps color="primary" icon="vibration" :label="$t('tt.phoneSensor.use')" data-tt="phone-sensor" @click="sensor" />
        <span v-if="trip.sos.sensor === 'granted'" data-tt="live-g" class="tt-live-g"><q-icon name="vibration" /> {{ $t('tt.phoneSensor.live', { g: fmt2(trip.sos.liveG ?? 0) }) }}</span>
        <span v-if="trip.sos.sensor === 'denied' || trip.sos.sensor === 'unsupported' || trip.sos.sensor === 'insecure'" data-tt="sensor-state">{{ $t('tt.phoneSensor.' + trip.sos.sensor) }}</span>
      </div>
    </div>

    <q-dialog :model-value="trip.sos.phase === 'countdown' || trip.sos.sent" persistent>
      <q-card class="tt-sos-card" data-tt="sos-dialog">
        <template v-if="trip.sos.phase === 'countdown'">
          <q-circular-progress
            show-value
            :value="trip.sos.left"
            :min="0"
            :max="15"
            size="96px"
            :thickness="0.14"
            color="negative"
            track-color="red-1"
            class="tt-ring"
          >
            {{ fmt(trip.sos.left) }}
          </q-circular-progress>
          <div class="tt-sos-title">{{ $t('tt.sos_countdown', { s: fmt(trip.sos.left) }) }}</div>
          <q-badge rounded class="tt-test">{{ $t('tt.tag.TEST') }}</q-badge>
          <q-btn class="tt-primary full-width q-mt-md" unelevated color="primary" size="lg" :label="$t('tt.sos_cancel')" @click="cancel" />
        </template>
        <template v-else>
          <q-icon name="task_alt" size="48px" color="positive" />
          <div class="tt-sos-title">{{ $t('tt.sos_sent') }}</div>
          <q-badge rounded class="tt-test">{{ $t('tt.tag.TEST') }}</q-badge>
          <div v-if="trip.sos.local" class="tt-sos-local" data-tt="sos-local">{{ $t('tt.phoneSensor.local', { g: fmt2(trip.sos.joltG ?? 0) }) }}</div>
          <div class="tt-sos-numbers-title">{{ $t('tt.sos_numbers') }}</div>
          <div class="tt-numbers">
            <div v-for="(n, k) in trip.numbers" :key="k" class="tt-number">
              <span>{{ $te(`tt.kind.${k}`) ? $t(`tt.kind.${k}`) : k }}</span>
              <b>{{ n ? fmtDigits(n) : '–' }}</b>
            </div>
          </div>
          <q-btn class="tt-primary full-width q-mt-md" unelevated color="primary" :label="$t('tt.close')" @click="trip.sos.sent = false" />
        </template>
      </q-card>
    </q-dialog>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import { trip, endTrip, cancelSos, pressSos, usePhoneSensor } from './tt';
import { clockTime } from './ttPure';

export default defineComponent({
  name: 'TtTrip',
  setup() {
    return { trip };
  },
  data: () => ({ showAll: false, isPhone: window.matchMedia('(pointer: coarse)').matches }),
  computed: {
    bn(): boolean {
      return this.$i18n.locale.startsWith('bn');
    },
    eta(): string {
      if (!this.trip.leftS) return '';
      return clockTime(new Date(Date.now() + this.trip.leftS * 1000), this.bn ? 'bn' : 'en');
    },
    progress(): string {
      if (!this.trip.leftM && !this.trip.leftS) return '';
      return this.$t('tt.left_short', {
        km: this.fmt(Math.round(this.trip.leftM / 100) / 10),
        min: this.fmt(Math.max(1, Math.round(this.trip.leftS / 60))),
      });
    },
  },
  methods: {
    fmt(n: number): string {
      return n.toLocaleString(this.bn ? 'bn-BD' : 'en-US', { maximumFractionDigits: 1, useGrouping: false });
    },
    fmtDigits(s: string): string {
      return this.bn ? s.replace(/\d/g, (d) => '০১২৩৪৫৬৭৮৯'[Number(d)]!) : s;
    },
    end() {
      this.showAll = false;
      void endTrip();
    },
    cancel() {
      cancelSos();
    },
    press() {
      pressSos();
    },
    sensor() {
      void usePhoneSensor();                                   // the permission request happens inside this tap
    },
    fmt2(n: number): string {
      return n.toLocaleString(this.bn ? 'bn-BD' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });
    },
  },
});
</script>

<style lang="scss">
.tt-live-g { font-variant-numeric: tabular-nums; }
.tt-sos-local { font-size: 13px; margin-top: 6px; color: var(--tt-ink-muted); }
.tt-trip {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3000;
}
.tt-sheet {
  position: relative;
  background: var(--tt-cream);
  color: var(--tt-ink);
  border-radius: 22px 22px 0 0;
  box-shadow: 0 -10px 30px -12px rgba(74, 38, 32, 0.45);
  padding: 14px 18px calc(16px + env(safe-area-inset-bottom));
  animation: tt-sheet-in 0.25s ease-out;
  @media screen and (min-width: 800px) {
    max-width: 440px;
    margin: 0 0 16px 16px;
    border-radius: 22px;
  }
}
.tt-sheet::before {
  content: '';
  display: block;
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--tt-line);
  margin: -4px auto 10px;
}
.tt-sos {
  position: absolute !important;
  right: 16px;
  top: -76px;
  box-shadow: 0 8px 20px -6px rgba(168, 58, 47, 0.7);
  font-weight: 800;
}
.tt-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.tt-eta {
  font-family: var(--tt-display);
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
}
.tt-sub {
  color: var(--tt-ink-muted);
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.tt-tag {
  background: #5b6f8a !important;
  font-weight: 600;
  padding: 3px 8px;
}
.tt-tag.tt-live {
  background: #4f7a3a !important;
}
.tt-test {
  background: #b5731f !important;
  font-weight: 700;
  padding: 3px 10px;
}
.tt-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: var(--tt-cream-2);
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  span {
    flex: 1;
  }
}
.tt-lines {
  margin: 6px 0 0;
  padding-left: 40px;
  color: var(--tt-ink-muted);
}
.tt-arrived {
  margin-top: 12px;
  font-weight: 700;
  color: #4f7a3a;
}
.tt-notes {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12.5px;
  color: var(--tt-ink-muted);
}
.tt-alerts {
  margin-bottom: 10px;
}
.tt-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: #fff4e5;
  border-left: 4px solid #d0884f;
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 6px;
  font-size: 13px;
  color: #4a2620;
  .tt-alert-text {
    flex: 1 1 60%;
  }
}
.tt-sos-card {
  width: 340px;
  max-width: 92vw;
  border-radius: 22px !important;
  padding: 24px;
  text-align: center;
  background: var(--tt-cream) !important;
  color: var(--tt-ink);
}
.tt-ring {
  font-family: var(--tt-display);
  font-weight: 700;
  font-size: 28px;
}
.tt-sos-title {
  font-family: var(--tt-display);
  font-size: 19px;
  font-weight: 600;
  margin: 12px 0 8px;
}
.tt-sos-numbers-title {
  margin-top: 14px;
  font-size: 13px;
  color: var(--tt-ink-muted);
}
.tt-numbers {
  margin-top: 6px;
  display: grid;
  gap: 6px;
}
.tt-number {
  display: flex;
  justify-content: space-between;
  background: var(--tt-cream-2);
  border-radius: 12px;
  padding: 8px 12px;
  b {
    font-size: 18px;
  }
}
.tt-nav-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
</style>
