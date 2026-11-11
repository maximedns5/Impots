"""La page 8 du parcours (D-375) montre l'erreur mesurée des fichiers commités, sans
script, et n'en tait aucune."""

import html
import json
import re

from impots import parcours
from impots.parcours import erreur

GRILLE = parcours.ROOT / "reports" / "verification" / "grille.json"
REGISTRE = parcours.ROOT / "reports" / "chiffrages_preregistres.md"


def _texte(corps: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", corps)))


def test_la_page_montre_la_grille_et_chaque_ligne_hors_de_sa_tolerance():
    page = erreur.page()
    parcours._check("erreur", page)
    assert page.script == ""
    texte = _texte(page.corps)
    rows = json.loads(GRILLE.read_text(encoding="utf-8"))["lignes"]
    notees = [r for r in rows if r["usage"] == "validation" and r["ecart"] is not None]
    tenues = sum(r["verdict"] == "dans la tolérance" for r in notees)
    assert f"{tenues} sur {len(notees)} lignes tenues" in texte
    assert (tenues, len(notees)) == (84, 113)  # D-371
    hors = {r["id"] for r in notees if r["verdict"] == "hors de la tolérance"}
    for ident in hors:
        bloc = re.search(rf'<section class="hors-ligne" id="hors-{ident}">(.*?)</section>',
                         page.corps, re.S)
        assert bloc, ident
        assert ("Pas encore expliquée" in bloc[1]) != (ident in erreur.EXPLICATIONS), ident
        assert "Ce qu'elle touche." in bloc[1], ident
    # Une explication sans ligne hors de tolérance serait une explication de trop.
    assert set(erreur.EXPLICATIONS) <= hors


def test_les_juges_sont_ceux_du_registre():
    texte = _texte(erreur.page().corps)
    note = re.search(r"\*\*(\d+) sur (\d+) dans la tolérance déclarée", REGISTRE.read_text(
        encoding="utf-8"))
    assert f"{note[1]} sur {note[2]} cas aveugles" in texte
    for cas in ("plf2027_art_2", "plf2027_art_74_ppa"):
        assert f"{cas} : chiffré" in texte


def test_la_page_ne_parle_pas_la_langue_du_depot():
    """Relecture adverse : ni jargon interne, ni seconde décomposition de la prime ; L0 est
    défini à son premier emploi."""
    texte = _texte(erreur.page().corps)
    for mot in ("VERIFIE_PAR", "But 19", "but 19", "étape « al »"):
        assert mot not in texte, mot
    assert texte.index("qu'elle appelle L0") < texte.index("la loi codée : chaque taux")
    assert "Le détail est sur la page 3" in texte
    assert "ne sont donc pas trois épreuves indépendantes" in texte
