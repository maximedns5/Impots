# « Ce que ça change » : le mode d'emploi

Pour le propriétaire et pour un lecteur. Le but 29 (`docs/BUT.md`, D-590) ; cet état est
celui de la branche `claude/but29-finition` (D-670 à D-674), partie de `claude/but29`.

## À quoi sert la page

Mesurer une proposition (le programme d'un candidat, une de ses mesures, ou une
proposition composée par le lecteur) dans tout ce qu'elle touche, pas seulement dans les
comptes : l'économie, la productivité des entreprises, le moral des gens, la santé, ce
qu'elle fait à un ménage comme le vôtre, et où elle tombe sur le territoire. Chaque
dimension montre ses nombres année par année (2026 à 2035), sa bande (les 5 et 95 % de
60 tirages des paramètres incertains), ses sources, ses limites et son statut. « En bref »
(D-650) résume par des règles écrites ; ce n'est pas un bilan et il le dit.

La page tourne dans le navigateur (le jumeau, numpy seul, D-415) : le calcul d'un
programme ou d'une composition prend quelques secondes. Seul « Votre barème » demande un
serveur et une passe sur la population.

## Les dimensions et leurs statuts

Trois statuts (`jumeau/impacts`, D-605) : **jugé** (un chiffrage officiel fait après coup,
préenregistré, et tenu), **sourcé, non jugé** (chaque coefficient a sa source, aucun juge
ne le tient), **illustratif** (un ordre de grandeur : une partie de la chaîne est choisie
ou déclarée). **Aucune dimension n'est « jugée » aujourd'hui.**

| dimension | statut par défaut | D-entrées |
|---|---|---|
| Les comptes publics (solde, dette, recettes, dépenses) | sourcé, non jugé | D-606 |
| L'économie en général (PIB, emploi, prix) | sourcé, non jugé | D-606, D-639, D-670 |
| La productivité des entreprises | sourcé, non jugé | D-600 à D-604, D-625 à D-627, D-672 |
| Le moral des gens (satisfaction, WELLBY) | sourcé, non jugé | D-595 à D-597, D-635 |
| La santé et le temps de vie | illustratif | D-620 à D-622, D-639 |
| Pour vous (des cas types par OpenFisca) | illustratif | D-630 à D-633, D-638, D-665 |
| Où ça tombe : les territoires | illustratif | D-645 à D-649 |

Ce que disent ces statuts :

