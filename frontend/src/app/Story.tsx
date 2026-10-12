import {useEffect} from "react";
import {useLocation, useNavigate} from "react-router-dom";

import {Button} from "@/components/ui";
import {useT} from "@/i18n";
import {back, next, setStep, STORY, useStory} from "./storySteps";

/** The walk's panel: title, two sentences, Back / Next / End. It opens the step's page and outlines the step's element. */
export function Story() {
  const t = useT();
  const i = useStory();
  const nav = useNavigate();
  const {pathname} = useLocation();
  const step = i == null ? null : STORY[i];
  useEffect(() => {                                   // the step's page, then its element outlined and scrolled into view
    if (!step) return;
    if (pathname !== step.route) { nav(step.route); return; }
    if (!step.target) return;
    let el: HTMLElement | null = null, tries = 0;
    const timer = window.setInterval(() => {                       // the page may still be loading its data; look for the element for a few seconds
      el = document.querySelector<HTMLElement>(`[data-story="${step.target}"]`);
      if (el || ++tries > 25) { window.clearInterval(timer); el?.classList.add("story-target"); el?.scrollIntoView({behavior: "smooth", block: "center"}); }
    }, 200);
    return () => { window.clearInterval(timer); el?.classList.remove("story-target"); };
  }, [step, pathname, nav]);
  useEffect(() => {
    if (i == null) return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setStep(next(i)); else if (e.key === "ArrowLeft") setStep(back(i)); else if (e.key === "Escape") setStep(null);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [i]);
  if (i == null || !step) return null;
  return (
    <aside className="story" role="dialog" aria-label={t("story.title")}>
      <div className="story-head"><b>{t("story.title")}</b><span className="muted small">{t("story.step", {i: i + 1, n: STORY.length})}</span></div>
      <h3>{t(`story.${step.key}.title`)}</h3>
      <p>{t(`story.${step.key}.text`)}</p>
      <div className="row">
        <Button kind="ghost" onClick={() => setStep(back(i))} disabled={i === 0}>{t("story.back")}</Button>
        {next(i) != null ? <Button onClick={() => setStep(next(i))}>{t("story.next")}</Button> : <Button onClick={() => setStep(null)}>{t("story.done")}</Button>}
        <Button kind="ghost" onClick={() => setStep(null)}>{t("story.end")}</Button>
      </div>
    </aside>
  );
}

/** The button that starts the walk; `?tour=1` in the address starts it too (the link for the defense). */
export function StoryStart() {
  const t = useT();
  const {search} = useLocation();
  const i = useStory();
  useEffect(() => { if (new URLSearchParams(search).get("tour") === "1" && i == null) setStep(0); }, [search]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (i != null) return null;
  return <button type="button" className="btn ghost small story-start" onClick={() => setStep(0)}>{t("story.start")}</button>;
}
