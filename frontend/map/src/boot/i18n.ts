import { App } from 'vue';
import { createI18n } from 'vue-i18n';
import messages from '../i18n';

export default ({ app }: { app: App }) => {
  app.use(createI18nForApp());
};

export const createI18nForApp = () => {
  let locale;
  if (process.env.NODE_ENV == 'test') {
    locale = 'en-US';
  } else {
    // TrafficTwin change: the language the person chose in either app (shared on this origin), else the browser's
    let chosen: string | null = null;
    try { chosen = localStorage.getItem('tt.lang'); } catch { chosen = null; }
    locale = chosen === 'bn' ? 'bn' : chosen === 'en' ? 'en-US' : navigator.language.startsWith('bn') ? 'bn' : navigator.language;
  }
  return createI18n({
    locale,
    fallbackLocale: 'en-US',
    globalInjection: true,
    messages,
  });
};