* La productivité a eu trois juges préenregistrés (le CICE, France Stratégie, D-601 et
  D-602 : non concluant ; le rapport TEPP, D-604 ; celui de 2018, D-625 et D-626 : sans
  puissance). Ses canaux (la pression du coût du travail, le salaire d'efficience, la R&D)
  restent « à côté » du socle, montrés à part.
* Le moral a passé deux contrôles de l'état de départ (D-596), pas un juge d'une mesure.
* Toute dimension d'une proposition composée, d'une mesure mise à l'échelle ou décalée,
  ou d'un barème réglé par le lecteur devient « illustratif », avec sa raison en tête de
  ses limites.
* Mélenchon et Tondelier : le programme entier passe par la chaîne des études (le
  jumeau complet le refuse, D-655), sans territoires ; la ligne « par ses mesures »
  (D-655 à D-658) passe dans le jumeau complet et porte toutes les dimensions ; le moral
  y devient illustratif.
* **Le pouvoir d'achat et l'entente** (le gain réel par UC, par décile, par type et par
  cas type ; la pauvreté, le Gini, D9/D1, S80/S20, les écarts entre groupes ; D-591,
  D-593, D-594) sont sur la page, avec la bande des tirages des θ que le tableau leur
  passe. « Sourcé, non jugé » tant que le juge de l'Insee (D-591) n'a pas rendu ; pour
  un programme composé de ses mesures, illustratifs comme le moral (ils lisent les
  chocs par décile). La distribution des niveaux de vie dans les cellules vient avec
  les entrées de la page : mesurée si `reports/jumeau/niveaux_de_vie_cellules.json` est
  commité, sinon approchée, et la dimension le dit.

## L'ouvrir en local

Depuis un worktree où les données sont reliées (`make data`, ou des liens dans
`data/raw` et `data/processed`) ; le Python du dépôt :

    cd /home/user/Impots-b29-finition
    PY=/home/user/Impots-but19/.venv/bin/python

**Écrire la page** dans un dossier (1 min 40 s ; les programmes y sont précalculés) :

    PYTHONPATH=src $PY -m impots.site_impacts ecrire /tmp/impots-ce-que-ca-change

**La servir seule** (statique : tout sauf « Votre barème ») :

    $PY -m http.server 8001 --bind 127.0.0.1 -d /tmp/impots-ce-que-ca-change
    # http://localhost:8001/impacts.html

(`PYTHONPATH=src $PY -m impots.site_impacts servir 8001` fait les deux : écrire, puis
servir.)

**Avec l'API**, qui sert aussi la page écrite et ouvre « Votre barème » :

    IMPOTS_AUTH=aucune IMPOTS_SITE_LOCAL=/tmp/impots-ce-que-ca-change \
      PYTHONPATH=src $PY -m uvicorn impots.api.main:app --port 8000
    # http://localhost:8000/site/impacts.html

Sans `IMPOTS_AUTH=aucune`, les calculs sont fermés (D-295). Ajouter `IMPOTS_PASSES=non`
fait un serveur qui ne lance aucune passe (il rend les propositions déjà passées) : à
préférer tant qu'une autre passe tourne sur la machine. Une adresse directe : un
programme par son identifiant après `#` (`#pres2027_retailleau_programme`), la ligne par
ses mesures avec `@mesures`, `#comparer`, `#bareme`.

Vérifié le 18 novembre (ces commandes lancées, ports 8765 à 8767 ; Chromium à 1 200 et
390 px : Retailleau, Mélenchon sur ses deux lignes, une proposition composée ; aucune
erreur, aucun défilement horizontal).

## Composer une proposition

Onglet « Composer la mienne » : « + une mesure » ajoute une mesure chiffrée d'un
programme, avec son échelle (×0,5, ×2) et son décalage (en années) ; « + une loi
simple » ajoute une loi hypothétique (un instrument : impôt sur le revenu, TVA,
cotisations des employeurs, dépense publique, investissement public ; un montant en Md€
par an ; ses années). « Calculer » : toutes les dimensions, « illustratif ». Par l'API :

    curl -s -X POST localhost:8000/impacts -H 'content-type: application/json' -d \
     '{"composition": [{"candidat": "pres2027_lisnard_l1_csg_activite_6_6",
                        "echelle": 0.5, "decalage": 1},
                       {"hypothese": {"instrument": "impot_sur_le_revenu",
                                      "montant": 5, "debut": 2027, "fin": 2035}}],
       "tirages": 8}'

Une composition ne change pas un paramètre de barème : elle met à l'échelle des mesures
déjà passées (l'intensité k, au premier ordre, D-605). Une hausse du Smic n'y entre pas.

## « Votre barème » (D-660, D-661, D-671)

Treize réglages d'un seul nombre (le Smic, les revalorisations du RSA, de la prime
d'activité, de l'AAH, de l'Aspa, des prestations familiales, des aides au logement et des
pensions, les taux de l'IR et une tranche en plus, le taux normal de TVA, les cotisations
salariales de retraite). « Lancer la passe » envoie `POST /impacts/proposition` ; l'API
fait la première année, le chemin annuel (OpenFisca sur 20 000 ménages), les cas types,
puis le jumeau. **Pronostic : 40 à 50 min et 6 Go par proposition**, une à la fois ;
l'état se suit sur la page ou par `GET /impacts/proposition/<id>`. En ligne de commande :

    IMPOTS_VERROU_PASSES=<le verrou commun> PYTHONPATH=src \
      $PY -m impots.parametrique lancer smic=5
    PYTHONPATH=src $PY -m impots.parametrique etat <id rendu>

