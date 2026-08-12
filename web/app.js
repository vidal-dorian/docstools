// Panneau de résultats (US-030), sélecteur de version persistant (US-031)
// et panneau de détail avec remarks/exemple (US-032, US-033).
// Voir docs/specification.md, section 7 — pas de framework, page statique.

import { renderRemarksMarkdown } from "./markdown.js";
import { highlightCSharp } from "./highlight.js";

const DEBOUNCE_MS = 300;
const SEARCH_ENDPOINT = "/api/search";
const VERSIONS_ENDPOINT = "/api/versions";
const GROUP_ENDPOINT = "/api/group";
const SUMMARY_MAX_LENGTH = 140;
const VERSION_STORAGE_KEY = "docstools:version";

const input = document.getElementById("search-input");
const versionSelect = document.getElementById("version-select");
const resultsEl = document.getElementById("results");
const detailEl = document.getElementById("detail");

let debounceTimer = null;
let activeController = null;

init();

async function init() {
  await loadVersions();
  restoreSelectedVersion();
}

async function loadVersions() {
  let response;
  try {
    response = await fetch(VERSIONS_ENDPOINT);
  } catch {
    return; // Le sélecteur reste sur "Toutes les versions" si l'appel échoue.
  }
  if (!response.ok) return;

  const versions = await response.json();
  for (const version of versions) {
    const option = document.createElement("option");
    option.value = version.moniker;
    option.textContent = version.label;
    versionSelect.appendChild(option);
  }
}

function restoreSelectedVersion() {
  const stored = localStorage.getItem(VERSION_STORAGE_KEY);
  if (!stored) return;

  // N'affecte le select que si l'option existe (liste de versions chargée).
  const hasOption = Array.from(versionSelect.options).some((o) => o.value === stored);
  if (hasOption) {
    versionSelect.value = stored;
  }
}

input.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const query = input.value.trim();

  if (!query) {
    activeController?.abort();
    renderResults([]);
    return;
  }

  debounceTimer = setTimeout(() => runSearch(query), DEBOUNCE_MS);
});

versionSelect.addEventListener("change", () => {
  localStorage.setItem(VERSION_STORAGE_KEY, versionSelect.value);

  const query = input.value.trim();
  if (query) {
    clearTimeout(debounceTimer);
    runSearch(query); // changement délibéré : recherche immédiate, pas de debounce
  }
});

async function runSearch(query) {
  activeController?.abort();
  activeController = new AbortController();

  const body = { q: query };
  if (versionSelect.value) {
    body.version = versionSelect.value;
  }

  let response;
  try {
    response = await fetch(SEARCH_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: activeController.signal,
    });
  } catch (error) {
    if (error.name === "AbortError") return;
    renderError();
    return;
  }

  if (!response.ok) {
    renderError();
    return;
  }

  const data = await response.json();
  renderResults(data.results);
}

function renderResults(results) {
  resultsEl.replaceChildren();
  for (const result of results) {
    resultsEl.appendChild(renderResultRow(result));
  }
}

function renderResultRow(result) {
  const li = document.createElement("li");
  li.className = "result";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "result-button";
  button.addEventListener("click", () => loadGroupDetail(result.group_id));

  const heading = document.createElement("div");
  heading.className = "result-heading";

  const title = document.createElement("span");
  title.className = "result-title";
  title.textContent = `${result.type}.${result.name}`;
  heading.appendChild(title);

  if (result.version_confidence === "unknown") {
    const badge = document.createElement("span");
    badge.className = "badge badge-unknown";
    badge.textContent = "version non vérifiée";
    heading.appendChild(badge);
  }

  button.appendChild(heading);

  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = truncate(result.summary, SUMMARY_MAX_LENGTH);
  button.appendChild(summary);

  const overloadCount = document.createElement("span");
  overloadCount.className = "result-overload-count";
  overloadCount.textContent =
    result.overload_count === 1 ? "1 surcharge" : `${result.overload_count} surcharges`;
  button.appendChild(overloadCount);

  li.appendChild(button);
  return li;
}

async function loadGroupDetail(groupId) {
  renderDetailLoading();

  let response;
  try {
    response = await fetch(`${GROUP_ENDPOINT}/${groupId}`);
  } catch {
    renderDetailError();
    return;
  }

  if (!response.ok) {
    renderDetailError();
    return;
  }

  const group = await response.json();
  renderDetail(group);
}

function renderDetail(group) {
  detailEl.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = `${group.type}.${group.name}`;
  detailEl.appendChild(heading);

  const docLink = document.createElement("a");
  docLink.href = group.doc_url;
  docLink.target = "_blank";
  docLink.rel = "noopener noreferrer";
  docLink.className = "detail-doc-link";
  docLink.textContent = "Voir sur learn.microsoft.com";
  detailEl.appendChild(docLink);

  for (const overload of group.overloads) {
    detailEl.appendChild(renderOverload(overload));
  }
}

