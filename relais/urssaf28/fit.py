"""Ajuste les points de la fonction des salaires horaires sur les ETP de l'Urssaf (2022),
sans reconstruire : la population donnée, rang gardé, facteur recalculé."""
import sys, json
import numpy as np, polars as pl
from impots.population import margins, incomes
S = '/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/'
U = [float(l.split()[1]) for l in open(S + 'point2/urssaf_bins.txt')][1:26]  # 1.0..3.4
U = np.array(U); U = U / U.sum()
d = pl.read_parquet(sys.argv[1]); F0 = float(sys.argv[2])
emp = d['is_salarie'].to_numpy().astype(bool)
w = d['salaire_brut_annuel'].to_numpy().astype(float)
priv = incomes._private_field(d, emp) & (w > 0)
q = d['quotite_travail'].to_numpy().astype(float)
mi = d['mois_travailles'].to_numpy().astype(np.int64)
m = np.array([bin(int(v)).count('1') for v in mi], dtype=float)
pw = d['weight'].to_numpy().astype(float); age = d['age'].to_numpy()
mm = np.where(m > 0, m, 12.0)
hrs = pw * q * mm / 12.0
h0 = np.where(priv, w / (margins.SMIC_ANNUEL_2024 * np.maximum(q, 1e-9) * mm / 12.0), 0)
raw = h0 / F0
under = priv & (raw < 4.0)
ref = under & (age >= 18) & (age <= 64)
o = np.flatnonzero(ref); o = o[np.argsort(raw[o], kind='stable')]
c = np.cumsum(pw[o]); rk = (c - pw[o] / 2) / c[-1]
rank = np.interp(raw[under], raw[o], rk)
edges = np.round(np.arange(1.0, 3.51, 0.1), 2)
def remap(points):
    v = np.array(sorted(points)); s = np.array([points[k] for k in sorted(points)])
    new = raw.copy(); new[under] = np.interp(rank, s, v)
    f = (h0[priv] * hrs[priv]).sum() / (new[priv] * hrs[priv]).sum()
    return new * f, f
def bins(h):
    hp, wp = h[priv], hrs[priv]
    b = np.histogram(hp, bins=edges, weights=wp)[0]
    return b / b.sum()
def stats(points):
    h, f = remap(points)
    b = bins(h)
    hp, wp = h[priv], hrs[priv]
    oo = np.argsort(hp); cc = np.cumsum(wp[oo]); cc = (cc - wp[oo] / 2) / cc[-1]
    qh = np.interp([.5, .7, .8, .9], cc, hp[oo])
    hr = h[ref] / f; pr = pw[ref]; op = np.argsort(hr); cp = np.cumsum(pr[op]); cp = (cp - pr[op]/2)/cp[-1]
    qp = np.interp([.5, .75, .9], cp, hr[op])
    g = lambda a, b_: 100 * b[int(round((a-1)*10)):int(round((b_-1)*10))].sum()
    return dict(f=round(f, 5), b20_25=round(g(2, 2.5), 2), b25_30=round(g(2.5, 3), 2),
                b30_35=round(g(3, 3.5), 2), b26_31=round(g(2.6, 3.1), 2), b31_35=round(g(3.1, 3.5), 2),
                b10_20=round(g(1, 2), 2),
                hsousD8=round(float((wp*(hp<2.507)).sum()/wp.sum()), 4),
                hsousD9=round(float((wp*(hp<3.346)).sum()/wp.sum()), 4),
                hsup35=round(float((wp*(hp>=3.5)).sum()/wp.sum()), 4),
                quant_h=np.round(qh, 3).tolist(), pers_Q2Q3D9_avantF=np.round(qp, 3).tolist(),
                rms_01=round(float(np.sqrt(((b[10:]-U[10:])**2).mean())*100), 3))
if __name__ == '__main__':
    base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
    d553 = {**base, 2.5: 0.864}
    print('D-553', stats(d553))
    print('D-521', stats(base))
    print('Urssaf', dict(b20_25=round(100*U[10:15].sum(),2), b25_30=round(100*U[15:20].sum(),2), b30_35=round(100*U[20:25].sum(),2), b26_31=round(100*U[16:21].sum(),2), b31_35=round(100*U[21:25].sum(),2), b10_20=round(100*U[:10].sum(),2)))
    def fit(xs, drop, targets):
        bb = {k: v for k, v in base.items() if k not in drop}
        def res(p):
            pts = {**bb, **dict(zip(xs, p))}
            b = bins(remap(pts)[0])
            return [100*(b[int(round((a-1)*10)):int(round((z-1)*10))].sum() - U[int(round((a-1)*10)):int(round((z-1)*10))].sum()) for a, z in targets]
        p0 = np.interp(xs, [2.01, 4.0], [0.75, 1.0])
        p = p0.copy()
        for it in range(30):
            r0 = np.array(res(p))
            J = np.zeros((len(r0), len(p)))
            for j in range(len(p)):
                dp = p.copy(); dp[j] += 1e-3; J[:, j] = (np.array(res(dp)) - r0) / 1e-3
            step = np.linalg.lstsq(J, -r0, rcond=None)[0]
            p = np.clip(p + step, 0.75, 0.999)
            if np.abs(step).max() < 1e-6: break
        pr = np.round(p, 3)
        pts = {**bb, **dict(zip(xs, pr))}
        print('FIT', xs, 'drop', drop, np.round(p, 4), 'résidus (arrondi 3)', np.round(res(pr), 3))
        print('   ', stats(pts))
        return pts
    T3 = [(2, 2.5), (2.5, 3), (3, 3.5)]
    fit([2.5, 3.0, 3.5], [3.04], T3)
    fit([2.5, 3.5], [], T3)
    fit([2.25, 2.5, 3.0, 3.5], [3.04], [(2, 2.25), (2.25, 2.5), (2.5, 3), (3, 3.5)] if False else [(2,2.2),(2.2,2.5),(2.5,3),(3,3.5)])
