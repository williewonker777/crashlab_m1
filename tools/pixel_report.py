#!/usr/bin/env python3
"""글자 주변 침범 측정: 글자 마스크를 팽창시킨 영역 안에 배경도 글자도 아닌 '이물 잉크'가 얼마나 있는지."""
import sys, glob, re, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

MAG = np.array([255,0,254])
def load(p): return np.asarray(Image.open(p).convert("RGB")).astype(np.int16)
def magenta(a): return (np.abs(a-MAG).sum(axis=2) < 150)

page=sys.argv[1]
root=os.path.join(os.path.dirname(__file__),"..",".shots","px")
rows=[]
for f in sorted(glob.glob(os.path.join(root,f"{page}-*-only.png")),
                key=lambda x:int(re.search(r"-(\d+)-only",x).group(1))):
    n=int(re.search(r"-(\d+)-only",f).group(1))
    full=f.replace("-only.png","-full.png")
    if not os.path.exists(full): continue
    ao,af=load(f),load(full)
    tm=magenta(ao)
    tot=int(tm.sum())
    if tot<50: continue
    # 글자에서 12px 이내 = 글자가 점유한 시각 영역
    near=ndi.binary_dilation(tm,iterations=12)
    ring=near & ~ndi.binary_dilation(tm,iterations=1)   # 글자 획 자체는 제외한 주변
    fm=magenta(af)
    # 이물: 링 안에서 배경(밝음)도 아니고 글자색도 아닌 픽셀
    bright=(af.sum(axis=2)>690)          # 거의 흰색/아주 연한 틴트
    foreign=ring & ~fm & ~bright
    cnt=int(foreign.sum()); ringn=int(ring.sum())
    pct=100.0*cnt/max(ringn,1)
    if pct>=1.0 and cnt>80:
        ys,xs=np.where(foreign)
        rows.append((pct,n,cnt,int(xs.min()),int(xs.max()),int(ys.min()),int(ys.max())))
rows.sort(reverse=True)
print(f"{page}: " + (f"침범 {len(rows)}장" if rows else "CLEAN"))
for pct,n,cnt,x0,x1,y0,y1 in rows:
    print(f"  s{n:<3} 침범 {pct:5.1f}%  ({cnt}px)  영역 x{x0}-{x1} y{y0}-{y1}")
