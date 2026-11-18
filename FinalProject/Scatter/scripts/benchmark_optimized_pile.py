import os,json,time,sys
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True)
hou.setUpdateMode(hou.updateMode.AutoUpdate)
obj=hou.node('/obj/SCATTER_PILE');solver=obj.node('GRAVITY_SETTLE')
mode=sys.argv[1]
if mode=='baseline':
    hou.setFrame(1);start=time.time()
    for dst,src in [('SIM_INPUT_VISUAL','RBD_VISUAL_INITIAL'),('SIM_INPUT_PROXY','RBD_PROXY_INITIAL'),('SIM_INPUT_WALLS','PACK_WALLS')]:
        obj.node(dst).parm('stash').set(obj.node(src).geometry().freeze())
    prep=time.time()-start;solver.parm('resetsim').pressButton();start=time.time()
    for frame in range(1,145):
        hou.setFrame(frame);solver.geometry(output_index=2)
        if frame%24==0:print('BASELINE',frame,round(time.time()-start,3),flush=True)
    result={'frames':144,'pieces':len(solver.geometry().prims()),'preparation_seconds':prep,'simulation_seconds':time.time()-start}
    with open(ROOT+'/geo/optimization_baseline.json','w') as f:json.dump(result,f,indent=2)
    print(result,flush=True)
else:
    obj.node('BULLET_COMPOUND_LIBRARY').parm('file').set('$HIP/geo/scatter_bullet_compounds_optimized.bgeo.sc')
    solver.parm('substeps').set(8);solver.parm('numiteration').set(40)
    with open(ROOT+'/scripts/manual_rebuild_pile.py',encoding='utf-8-sig') as f:code=f.read()
    obj.setUserData('manual_build_code',code)
    for name in ['FINAL_CONTACT_CLEANUP','FINAL_PROXY_CLEANUP']:
        n=obj.node(name)
        if n and n.parm('python'):n.parm('python').set(n.parm('python').eval().replace('bullet_hull_metadata.json','bullet_hull_metadata_optimized.json'))
    exec(code,{'node':obj})
    assert obj.evalParm('build_status').startswith('Ready:'),obj.evalParm('build_status')
    with open(ROOT+'/geo/optimized_cache_pointer.json','w') as f:json.dump({'key':obj.userData('pile_active_cache')},f)
    for name in ['SIM_INPUT_VISUAL','SIM_INPUT_PROXY','SIM_INPUT_WALLS']:obj.node(name).parm('stash').set(hou.Geometry())
    hou.setFrame(1)
    hou.hipFile.save(ROOT+'/Scatter_Pile_Optimized_Candidate.hipnc')
    print('CANDIDATE_SAVED',flush=True)
