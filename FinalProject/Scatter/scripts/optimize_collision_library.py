"""Shape-aware convex grouping: enclose every render face while retaining principal holes."""
import os,json,math,time
from collections import defaultdict
import numpy as np
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
with open(ROOT+'/geo/scatter_asset_library.json') as f:assets=json.load(f)
old=hou.Geometry();old.loadFromFile(ROOT+'/geo/scatter_bullet_compounds.bgeo.sc')
hou.hipFile.clear(suppress_save_prompt=True)
obj=hou.node('/obj').createNode('geo','build_optimized_proxies')
stash=obj.createNode('stash');hullnode=obj.createNode('shrinkwrap');hullnode.setInput(0,stash)
hullnode.parm('removeinlinepoints').set(0)
output=hou.Geometry();output.addAttrib(hou.attribType.Prim,'name','');output.addAttrib(hou.attribType.Prim,'segment',0)
metadata={};stats={};proof={};serial=0

def unique_axes(a):
    a=np.asarray(a,dtype=float).reshape(-1,3);n=np.linalg.norm(a,axis=1);a=a[n>1e-10]/n[n>1e-10,None]
    idx=np.argmax(np.abs(a),axis=1);a*=np.where(a[np.arange(len(a)),idx]<0,-1.,1.)[:,None]
    return np.unique(np.round(a,7),axis=0)

def record(g):
    points=np.array([tuple(p.position()) for p in g.points()]);normals=[];edges=[]
    for face in g.prims():
        n=tuple(face.normal())
        if np.linalg.norm(n)>1e-10:normals.append(n)
        poly=[np.asarray(tuple(p.position())) for p in face.points()]
        edges.extend([b-a for a,b in zip(poly,poly[1:]+poly[:1])])
    return {'vertices':points.tolist(),'normals':unique_axes(normals).tolist(),'edges':unique_axes(edges).tolist()}

def append_hull(name,positions):
    global serial
    positions=np.unique(np.round(positions,9),axis=0)
    geom=hou.Geometry();geom.createPoints(positions.tolist())
    if len(positions)<4 or np.linalg.matrix_rank(positions-positions.mean(axis=0),tol=1e-7)<3:
        # Give an exactly planar face a microscopic thickness, never shrink it.
        geom.clear();geom.createPoints(np.concatenate([positions+[0,0,1e-5],positions+[0,0,-1e-5],positions+[0,1e-5,0],positions+[0,-1e-5,0]]).tolist())
    stash.parm('stash').set(geom);hull=hullnode.geometry().freeze()
    if not hull.prims():raise RuntimeError('Empty hull for '+name)
    normals=[];offsets=[];center=np.mean([tuple(p.position()) for p in hull.points()],axis=0)
    for face in hull.prims():
        n=np.array(tuple(face.normal()));p=np.array(tuple(face.points()[0].position()))
        if np.dot(n,center-p)>0:n=-n
        normals.append(n);offsets.append(np.dot(n,p))
    normals=np.asarray(normals);offsets=np.asarray(offsets)
    distances=offsets-normals@center
    if np.min(distances)<=1e-10:raise RuntimeError('Degenerate convex proxy: '+name)
    scale=max(1.,float(np.max(((positions-center)@normals.T)/distances)))+1e-6
    for point in hull.points():point.setPosition(hou.Vector3((center+(np.asarray(tuple(point.position()))-center)*scale).tolist()))
    error=float(np.max((positions-center)@normals.T-distances*scale))
    if error>2e-6:raise RuntimeError('Proxy under-covers source face: '+name+' '+str(error))
    proof[name]=max(proof.get(name,0),error)
    hull.addAttrib(hou.attribType.Prim,'name',name);hull.addAttrib(hou.attribType.Prim,'segment',serial)
    for p in hull.prims():p.setAttribValue('name',name);p.setAttribValue('segment',serial)
    metadata.setdefault(name,[]).append(record(hull));output.merge(hull);serial+=1

def components(asset):
    parent=list(range(len(asset['vertices'])))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for face in asset['faces']:
        root=find(face[0])
        for v in face[1:]:parent[find(v)]=root
    groups=defaultdict(list)
    for i,f in enumerate(asset['faces']):groups[find(f[0])].append(i)
    return list(groups.values())

def sector(x,z,n,phase=0.):return int(math.floor((math.atan2(z,x)/(2*math.pi)+phase)%1*n))

