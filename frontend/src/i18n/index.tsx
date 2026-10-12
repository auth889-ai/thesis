import {createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode} from "react";

import {FALLBACK, MESSAGES, translate, type Translate} from "./core";
export {FALLBACK, LANGUAGES, MESSAGES, translate} from "./core";
export type {Translate, Vars} from "./core";
const STORE = "tt.lang";

const stored = (): string | null => { try { const v = localStorage.getItem(STORE); return v && v in MESSAGES ? v : null; } catch { return null; } };

type I18n = {lang: string; chosen: boolean; setLang: (lang: string, remember?: boolean) => void; t: Translate};
const Ctx = createContext<I18n>({lang: FALLBACK, chosen: false, setLang: () => undefined, t: (key, vars) => translate(FALLBACK, key, vars)});

/** `chosen` is true once the person picked a language themselves; until then a city may suggest its own. */
export function I18nProvider({children}: {children: ReactNode}) {
  const [lang, setState] = useState<string>(() => stored() ?? FALLBACK);
  const [chosen, setChosen] = useState<boolean>(() => stored() != null);
  const setLang = useCallback((next: string, remember = true) => {
    if (!(next in MESSAGES)) return;
    setState(next);
    if (remember) { setChosen(true); try { localStorage.setItem(STORE, next); } catch { /* private mode */ } }
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const value = useMemo<I18n>(() => ({lang, chosen, setLang, t: (key, vars) => translate(lang, key, vars)}), [lang, chosen, setLang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
export const useT = () => useContext(Ctx).t;
