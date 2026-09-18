# M1 §6.1 — ce qui manque vraiment au backtest de la dette, 2019 → 2025

**Établi par inspection le 2026-09-18, sans rien calculer.** Le backtest §6.1 était porté
au journal comme « bloqué sur un compte des APU sourcé ». C'est vrai, mais bien plus étroit
qu'il n'y paraissait : **quatre des cinq entrées sont déjà sourcées et présentes**, et le
blocage tient à **une URL et un millésime**.

## 1. État mesuré des cinq entrées

| entrée de §3.1 | fichier | état | verdict |
|---|---|---|---|
| `b` — stock Maastricht | `insee_dette_maastricht_detail.xlsx` | sourcé, présent | **prêt** |
| `b` — contrôle trimestriel | `insee_ir158_dette_t1_2026_series.xls` | sourcé, présent | **prêt** |
| `g` — PIB nominal | `insee_cn2025_pib_T1101_1103.xlsx` | sourcé, présent | **prêt** |
| `r`, `p` — D.41 et B.9 | `insee_cn2024_t7301_...S13.xlsx` | **EN QUARANTAINE** | bloqué (§2) |
| `sfa` — ajustement flux-stocks | *aucun* | absent | bloqué (§3) |

## 2. Le compte des APU : il est sur le disque, c'est son URL qui manque

Le fichier existe, dans `data/raw/_unsourced/`, 63 699 octets. Il porte bien ce qu'il faut :
la feuille `T_7301` couvre **1949 → 2024** et contient `D41 Intérêts` (en ressources ET en
emplois, deux lignes distinctes — l'intérêt NET est la différence, et les confondre
fausserait `r` d'un facteur proche de deux) ainsi que `B9 Capacité (+) ou besoin (−) de
financement`.

Il est inutilisable non parce qu'il manque, mais parce que **D-028 le refuse** : son entrée
au manifeste n'a pas d'URL, donc `require_sourced()` refuse de l'ouvrir. C'est le
comportement correct — « un checksum prouve qu'un fichier n'a pas changé ; seule une URL
prouve d'où il vient ». **Le déblocage est une URL ajoutée à `KNOWN_SOURCES`**, pas un
téléchargement.

**Deux millésimes, pas un.** Ce fichier est le millésime 2024 et s'arrête en 2024 : il
couvre 2019 → 2024, soit six des sept années. **L'année 2025 demande le millésime 2025 de
la même table 7.301**, que l'INSEE publie fin mai de l'année suivante — donc disponible à
cette date. Sans lui, le backtest tourne sur 2019 → 2024 et le dit, ce qui reste un
backtest ; il ne doit pas être étendu à 2025 par prolongement.

## 3. L'ajustement flux-stocks n'a aucune source au dépôt

Vérifié : `insee_dette_maastricht_detail.xlsx` ne porte que le stock, aucun libellé
d'ajustement. Et le SFA **n'est pas une opération du SEC** — ce n'est pas une ligne du
compte des APU, mais le pont entre `B.9` et la variation de la dette Maastricht. Il ne
sortira donc jamais de la table 7.301, quel qu'en soit le millésime.

C'est l'entrée qui demande un vrai téléchargement. Deux routes, à confirmer à la source :

* **la notification EDP** (tableaux de notification du déficit et de la dette), qui publie
  l'ajustement flux-stocks ligne à ligne — c'est la route la plus directe ;
* **Eurostat**, jeu `gov_10dd_edpt1`, qui porte le même pont sous le libellé
  *stock-flow adjustment*.

Les deux identifiants sont donnés comme **repères de recherche, non comme URL vérifiées** :
le manifeste exige l'URL réelle, et une URL recopiée de mémoire est exactement ce que D-028
interdit d'inscrire.

**Et le SFA n'est pas optionnel ici.** §3.1 le laisse à zéro par défaut pour une
PROJECTION, avec bannière ; `backtest` le prend sans défaut et refuse `None`. La raison est
au dossier : *un backtest qui laisse tomber un terme réalisé et « passe » quand même a été
ajusté, pas testé.* Le refus tiendra tant que cette source n'existe pas, et c'est voulu.

## 4. Ce qu'il faut demander au réseau du propriétaire

1. **L'URL** du `insee_cn2024_t7301_compte_administrations_publiques_S13.xlsx` déjà détenu —
   aucune donnée à retélécharger, seulement la provenance à établir.
2. **La table 7.301, millésime 2025**, pour l'année 2025.
3. **Une source d'ajustement flux-stocks 2019 → 2025**, notification EDP ou Eurostat
   `gov_10dd_edpt1`, avec son URL.

Le reste de la liste de téléchargement de la phase 8 (accises DGDDI, COICOP, versement
mobilité, DMTO, CIR, taxe sur les salaires, TASCOM/TGAP/TTF) concerne §2 et M2, pas §6.1,
et ne bloque pas ce backtest.

## 5. Une correction, au passage

Le premier contrôle mené ici a conclu que **76 des 144 fichiers du manifeste étaient absents
du disque**. C'était faux : il cherchait dans `data/raw/` alors que D-028 **déplace** les
fichiers non sourcés vers `data/raw/_unsourced/`. Les 76 sont présents, et les 76 « absents »
étaient exactement les 76 en quarantaine — une coïncidence parfaite qui aurait dû alerter
tout de suite. Consigné parce que la conclusion fausse était alarmante et aurait déclenché
une campagne de téléchargement inutile.