**Pourquoi le verrou commun.** Une passe tient 6 Go ; la machine en a 15 pour tout. Deux
passes ensemble (une proposition et une étude, ou deux agents) font tomber l'une ou
l'autre faute de mémoire (c'est arrivé la nuit du but 29, D-661). Sans
`IMPOTS_VERROU_PASSES`, le verrou des propositions est privé
(`data/processed/propositions/passe.lock`) et ne protège pas des autres passes (D-666) :
donner le verrou commun que les autres passes prennent avec `flock`. Lancer d'un worktree
dont `src/` est commité (sinon les rapports le disent « modifié »). Le résultat est
toujours « illustratif » : il n'est ni préenregistré ni jugé.

## Ce qui n'est pas fait

* Aucune vraie proposition « Votre barème » n'a tourné : ses temps et sa mémoire sont un
  pronostic (D-661).
* Le juge du pouvoir d'achat et de l'entente (D-591) attend ses passes (D-592).
* Aucune dimension n'est jugée ; le moral, la santé et l'entente n'ont pas de juge
  aveugle connu.
* Les impôts des entreprises (IS, CVAE) ne se règlent pas dans « Votre barème » ; l'âge de
  départ non plus (la santé seule le lit, sur un programme entier, D-622).
* Le site commité n'est pas reconstruit ; `make impact` et les tests lourds n'ont pas
  tourné pour le but 29.
* Restes écrits dans D-666 : la file des propositions compte ses places sans verrou ; un
  pid réutilisé peut faire paraître vivante une passe perdue ; la part des gagnants par
  territoire est celle des cellules, pas des ménages ; « Pour vous » ne montre pas sur la
  page la bande que porte sa fiche ; une composition n'est bornée que par le débit.
* Le même PIB en volume est cité deux fois dans « En bref » sur la chaîne des études
  (l'économie et la productivité, D-670) : redondant, plus contradictoire.

## Les décisions qui attendent le propriétaire

* La ligne de Mélenchon et de Tondelier mise en avant : programme entier par la chaîne
  des études (aujourd'hui) ou « par ses mesures » (D-652, D-658).
* Brancher le canal de la pression du coût par défaut, ou le garder à côté faute de
  puissance (proposé : à côté) (D-604, D-626).
* Un juge de la productivité qui ait de la puissance ; aucun juge du salaire d'efficience
  (le Smic) (D-604).
* Le moral : l'ancrage du chômage autour de soi (ou la règle 10/3, 2,4 fois plus),
  l'adaptation hédonique, les moins de 16 ans, un coefficient du revenu estimé sur SRCV
  (D-597, D-635).
* La certitude « probablement » lit de la même façon les bandes de tirages et les
  enveloppes de bornes publiées (D-650, D-666).
* La santé : les calendriers d'âge des programmes, la part causale du gradient et r, la
  bascule vers l'invalidité et le chômage après un report, le temps de travail (D-622).
* Le double compte santé : retirer du canal du revenu (choisi) ou du chômage (D-639).
* Pour vous : la grille des cas types, l'indépendant par OpenFisca, le salaire moyen par
  tranche, le contrôle du logement et des couples sur un cas publié (D-633).
* Les territoires : la table sur la passe même des cellules, les régions de métropole, le
  revenu de l'outre-mer, la densité, une bande par territoire (D-649).
* « En bref » : les seuils de l'échéance, les déciles du bas et du haut, la longueur du
  paragraphe ; les phrases rendues sont à relire (D-650, D-651).
* « Votre barème » : une clé pour une instance publique, l'effacement des propositions,
  les impôts des entreprises, un chemin annuel plus rapide (D-661).
* Le verrou des propositions commun par défaut, et la file sous verrou (D-666).
* Le juge du pouvoir d'achat et de l'entente (D-591, D-592).
