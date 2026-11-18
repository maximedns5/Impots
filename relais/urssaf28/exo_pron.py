import sys
S='/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/'
sys.argv=[sys.argv[0], S+'suite28/population_d553.parquet','1.022156']
exec(open(S+'urssaf28/fit.py').read().split("if __name__")[0])
base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
A = {k: v for k, v in base.items() if k != 3.04}; A.update({2.5: 0.852, 3.0: 0.907, 3.5: 0.940})
def parts(h):
    hp, wp = h[priv], hrs[priv]; t = wp.sum()
    return [float((wp*((hp>=a)&(hp<b))).sum()/t) for a,b in ((2.086,2.607),(2.607,3.129))]
for nom, pts in (('d553', {**base, 2.5: 0.864}), ('d521', base), ('A', A)):
    print(nom, np.round(np.array(parts(remap(pts)[0]))*100, 3))