start=time.time()
for asset in assets:
    name=asset['name'];number=int(name.split('_')[1]);v=np.asarray(asset['vertices']);world=v+asset['center_m'];faces=asset['faces']
    buckets=defaultdict(list)
    if number==1:buckets['solid_barrel']=list(range(len(faces)))
    elif number in [2,3]:
        r,wire,h,turns=(.088,.0105,.4,6.5) if number==2 else (.057,.0075,.27,6.)
        count=int(turns*8)
        def height(t):
            u=t*turns
            if u<1:return wire*2*u
            if u>turns-1:return h-wire*2-wire*2*(turns-u)
            return wire*2+(h-wire*6)*(u-1)/(turns-2)
        centers=[]
        for t in (np.arange(count)+.5)/count:
            a=2*math.pi*turns*t;centers.append([r*math.cos(a),height(t)+wire,r*math.sin(a)])
        centers=np.asarray(centers)
        for i,f in enumerate(faces):buckets[int(np.argmin(np.sum((centers-world[f].mean(axis=0))**2,axis=1)))].append(i)
    elif number in [10,11]:
        for component in components(asset):
            ids=np.unique([p for i in component for p in faces[i]])
            radial=np.linalg.norm(world[ids][:,[0,2]],axis=1)
            if radial.max()>.24:kind='tire'
            elif radial.min()>.16 and radial.max()>.19:kind='rim_barrel'
            elif radial.min()<.07 and radial.max()>.16:kind='rim_disc'
            else:kind='small_'+str(component[0])
            for i in component:
                c=world[faces[i]].mean(axis=0);r=np.linalg.norm(c[[0,2]])
                if kind=='tire':key=(kind,sector(c[0],c[2],24))
                elif kind=='rim_barrel':key=(kind,0 if c[1]<.06 else (1 if c[1]<.17 else 2),sector(c[0],c[2],16))
                elif kind=='rim_disc':
                    if r<.100:key=('hub_ring',sector(c[0],c[2],16))
                    elif r>.150:key=('disc_outer_ring',sector(c[0],c[2],16))
                    else:key=('spoke',sector(c[0],c[2],10,.05))
                else:key=kind
                buckets[key].append(i)
    elif number==7:
        for i,f in enumerate(faces):
            c=world[f].mean(axis=0);r=np.linalg.norm(c[[0,2]])
            key=('outer_disc',sector(c[0],c[2],16)) if r>.077 else ('hub',sector(c[0],c[2],12))
            buckets[key].append(i)
    elif number==8:
        for i,f in enumerate(faces):
            c=world[f].mean(axis=0);buckets[sector(c[0],c[2],22)].append(i)
    elif number==9:
        for component in components(asset):
            ids=np.unique([p for i in component for p in faces[i]]);points=world[ids];lo=points.min(axis=0);hi=points.max(axis=0)
            head=lo[1]>.32
            bearing=lo[1]<.02 and hi[1]>.07 and hi[1]<.11 and hi[0]-lo[0]>.07
            for i in component:
                c=world[faces[i]].mean(axis=0)
                if head:
                    # Separate horizontal crown faces so they cannot fill the skirt cavity.
                    key=('crown' if np.ptp(world[faces[i]][:,1])<.0001 and c[1]>.435 else 'head',sector(c[0],c[2],12))
                elif bearing:key=('bearing',sector(c[0],c[1]-.05,8))
                else:key=('component',component[0])
                buckets[key].append(i)
    else:
        groups=defaultdict(list)
        for p in old.prims():
            if p.stringAttribValue('name')==name:groups[p.intAttribValue('segment')].append(p)
        for group in groups.values():append_hull(name,[tuple(p.position()) for f in group for p in f.points()])
    if buckets:
        assigned=[i for group in buckets.values() for i in group]
        assert sorted(assigned)==list(range(len(faces)))
        for group in buckets.values():append_hull(name,v[np.unique([j for i in group for j in faces[i]])])
    stats[name]=len(metadata[name]);print('OPTIMIZED',name,stats[name],flush=True)
output.saveToFile(ROOT+'/geo/scatter_bullet_compounds_optimized.bgeo.sc')
with open(ROOT+'/geo/bullet_hull_metadata_optimized.json','w') as f:json.dump(metadata,f,separators=(',',':'))
with open(ROOT+'/geo/bullet_proxy_stats_optimized.json','w') as f:json.dump(stats,f,indent=2)
with open(ROOT+'/geo/proxy_enclosure_validation.json','w') as f:json.dump({'all_targeted_faces_assigned':True,'maximum_outside_distance_m':proof,'seconds':time.time()-start},f,indent=2)
print('TOTAL_OPTIMIZED_HULLS',sum(stats.values()),'seconds',time.time()-start,flush=True)

