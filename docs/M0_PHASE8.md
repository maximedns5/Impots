# M0 Phase 8 — gate de reconnaissance

**2026-09-13.** Une section par item R. Chacune finit soit par des entrées de manifeste
(chemin, identifiant de source, sha256, millésime), soit par un constat daté « n'existe pas /
inaccessible ». **La reconnaissance localise et manifeste des fichiers ; elle n'écrit jamais
de chiffres** (D-026) — chaque nombre ci-dessous est lu dans un fichier manifesté, et le
fichier est nommé à côté.

Rien des §2-§5 n'est figé tant que ce gate n'est pas relu.

## État d'ensemble

| item | verdict | manifesté |
|---|---|---|
| R1 — AFT, encours et structure de maturité | **partiel** | non — voir §R1 |
| R2 — charge d'intérêt | **trouvé** | 1 fichier |
| R3 — encours et ratio de dette | **trouvé** | 4 fichiers |
| R4 — accises | trouvé (à télécharger) | — |
| R5 — TVA | trouvé (à télécharger) | — |
| R6 — DMTG | gate F7 inchangé, non élargi | — |
| R7 — entreprises et local | partiel (à télécharger) | REI et Stat 46 déjà manifestés |
| R8 — benchmark D.29 | trouvé (à télécharger) | TES déjà manifesté |

**Intégrité du manifeste au démarrage de la phase** : 126 entrées antérieures, **50 fichiers
sourcés dans `data/raw/`, 76 en quarantaine dans `data/raw/_unsourced/`, 126 sha256
conformes, 0 divergent, 0 perdu.** Vérifié octet par octet avant toute nouvelle entrée : un
manifeste ne vaut que sa dernière vérification.

## R2 — la charge d'intérêt : MESURÉE, et l'ancre attendue était fausse

`plf2026_pap_engagements_financiers.pdf` — Projet annuel de performances (bleu budgétaire),
annexe au PLF 2026, mission « Engagements financiers de l'État », 117 pages.
sha256 `2715898f5466cd90…`

Tableau « RÉCAPITULATION DES CRÉDITS PAR PROGRAMME ET TITRE POUR 2025, 2026, 2027 ET 2028 »,
programme 117 « Charge de la dette et trésorerie de l'État » (crédits évaluatifs) :

| colonne | montant |
|---|---|
| LFI 2025 | 54,207 md€ |
| **PLF 2026** | **58,615 md€** |
| Prévision indicative 2027 | 68,660 md€ |
| Prévision indicative 2028 | 76,676 md€ |

**La spec annonçait « près de 77 md€ » pour 2026, d'après la presse secondaire, marqué NON
MESURÉ. Mesuré, c'est la projection indicative 2028.** La charge 2026 vaut 58,615 md€ —
l'ancre de presse était **31 % trop haute**, et t₀ posé dessus aurait faussé toute
l'arithmétique taux implicite × encours.

Le rattachement des colonnes est vérifié indépendamment par les variations imprimées à côté :
+8,13 %, +17,14 %, +11,67 %, qui se reproduisent exactement depuis les quatre montants. Ce
n'est donc pas une lecture de colonne au jugé — c'est le piège « colonnes d'année
budgétaire » que le handoff signalait pour les Voies et Moyens, rencontré dans un autre
document.

## R3 — encours et ratio : l'ancre confirmée depuis le fichier

`insee_ir158_dette_t1_2026.pdf` — INSEE, Informations Rapides n° 158, 25 juin 2026.
sha256 `71475685591aca39…`

Lu dans le fichier : « À la fin du premier trimestre 2026, la dette publique au sens de
Maastricht s'établit à **3 536,1 Md€** » et « **117,5 %** du PIB, après 115,7 % au quatrième
trimestre 2025 ». La série trimestrielle imprimée : 3 346,3 / 3 417,2 / 3 484,1 / 3 460,5 /
3 536,1 md€, et 113,4 / 115,2 / 117,0 / 115,7 / 117,5 % du PIB.

**C'est exactement le chiffre que la spec portait en [VERIFIED 2026-09-11]** — désormais lu
dans le fichier manifesté plutôt que relayé, ce qui est la différence entre un chiffre vrai
et un chiffre vérifiable.

Manifestés également : `insee_ir158_dette_t1_2026_series.xls` (séries longues, support du
backtest 2019→2025), `insee_dette_maastricht_detail.xlsx` (ventilation par sous-secteur et
instrument, pour la décomposition §3.6), `insee_cn2025_pib_T1101_1103.xlsx` (PIB, le
dénominateur).

## R1 — AFT : partiel, et le blocage est le constat

**`www.aft.gouv.fr` rend 403 à tout client scripté** — page d'encours, bulletins mensuels,
et chaque fichier sous `/files/medias-aft/`, avec ou sans User-Agent de navigateur, en http
comme en https, avec ou sans `www`. Vérifié depuis la machine du propriétaire, qui atteint
pourtant insee.fr et data.gouv.fr sans difficulté : **ce n'est pas le blocage proxy du
conteneur, c'est l'AFT qui refuse les clients non interactifs.**

Ce que la reconnaissance a trouvé à la place, et qui n'est **pas manifesté** parce que la
provenance n'est pas celle de l'éditeur :

* des instantanés `web.archive.org` du bulletin mensuel n° 428 (janvier 2026), de
  l'historique des adjudications MLT et BTF, et de l'historique des syndications ;
* le seul jeu AFT sur data.gouv.fr est en réalité les **données de graphiques d'un rapport
  de la Cour des comptes** de 2022 — pas le fichier primaire par ligne de dette.

**Décision, et elle appartient au propriétaire** : un instantané d'archive n'est pas le
fichier de l'éditeur. Il porte un sha256 stable et une date de capture, ce qui suffirait à la
règle du pointeur, mais il introduit un intermédiaire dans la chaîne de provenance d'une
donnée qui porterait l'échéancier de remboursement et le taux implicite. Les identifiants
sont au dossier ci-dessus ; **le téléchargement depuis l'AFT reste à faire par un navigateur
sur la machine du propriétaire**, et R1 reste PARTIEL jusque-là.

## R4, R5, R7, R8 — localisés, téléchargement à faire

Candidats vérifiés vivants (statut HTTP, type et taille observés par la reconnaissance) :
accises DGDDI sur `douane.gouv.fr`, TVA côté Voies et Moyens tome I (**déjà manifesté**) et
consommation COICOP côté INSEE, versement mobilité sur `open.urssaf.fr`, DMTO sur
`data.economie.gouv.fr`, REI sur `data.ofgl.fr` (**mais nous avons déjà `rei_2025.zip`
manifesté et `verify_rei.py` — ne pas ré-importer**), et Eurostat `gov_10a_taxag` pour la
D.29. Aucun n'est manifesté à cette heure : localiser n'est pas manifester.

## R6 — DMTG

Le gate F7 tel que spécifié **reste inchangé et n'est pas élargi** par cette phase. Rien à
manifester ici.
