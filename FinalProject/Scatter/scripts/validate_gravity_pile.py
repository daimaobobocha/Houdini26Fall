import os,json,time,sys
import numpy as np
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
sys.path.insert(0,os.path.dirname(__file__))
from pile_engine import canonical
visual=hou.Geometry();visual.loadFromFile(sys.argv[1] if len(sys.argv)>1 else ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc')
proxies=hou.Geometry();proxies.loadFromFile(sys.argv[2] if len(sys.argv)>2 else ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
with open(ROOT+'/geo/scatter_asset_library.json') as f:assets=json.load(f)
source={a['name']:a for a in assets}

def hull_data(g,prims):
    point_ids=sorted({p.number() for face in prims for p in face.points()})
    verts=np.array([tuple(g.point(i).position()) for i in point_ids],dtype=float)
    normals=[];edges=[]
    for face in prims:
        normal=tuple(face.normal())
        if np.linalg.norm(normal)>1.e-9:normals.append(normal)
        pts=[np.asarray(tuple(p.position())) for p in face.points()]
        edges.extend([b-a for a,b in zip(pts,pts[1:]+pts[:1])])
    return {'vertices':verts,'normals':canonical(normals),'edges':canonical(edges)}

def transform(hull,matrix):
    R=matrix[:3,:3];t=matrix[3,:3]
    verts=hull['vertices']@R+t
    return {'vertices':verts,'normals':hull['normals']@R,'edges':hull['edges']@R,
            'lo':verts.min(axis=0),'hi':verts.max(axis=0)}

local_cache={};bodies=[];barrels=[];motion=[];visual_bounds=[]
for p in visual.prims():
    asset=p.stringAttribValue('asset_name');mat=np.array(p.fullTransform().asTuple()).reshape(4,4)
    v=np.asarray(source[asset]['vertices'])@mat[:3,:3]+mat[3,:3]
    visual_bounds.append((v.min(axis=0),v.max(axis=0)))
    if 'OilBarrel' in asset:
        barrels.append({'name':p.stringAttribValue('name'),'bottom_m':float(v[:,1].min()),
                        'upright_error':float(np.linalg.norm(mat[1,:3]-[0,1,0]))})
    pt=p.points()[0]
    speed=float(np.linalg.norm(pt.attribValue('v'))) if visual.findPointAttrib('v') else 0.
    angular=float(np.linalg.norm(pt.attribValue('w'))) if visual.findPointAttrib('w') else 0.
    motion.append({'name':p.stringAttribValue('name'),'linear_speed_m_s':speed,'angular_speed_rad_s':angular})
for packed in proxies.prims():
    asset=packed.stringAttribValue('asset_name');g=packed.getEmbeddedGeometry()
    matrix=np.array(packed.fullTransform().asTuple()).reshape((4,4))
    if asset not in local_cache:
        if 'OilBarrel' in asset:
            # Bullet uses the whole closed drum's hull, not its internal decomposition.
            temp=hou.node('/obj').createNode('geo','barrel_hull_check')
            stash=temp.createNode('stash');stash.parm('stash').set(g)
            shrink=temp.createNode('shrinkwrap');shrink.setInput(0,stash)
            convex=shrink.geometry();local_cache[asset]=[hull_data(convex,list(convex.prims()))]
            temp.destroy()
        else:
            groups={}
            for prim in g.prims():groups.setdefault(prim.intAttribValue('segment'),[]).append(prim)
            local_cache[asset]=[hull_data(g,prims) for prims in groups.values()]
    parts=[transform(h,matrix) for h in local_cache[asset]]
    bodies.append({'name':packed.stringAttribValue('name'),'asset':asset,'parts':parts,
                   'lo':np.min([p['lo'] for p in parts],axis=0),'hi':np.max([p['hi'] for p in parts],axis=0),
                   'lows':np.array([p['lo'] for p in parts]),'highs':np.array([p['hi'] for p in parts])})

if len(sys.argv)==1:
    with open(ROOT+'/geo/bullet_hull_metadata.json','w') as f:
        json.dump({name:[{k:v.tolist() for k,v in h.items()} for h in hulls] for name,hulls in local_cache.items()},f,separators=(',',':'))

def signed_overlap(a,b):
    cross=np.cross(a['edges'][:,None,:],b['edges'][None,:,:]).reshape(-1,3)
    axes=canonical(np.concatenate([a['normals'],b['normals'],cross]))
    ap=a['vertices']@axes.T;bp=b['vertices']@axes.T
    return float(np.min(np.minimum(ap.max(axis=0),bp.max(axis=0))-np.maximum(ap.min(axis=0),bp.min(axis=0))))

penetrations=[];checked=0;nearest_contacts={b['name']:float('inf') for b in bodies};contact_edges=[]
t=time.time()
for i,a in enumerate(bodies):
    floor_gap=min(p['lo'][1] for p in a['parts']);nearest_contacts[a['name']]=abs(float(floor_gap))
    for b in bodies[:i]:
        tol=.012
        if np.any(a['hi']+tol<b['lo']) or np.any(b['hi']+tol<a['lo']):continue
        mask=np.all(a['highs'][:,None,:]+tol>=b['lows'][None,:,:],axis=2)&np.all(b['highs'][None,:,:]+tol>=a['lows'][:,None,:],axis=2)
        near=False
        for ai,bi in np.argwhere(mask):
            aa=a['parts'][ai];bb=b['parts'][bi]
            ov=signed_overlap(aa,bb);checked+=1
            gap=max(0.,-ov)
            if gap<nearest_contacts[a['name']]:nearest_contacts[a['name']]=gap
            if gap<nearest_contacts[b['name']]:nearest_contacts[b['name']]=gap
            if ov>=-.004:near=True
            if ov>.00002:
                penetrations.append({'a':a['name'],'b':b['name'],'depth_m':ov,'components':[int(ai),int(bi)]})
        if near:contact_edges.append([a['name'],b['name']])
    if (i+1)%10==0:print('CHECKED_BODIES',i+1,'component_pairs',checked,'seconds',round(time.time()-t,2),flush=True)
roots={b['name'] for b in bodies if min(p['lo'][1] for p in b['parts'])<.004 or 'OilBarrel' in b['asset']}
connected=set(roots)
for _ in bodies:
    previous=len(connected)
    for a,b in contact_edges:
        if a in connected or b in connected:connected.update([a,b])
    if previous==len(connected):break
report={'piece_count':len(bodies),'component_pairs_tested':checked,'penetrations_over_0_02mm':penetrations,
        'max_proxy_penetration_m':max([p['depth_m'] for p in penetrations],default=0.),'barrels':barrels,
        'max_linear_speed_m_s':max([m['linear_speed_m_s'] for m in motion],default=0.),
        'max_angular_speed_rad_s':max([m['angular_speed_rad_s'] for m in motion],default=0.),
        'without_support_contact_chain':[b['name'] for b in bodies if b['name'] not in connected],
        'maximum_nearest_contact_gap_m':max(nearest_contacts.values(),default=0.),
        'motion':motion,'contact_gaps':nearest_contacts,
        'bounds_min_m':np.min([b[0] for b in visual_bounds],axis=0).tolist(),
        'bounds_max_m':np.max([b[1] for b in visual_bounds],axis=0).tolist()}
with open(sys.argv[3] if len(sys.argv)>3 else ROOT+'/geo/gravity_pile_validation.json','w') as f:json.dump(report,f,indent=2)
print('VALIDATION_SUMMARY',json.dumps({k:v for k,v in report.items() if k not in ['motion','contact_gaps','penetrations_over_0_02mm']}),flush=True)
