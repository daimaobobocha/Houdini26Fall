"""Deterministic convex-proxy drop packing. Units: meters. No external Python packages beyond NumPy.

Collision proxies are enclosing 26-DOPs. The complete separating-axis test includes
both face normals and crossed edge directions. A vertical configuration-space sweep
finds the first contact, rather than checking only sparse simulation frames.
"""
import itertools
import math
import numpy as np

GAP=.003

def canonical(vectors,precision=7):
    a=np.asarray(vectors,dtype=float).reshape((-1,3))
    norm=np.linalg.norm(a,axis=1);a=a[norm>1.e-9]/norm[norm>1.e-9,None]
    idx=np.argmax(np.abs(a),axis=1)
    a*=np.where(a[np.arange(len(a)),idx]<0,-1.,1.)[:,None]
    return np.unique(np.round(a,precision),axis=0)

def make_proxy(vertices):
    vertices=np.asarray(vertices,dtype=float)
    directions=np.array([v for v in itertools.product([-1,0,1],repeat=3) if v!=(0,0,0)],dtype=float)
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    support=np.max(vertices@directions.T,axis=0)+1.e-5
    triples=np.array(list(itertools.combinations(range(26),3)))
    matrices=directions[triples];det=np.linalg.det(matrices)
    valid=np.abs(det)>1.e-8;matrices=matrices[valid];triples=triples[valid]
    pts=np.linalg.solve(matrices,support[triples][...,None])[...,0]
    pts=pts[np.all(pts@directions.T<=support[None,:]+1.e-9,axis=1)]
    pts=np.unique(np.round(pts,9),axis=0)
    faces=[];normals=[];edge_vectors=[]
    for normal,d in zip(directions,support):
        ids=np.where(np.abs(pts@normal-d)<2.e-8)[0]
        if len(ids)<3:continue
        center=pts[ids].mean(axis=0)
        u=pts[ids[0]]-center;u/=np.linalg.norm(u);v=np.cross(normal,u)
        angles=np.arctan2((pts[ids]-center)@v,(pts[ids]-center)@u)
        ids=ids[np.argsort(angles)]
        faces.append(ids.tolist());normals.append(normal)
        for i,j in zip(ids,np.roll(ids,-1)):edge_vectors.append(pts[j]-pts[i])
    normals=canonical(normals);edges=canonical(edge_vectors)
    # Every render vertex must be enclosed by every proxy halfspace.
    assert np.max(vertices@directions.T-support)<1.e-6
    return {'vertices':pts.tolist(),'normals':normals.tolist(),'edges':edges.tolist(),'faces':faces}

def rotation(rx,ry,rz):
    x,y,z=np.radians([rx,ry,rz]);cx,sx=np.cos(x),np.sin(x);cy,sy=np.cos(y),np.sin(y);cz,sz=np.cos(z),np.sin(z)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1.]])@np.array([[cy,0,sy],[0,1.,0],[-sy,0,cy]])@np.array([[1.,0,0],[0,cx,-sx],[0,sx,cx]])

def oriented(asset,R):
    proxy=asset['proxy']
    verts=np.asarray(proxy['vertices'])@R.T
    return {'vertices':verts,'normals':np.asarray(proxy['normals'])@R.T,
            'edges':np.asarray(proxy['edges'])@R.T,'lo':verts.min(axis=0),'hi':verts.max(axis=0),'R':R}

def axes_for(a,b):
    cross=np.cross(a['edges'][:,None,:],b['edges'][None,:,:]).reshape((-1,3))
    return canonical(np.concatenate([a['normals'],b['normals'],cross]))

def drop_contact(a,x,z,b):
    if x+a['hi'][0]+GAP<b['lo'][0] or x+a['lo'][0]-GAP>b['hi'][0] or z+a['hi'][2]+GAP<b['lo'][2] or z+a['lo'][2]-GAP>b['hi'][2]:return None
    axes=axes_for(a,b)
    av=a['vertices']@axes.T
    bv=b['vertices']@axes.T
    offset=x*axes[:,0]+z*axes[:,2]
    low=bv.min(axis=0)-av.max(axis=0)-offset-GAP
    high=bv.max(axis=0)-av.min(axis=0)-offset+GAP
    ay=axes[:,1];horizontal=np.abs(ay)<1.e-8
    if np.any((low[horizontal]>0)|(high[horizontal]<0)):return None
    low=low[~horizontal]/ay[~horizontal];high=high[~horizontal]/ay[~horizontal]
    bottom=np.minimum(low,high).max();top=np.maximum(low,high).min()
    return float(top) if bottom<=top+1.e-9 else None

def overlap(a,b,tolerance=1.e-7):
    if np.any(a['hi']<b['lo']-tolerance) or np.any(b['hi']<a['lo']-tolerance):return False
    axes=axes_for(a,b);av=a['vertices']@axes.T;bv=b['vertices']@axes.T
    return bool(np.all(np.minimum(av.max(axis=0),bv.max(axis=0))-np.maximum(av.min(axis=0),bv.min(axis=0))>tolerance))

