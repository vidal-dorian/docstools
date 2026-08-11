// Panneau de résultats (US-030) et sélecteur de version persistant (US-031).
// Voir docs/specification.md, section 7 — pas de framework, page statique.

const DEBOUNCE_MS = 300;
const SEARCH_ENDPOINT = "/api/search";
const VERSIONS_ENDPOINT = "/api/versions";
const SUMMARY_MAX_LENGTH = 140;
const VERSION_STORAGE_KEY = "docstools:version";

const input = document.getElementById("search-input");
const versionSelect = document.getElementById("version-select");
const resultsEl = document.getElementById("results");

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

  li.appendChild(heading);

  const summary = document.createElement("p");
  summary.className = "result-summary";
  summary.textContent = truncate(result.summary, SUMMARY_MAX_LENGTH);
  li.appendChild(summary);

  const overloadCount = document.createElement("span");
  overloadCount.className = "result-overload-count";
  overloadCount.textContent =
    result.overload_count === 1 ? "1 surcharge" : `${result.overload_count} surcharges`;
  li.appendChild(overloadCount);

  return li;
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
