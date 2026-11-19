import hou,os,json,collections,math
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/ICA10.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
asset=hou.node('/obj/STAIRCASE/ICA10_Stairs')
source=[list(p.position()) for p in asset.inputs()[0].geometry().points()]
def info(node):
    geo=node.geometry()
    assert geo.prims() and not node.errors(),(node.path(),node.errors())
    edges=collections.Counter()
    for p in geo.prims():
        vs=[v.point().number() for v in p.vertices()]
        for a,b in zip(vs,vs[1:]+vs[:1]):edges[tuple(sorted((a,b)))]+=1
    return {'points':len(geo.points()),'primitives':len(geo.prims()),'open_edges':sum(v==1 for v in edges.values()),'nonmanifold_edges':sum(v>2 for v in edges.values()),'bbox':[list(geo.boundingBox().minvec()),list(geo.boundingBox().maxvec())]}
report={'baseline':info(asset),'branches':{}}
for n in ['OUT_Stringer','OUT_Handrail_Main','OUT_Pillars','OUT_Midrail']:
    report['branches'][n]=info(asset.node(n))
    assert report['branches'][n]['open_edges']==0,(n,report['branches'][n])
# Test a newly instantiated asset with no original /obj paths.
hou.hipFile.clear(suppress_save_prompt=True)
hou.hda.installFile(ROOT+'/hda/ICA10_Stairs.hdanc')
g=hou.node('/obj').createNode('geo','INDEPENDENT_TEST')
curve=g.createNode('python','INPUT_CURVE')
curve.parm('python').set('import hou\ng=hou.pwd().geometry()\npts=g.createPoints('+repr(source)+')\np=g.createPolygon(is_closed=False)\nfor pt in pts:p.addVertex(pt)')
fresh=g.createNode('ica10::procedural_stairs::1.0','fresh_stair_asset');fresh.setInput(0,curve)
report['independent_asset']=info(fresh)
assert report['baseline']['primitives']==report['independent_asset']['primitives']
for name,val in [('sizex',14),('length',1),('offset1',2),('midrailcount',2),('railheight',5)]:
    original=fresh.parm(name).eval();fresh.parm(name).set(val)
    report['change_'+name]=info(fresh)
    assert report['change_'+name]!=report['independent_asset'],name
    fresh.parm(name).set(original)
extended=source+[[0,23,-35],[0,23,-42]]
curve.parm('python').set('import hou\ng=hou.pwd().geometry()\npts=g.createPoints('+repr(extended)+')\np=g.createPolygon(is_closed=False)\nfor pt in pts:p.addVertex(pt)')
report['extended_curve']=info(fresh)
assert report['extended_curve']['primitives']>report['baseline']['primitives']
with open(ROOT+'/stair_validation.json','w') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2),flush=True)
