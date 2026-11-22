"""Programme linéaire de production d'ISCompany, résolu avec HiGHS.

Quatre produits fabriqués à partir d'une seule matière première :

    max  4 x1 + 6 x2 + 7 x3 + 8 x4                 (bénéfice, en €)
    s.c. x1 + x2 + x3 + x4 = 950                  (ventes totales)
         x4 >= 400                                (demande minimale du produit 4)
         2 x1 + 3 x2 + 4 x3 + 7 x4 <= 4600        (matière première, en unités)
         3 x1 + 4 x2 + 5 x3 + 6 x4 <= 5000        (heures de travail)
         x1, x2, x3, x4 >= 0
"""

from dataclasses import dataclass, field

import highspy
import numpy as np

PRODUITS = ["P1", "P2", "P3", "P4"]
CONTRAINTES = ["Ventes totales", "Demande min. P4", "Matière première", "Heures de travail"]

BENEFICE = (4.0, 6.0, 7.0, 8.0)
MATIERE = (2.0, 3.0, 4.0, 7.0)
HEURES = (3.0, 4.0, 5.0, 6.0)


@dataclass
class Donnees:
    benefice: tuple = BENEFICE
    ventes: float = 950
    demande_p4: float | None = 400   # None : contrainte supprimée
    matiere: float = 4600
    heures: float = 5000


@dataclass
class Resultat:
    profit: float
    x: np.ndarray
    prix_duaux: np.ndarray            # valeur marginale de chaque contrainte (€ par unité de second membre)
    couts_reduits: np.ndarray
    ecarts: np.ndarray                # marge non utilisée de chaque contrainte
    plages_couts: list = field(default_factory=list)   # [(min, max)] du bénéfice unitaire gardant la base optimale
    plages_seconds_membres: list = field(default_factory=list)


def resoudre(d: Donnees = Donnees()) -> Resultat:
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    inf = highspy.kHighsInf
    idx = np.arange(4, dtype=np.int32)
    for _ in range(4):
        h.addVar(0, inf)
    h.changeColsCost(4, idx, np.array(d.benefice, float))
    h.changeObjectiveSense(highspy.ObjSense.kMaximize)

    lignes = [
        ((1, 1, 1, 1), d.ventes, d.ventes),
        ((0, 0, 0, 1), d.demande_p4 if d.demande_p4 is not None else 0.0, inf),
        (MATIERE, -inf, d.matiere),
        (HEURES, -inf, d.heures),
    ]
    for coef, bas, haut in lignes:
        h.addRow(bas, haut, 4, idx, np.array(coef, float))

    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise ValueError(f"Pas de solution optimale : {h.modelStatusToString(h.getModelStatus())}")

    sol = h.getSolution()
    x = np.array(sol.col_value)
    activite = np.array(sol.row_value)
    seconds = np.array([d.ventes, d.demande_p4 or 0.0, d.matiere, d.heures])
    ecarts = np.abs(seconds - activite)
    ecarts[0] = 0.0  # contrainte d'égalité

    status, r = h.getRanging()
    plages_c = [(r.col_cost_dn.value_[j], r.col_cost_up.value_[j]) for j in range(4)]
    plages_b = [(r.row_bound_dn.value_[i], r.row_bound_up.value_[i]) for i in range(4)]
    return Resultat(
        profit=float(h.getInfo().objective_function_value),
        x=np.round(x, 6) + 0.0,
        prix_duaux=np.round(np.array(sol.row_dual), 6) + 0.0,
        couts_reduits=np.round(np.array(sol.col_dual), 6) + 0.0,
        ecarts=np.round(ecarts, 6) + 0.0,
        plages_couts=plages_c,
        plages_seconds_membres=plages_b,
    )


def resoudre_dual(d: Donnees = Donnees()) -> tuple[float, np.ndarray]:
    """Programme dual (min 950 y1 + 400 y2 + 4600 y3 + 5000 y4), résolu séparément pour vérifier la dualité forte."""
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    inf = highspy.kHighsInf
    idx = np.arange(4, dtype=np.int32)
    h.addVar(-inf, inf)   # y1 libre (contrainte d'égalité)
    h.addVar(-inf, 0)     # y2 <= 0 (contrainte « >= » dans un maximum)
    h.addVar(0, inf)      # y3 >= 0
    h.addVar(0, inf)      # y4 >= 0
    h.changeColsCost(4, idx, np.array([d.ventes, d.demande_p4 or 0.0, d.matiere, d.heures], float))
    colonnes = np.array([(1, 1, 1, 1), (0, 0, 0, 1), MATIERE, HEURES], float)  # une ligne par variable duale
    for j in range(4):
        h.addRow(d.benefice[j], inf, 4, idx, colonnes[:, j])
    h.run()
    return float(h.getInfo().objective_function_value), np.round(np.array(h.getSolution().col_value), 6) + 0.0
