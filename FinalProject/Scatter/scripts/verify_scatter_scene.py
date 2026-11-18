import os,sys,json,time
import hou,numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
sys.path.insert(0,os.path.dirname(__file__))
from pile_engine import oriented,validate
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');ctrl=obj.node('CONTROLS');out=obj.node('OUT_SCATTER');scatter=obj.node('COLLISION_SAFE_DROP_SCATTER')
with open(ROOT+'/geo/scatter_collision_library.json') as f:assets=json.load(f)
cases=[]
for dims in [(220,180,100,65),(50,50,50,100),(50,50,50,0),(100,70,50,100),(220,180,100,25)]:
    for parm,value in zip(['length_cm','width_cm','height_cm','density'],dims):ctrl.parm(parm).set(value)
    start=time.time();output=out.geometry();data=scatter.geometry()
    placements=json.loads(data.attribValue('placements'));stats=json.loads(data.attribValue('placement_stats'))
    assert len(output.prims())==len(placements)
    bodies=[];max_error=0.
    for i,item in enumerate(placements):
        a=oriented(assets[item['asset_index']],np.asarray(item['rotation']));pos=np.asarray(item['P'])
        a['vertices']+=pos;a['lo']+=pos;a['hi']+=pos;bodies.append(a)
        packed=output.prims()[i]
        embedded=packed.getEmbeddedGeometry();matrix=packed.fullTransform()
        # Compare the actual Copy-to-Points instance transform to the tested transform.
        for point in list(embedded.points())[::max(1,len(embedded.points())//20)]:
            actual=np.asarray(tuple(point.position()*matrix))
            expected=np.asarray(point.position())@np.asarray(item['rotation']).T+pos
            max_error=max(max_error,float(np.linalg.norm(actual-expected)))
    stats.update(validate(bodies,dims[0]*.01,dims[1]*.01,dims[2]*.01))
    stats['max_instance_transform_error_m']=max_error;stats['cook_and_validation_seconds']=round(time.time()-start,3)
    assert not stats['overlapping_proxy_pairs'] and not stats['outside_bounds']
    assert max_error<1.e-5,stats
    cases.append(stats);print('VERIFIED',json.dumps(stats),flush=True)
for parm,value in zip(['length_cm','width_cm','height_cm','density'],[220,180,100,65]):ctrl.parm(parm).set(value)
out.geometry()
with open(ROOT+'/geo/scatter_test_results.json','w') as f:json.dump(cases,f,indent=2)
print('LIGHT_PARMS',[(p.name(),p.eval()) for p in hou.node('/obj').createNode('hlight','probe_light').parms() if p.name() in ['light_type','light_intensity','light_color','light_enable','areasize','shadow_type']],flush=True)
print('IFD_AVAILABLE','ifd' in hou.ropNodeTypeCategory().nodeTypes(),flush=True)
