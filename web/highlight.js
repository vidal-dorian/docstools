// Coloration syntaxique C# minimale pour les signatures et exemples de code
// (US-035) : le corpus ECMAXML n'expose que du C#, pas besoin de détection
// de langage. Tokenizer par expressions régulières, pas de dépendance
// externe — cohérent avec le reste de web/ (page statique, sans build).

import { escapeHtml } from "./markdown.js";

const KEYWORDS = new Set(
  (
    "abstract as async await base bool break byte case catch char checked class const " +
    "continue decimal default delegate do double else enum event explicit extern false " +
    "finally fixed float for foreach goto if implicit in int interface internal is lock " +
    "long namespace new null object operator out override params private protected public " +
    "readonly record ref return sbyte sealed short sizeof stackalloc static string struct " +
    "switch this throw true try typeof uint ulong unchecked unsafe ushort using var virtual " +
    "void volatile while yield get set value nameof when where select from let orderby " +
    "group into on equals by ascending descending init required partial"
  ).split(" ")
);

// Ordre important : commentaires et chaînes avant les nombres/identifiants,
// pour qu'un `//` ou un guillemet à l'intérieur d'une chaîne ne soit jamais
// réinterprété comme un autre token.
const TOKEN_RE =
  /\/\/[^\n]*|\/\*[\s\S]*?\*\/|@"(?:[^"]|"")*"|\$@"(?:[^"]|"")*"|\$"(?:[^"\\]|\\.)*"|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\b\d+(?:\.\d+)?[fFdDmMuUlL]?\b|\b[A-Za-z_][A-Za-z0-9_]*\b/g;

export function highlightCSharp(code) {
  let html = "";
  let lastIndex = 0;
  TOKEN_RE.lastIndex = 0;
  let match;
  while ((match = TOKEN_RE.exec(code)) !== null) {
    html += escapeHtml(code.slice(lastIndex, match.index));
    html += renderToken(match[0]);
    lastIndex = TOKEN_RE.lastIndex;
  }
  html += escapeHtml(code.slice(lastIndex));
  return html;
}

function renderToken(token) {
  const category = classify(token);
  return category ? `<span class="tok-${category}">${escapeHtml(token)}</span>` : escapeHtml(token);
}

function classify(token) {
  if (token.startsWith("//") || token.startsWith("/*")) return "comment";
  if (token[0] === '"' || token[0] === "'" || token[0] === "@" || token[0] === "$") return "string";
  if (/^\d/.test(token)) return "number";
  if (KEYWORDS.has(token)) return "keyword";
  return null;
}