def pose_for(index,rng):
    yaw=rng.uniform(-180,180)
    if index==0:rx=rng.choice([0,90]);rz=rng.uniform(-9,9)
    elif index in [1,2]:rx=rng.choice([0,90]);rz=rng.uniform(-15,15)
    elif index in [3,4,5]:rx=rng.uniform(-12,12);rz=rng.choice([0,90])+rng.uniform(-10,10)
    elif index in [6,7,9,10,12]:rx=rng.uniform(-20,20);rz=rng.uniform(-20,20)
    elif index in [8,14]:rx=90+rng.uniform(-18,18);rz=rng.uniform(-20,20)
    elif index==11:rx=rng.uniform(-20,20);rz=rng.uniform(-15,15)
    else:rx=90+rng.uniform(-20,20);rz=rng.uniform(-25,25)
    return rotation(rx,yaw,rz)

def generate(assets,length,width,height,density,upright_barrels=False):
    length=max(.5,float(length));width=max(.5,float(width));height=max(.5,float(height))
    density=float(np.clip(density,0,100))
    target=0 if density==0 else max(1,int(round(length*width*(density/100)*32)))
    # Density means requested items per footprint area; actual count is capacity limited.
    target=min(target,600)
    rng=np.random.default_rng(73419)
    results=[];placed=[]
    weights=np.array([.35,.8,.9,.55,.8,1.,1.1,1.1,1.1,.55,.7,.7,1.1,1.1,1.1]);weights/=weights.sum()
    if upright_barrels:weights[0]=0.;weights/=weights.sum()
    # A shuffled balanced first cycle represents every asset that can fit.
    initial=[0,9,11,3,10,1,4,12,2,5,6,7,8,13,14]
    failures=0
    for slot in range(target):
        requested=initial[slot] if slot<len(initial) else int(rng.choice(len(assets),p=weights))
        best=None
        for attempt in range(20):
            index=requested if attempt<12 else int(rng.choice(len(assets),p=weights))
            a=oriented(assets[index],np.eye(3) if upright_barrels and index==0 else pose_for(index,rng))
            xmin=-length/2-a['lo'][0]+GAP;xmax=length/2-a['hi'][0]-GAP
            zmin=-width/2-a['lo'][2]+GAP;zmax=width/2-a['hi'][2]-GAP
            if xmin>xmax or zmin>zmax or a['hi'][1]-a['lo'][1]+GAP>height:continue
            # Center-biased samples form a heap, with occasional edge samples.
            if upright_barrels and index==0:
                x=float(np.clip(-length*.27,xmin,xmax));z=float(np.clip(-width*.27,zmin,zmax))
            elif rng.random()<.8:
                x=float(np.clip(rng.normal(0,length*.20),xmin,xmax));z=float(np.clip(rng.normal(0,width*.20),zmin,zmax))
            else:x=rng.uniform(xmin,xmax);z=rng.uniform(zmin,zmax)
            y=-a['lo'][1]+GAP
            for b in placed:
                contact=drop_contact(a,x,z,b)
                if contact is not None:y=max(y,contact)
            if upright_barrels and index==0:
                if y>-a['lo'][1]+GAP+1.e-6:continue
                y=assets[index]['center_m'][1]
            if y+a['hi'][1]>height-GAP:continue
            # Favor a gentle central mound and low stable placements near the perimeter.
            score=y+.12*(x*x/(length*length)+z*z/(width*width))
            if best is None or score<best[0]:best=(score,index,a,np.array([x,y,z]))
            if attempt>=4 and best is not None:break
        if best is None:
            failures+=1
            if failures>=15:break
            continue
        failures=0;_,index,a,pos=best
        a['vertices']=a['vertices']+pos;a['lo']=a['lo']+pos;a['hi']=a['hi']+pos
        placed.append(a)
        results.append({'name':assets[index]['name'],'asset_index':index,'P':pos.tolist(),
                        'rotation':a['R'].tolist(),'id':len(results)})
    return results,placed,{'requested_count':target,'placed_count':len(results),'length_m':length,'width_m':width,
                            'height_m':height,'density_percent':density,'clearance_m':GAP}

def validate(placed,length,width,height):
    overlaps=[];outside=[]
    lower=np.array([-length/2,0,-width/2]);upper=np.array([length/2,height,width/2])
    for i,a in enumerate(placed):
        if np.any(a['lo']<lower-1.e-6) or np.any(a['hi']>upper+1.e-6):outside.append(i)
        for j in range(i):
            if overlap(a,placed[j]):overlaps.append([j,i])
    return {'overlapping_proxy_pairs':overlaps,'outside_bounds':outside,'tested_pairs':len(placed)*(len(placed)-1)//2}
