"""Les grandeurs de contrôle, en proxy (Python, sans openfisca), sur trois populations."""
import sys
import numpy as np, polars as pl
from impots.population import margins, incomes
S = '/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/'
def load(path):
    d = pl.read_parquet(path)
    emp = d['is_salarie'].to_numpy().astype(bool)
    w = d['salaire_brut_annuel'].to_numpy().astype(float)
    priv = incomes._private_field(d, emp) & (w > 0)
    q = d['quotite_travail'].to_numpy().astype(float)
    mi = d['mois_travailles'].to_numpy().astype(np.int64)
    m = np.array([bin(int(v)).count('1') for v in mi], dtype=float); mm = np.where(m > 0, m, 12.0)
    pw = d['weight'].to_numpy().astype(float)
    x = np.where(priv, w / (margins.SMIC_ANNUEL_2024 * np.maximum(q, 1e-9) * mm / 12.0), 0)
    return dict(w=w[priv], x=x[priv], pw=pw[priv], hrs=(pw*q*mm/12)[priv])
def proxies(p, w=None, x=None):
    w = p['w'] if w is None else w; x = p['x'] if x is None else x; pw = p['pw']
    M = pw * w
    out = {}
    out['masse'] = M.sum()
    out['BM'] = M[x <= 2.5].sum()
    out['BF'] = M[x <= 3.5].sum()
    out['RG'] = (M * np.where(x < 1.6, 0.3194 / 0.6 * (1.6 / np.maximum(x, 1e-9) - 1), 0)).sum()
    out['L531'] = M[(x >= 2.5) & (x < 3.5)].sum() / M[x < 3.5].sum()
    y = x / 1.0429
    c26 = 0.02 + 0.3821 * np.clip(0.5 * (3 / np.maximum(y, 1e-9) - 1), 0, None) ** 1.75
    out['EXO'] = (M * c26 * ((y >= 2) & (y < 3))).sum()
    out['EXO_a'] = (M * c26 * ((y >= 2) & (y < 2.5))).sum()
    out['EXO_b'] = (M * c26 * ((y >= 2.5) & (y < 3))).sum()
    return out
if __name__ == '__main__':
    pops = {k: load(S + f'suite28/population_{k}.parquet') for k in ('d521', 'd553')}
    r = {k: proxies(v) for k, v in pops.items()}
    # la population A en mémoire, depuis D-553
    sys.argv = [sys.argv[0], S + 'suite28/population_d553.parquet', '1.022156']
    exec(open(S + 'urssaf28/fit.py').read().split("if __name__")[0])
    base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
    A = {k: v for k, v in base.items() if k != 3.04}; A.update({2.5: 0.852, 3.0: 0.907, 3.5: 0.940})
    h, f = remap(A)
    p = pops['d553']
    hp = h[priv]; wnew = hp * margins.SMIC_ANNUEL_2024 * np.maximum(q[priv], 1e-9) * mm[priv] / 12
    # vérifie : le remap de D-553 sur lui-même
    hB, fB = remap({**base, 2.5: 0.864})
    print('auto-reproduction D-553 : écart max des x', float(np.abs(hB[priv] - p['x']).max()), 'facteur', fB)
    r['A'] = proxies(p, w=wnew, x=hp)
    keys = list(r['d553'])
    for k in keys:
        print(f"{k:6} d521 {r['d521'][k]:.6g}  d553 {r['d553'][k]:.6g}  A {r['A'][k]:.6g}   d553/d521 {r['d553'][k]/r['d521'][k]:.4f}  A/d553 {r['A'][k]/r['d553'][k]:.4f}")
