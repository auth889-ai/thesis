/**
 * REFERENCES — every paper, dataset, standard, tool and service the code uses, grouped by
 * contribution, with the files that use it. Read from /api/references (docs/references.json);
 * nothing is typed in here.
 */
import {api} from "../services/api.js";

const TYPE = {paper: "paper", dataset: "dataset", standard: "standard", software: "software", api: "service", report: "report", book: "book"};

export class ReferencesPage extends HTMLElement {
  connectedCallback() { this.innerHTML = `<div class="panel-loading">Loading the references…</div>`; this.load(); }

  async load() {
    let R;
    try { R = await api.references(); } catch (e) { this.innerHTML = `<div class="note warn">References unavailable: ${e.message}</div>`; return; }
    const ident = (it) => [it.doi ? `<a href="https://doi.org/${it.doi}" target="_blank" rel="noopener">doi:${it.doi}</a>` : "", it.data_doi ? `<a href="https://doi.org/${it.data_doi}" target="_blank" rel="noopener">data doi:${it.data_doi}</a>` : "",
                           it.url && !it.doi ? `<a href="${it.url}" target="_blank" rel="noopener">${it.url.replace(/^https?:\/\//, "")}</a>` : ""].filter(Boolean).join(" · ");
    this.innerHTML = `
      <div class="rf-head">
        <p>${R.count} references, grouped by the three contributions of the project. Each entry names the files that use it, so every citation is traceable to code. Source: <code>${R.source}</code>; the same list is exported as <code>docs/REFERENCES.md</code>.</p>
        <nav class="rf-toc">${R.groups.map(g => `<a href="#references" data-jump="${g.id}">${g.title}</a>`).join("")}</nav>
      </div>
      ${R.groups.map(g => `
        <section class="rf-group" id="rf-${g.id}">
          <h3>${g.title}</h3>
          <ol class="rf-list">
            ${g.items.map(it => `
              <li class="rf-item ${it.context_only ? "ctx" : ""}">
                <div class="rf-title"><span class="rf-type">${TYPE[it.type] || it.type}</span> ${it.title}</div>
                <div class="rf-meta">${it.authors || ""}${it.venue ? ` · <i>${it.venue}</i>` : ""}${it.year ? ` · ${it.year}` : ""}${ident(it) ? ` · ${ident(it)}` : ""}</div>
                <div class="rf-use"><b>Used for:</b> ${it.used_for}${it.context_only ? ` <span class="pill warn">context only</span>` : ""}</div>
                ${it.code ? `<div class="rf-use"><b>Code:</b> ${it.code}</div>` : ""}
                <div class="rf-files">${(it.files || []).map(f => `<code>${f}</code>`).join(" ")}</div>
              </li>`).join("")}
          </ol>
        </section>`).join("")}`;
    this.querySelectorAll("[data-jump]").forEach(a => a.addEventListener("click", (e) => { e.preventDefault(); this.querySelector(`#rf-${a.dataset.jump}`)?.scrollIntoView({behavior: "smooth", block: "start"}); }));
  }
}
customElements.define("references-page", ReferencesPage);
