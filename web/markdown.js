// Rendu Markdown minimal pour les remarks ECMAXML (US-033).
//
// Ne vise pas CommonMark complet : seulement les constructions réellement
// observées dans le corpus dotnet-api-docs (titres, paragraphes, listes,
// tableaux, blockquotes `[!NOTE]`, code inline, et les extensions DocFX
// `<xref:...>` / `[!INCLUDE[...]]`, qui ne sont ni du HTML ni du Markdown
// standard et doivent être neutralisées avant tout rendu).
//
// La section "## Examples" est retirée : elle est gérée séparément par
// l'appelant (example_code / lien vers la doc, cf. US-014 et US-033).

const ADMONITION_LABELS = {
  NOTE: "Remarque",
  TIP: "Astuce",
  IMPORTANT: "Important",
  WARNING: "Avertissement",
  CAUTION: "Attention",
};

export function renderRemarksMarkdown(markdown) {
  const withoutExamples = stripExamplesSection(markdown);
  const withoutOwnHeading = stripLeadingRemarksHeading(withoutExamples);
  const preprocessed = preprocessDocfxExtensions(withoutOwnHeading);
  return blocksToHtml(preprocessed);
}

function stripExamplesSection(markdown) {
  const match = markdown.match(/^##\s*Examples\s*$/im);
  return match ? markdown.slice(0, match.index) : markdown;
}

// L'ECMAXML fait toujours précéder ses remarks d'un "## Remarks" en tout
// début de contenu — déjà représenté par notre propre titre "Remarques"
// côté appelant, donc retiré ici pour éviter le doublon.
function stripLeadingRemarksHeading(markdown) {
  const match = markdown.match(/^\s*##\s*Remarks\s*$/m);
  if (match && match.index !== undefined && markdown.slice(0, match.index).trim() === "") {
    return markdown.slice(match.index + match[0].length);
  }
  return markdown;
}

function preprocessDocfxExtensions(markdown) {
  return markdown
    .replace(/\[!INCLUDE\[[^\]]*\]\([^)]*\)\]/g, "")
    // Inclusion de code (US-014) : parfois présente hors de toute section
    // "## Examples" formelle — jamais résolvable côté client, à retirer
    // partout où elle apparaît (legacy [!code-xxx[...]] et :::code...:::).
    .replace(/\[!code-[a-zA-Z]+\[[^\]]*\]\([^)]*\)\]/g, "")
    .replace(/:::code\b[^\n]*:::/g, "")
    .replace(/<xref:([^?>]+)(?:\?[^>]*)?>/g, (_, target) => xrefLabel(target))
    .replace(
      /^(\s*>\s*)\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$/gim,
      (_, prefix, kind) => `${prefix}**${ADMONITION_LABELS[kind] ?? kind}**`
    );
}

function xrefLabel(target) {
  return target.split("(")[0].split(".").pop();
}

function blocksToHtml(markdown) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const htmlBlocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === "") {
      i++;
      continue;
    }

    const heading = line.match(/^(#{2,4})\s+(.*)$/);
    if (heading) {
      const level = heading[1].length;
      htmlBlocks.push(`<h${level}>${inlineToHtml(heading[2])}</h${level}>`);
      i++;
      continue;
    }

    if (isTableStart(lines, i)) {
      const table = parseTable(lines, i);
      htmlBlocks.push(table.html);
      i = table.next;
      continue;
    }

    if (/^\s*>/.test(line)) {
      const quote = parseBlockquote(lines, i);
      htmlBlocks.push(quote.html);
      i = quote.next;
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const list = parseList(lines, i, /^\s*[-*]\s+/, "ul");
      htmlBlocks.push(list.html);
      i = list.next;
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const list = parseList(lines, i, /^\s*\d+\.\s+/, "ol");
      htmlBlocks.push(list.html);
      i = list.next;
      continue;
    }

    const paragraphLines = [];
    while (i < lines.length && lines[i].trim() !== "" && !isBlockStart(lines, i)) {
      paragraphLines.push(lines[i]);
      i++;
    }
    const paragraphHtml = inlineToHtml(paragraphLines.join(" ")).trim();
    // Une ligne réduite à une inclusion retirée (:::code...:::) ne laisse
    // qu'un paragraphe vide après nettoyage — on ne l'affiche pas.
    if (paragraphHtml) {
      htmlBlocks.push(`<p>${paragraphHtml}</p>`);
    }
  }

  return htmlBlocks.join("\n");
}

function isBlockStart(lines, i) {
  const line = lines[i];
  return (
    /^#{2,4}\s+/.test(line) ||
    /^\s*>/.test(line) ||
    /^\s*[-*]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    isTableStart(lines, i)
  );
}

function isTableStart(lines, i) {
  return (
    /^\|.*\|\s*$/.test(lines[i]) &&
    i + 1 < lines.length &&
    /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(lines[i + 1])
  );
}

function parseTable(lines, start) {
  const headerCells = splitTableRow(lines[start]);
  let i = start + 2; // saute l'en-tête et la ligne de séparation `|---|---|`
  const bodyRows = [];
  while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
    bodyRows.push(splitTableRow(lines[i]));
    i++;
  }

  const thead = `<tr>${headerCells.map((c) => `<th>${inlineToHtml(c)}</th>`).join("")}</tr>`;
  const tbody = bodyRows
    .map((row) => `<tr>${row.map((c) => `<td>${inlineToHtml(c)}</td>`).join("")}</tr>`)
    .join("");
  return { html: `<table>${thead}${tbody}</table>`, next: i };
}

function splitTableRow(line) {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function parseBlockquote(lines, start) {
  const quoteLines = [];
  let i = start;
  while (i < lines.length && /^\s*>/.test(lines[i])) {
    quoteLines.push(lines[i].replace(/^\s*>\s?/, ""));
    i++;
  }
  return { html: `<blockquote>${blocksToHtml(quoteLines.join("\n"))}</blockquote>`, next: i };
}

function parseList(lines, start, itemPattern, tag) {
  const items = [];
  let i = start;
  while (i < lines.length && itemPattern.test(lines[i])) {
    items.push(lines[i].replace(itemPattern, ""));
    i++;
  }
  const inner = items.map((item) => `<li>${inlineToHtml(item)}</li>`).join("");
  return { html: `<${tag}>${inner}</${tag}>`, next: i };
}

// Marqueur peu susceptible d'apparaître dans du texte réel, pour protéger
// le contenu des spans de code inline pendant le traitement gras/italique/liens.
const CODE_PLACEHOLDER = "CODE";
const CODE_PLACEHOLDER_RE = new RegExp(`${CODE_PLACEHOLDER}(\\d+)`, "g");

function inlineToHtml(text) {
  const codeSpans = [];
  let working = escapeHtml(text).replace(/`([^`]+)`/g, (_, code) => {
    codeSpans.push(code);
    return `${CODE_PLACEHOLDER}${codeSpans.length - 1}`;
  });

  working = working
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  return working.replace(CODE_PLACEHOLDER_RE, (_, idx) => `<code>${codeSpans[idx]}</code>`);
}

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
