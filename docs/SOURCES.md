# Les sources : où chercher un nombre avant d'ouvrir un PDF

Le registre des sources (but 27, D-491 à D-493) garde, une ligne par nombre, chaque valeur
que le dépôt cite d'un document public, avec le document, la page ou le tableau, et ce que
la relecture automatique y a trouvé. **On le lit avant d'ouvrir un document.**

## Les trois fichiers

| Fichier | Dans git | Ce qu'il contient |
|---|---|---|
| `src/impots/sources/registre.jsonl` | oui | une ligne par nombre cité : `id`, `valeur`, `unite`, `annee`, `document`, `sha256`, `localisation`, `source` (la citation), `cite_par` (où le dépôt la cite), `relecture` |
| `src/impots/sources/documents.jsonl` | oui | l'inventaire des documents : éditeur, URL, empreinte, date de téléchargement, `millesime` (fixe, édition datée, série révisée), quarantaine, fichiers qui les citent, nombre de valeurs |
| `data/interim/sources/texte/<fichier>.json` | non | le texte de chaque document, page par page (PDF : page du PDF, pas le folio ; classeur : une page par feuille, lignes préfixées `L12:`) |

## Chercher un nombre

```sh
PYTHONPATH=src python -m impots.sources chercher Mésange 48      # tous les mots, sans casse
PYTHONPATH=src python -m impots.sources valeur grille.rsa_montant.2024
PYTHONPATH=src python -m impots.sources bilan                    # les comptes par statut
PYTHONPATH=src python -m impots.sources texte                    # extraire tout le texte
```

En Python : `from impots.sources import valeur, entree, chercher` ;
`valeur("jumeau.menages.emploi.part_qualifies.valeur")` rend 0,69.

Les identifiants : `grille.<ligne>.<année>` (la grille, `docs/verification/lignes.json`),
`marges.<NOM>[clé]` (`population/margins.py`), `jumeau.<fichier>.<chemin>`,
`comportements.<fichier>.<chemin>`, `macro.<fichier>.<chemin>`,
`predictif.<fichier>.<chemin>` (les YAML de paramètres).

Un nombre qui n'est pas au registre : le chercher dans le texte extrait, pas dans le PDF :
`grep -l "Valeur ajoutée" data/interim/sources/texte/*.json`, ou
`impots.sources.texte.pages("insee_G2017-04_mesange.pdf")[47]` pour la page 48.

## Lire la relecture

| Statut | Ce qu'il veut dire |
|---|---|
| `retrouvée` | le nombre est sur la page ou la feuille dite (`page`, `lu`, `echelle` : 69 à l'échelle 100 pour 0,69) |
| `retrouvée, arrondie` | à l'arrondi du nombre cité (0,07 cité, 0,072 imprimé) |
| `retrouvée (calculée)` | la citation écrit une somme qui redonne la valeur, et chaque terme est dans le document |
| `retrouvée ailleurs` | dans le document, pas à la page dite : la localisation est à corriger |
| `introuvable (calculée)` | la citation dit un calcul ; le nombre n'est pas imprimé, ses termes peut-être |
| `introuvable` | le document est lu, le nombre n'y est pas ; `voisin` donne le plus proche à 5 % près, une piste, pas un verdict |
| `choisie` | la citation dit une valeur choisie, non vérifiée, ou une décision du propriétaire |
| `source secondaire, à vérifier` | la citation dit « source secondaire » : le nombre n'est lu que dans une reprise (presse, note de tiers), la publication d'origine pas encore (D-512) |
| `non relue` | pas de document au manifeste (page d'accueil, document hors manifeste), document absent de `data/raw/`, nombre trivial (0, 1, une année) ou trop court sans page |

La relecture dit qu'un nombre est présent, pas qu'il est la bonne ligne du bon tableau.
Un nombre lu de moins de trois chiffres significatifs ne confirme pas un nombre cité plus
précis ; sans page dite, il en faut quatre.

## Ajouter une source, ou changer une valeur citée

1. Le document va dans `data/raw/` (le fichier, jamais dans git) et son entrée dans
   `data/raw/MANIFEST.json` : URL, `sha256`, `bytes`, `downloaded`, `licence`,
   `description`. Une citation qui nomme le fichier du manifeste (ou son URL exacte) est
   relue ; une page d'accueil ne l'est que si un fichier du manifeste est servi sous son
   identifiant (`/statistiques/8988833` désigne `/fichier/8988833/…`).
2. La valeur est citée là où le code la lit (un YAML avec `source:` à côté, une `Figure`
   de `margins.py`, une ligne de `lignes.json`), avec la page (« p. 48 du PDF ») ou la
   feuille (« onglet « Tableau 2 » »).
3. `PYTHONPATH=src python -m impots.sources recolter` récolte de nouveau et relit (une
   minute quand le texte est déjà extrait) ; on commite `registre.jsonl` et
   `documents.jsonl` avec le changement.
4. `python -m impots.sources verifier [fichier]` (et `tests/test_sources.py`) dit toute
   valeur citée qui n'est plus celle du registre : une valeur changée sans nouvelle
   récolte se voit.

Les évaluations préalables des PLF et des PLFSS et les chiffrages de tiers ne sont jamais
extraits (`texte.INTERDITS`).

---

# Data sources (the landscape, phase 0)

## Open tier — usable today, no accreditation

| Source | Grain | Use | Endpoint |
|---|---|---|---|
| OpenFisca-France parameters | statutory rates, date-versioned | the legal rule set | pypi: OpenFisca-France |
| Filosofi | income deciles by commune/IRIS | calibration targets | insee.fr, data.gouv.fr |
| Enquête Emploi fichier détail | ~110k individuals/yr | population skeleton | insee.fr (open download) |
| SIRENE | exhaustive firm register | firm demography | portail-api.insee.fr |
| ESANE published tables | sector x size aggregates | firm calibration targets | insee.fr |
| URSSAF open data | quarterly wage bill, exonérations | contribution totals | open.urssaf.fr |
| INSEE TES | input-output flows | macro layer backbone | insee.fr |
| Voies et Moyens (PLF annexes) | tax yields, dépenses fiscales | validation ground truth | budget.gouv.fr |
| DBnomics | INSEE/Eurostat/OECD/BdF series | macro time series | db.nomics.world |
| BODACC, RNE/INPI | firm failures, filed accounts | firm distress, partial financials | data.gouv.fr |

## Accredited tier — CASD, needs an institution

ERFS-FPR, POTE, FARE/ESANE microdata, DSN/Base Tous Salariés, LIFI, EIC/EIR.
Comité du Secret Statistique authorisation, ~4-8 months lead time,
~EUR 290/month subsidised, 12-month minimum. An unaffiliated individual cannot
subscribe alone.

## The gap with no workaround

Budget de Famille: last usable vintage 2017. New wave launched Jan 2026,
microdata expected 2027-28. All indirect-tax incidence work before then rests
on nine-year-old consumption patterns or Eurostat's coarser HBS.
