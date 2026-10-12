<template>
  <!-- TrafficTwin addition: the menu as a side drawer — our name, our pages grouped, and Headway's attributions -->
  <q-btn flat round dense icon="menu" class="tt-menu-btn" data-tt="menu" :aria-label="$t('tt.menu.open')" @click="open = true" />
  <q-dialog v-model="open" position="left" full-height>
    <q-card class="tt-drawer" data-tt="drawer">
      <div class="tt-drawer-head">
        <span class="tt-mark">TT</span>
        <div>
          <div class="tt-drawer-name">TrafficTwin</div>
          <div class="tt-drawer-sub">{{ $t('tt.menu.tagline') }}</div>
        </div>
      </div>
      <q-list>
        <template v-for="g in groups" :key="g.key">
          <q-item-label header class="tt-group">{{ $t(`tt.menu.group_${g.key}`) }}</q-item-label>
          <q-item v-for="m in g.items" :key="m.key" clickable :href="m.href" :data-tt="`menu-${m.key}`">
            <q-item-section avatar><q-icon :name="m.icon" /></q-item-section>
            <q-item-section>{{ $t(`tt.menu.${m.key}`) }}</q-item-section>
          </q-item>
        </template>
        <q-item clickable data-tt="menu-language" @click="toggleLanguage">
          <q-item-section avatar><q-icon name="translate" /></q-item-section>
          <q-item-section>{{ $t('tt.menu.language') }}</q-item-section>
        </q-item>
        <q-separator spaced />
        <q-item clickable to="/attributions" @click="open = false">
          <q-item-section avatar><q-icon name="favorite_border" /></q-item-section>
          <q-item-section>{{ $t('attributions') }}</q-item-section>
        </q-item>
      </q-list>
    </q-card>
  </q-dialog>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'TtMenu',
  data: () => ({
    open: false,
    groups: [
      { key: 'safety', items: [
        { key: 'emergency', icon: 'local_hospital', href: '/app/emergency' },
        { key: 'offline', icon: 'wifi_off', href: '/app/offline' },
      ] },
      { key: 'cities', items: [{ key: 'add_city', icon: 'add_location_alt', href: '/app/add-city' }] },
      { key: 'research', items: [
        { key: 'research_lab', icon: 'insights', href: '/app/lab/evidence' },
        { key: 'city3d', icon: 'view_in_ar', href: '/app/3d' },
        { key: 'simulations', icon: 'hub', href: '/app/lab/control-room' },
      ] },
      { key: 'settings', items: [{ key: 'settings', icon: 'settings', href: '/app/settings' }] },
    ],
  }),
  methods: {
    // one language setting for both apps (tt.lang), Bangla <-> English
    toggleLanguage() {
      const next = this.$i18n.locale.startsWith('bn') ? 'en' : 'bn';
      try {
        localStorage.setItem('tt.lang', next);
      } catch {
        /* this page only */
      }
      this.$i18n.locale = next === 'bn' ? 'bn' : 'en-US';
      document.documentElement.lang = next;
      this.open = false;
    },
  },
});
</script>

<style lang="scss">
.tt-drawer {
  width: 300px;
  max-width: 86vw;
  background: var(--tt-cream) !important;
  color: var(--tt-ink);
  border-radius: 0 22px 22px 0 !important;
}
.tt-drawer-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 18px 12px;
  .tt-mark {
    width: 42px;
    height: 42px;
    font-size: 15px;
    border-radius: 14px;
  }
}
.tt-drawer-name {
  font-family: var(--tt-display);
  font-weight: 700;
  font-size: 20px;
}
.tt-drawer-sub {
  font-size: 12.5px;
  color: var(--tt-ink-muted);
}
.tt-group {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--tt-ink-muted) !important;
  padding-top: 14px;
}
.tt-menu-btn {
  color: var(--tt-ink);
}
</style>
