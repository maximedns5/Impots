# Handoff — faire fonctionner la PR #1, en local, à partir du 2026-09-24

> **CLOS le 2026-10-01 — à ne plus suivre.** La mission est accomplie : empreinte
> normalisée pour EconStor (D-159), profil corrigé (D-160), passe complète verte sur
> `a9ea26f`, CI verte après D-171, et la PR #1 fusionnée dans `main` par la PR #2
> (`1e12460`). Conservé pour son récit ; l'état courant est dans `docs/STATE_AND_NEXT.md`.

**Pour la session Claude Code qui tourne sur la machine du propriétaire.** Cette machine
a le réseau ouvert ; la session cloud qui a écrit ce document ne l'avait pas (le proxy
refusait `www.insee.fr`, `www.impots.gouv.fr` et `www.econstor.eu`). Tout ce qui suit est
vérifié sauf mention contraire, et chaque vérification dit comment la refaire.

**Mission** : [maximedns5/Impots#1](https://github.com/maximedns5/Impots/pull/1), branche
`claude/keen-newton-dubgu8`, devient **verte en CI sur sa tête**, avec **une ligne PASS
au journal `reports/full_pass_log.md`** plus récente que le travail qu'elle couvre.

Lire d'abord : ce fichier en entier, puis **D-158** dans `docs/DECISIONS.md` (la chaîne de
données), puis `src/impots/donnees.py`. Les règles de `docs/CHARTER.md` et des entrées D
restent en vigueur ; les plus exposées ici sont rappelées au §7.

---

## 1. L'état à la remise

**Dernier commit de code : `a46412b`.** Il introduit la chaîne de données (D-158) :

* `impots data check | fetch | prepare --profile tests`, et `make data` ;
* `make full` lance le préflight d'abord et s'arrête en une seconde si une dépendance
  manque, sans écrire de ligne au journal ;
* la CI (`.github/workflows/test.yml`, job `pytest`) : cache des sources → `fetch` →
  construction des deux artefacts dérivés → préflight → suite complète.

Le profil `tests` comprend **10 sources brutes et 2 artefacts dérivés**, dérivés des
constantes des lecteurs eux-mêmes :

| fichier | nature | produit par |
|---|---|---|
| `dgfip_stats_33_ifi_2024.xlsx`, `dgfip_stat_41_ir_2024_tables.xlsx`, `dgfip_stat_39_impot_benefice_2024_donnees.xlsx` | brut | `fetch` (impots.gouv.fr) |
| `insee_G2017-04_mesange.pdf`, `insee_esane2023_…xlsx`, `insee_focus372_…xlsx`, `FD_EEC_2024.parquet`, `Varmod_EEC_2024.csv` | brut | `fetch` (insee.fr) |
| `imk_wp117_2013_gechert_meta_regression.pdf`, `imk_wp139_2014_gechert_rannenberg_regime_dependent.pdf` | brut | `fetch` (econstor.eu) — **LE BLOCAGE, §2** |
| `data/processed/firm_cells_2023.json` | dérivé | `impots entreprises cells` |
| `data/processed/population_2024.parquet` | dérivé | `impots population build` |

## 2. Le blocage, et ce qui est prouvé

**Premier run CI de la chaîne, sur `a46412b` :** 8 sources sur 10 téléchargées et
vérifiées au sha256 depuis les runners GitHub — toutes celles d'INSEE et de la DGFiP.
**Les deux PDF IMK d'EconStor échouent la garde de checksum**, avec exactement la taille du
manifeste. Trois téléchargements de la même URL, trois sha256 :

| | wp117 (1 361 763 octets) | wp139 (908 163 octets) |
|---|---|---|
| manifeste (copie du propriétaire) | `4b5350969f656d6d…` | `ad8415979ccae933…` |
| runner A (run 35877435597) | `c77079a3b063995a…` | `10f50864c6dabf03…` |
| runner B (run 35877431005) | `f62660e2deff7c19…` | `09e7e6935f1ac047…` |

