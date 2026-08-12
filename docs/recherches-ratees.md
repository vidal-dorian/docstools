# Journal des recherches sans bon résultat (US-040)

Cas réels où le classement BM25 (spec §5, étage 1) ne remonte pas le
résultat attendu en premier. Objectif : accumuler au moins 15 cas avant de
démarrer US-042 (rerank), pour mesurer objectivement une amélioration
plutôt que d'ajuster à l'aveugle sur quelques exemples.

Format : requête → attendu → obtenu → diagnostic.

## Cas consignés

1. **"remove month to date"** → `DateTime.AddMonths` (accepte un entier
   négatif) → ne remonte pas. Nécessite de comprendre que "remove" et
   "add ... a negative number" sont sémantiquement liés — hors de portée du
   BM25 lexical, candidat pour le rerank vectoriel (US-042).

2. **"serialize json"** → `JsonSerializer.*` en tête → n'apparaît pas en
   premier. Deux tokens présents dans beaucoup de résumés (« serialize »,
   « json » sont des mots courants dans la doc BCL) ; sans signal
   sémantique, le BM25 ne peut pas privilégier le type dont le nom
   correspond exactement à la requête.

3. **"array"** → les méthodes de `System.Array` (`Clear`, `Clone`,
   `ConvertAll`, `Empty`, ...) → obtenu : des membres sans rapport (ex.
   `JsonValueKind.Array`, un champ d'énumération nommé littéralement
   "Array"). Cause identifiée : le poids de la colonne `name` (8×, spec §5)
   dépasse largement celui de `type_name` (3×) — un champ dont le *nom*
   correspond exactement à la requête bat systématiquement une méthode dont
   seul le *type* correspond, même quand le type est manifestement ce que
   l'utilisateur cherche.

4. **"string"** → premier résultat sans documentation exploitable, lien
   `doc_url` en 404 (`EventFieldFormat.String`, un membre d'énumération).
   **Cause trouvée et corrigée** dans cette même série de correctifs : les
   membres d'énumération n'ont pas de page dédiée sur
   learn.microsoft.com — leur `doc_url` pointe désormais vers la page du
   type (`ingest/parser.py`, `load_type`). Le problème de classement
   (pourquoi ce membre sort en premier) reste lié au point 3.

5. **"Convert"** → `Decimal.ConvertToInteger<TInteger>`,
   `Double.ConvertToInteger<TInteger>` → obtenu :
   `Int32RectValueSerializer.ConvertFromString` et consorts. Même cause que
   le point 3 : correspondance exacte sur `name` (méthode `ConvertFromString`
   contient "Convert" en préfixe) qui écrase des types plus pertinents.

6. **"time"** → `DateTime.TimeOfDay`, un type `DataType.Time` simple →
   obtenu : `TimeSpanValidatorAttribute.TimeSpanMaxValue`, un nom composé
   plus long qui matche aussi bien lexicalement mais est un résultat bien
   plus spécialisé/rare. Le BM25 ne distingue pas facilement les API
   « cœur » d'usage courant des API avancées/spécialisées.

7. **"add seconds"** → `DateInterval.Second`, `DateTime.Second`,
   `TimeSpan.Seconds` (assez loin dans les résultats) → en tête :
   `ISymbolVariable.AddressField2`, `UnicastIPAddressInformation.*`,
   `Matrix3x2.Add`. Cause : le token court `"add"` en préfixe (`"add"*`,
   voir `api/search.py`) matche n'importe quel identifiant commençant par
   ces lettres — `address`, `addressfield`, etc. — sans rapport avec le
   verbe « add ».
   ⚠️ Piste testée et abandonnée : restreindre le caractère préfixe au
   seul dernier token de la requête (motif "recherche instantanée")
   supprime bien le bruit sur "add", mais casse le cas nominal
   `AddMonths` — les noms d'identifiants composés (`AddMonths`) sont
   indexés comme un unique token FTS5 non segmenté (`addmonths`), donc
   *tout* le bénéfice du préfixe `"add"*` sur les noms composés vient
   justement de cette correspondance partielle. Un vrai correctif demande
   de segmenter les identifiants (`AddMonths` → tokens `add` + `months`)
   à l'ingestion, ce qui touche le schéma FTS et nécessite un rebuild —
   à traiter comme une US à part entière, pas un correctif ponctuel.

8. **"Duration"** → la classe `Duration` elle-même, `TimeSpan.Duration`,
   `Duration.Compare`, `Duration.ToString` → obtenu :
   `HttpClientLoggingTagNames.Duration`, `PhonemeReachedEventArgs.Duration`,
   `XmlTypeCode.Duration` — encore la cause du point 3 (poids `name` ≫
   `type_name`).

## Diagnostic global

6 des 8 cas (3, 4, 5, 7, 8) partagent une racine commune : le BM25 pondéré
par colonne (spec §5) ne peut pas, à lui seul, distinguer « ce nom
correspond au hasard » de « ce nom est ce que l'utilisateur cherche
vraiment ». Les deux pistes concrètes identifiées :

- **Segmentation des identifiants composés** à l'ingestion (`AddMonths` →
  `add months`) — corrigerait le point 7 sans casser le point 1 des tests
  existants, mais nécessite un rebuild complet de l'index et une US dédiée.
- **Rerank sémantique** (US-041/042/043, actuellement bloqué) —
  seule piste identifiée pour les cas 1 et 2, qui demandent de comprendre
  le sens de la requête plutôt que son vocabulaire exact.

**8 cas consignés sur 15 requis avant de démarrer US-042.**
