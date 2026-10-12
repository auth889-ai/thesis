import enUS from './en-US';
import es from './es';
// TrafficTwin change: Bangla, and the map app's own strings under `tt` (adding a language = one folder with index.ts and tt.ts)
import bn from './bn';
import enTT from './en-US/tt';
import bnTT from './bn/tt';

export default {
  'en-US': { ...enUS, tt: enTT },
  es: { ...es, tt: enTT },
  bn: { ...bn, tt: bnTT },
};
