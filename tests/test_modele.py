"""Vérifie que le modèle retrouve les résultats du solveur LINGO utilisés dans le rapport."""

from dataclasses import replace

import numpy as np
import pytest

from src import analyses
from src.modele import Donnees, resoudre, resoudre_dual


def test_solution_optimale():
    r = resoudre()
    assert r.profit == pytest.approx(6650)
    np.testing.assert_allclose(r.x, [0, 400, 150, 400], atol=1e-6)


def test_prix_duaux_et_couts_reduits():
    r = resoudre()
    np.testing.assert_allclose(r.prix_duaux, [3, -2, 1, 0], atol=1e-6)
    assert r.couts_reduits[0] == pytest.approx(-1)  # P1 devient rentable à partir de +1 €
    assert r.ecarts[3] == pytest.approx(250)        # 250 heures non utilisées


def test_dualite_forte():
    z, y = resoudre_dual()
    assert z == pytest.approx(6650)
    np.testing.assert_allclose(y, [3, -2, 1, 0], atol=1e-6)


def test_plage_matiere_premiere():
    lo, hi = resoudre().plages_seconds_membres[2]
    assert (lo, hi) == (pytest.approx(4450), pytest.approx(4850))


@pytest.mark.parametrize("modif, profit", [
    (dict(benefice=(4, 6.5, 7, 8)), 6850),
    (dict(benefice=(4.6, 6, 7, 8)), 6650),
    (dict(benefice=(4, 6, 6.4, 8)), 6575),
    (dict(ventes=980), 6740),
    (dict(matiere=4500), 6550),
    (dict(matiere=4400), 6400),
    (dict(ventes=1050, matiere=5100), 7100),
])
def test_scenarios(modif, profit):
    assert resoudre(replace(Donnees(), **modif)).profit == pytest.approx(profit)


def test_paliers_parametriques():
    p = analyses.paliers(analyses.parametrique_matiere())
    np.testing.assert_allclose(p["valeur_marginale"].to_numpy(), [2, 1, 1 / 3, 0], atol=1e-3)


def test_delai_recuperation():
    t = analyses.investissement(gain_mensuel=450, taux=0.10, annees=10)
    assert t["gain_actualise"].iloc[1] == pytest.approx(5400 / 1.1)
    d = analyses.delai_recuperation(t, 30_000)
    assert 7 < d < 8
