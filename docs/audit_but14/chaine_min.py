# Re-implementation minimale de chaine.run (vue mecanique + boucle), pour un choc IR permanent
import time
b0,r,Y0,p0,s0=1.15693757321829,0.01882827582292081,2991.056e9,-0.029870353480509815,0.5505
real,pr=0.01,0.02; g=(1+real)*(1+pr)-1
M={1:0.41,2:0.83,3:0.88}; F={1:0.19,2:0.50,3:0.58}; SD=0.66   # IR Mesange, TAX WP117
def run(cost_share, theta, pers, H=10):
    Y=Y0; s=s0; R=p0+s0; b=b0; ref=[]; Ys=[]
    for t in range(H):
        Y*=1+g; s*=(1+pr)/(1+g); b=b*(1+r)/(1+g)-(R-s); ref.append(b); Ys.append(Y)
    units=[cost_share*100]*H  # choc permanent en points de PIB
    gap=[];phi=[]
    for k in range(H):
        y=f=0.0
        for j in range(k+1):
            st=units[j]-(units[j-1] if j else 0)
            if not st: continue
            h=k-j+1
            if h>3:
                if pers=='eteint': continue
                h=3
            m=M[h]+(2*theta-1)*SD
            y+=st*m/100; f+=st*F[h]*m/M[h]/100
        gap.append(y); phi.append(f)
    D=0; out=[]
    for k in range(H):
        D=D*(1+r)/(1+g)+cost_share-phi[k]
        out.append(((ref[k]+D)/(1+gap[k])-ref[k])*100)
    return out
t=time.perf_counter()
for pers in ('eteint','tenu'):
    for th in (0,0.5,1):
        o=run(0.01,th,pers); print(pers,th,[round(x,2) for x in o])
print('mecanique',[round(x,2) for x in run(0.01,0.5,'eteint')][:1])
n=1000
t=time.perf_counter()
for _ in range(n): run(0.01,0.5,'tenu')
print('ms par chemin', (time.perf_counter()-t)/n*1000)
