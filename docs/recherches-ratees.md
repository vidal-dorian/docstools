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

9. **"array"** (re-testé après le correctif du point 4) → toujours pas de
   méthodes `System.Array` en tête. Confirme que le point 4 n'a corrigé que
   le lien 404, pas le classement — cause toujours celle du point 3.

10. **"string"** (re-testé) → `EventFieldFormat.String` toujours en tête
    avec un lien en 404, malgré le correctif ingéré (point 4). Cause la
    plus probable : le correctif touche `ingest/parser.py`, donc seul un
    **rebuild de l'index** en prend le bénéfice — pas un redéploiement de
    l'API/du web. Si le rebuild lancé sur le Pi (tmux `docstools-build`,
    18h15–18h31) a démarré depuis un clone dont le `git pull` n'incluait
    pas encore ce correctif (mergé ~17h25), l'index reconstruit contient
    encore l'ancien comportement. À vérifier : `git log -1` dans le clone
    `docstools` utilisé pour le build sur le Pi doit inclure le commit
    `fix(ingest): doc_url d'un membre d'énum...`. Si c'est le cas et que le
    404 persiste quand même, il faudra rouvrir une investigation — mais le
    correctif est vérifié par test unitaire et fonctionne en isolation.

11. **"Remove"** → méthodes de suppression sur `List`/`Dictionary` (Remove,
    RemoveAt, ...) → obtenu : `IInternalConfigRecord.Remove`,
    `MergeAction.Remove`, `EventAccessors.Remover` — encore la cause du
    point 3 (bien que ceux-ci soient de vraies méthodes, pas des champs
    d'énum, elles restent des correspondances exactes sur `name` dans des
    types nichés/peu courants, qui priment sur les méthodes usuelles de
    `List`/`Dictionary` où seul le *type* est évident).

12. **Documentation vide sur de nombreuses surcharges** (ex.
    `SetterBaseCollection.RemoveItem`, `RuntimeFallbacks.Runtime` vu plus
    tôt : "To be added.") → pas un bug d'ingestion : le corpus ECMAXML
    source (`dotnet/dotnet-api-docs`) ne documente réellement pas certains
    membres internes/avancés (WPF, config runtime, ...) — on ingère
    fidèlement ce qui existe. Renforce le diagnostic du point 3 : le
    classement devrait pénaliser les résultats sans contenu exploitable au
    profit de résultats bien documentés, ce que le BM25 pondéré par colonne
    ne fait pas nativement (une correspondance sur `name` suffit, qu'il y
    ait un résumé ou non).

## Diagnostic global

La majorité des cas (3, 5, 6, 8, 9, 11, 12) partagent une racine commune :
le BM25 pondéré par colonne (spec §5) ne peut pas, à lui seul, distinguer
« ce nom correspond au hasard » de « ce nom est ce que l'utilisateur
cherche vraiment », ni privilégier un résultat bien documenté face à un
résultat vide. Les pistes concrètes identifiées :

- **Segmentation des identifiants composés** à l'ingestion (`AddMonths` →
  `add months`) — corrigerait le point 7 sans casser le point 1 des tests
  existants, mais nécessite un rebuild complet de l'index et une US dédiée.
- **Pénaliser les résultats sans documentation** dans le classement (point
  12) — piste indépendante du rerank, pourrait s'implémenter côté BM25/tri
  applicatif sans attendre le vectoriel.
- **Rerank sémantique** (US-041/042/043, actuellement bloqué) —
  seule piste identifiée pour les cas 1 et 2, qui demandent de comprendre
  le sens de la requête plutôt que son vocabulaire exact.

**12 cas consignés sur 15 requis avant de démarrer US-042.**