**Conclusion prouvée : EconStor réécrit le fichier à chaque requête**, dans des champs de
longueur fixe (la taille ne bouge jamais). Deux runners, à quelques secondes d'écart, ont
reçu des octets différents : ce n'est PAS un changement de millésime, et **aucun sha256
brut ne pourra jamais correspondre à un téléchargement neuf.** Le job s'est arrêté à
l'étape `fetch` : la construction de la population, le préflight et la suite n'ont donc
**pas encore tourné en CI**.

**Ce qui n'est PAS connu :** quels octets EconStor réécrit. Hypothèses, non vérifiées :
l'identifiant du PDF (`/ID [<…><…>]` du trailer), les dates d'info (`/CreationDate`,
`/ModDate`), des métadonnées XMP (`xmp:MetadataDate`, `xmpMM:InstanceID`), ou un filigrane
daté dans un flux de contenu. **C'est le premier travail de cette session (§4).**

Un commentaire sur la PR consigne ce constat :
https://github.com/maximedns5/Impots/pull/1#issuecomment-5797483519

## 3. Mise en place

```bash
git checkout claude/keen-newton-dubgu8 && git pull origin claude/keen-newton-dubgu8
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -c "from importlib.metadata import version as v; print(v('openfisca-france'), v('openfisca-core'))"
# attendu : 176.0.8 44.7.0 — les goldens y sont ancrés ; ne pas monter de version ici
```

**Le clone est NEUF : `data/raw/` ne contient que `MANIFEST.json`, comme la CI.** Les copies
du propriétaire — celles dont le manifeste a pris l'empreinte — sont dans son ANCIEN
dossier de travail (celui qui a journalisé la passe du 2026-09-18, `46bc81f`). Les
chercher, sans rien supposer :

```bash
find ~ -type f -name "imk_wp117_2013_gechert_meta_regression.pdf" 2>/dev/null
```

S'il existe un ancien `data/raw/`, en copier les fichiers dans celui du clone, puis laisser
le préflight trancher — il compare taille ET sha256 au manifeste, fichier par fichier :

```bash
.venv/bin/impots data check --profile tests
```

**Ne jamais committer ces fichiers** (D-016) : `data/raw/*` est gitignoré, et
`python scripts/check_no_data_committed.py --tree` est la garde qui le vérifie.

## 4. Diagnostiquer EconStor — avant d'écrire une ligne de correctif

Télécharger chaque PDF **deux fois**, puis comparer les deux téléchargements entre eux
**et**, si l'ancienne copie a été retrouvée, avec elle. Les URL sont lues dans
`MANIFEST.json` par le script — **aucune n'est à taper à la main** (la première version de
ce document en recopiait une de mémoire, et elle était fausse) :

```bash
python3 - <<'PY'
import hashlib, json, pathlib, urllib.request

manifeste = json.loads(pathlib.Path("data/raw/MANIFEST.json").read_text())["files"]
for nom in ("imk_wp117_2013_gechert_meta_regression.pdf",
            "imk_wp139_2014_gechert_rannenberg_regime_dependent.pdf"):
    entree = manifeste[nom]
    print(f"\n=== {nom}\n    manifeste : {entree['bytes']} octets, sha256 {entree['sha256'][:16]}…")
    versions = {}
    for n in (1, 2):
        requete = urllib.request.Request(entree["url"], headers={"User-Agent": "impots-diagnostic"})
        versions[f"téléchargement {n}"] = urllib.request.urlopen(requete, timeout=120).read()
    locale = pathlib.Path("data/raw") / nom
    if locale.exists():
        versions["copie du propriétaire"] = locale.read_bytes()
    for etiquette, b in versions.items():
        print(f"    {etiquette:<22} {len(b)} octets  sha256 {hashlib.sha256(b).hexdigest()[:16]}…")
    etiquettes = list(versions)
    reference = versions[etiquettes[0]]
    for autre in etiquettes[1:]:
        b = versions[autre]
        d = [i for i, (x, y) in enumerate(zip(reference, b)) if x != y]
        print(f"\n    {etiquettes[0]} ≠ {autre} : {len(d)} octets différents ; zones :")
        for debut in sorted({i // 64 * 64 for i in d})[:10]:
            print(f"      @{debut}\n        A: {reference[max(0, debut-48):debut+112]!r}"
                  f"\n        B: {b[max(0, debut-48):debut+112]!r}")
PY
```

