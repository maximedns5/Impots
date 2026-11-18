import sys
S='/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/'
sys.argv=[sys.argv[0], S+'suite28/population_d553.parquet','1.022156']
exec(open(S+'urssaf28/fit.py').read().split("if __name__")[0])
base = dict(margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022)
A = {k: v for k, v in base.items() if k != 3.04}; A.update({2.5: 0.852, 3.0: 0.907, 3.5: 0.940})
for nom, pts in (('d521', base), ('d553', {**base, 2.5: 0.864}), ('A', A)):
    h, f = remap(pts); hp, wp = h[priv], hrs[priv]
    den = (wp*((hp>=1)&(hp<3.5))).sum()
    r = lambda a,b: round(100*float((wp*((hp>=a)&(hp<b))).sum()/den),2)
    print(nom, 'f', round(f,5), '[3.5;4)', r(3.5,4), '[3.9;4)', r(3.9,4.0), '[4;inf)', r(4,99), '<1', round(100*float((wp*(hp<1)).sum()/den),2), '[2.5;3.5)', r(2.5,3.5))
