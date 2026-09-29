"""Validated reference prototype of the FuelRoute DP optimizer + LP oracle.
Verified: 300 random instances, 0 mismatches vs brute-force oracle (143 feasible / 157 infeasible).
Port into apps/planner/optimizer.py (keep the algorithm; add Decimal money, dataclasses, typing).
Candidate tuple = (M_mile_int, k_detour_burn_int, price_per_gallon). Modes: priced | free."""
import numpy as np, itertools, random
from scipy.optimize import linprog
INF=np.inf; EPS=1e-4
def shift_down(f,L):
    n=len(f); out=np.full(n,INF)
    if L<n: out[:n-L]=f[L:]
    return out
def dp(cands,MD,G,mpg,p0,mode):
    idx=np.arange(G+1)
    if mode=='priced': f=idx*(p0/mpg)
    else: f=np.full(G+1,INF); f[G]=0
    pos=0; hist=[]
    for (M,k,price) in cands:
        L=M-pos; f=shift_down(f,L); pos=M
        fd=shift_down(f,k); c=price/mpg
        A=fd-idx*c; pm=np.minimum.accumulate(A)
        arg=np.maximum.accumulate(np.where(A==pm,idx,0))
        h=idx*c+pm+EPS; visit=h<f
        f=np.where(visit,h,f); hist.append((visit,arg,k,L))
    L=MD-pos; f=shift_down(f,L); ge=int(np.argmin(f)); cost=f[ge]
    if not np.isfinite(cost): return None
    g=ge+L; buys=[]
    for i in range(len(cands)-1,-1,-1):
        visit,arg,k,Li=hist[i]
        if visit[g]:
            gd=arg[g]; buys.append((i,g-gd)); g=gd+k
        g+=Li
    return cost,g,buys[::-1]
def oracle(cands,MD,G,mpg,p0,mode):
    best=INF; n=len(cands)
    for r in range(n+1):
        for sub in itertools.combinations(range(n),r):
            # nodes: start, stops..., end. variables: buy at start (priced), buy at each stop
            nodes=[(0,0,p0)]+[cands[i] for i in sub]
            m=len(nodes); cost=[nodes[j][2]/mpg for j in range(m)]
            # fuel after node j: F_j = sum buys<=j - burn ; burn = legs + detours k of visited stops
            # constraints: fuel arriving at node j (before detour) >=k_j ... use cumulative
            A=[];b=[]
            pos=[nodes[j][0] for j in range(m)]
            ks=[nodes[j][1] for j in range(m)]
            for j in range(m):
                # arrive at route pt j: fuel = sum_{t<j} x_t - pos[j] - sum_{t<j} ks[t] ; after detour subtract ks[j]
                # need after detour >=0 (before buying at j) and after buy <=G
                A.append([-1 if t<j else 0 for t in range(m)]); b.append(-(pos[j]+sum(ks[:j+1])))
                A.append([1 if t<=j else 0 for t in range(m)]); b.append(G+pos[j]+sum(ks[:j+1]) - 0)
            # after buy at j: sum_{t<=j}x_t - pos[j]-sum ks[:j+1] <= G  (included above)
            # end: fuel>=0
            A.append([-1]*m); b.append(-(MD+sum(ks)))
            bounds=[(0,None)]*m
            if mode=='free':
                bounds[0]=(G,G); cost[0]=0
            res=linprog(cost,A_ub=A,b_ub=b,bounds=bounds,method='highs')
            if res.success:
                c=res.fun+EPS*len(sub)
                best=min(best,c)
    return best
random.seed(1); bad=0; feas=0; inf=0; worst=0
for t in range(300):
    G=random.choice([20,30,50]); MD=random.randint(10,120)
    n=random.randint(0,6)
    cands=sorted([(random.randint(0,MD),random.randint(0,4),round(random.uniform(2.5,4.5),3)) for _ in range(n)],key=lambda x:(x[0],x[2]))
    mode=random.choice(['priced','free']); p0=round(random.uniform(3,4),3)
    d=dp(cands,MD,G,10,p0,mode); o=oracle(cands,MD,G,10,p0,mode)
    if d is None:
        inf+=1
        if o<INF: bad+=1; print("DP says infeasible but oracle feasible",t)
    else:
        feas+=1; diff=abs(d[0]-o); worst=max(worst,diff)
        if diff>1e-6: bad+=1; print("mismatch",t,d[0],o,cands,MD,G,mode)
print("instances 300 feasible",feas,"infeasible",inf,"bad",bad,"max diff",worst)
# reconstruction check: replay
c=[(5,1,3.0),(40,2,3.5),(70,0,2.8)]
r=dp(c,100,50,10,3.6,'priced'); print(r)
