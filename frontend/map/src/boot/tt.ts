// TrafficTwin addition: the map app's service worker (public/sw.js): the offline shell and the trip pack; it also replaces the
// worker the React pages had at "/" before the map app. Not in development (Quasar's dev server).
// Boot files load as their own chunk, often after the page's load event has fired: register now in that case (waiting for
// 'load' alone meant the worker was never registered; found by the walkthrough video, 2026-10-09).
export const whenLoaded = (doc: Pick<Document, 'readyState'>, win: Pick<Window, 'addEventListener'>, fn: () => void) => {
  if (doc.readyState === 'complete') fn();
  else win.addEventListener('load', fn);
};

export default () => {
  if (process.env.PROD && 'serviceWorker' in navigator) {
    whenLoaded(document, window, () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => undefined);
      // the files this first visit loaded before the worker was in charge, so the app also reopens offline
      const send = () =>
        navigator.serviceWorker.ready
          .then((reg) => reg.active?.postMessage({ type: 'tt-store-loaded', urls: performance.getEntriesByType('resource').map((r) => r.name) }))
          .catch(() => undefined);
      void send();
      setTimeout(() => void send(), 10_000); // again for what loaded while the worker was taking over (map style, icon fonts)
    });
  }
};
