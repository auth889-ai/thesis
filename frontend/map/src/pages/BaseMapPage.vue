<template>
  <div class="top-card">
    <search-box
      :tabindex="1"
      @did-select-place="searchBoxDidSelectPlace"
      @did-submit-search="
        (searchText) =>
          $router.push(`/search/${encodeURIComponent(searchText)}`)
      "
    >
      <!-- TrafficTwin change: our menu drawer (src/traffictwin/TtMenu.vue) in place of Headway's dropdown (its About and Contact pointed at maps.earth; Attributions is in the drawer) -->
      <tt-menu />
    </search-box>
    <!-- TrafficTwin change: nearest hospitals under the search -->
    <tt-hospitals />
    <!-- TrafficTwin change: the forecast layer (recorded traffic, forecast, best time to leave) -->
    <tt-forecast />
    <!-- TrafficTwin change: the thesis's simulations run from the map -->
    <tt-simulation />
  </div>
</template>

<script lang="ts">
import { getBaseMap } from 'src/components/BaseMap.vue';
import SearchBox from 'src/components/SearchBox.vue';
import TtHospitals from 'src/traffictwin/TtHospitals.vue'; // TrafficTwin change
import TtForecast from 'src/traffictwin/TtForecast.vue'; // TrafficTwin change
import TtSimulation from 'src/traffictwin/TtSimulation.vue'; // TrafficTwin change
import TtMenu from 'src/traffictwin/TtMenu.vue'; // TrafficTwin change
import Place from 'src/models/Place';
import Config from 'src/utils/Config';
import { defineComponent } from 'vue';

export default defineComponent({
  name: 'BaseMapPage',
  components: { SearchBox, TtHospitals, TtForecast, TtSimulation, TtMenu }, // TrafficTwin change: TtHospitals, TtForecast, TtSimulation, TtMenu
  data: function (): {
    aboutUrl?: string;
    aboutLinkText?: string;
    contactUrl?: string;
    contactLinkText?: string;
  } {
    return Config.shared;
  },
  mounted: function () {
    getBaseMap()?.removeAllMarkers();
  },
  methods: {
    searchBoxDidSelectPlace(place?: Place) {
      if (place) {
        this.$router.push(`/place/${place.urlEncodedId()}`);
      }
    },
  },
});
</script>

<style lang="scss">
// override some styles from the default layout.
.front-page {
  .top-card {
    @media screen and (max-width: 799px) {
      width: 100%;
      padding: 16px;
      border-bottom: solid #ccc 1px;
    }

    @media screen and (min-width: 800px) {
      z-index: 1;
      position: absolute;
      left: 0;
      width: calc(var(--left-panel-width) - 32px);
      margin: 16px;
      border: none;
      padding: 0;
      // q-card style
      box-shadow:
        0 1px 5px rgba(0, 0, 0, 0.2),
        0 2px 2px rgba(0, 0, 0, 0.14),
        0 3px 1px -2px rgba(0, 0, 0, 0.12);
      border-radius: 4px;
    }
  }

  .settings-button {
    padding-left: 12px;
    padding-right: 12px;
    // Only round the outer corners to make this button
    // feel like it's part of the text-input component
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
  }

  @media screen and (min-width: 800px) {
    #map {
      width: 100%;
      flex: 1;
    }
    #map:before {
      // hide left inner shadow from default layout.
      content: none;
    }
  }
}
</style>
