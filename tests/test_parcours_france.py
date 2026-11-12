"""La page 2 du parcours (D-375) montre les nombres de la grille commitée, et se lit sans
son script."""

import html
import json
import re

from impots import parcours
from impots.parcours import france

GRILLE = parcours.ROOT / "reports" / "verification" / "grille.json"


def _grille():
    return json.loads(GRILLE.read_text(encoding="utf-8"))["lignes"]


def test_la_page_montre_le_compte_et_les_lignes_hors_de_la_grille():
    page = france.page()
    parcours._check("france", page)
    rows = _grille()
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    tenues = sum(r["verdict"] == "dans la tolérance" for r in notees)
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", page.corps)))
    assert f"{tenues} lignes notées sur {len(notees)}" in texte
    assert (tenues, len(notees)) == (84, 113)  # D-371
    for annee in france.ANNEES:
        n = [r for r in notees if r["annee"] == annee]
        t = sum(r["verdict"] == "dans la tolérance" for r in n)
        assert f"{t} lignes sur {len(n)} tiennent leur tolérance en {annee}" in texte
    # Chaque ligne hors de sa tolérance est nommée dans la vue de son année, avec son écart.
    for r in notees:
        if r["verdict"] == "hors de la tolérance":
            assert f"{r['ligne']} : {france.pct(r['ecart'])}" in texte, r["id"]
    # Chaque total publié de la grille a sa source cliquable.
    for r in rows:
        if r.get("url"):
            assert html.escape(r["url"]) in page.corps, r["id"]


def test_la_page_se_lit_sans_script():
    page = france.page()
    assert "<noscript>" in page.corps
    # Sans script, les trois années sont là, aucune n'est cachée.
    for annee in france.ANNEES:
        assert re.search(rf'<section class="vue-annee" data-annee="{annee}"[^>]*>',
                         page.corps)
    assert 'class="vue-annee" data-annee="2022" hidden' not in page.corps


def test_la_page_dit_le_perimetre_des_salaires_et_la_population_unique():
    """Relecture adverse : la ligne des salaires déclarés suit en partie un total calé, et
    les trois années sont une seule population ramenée en arrière."""
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", france.page().corps)))
    assert "n'en est pas indépendante" in texte
    assert "Ces trois années ne sont pas trois épreuves." in texte
    assert "38,74 M en 2022, en 2023 et en 2024" in texte
    assert "Le rang de chacun dans la distribution vient de l'enquête" not in texte


def test_les_liens_morts_de_margins_ne_sont_pas_affiches():
    """Les deux URL mortes de margins.py, corrigées à la source (D-378)."""
    corps = france.page().corps
    for mort in ("https://www.insee.fr/fr/statistiques/8268533",
                 "https://www.securite-sociale.fr/la-secu-en-detail/"
                 "comptes-de-la-securite-sociale"):
        assert html.escape(mort) not in corps
    assert html.escape("https://www.insee.fr/fr/statistiques/9005622?geo=FE-1") in corps


def test_les_lignes_calees_par_le_non_recours_sont_marquees_sans_changer_le_compte():
    """Seconde relecture adverse : le calage du non-recours impose la part des ayants
    droit servis ; les lignes des foyers servis sont marquées, le compte préenregistré ne
    bouge pas, et la page dit combien des lignes tenues sont de celles-là."""
    page = france.page()
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", page.corps)))
    rows = _grille()
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    calees = [r for r in notees if r["id"] in france.CALEES_PAR_LE_RECOURS
              and r["verdict"] == "dans la tolérance"]
    assert len(calees) == 2  # rsa_foyers_servis, 2023 et 2024
    assert "84 lignes notées sur 113 tiennent leur tolérance (dont 2 calées par le " \
           "non-recours" in texte
    for ident in france.CALEES_PAR_LE_RECOURS:
        ligne = re.search(rf'<tr id="ligne-{ident}">(.*?)</tr>', page.corps, re.S)[1]
        notees_ici = [r for r in notees if r["id"] == ident]
        assert ligne.count(france.MARQUE_RECOURS) == len(notees_ici), ident


def test_le_non_recours_est_decrit_par_son_vrai_calage():
    """Le calage vise le milieu de la fourchette de la Drees en foyers (35 % pour le RSA,
    50 % pour la prime), pas des allocataires ; le pont de la prime dit 42 % en montant."""
    texte = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", france.page().corps)))
    # `\s+` a ramené les espaces fines et insécables à des espaces : on compare ainsi.
    assert "35 % pour le RSA (la Drees dit 33 à 37 %)" in texte
    assert "50 % pour la prime (48 à 52 %)" in texte
    assert "un non-recours d'environ 42 % des montants" in texte
    assert "calée sur les allocataires que compte la Drees" not in texte