## 5. Corriger, selon ce que le diagnostic montre

**Ce qu'il ne faut PAS faire, quel que soit le diagnostic :**

* remplacer le `sha256` du manifeste par celui d'un téléchargement neuf — le suivant
  différera encore, et la CI retombera au prochain run ;
* retirer la vérification pour ces deux fichiers, ou pour econstor.eu — ce serait enlever
  la garde pour la seule source qui a prouvé qu'elle en avait besoin ;
* « tolérer » une différence de quelques octets sans savoir lesquels — une garde qui ne
  sait pas ce qu'elle ignore n'est plus une garde.

**Cas A — seuls des champs de métadonnées de longueur fixe diffèrent** (trailer `/ID`,
dates d'info, XMP). C'est l'hypothèse la plus probable, puisque la taille ne change pas.
Écrire une **empreinte normalisée**, déclarée par entrée et non implicite :

1. **Ajouter les champs à `ManifestEntry` AVANT de toucher `MANIFEST.json`**
   (`src/impots/population/ingest.py`) — par exemple `normalization: str | None = None`
   et `normalized_sha256: str | None = None`. **Piège D-142** : `load_manifest()` refuse
   tout champ inconnu (`test_an_entry_in_an_unknown_shape_is_refused_rather_than_ignored`)
   — ajouter les clés au JSON d'abord ferait tomber TOUT chargement de manifeste.
2. Écrire la normalisation dans `src/impots/donnees.py` : une fonction qui remplace
   **exactement** les champs identifiés au §4 par un gabarit de même longueur, et rien
   d'autre. Nommée et versionnée (`"pdf-stamp-v1"`), pour qu'un changement de règle soit
   un changement visible.
3. **L'appliquer aux DEUX endroits** : `telecharger()` (l'acceptation d'un téléchargement)
   ET `_conforme()` (le préflight et le raccourci « déjà présent »). **Piège D-151** : un
   contrat porté par deux fonctions n'est pas élargi tant que les deux ne le sont pas —
   sinon `fetch` accepterait un fichier que `check` déclarerait ensuite non conforme.
   Règle : si l'entrée déclare une normalisation, taille égale ET sha256 normalisé égal ;
   sinon, comportement inchangé (sha256 brut) pour les huit autres sources.
4. Dans `MANIFEST.json`, pour ces deux entrées seulement : garder `sha256` (l'empreinte
   brute de la copie du propriétaire, qui reste sa provenance), ajouter `normalization`
   et `normalized_sha256`. Calculer ce dernier sur la copie du propriétaire **et** vérifier
   que les deux téléchargements neufs donnent le MÊME — sinon la normalisation est
   incomplète, et c'est le §4 qu'il faut reprendre.
5. **Tests de mise à mort, chacun VU échouer** (`tests/test_donnees.py`) :
   * un octet modifié HORS des champs normalisés → refusé (la garde ne s'est pas trop
     élargie) ;
   * un octet modifié DANS un champ normalisé → accepté ;
   * une entrée sans `normalization` garde la comparaison brute (les huit autres sources) ;
   * `fetch` et `check` rendent le même verdict sur le même fichier (le piège D-151).
6. Consigner **D-159** en français : le constat (trois empreintes, même taille), le
   diagnostic du §4 avec les zones qui diffèrent, la règle de normalisation, et ce
   qu'elle n'ignore pas. Note utile : `imk.load()` ne vérifie PAS le sha256 lui-même —
   l'étape de téléchargement est donc la seule garde d'intégrité de ces deux PDF.

**Cas B — la différence touche du contenu de page** (un filigrane daté dans un flux).
Une normalisation d'octets serait alors fragile. Deux voies, **toutes deux des décisions
du propriétaire** (D-004, provenance) : une autre URL qui sert des octets stables (l'IMK
publie aussi ses working papers), ou une empreinte sur le **texte extrait** des pages
(`pypdf` est déjà une dépendance) plutôt que sur les octets. Présenter le diagnostic et
les deux voies ; ne pas trancher seul.

**Cas C — les deux téléchargements neufs sont identiques entre eux.** Contredirait le
constat CI (deux runners, deux empreintes). Si cela arrive, EconStor a changé de
comportement : c'est une décision de millésime (D-004), à consigner avant toute
mise à jour du manifeste.

## 6. Vérifier, puis pousser

```bash
.venv/bin/ruff check src tests scripts
.venv/bin/python -m pytest tests/test_donnees.py tests/test_provenance.py -q
make data      # télécharge ce qui manque, construit ce qui manque, puis vérifie
make full      # préflight, puis la suite complète (~50 min), une ligne au journal
```

**`make full` est autorisé pour cette tâche** : c'est la mission. Sa ligne au journal est
la preuve demandée — la committer (`reports/full_pass_log.md`,
`reports/full_pass_durations.md`).

**Si des tests échouent maintenant, ce ne sont plus des fichiers absents** : le préflight
l'aurait dit avant. Chacun est un vrai échec à diagnostiquer. Rappel mesuré : sur les 18
rouges d'origine, 7 passent déjà sans données, et les 11 autres dépendent réellement des
données — `test_zero_masked` (6, la population), `test_top_tail` (2), `test_accuracy` (2),
et le test d'intégration `test_the_macro_horizon_is_read_from_the_store`.

Puis pousser sur `claude/keen-newton-dubgu8`. **Ne jamais réécrire l'historique de cette
branche** : elle porte une PR ouverte. Fusionner, pas rebaser.

**En CI, deux choses tourneront pour la PREMIÈRE fois** : la construction de la population
sur un runner, et les tests de population qui y sautaient jusqu'ici faute de population.
Leur durée et leur verdict en CI sont inconnus. Un échec qui passe en local est une
différence d'environnement à diagnostiquer — **jamais** un test à sauter ou à mettre en
quarantaine. Une seule relance autorisée, et seulement pour une panne d'infrastructure
(le job mort avant tout corps de test).

**Mettre à jour la description de la PR** : elle s'arrête à M4 (`0a82d09`). Il y manque
M5, M6, la correction de D-157, la chaîne de données (D-158) et le correctif EconStor.

## 7. Règles de ce dépôt qui s'appliquent ici

* **Aucune donnée dans git** (D-016). **Aucun chiffre de mémoire** (D-026) : une valeur
  vient d'un fichier manifesté, ou elle n'existe pas.
* **Toute garde livre son test de mise à mort, et on l'a VUE échouer.** Quand un test de
  mise à mort échoue, suspecter le test d'abord.
* **Un contrat porté par deux fonctions ou deux tests est élargi partout** (D-151).
* **Ne pas toucher `src/impots/population/calibrate.py`** : clôturé à la phase 7 (§8 de
  `docs/PHASE8_SPEC.md`). Le constat de M6 sur les cibles de marge nulles (D-157) est une
  note au relecteur, pas une modification à faire ici.
* Entrées D **en français**, messages de commit **en anglais**.
* **Ne jamais sauter, désactiver ou mettre en quarantaine un test pour passer au vert.**

## 8. Hors périmètre de cette mission — décisions du propriétaire

Rien de ceci n'est nécessaire pour que la PR passe ; ne pas les trancher :

* le seuil de l'univers de couverture de §2.4 (aucune entrée D ne l'enregistre) ;
* `data/processed/receipts_anchors.json` (les ancres de recettes, `docs/M2_ANCHORS.md`) ;
* le fichier Eurostat `gov_10a_taxag` pour le benchmark du panneau M5 ;
* le coût CI : chaque commit lance **trois** runs complets (deux `push`, un
  `pull_request`) — `on: push: branches: [main]` le réduirait, mais c'est un choix sur
  la CI de tout le dépôt.

## 9. Définition de « fini »

1. Le §4 a été fait, et son résultat est consigné (D-159).
2. `impots data fetch --profile tests` réussit sur un clone neuf, **y compris pour les deux
   PDF EconStor**, sans affaiblir la vérification des huit autres sources.
3. `make full` en local : une ligne **PASS** au journal, committée.
4. La CI est **verte sur la tête de la PR** — les quatre étapes de la chaîne, puis la suite.
5. La description de la PR décrit ce que la branche contient.
