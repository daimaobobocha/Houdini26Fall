import os,json,time
import hou,numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');out=obj.node('OUT_SCATTER')
print('GEO_CONTROL_MINIMA',[(k,obj.parm(k).parmTemplate().minValue(),obj.parm(k).parmTemplate().minIsStrict()) for k in ['length_cm','width_cm','height_cm']],flush=True)
records=[]
for dimensions in [(50,50,50,100),(50,50,50,0)]:
    start=time.time()
    for k,v in zip(['length_cm','width_cm','height_cm','density'],dimensions):obj.parm(k).set(v)
    hou.setFrame(1)
    g=out.geometry()
    if g is None:raise RuntimeError([(n.name(),n.errors()) for n in [out,obj.node('GRAVITY_SETTLE'),obj.node('INITIAL_SAFE_LAYOUT')]])
    record={'parameters':dimensions,'piece_count':len(g.prims()),'elapsed_seconds':round(time.time()-start,3),'errors':out.errors()}
    if dimensions[-1]==0:assert len(g.prims())==0
    if dimensions[-1]>0:
        assert len(g.prims())>0
        for prim in g.prims():
            assert 'OilBarrel' not in prim.stringAttribValue('asset_name')
            internal=prim.getEmbeddedGeometry();m=prim.fullTransform()
            bounds=np.array([tuple(p.position()*m) for p in internal.points()])
            assert np.all(bounds.min(axis=0)>=[-.251,-.001,-.251])
            assert np.all(bounds.max(axis=0)<=[.251,.501,.251])
    records.append(record);print('CONTROL_CASE',record,flush=True)
with open(ROOT+'/geo/gravity_control_tests.json','w') as f:json.dump(records,f,indent=2)