function renderOverload(overload) {
  const article = document.createElement("article");
  article.className = "overload";

  const signature = document.createElement("pre");
  signature.className = "overload-signature";
  // highlightCSharp() échappe tout le texte source avant de générer ses
  // propres balises : pas de contenu utilisateur non maîtrisé ici.
  signature.innerHTML = highlightCSharp(overload.signature);
  article.appendChild(signature);

  if (overload.params.length > 0) {
    const paramsHeading = document.createElement("h3");
    paramsHeading.textContent = "Paramètres";
    article.appendChild(paramsHeading);

    const paramsList = document.createElement("dl");
    paramsList.className = "overload-params";
    for (const param of overload.params) {
      const dt = document.createElement("dt");
      dt.textContent = `${param.name} — ${param.type}`;
      const dd = document.createElement("dd");
      dd.textContent = param.doc;
      paramsList.appendChild(dt);
      paramsList.appendChild(dd);
    }
    article.appendChild(paramsList);
  }

  if (overload.return_type) {
    const returnsHeading = document.createElement("h3");
    returnsHeading.textContent = "Retour";
    article.appendChild(returnsHeading);

    const returns = document.createElement("p");
    returns.textContent = overload.returns_doc
      ? `${overload.return_type} — ${overload.returns_doc}`
      : overload.return_type;
    article.appendChild(returns);
  }

  if (overload.exceptions.length > 0) {
    const exceptionsHeading = document.createElement("h3");
    exceptionsHeading.textContent = "Exceptions";
    article.appendChild(exceptionsHeading);

    const exceptionsList = document.createElement("ul");
    exceptionsList.className = "overload-exceptions";
    for (const exception of overload.exceptions) {
      const li = document.createElement("li");
      li.textContent = `${exception.type} — ${exception.doc}`;
      exceptionsList.appendChild(li);
    }
    article.appendChild(exceptionsList);
  }

  const remarksHtml = overload.remarks_md ? renderRemarksMarkdown(overload.remarks_md).trim() : "";
  if (remarksHtml) {
    const remarksHeading = document.createElement("h3");
    remarksHeading.textContent = "Remarques";
    article.appendChild(remarksHeading);

    const remarksEl = document.createElement("div");
    remarksEl.className = "overload-remarks";
    // renderRemarksMarkdown() échappe tout le texte source avant de générer
    // ses propres balises : pas de contenu utilisateur non maîtrisé ici.
    remarksEl.innerHTML = remarksHtml;
    article.appendChild(remarksEl);
  }

  const exampleHeading = document.createElement("h3");
  exampleHeading.textContent = "Exemple";
  article.appendChild(exampleHeading);
  if (overload.example_code) {
    const example = document.createElement("pre");
    example.className = "overload-example";
    // highlightCSharp() échappe tout le texte source avant de générer ses
    // propres balises : pas de contenu utilisateur non maîtrisé ici.
    example.innerHTML = highlightCSharp(overload.example_code);
    article.appendChild(example);
  } else {
    // Aucun exemple inline disponible (US-014) : un lien remplace la
    // section plutôt que de l'afficher vide.
    const link = document.createElement("a");
    link.href = overload.doc_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Voir un exemple sur learn.microsoft.com";
    article.appendChild(link);
  }

  if (overload.versions.length > 0) {
    const versionsHeading = document.createElement("h3");
    versionsHeading.textContent = "Disponibilité par version";
    article.appendChild(versionsHeading);
    article.appendChild(renderVersionTable(overload.versions));
  }

  return article;
}

function renderVersionTable(versions) {
  const table = document.createElement("table");
  table.className = "overload-versions";

  const headRow = document.createElement("tr");
  for (const label of ["Version", "Statut"]) {
    const th = document.createElement("th");
    th.textContent = label;
    headRow.appendChild(th);
  }
  table.appendChild(headRow);

  for (const version of versions) {
    const row = document.createElement("tr");
    const label = document.createElement("td");
    label.textContent = version.label;
    const status = document.createElement("td");
    status.textContent = version.status;
    row.appendChild(label);
    row.appendChild(status);
    table.appendChild(row);
  }

  return table;
}

function renderDetailLoading() {
  detailEl.replaceChildren();
  const p = document.createElement("p");
  p.className = "detail-placeholder";
  p.textContent = "Chargement…";
  detailEl.appendChild(p);
}

function renderDetailError() {
  detailEl.replaceChildren();
  const p = document.createElement("p");
  p.className = "detail-placeholder detail-error";
  p.textContent = "Impossible de charger le détail. Réessayez.";
  detailEl.appendChild(p);
}

function truncate(text, maxLength) {
  if (!text || text.length <= maxLength) return text || "";
  return `${text.slice(0, maxLength - 1).trimEnd()}…`;
}

function renderError() {
  resultsEl.replaceChildren();
  const li = document.createElement("li");
  li.className = "result-error";
  li.textContent = "La recherche a échoué. Réessayez.";
  resultsEl.appendChild(li);
}
