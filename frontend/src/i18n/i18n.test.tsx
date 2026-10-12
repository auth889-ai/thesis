import {fireEvent, render, screen} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {FALLBACK, I18nProvider, LANGUAGES, MESSAGES, translate, useI18n} from "./index";

const real = (lang: string) => Object.keys(MESSAGES[lang]).filter((k) => !k.startsWith("_")).sort();

function Probe() {
  const {t, lang, setLang} = useI18n();
  return <div><span data-testid="label">{t("nav.home.label")}</span><span data-testid="lang">{lang}</span>{LANGUAGES.map((l) => <button key={l} onClick={() => setLang(l)}>{l}</button>)}</div>;
}

describe("translations", () => {
  it("ships English and Bangla, discovered from the locale files", () => {
    expect(LANGUAGES).toEqual(expect.arrayContaining(["en", "bn"]));
    expect(LANGUAGES[0]).toBe(FALLBACK);
  });

  it("every language has exactly the keys English has, with the same placeholders", () => {
    const holes = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
    for (const lang of LANGUAGES) {
      expect(real(lang)).toEqual(real(FALLBACK));
      for (const k of real(lang)) expect([lang, k, holes(MESSAGES[lang][k])]).toEqual([lang, k, holes(MESSAGES[FALLBACK][k])]);
    }
  });

  it("fills placeholders, falls back to English, then to the key", () => {
    expect(translate("en", "city.plusMin", {n: 30})).toBe("+30 MIN");
    expect(translate("bn", "city.noData", {city: "বার্লিন"})).toContain("বার্লিন");
    expect(translate("xx", "nav.city3d.label")).toBe("3D City");
    expect(translate("en", "no.such.key")).toBe("no.such.key");
  });

  it("switching the language changes the text and the document language", () => {
    render(<I18nProvider><Probe /></I18nProvider>);
    expect(screen.getByTestId("label").textContent).toBe("Home");
    fireEvent.click(screen.getByText("bn"));
    expect(screen.getByTestId("label").textContent).toBe(MESSAGES.bn["nav.home.label"]);
    expect(document.documentElement.lang).toBe("bn");
  });

  it("every status the twin runtime can report has a word in every language", () => {
    for (const st of ["idle", "starting", "running", "paused", "done", "stopped", "failed"]) for (const lang of LANGUAGES) expect([lang, st, typeof MESSAGES[lang][`twin.state.${st}`]]).toEqual([lang, st, "string"]);
  });

  it("the Bangla file says it has not been reviewed", () => {
    expect(MESSAGES.bn._review).toMatch(/not yet reviewed/i);
  });
});
