"""Minimal static contact correction after native Bullet, using the actual compound hulls."""
import json
import numpy as np

def axes_unique(a):
    a=np.asarray(a).reshape(-1,3);n=np.linalg.norm(a,axis=1);a=a[n>1e-9]/n[n>1e-9,None]
    idx=np.argmax(np.abs(a),axis=1);a*=np.where(a[np.arange(len(a)),idx]<0,-1.,1.)[:,None]
    return np.unique(np.round(a,7),axis=0)

def separation(a,b):
    axes=axes_unique(np.concatenate([a['normals'],b['normals'],np.cross(a['edges'][:,None,:],b['edges'][None,:,:]).reshape(-1,3)]))
    ap=a['vertices']@axes.T;bp=b['vertices']@axes.T
    amin=ap.min(axis=0);amax=ap.max(axis=0);bmin=bp.min(axis=0);bmax=bp.max(axis=0)
    overlaps=np.minimum(amax,bmax)-np.maximum(amin,bmin)
    if np.any(overlaps<=1.e-7):return None
    positive=bmax-amin+.0003;negative=bmin-amax-.0003
    vectors=np.concatenate([axes*positive[:,None],axes*negative[:,None]])
    return vectors[np.argsort(np.linalg.norm(vectors,axis=1))]

def clean_contacts(visual,proxy,metadata,L,W,H):
    bodies=[]
    mass=[18.,3.,1.5,12.,6.,3.6,5.,2.,1.8,18.,8.,6.,3.,4.,.8]
    for prim in proxy.prims():
        name=prim.stringAttribValue('name');asset=prim.stringAttribValue('asset_name')
        m=np.array(prim.fullTransform().asTuple()).reshape(4,4);R=m[:3,:3];t=m[3,:3]
        parts=[]
        for h in metadata[asset]:
            v=np.asarray(h['vertices'])@R+t
            parts.append({'vertices':v,'normals':np.asarray(h['normals'])@R,'edges':np.asarray(h['edges'])@R,'lo':v.min(axis=0),'hi':v.max(axis=0)})
        bodies.append({'name':name,'asset':asset,'parts':parts,'lo':np.min([p['lo'] for p in parts],axis=0),
                       'hi':np.max([p['hi'] for p in parts],axis=0),'lows':np.array([p['lo'] for p in parts]),
                       'highs':np.array([p['hi'] for p in parts]),'mass':mass[int(asset.split('_')[1])-1],
                       'fixed':'OilBarrel' in asset,'delta':np.zeros(3)})
    def collision_free(mover,delta):
        for other in bodies:
            if other is mover:continue
            if np.any(mover['hi']+delta<other['lo']) or np.any(other['hi']<mover['lo']+delta):continue
            mask=np.all(mover['highs'][:,None,:]+delta>other['lows'][None,:,:],axis=2)&np.all(other['highs'][None,:,:]>mover['lows'][:,None,:]+delta,axis=2)
            for ai,bi in np.argwhere(mask):
                part=mover['parts'][ai]
                moved={'vertices':part['vertices']+delta,'normals':part['normals'],'edges':part['edges']}
                if separation(moved,other['parts'][bi]) is not None:return False
        return True
    count=0
    for iteration in range(30):
        corrected=False
        for i,a in enumerate(bodies):
            for b in bodies[:i]:
                if np.any(a['hi']<b['lo']) or np.any(b['hi']<a['lo']):continue
                mask=np.all(a['highs'][:,None,:]>b['lows'][None,:,:],axis=2)&np.all(b['highs'][None,:,:]>a['lows'][:,None,:],axis=2)
                for ai,bi in np.argwhere(mask):
                    choices=separation(a['parts'][ai],b['parts'][bi])
                    if choices is None:continue
                    mover=a
                    if a['fixed'] or (not b['fixed'] and b['mass']<a['mass']):mover=b;choices=-choices
                    if mover['fixed']:raise RuntimeError('Two static colliders intersect')
                    # Preserve floor and container bounds during the minimal correction.
                    low=np.array([-L/2,.00001,-W/2])-mover['lo']
                    high=np.array([L/2,H,W/2])-mover['hi']
                    valid=np.all(choices>=low-1.e-8,axis=1)&np.all(choices<=high+1.e-8,axis=1)
                    if not np.any(valid):raise RuntimeError('No bounds-safe contact correction')
                    candidates=list(choices[valid][:64])
                    # A compound may have multiple simultaneous contacts. Search a tiny
                    # horizontal neighborhood without sacrificing a ground support.
                    for distance in np.concatenate([np.arange(.001,.051,.001),np.arange(.055,.405,.005)]):
                        for angle in np.arange(16)*np.pi/8:
                            d=np.array([np.cos(angle)*distance,0.,np.sin(angle)*distance])
                            if np.all(d>=low-1.e-8) and np.all(d<=high+1.e-8):candidates.append(d)
                    candidates.sort(key=lambda v:np.linalg.norm(v))
                    delta=next((d for d in candidates if collision_free(mover,d)),None)
                    if delta is None:raise RuntimeError('No collision-free local contact correction for '+mover['name']+' '+mover['asset'])
                    mover['delta']+=delta
                    for p in mover['parts']:p['vertices']+=delta;p['lo']+=delta;p['hi']+=delta
                    for key in ['lo','hi','lows','highs']:mover[key]+=delta
                    corrected=True;count+=1
                    break
        if not corrected:break
    else:raise RuntimeError('Contact correction did not converge')
    byname={b['name']:b['delta'] for b in bodies}
    for g in [visual,proxy]:
        for p in g.prims():
            delta=byname[p.stringAttribValue('name')]
            if np.linalg.norm(delta)>0:
                point=p.points()[0];point.setPosition(point.position()+__import__('hou').Vector3(tuple(delta)))
        if g.findGlobalAttrib('contact_cleanup') is None:g.addAttrib(__import__('hou').attribType.Global,'contact_cleanup','')
        g.setGlobalAttribValue('contact_cleanup',json.dumps({k:v.tolist() for k,v in byname.items() if np.linalg.norm(v)>0}))
    return visual,proxy,{'corrections':count,'max_translation_m':max([float(np.linalg.norm(v)) for v in byname.values()],default=0.),
                        'moved':{k:v.tolist() for k,v in byname.items() if np.linalg.norm(v)>0}}
