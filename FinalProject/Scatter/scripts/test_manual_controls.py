import os,time,json,hashlib,sys
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(sys.argv[1] if len(sys.argv)>1 else ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');out=obj.node('OUT_SCATTER');guide=obj.node('BOUNDS_GUIDE')
params=['length_cm','width_cm','height_cm','density'];original={k:obj.evalParm(k) for k in params}
def signature():
    g=out.geometry()
    return len(g.prims()),hashlib.sha256(repr([p.fullTransform().asTuple() for p in g.prims()]).encode()).hexdigest()
start_signature=signature()
watched=[obj.node(k) for k in ['INITIAL_SAFE_LAYOUT','RBD_VISUAL_INITIAL','RBD_PROXY_INITIAL','GRAVITY_SETTLE']]
counts=[n.cookCount() for n in watched]
t=time.time()
for i in range(100):
    obj.parm('length_cm').set(50.+i*4.)
    obj.parm('density').set(float(i%101))
    guide.geometry();assert signature()==start_signature
duration=time.time()-t
assert [n.cookCount() for n in watched]==counts
print('SLIDER_TEST',{'updates':100,'seconds':duration,'simulation_cooks':0,'output_preserved':True},flush=True)
for k,v in original.items():obj.parm(k).set(v)
t=time.time();obj.parm('rebuild_pile').pressButton()
assert signature()==start_signature
assert [n.cookCount() for n in watched]==counts
print('CACHE_HIT_TEST',{'seconds':time.time()-t,'simulation_cooks':0},flush=True)
for k,v in zip(params,[50,50,50,60]):obj.parm(k).set(v)
t=time.time();obj.parm('rebuild_pile').pressButton()
assert 0<len(out.geometry().prims())<80
assert obj.evalParm('build_status').startswith('Ready:')
print('NONZERO_BUILD_TEST',{'seconds':time.time()-t,'pieces':len(out.geometry().prims()),'status':obj.evalParm('build_status')},flush=True)
obj.parm('density').set(0);obj.parm('rebuild_pile').pressButton()
assert len(out.geometry().prims())==0
print('EMPTY_BUILD_TEST','passed',flush=True)
# Failed preparation must preserve the last published non-empty result.
for k,v in original.items():obj.parm(k).set(v)
obj.parm('rebuild_pile').pressButton();before=signature()
initial=obj.node('RBD_VISUAL_INITIAL');code=initial.parm('python').unexpandedString()
initial.parm('python').set("raise RuntimeError('intentional preparation failure for rollback test')")
obj.parm('density').set(13.731)
try:obj.parm('rebuild_pile').pressButton()
except Exception:pass
assert signature()==before
assert obj.userData('pile_build_running') is None
assert hou.updateModeSetting()==hou.updateMode.AutoUpdate
initial.parm('python').set(code)
print('FAILED_BUILD_KEEPS_RESULT','passed',flush=True)
with open(ROOT+'/geo/manual_controls_test_results.json','w') as f:json.dump({'slider_updates':100,'slider_seconds':duration,'slider_solver_cooks':0,'cache_hit_solver_cooks':0,'nonzero_build':True,'zero_density':True,'failed_build_keeps_previous':True},f,indent=2)
# Deliberately do not save the test parameter values or injected failure to the HIP.
