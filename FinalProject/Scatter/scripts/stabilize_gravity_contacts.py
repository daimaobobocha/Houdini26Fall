"""A short physical relaxation of the already settled pile; no geometric repositioning."""
import os,json,time,re
import numpy as np
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');solver=obj.node('GRAVITY_SETTLE');initial=obj.node('INITIAL_SAFE_LAYOUT')
# Static input attributes must not re-activate resting bodies on every frame.
solver.parm('overwritefromsop').set(0)
saved=hou.Geometry();saved.loadFromFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc')
records=[]
for i,p in enumerate(saved.prims()):
    matrix=np.array(p.fullTransform().asTuple()).reshape(4,4)
    asset=p.stringAttribValue('asset_name')
    records.append({'name':asset,'asset_index':int(asset.split('_')[1])-1,'P':matrix[3,:3].tolist(),'rotation':matrix[:3,:3].T.tolist(),'id':i})
original=initial.parm('python').unexpandedString()
line='placements,collision_bodies,stats=generate(assets,length,width,height,density,upright_barrels=True)'
replacement='placements=json.loads('+repr(json.dumps(records))+');collision_bodies=[];stats={"placed_count":len(placements)}'
assert line in original
initial.parm('python').set(original.replace(line,replacement))
for name in ['RBD_VISUAL_INITIAL','RBD_PROXY_INITIAL']:
    n=obj.node(name);code=n.parm('python').unexpandedString()
    code=code.replace("'bullet_linear_sleep_threshold':.004","'bullet_linear_sleep_threshold':.025")
    code=code.replace("'bullet_angular_sleep_threshold':.008","'bullet_angular_sleep_threshold':.25")
    n.parm('python').set(code)
solver.parm('bullet_linear_sleep_threshold').set(.025);solver.parm('bullet_angular_sleep_threshold').set(.25)
drag_original=solver.parm('drag_airresist').expression();spin_original=solver.parm('dragspin_spinresist').expression()
solver.parm('drag_airresist').deleteAllKeyframes();solver.parm('drag_airresist').set(1.)
solver.parm('dragspin_spinresist').deleteAllKeyframes();solver.parm('dragspin_spinresist').set(2.)
t=time.time();stable=0
for frame in range(1,170):
    hou.setFrame(frame);g=solver.geometry(output_index=2)
    if frame%12==0:
        speed=max([np.linalg.norm(p.attribValue('v')) for p in g.points()],default=0.)
        spin=max([np.linalg.norm(p.attribValue('w')) for p in g.points()],default=0.)
        print('CONTACT_RELAX',frame,'v',float(speed),'w',float(spin),'seconds',round(time.time()-t,1),flush=True)
        stable=stable+1 if speed<1.e-6 and spin<1.e-6 else 0
        if frame>=72 and stable>=2:break
visual=solver.geometry().freeze();proxy=solver.geometry(output_index=2).freeze()
visual.saveToFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc');visual.saveToFile(ROOT+'/geo/Scatter_Pile_Default.bgeo.sc')
proxy.saveToFile(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
# Restore procedural initial placement; only this verified default result is cached.
initial.parm('python').set(original)
solver.parm('drag_airresist').setExpression(drag_original)
solver.parm('dragspin_spinresist').setExpression(spin_original)
obj.node('SETTLED_DEFAULT_CACHE').parm('reload').pressButton()
obj.setSelected(True,clear_all_selected=True);hou.setFrame(1)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('RESTING_RESULT',len(visual.prims()),'max_v',float(speed),'max_w',float(spin),flush=True)
