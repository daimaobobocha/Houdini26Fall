import os,time,json
import hou,numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');solver=obj.node('GRAVITY_SETTLE')
for key,value in {'adddrag':1,'adddragspin':1,'ground_friction':.7,'ground_dynamicfriction':.7,'collision_friction':0.}.items():solver.parm(key).set(value)
solver.parm('drag_airresist').setExpression('if($F<120,0.15,0.8)')
solver.parm('dragspin_spinresist').setExpression('if($F<120,0.2,1.0)')
for name in ['RBD_VISUAL_INITIAL','RBD_PROXY_INITIAL']:
    node=obj.node(name);code=node.parm('python').unexpandedString().replace("'friction':.55","'friction':.7")
    node.parm('python').set(code)
obj.node('SETTLED_FRAME').parm('frame').set(481)
hou.playbar.setFrameRange(1,481);hou.playbar.setPlaybackRange(1,481)
hou.setFrame(1);hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
t=time.time();stable=0
for frame in range(1,482):
    hou.setFrame(frame);g=solver.geometry(output_index=2)
    if g is None:raise RuntimeError(solver.errors())
    if frame==1 or frame%24==0:
        speed=max([np.linalg.norm(p.attribValue('v')) for p in g.points()],default=0.)
        spin=max([np.linalg.norm(p.attribValue('w')) for p in g.points()],default=0.)
        print('SETTLING',frame,'max_v',round(float(speed),5),'max_w',round(float(spin),5),'sec',round(time.time()-t,1),flush=True)
        if frame>=240:
            stable=stable+1 if speed<.004 and spin<.008 else 0
            if stable>=2:break
visual=solver.geometry().freeze();proxy=solver.geometry(output_index=2).freeze()
visual.saveToFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc');visual.saveToFile(ROOT+'/geo/Scatter_Pile_Default.bgeo.sc')
proxy.saveToFile(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
settings={k:obj.evalParm(k) for k in ['length_cm','width_cm','height_cm','density']}
settings.update({'settled_frame':frame,'max_linear_speed_m_s':float(speed),'max_angular_speed_rad_s':float(spin)})
with open(ROOT+'/geo/gravity_settings.json','w') as f:json.dump(settings,f,indent=2)
obj.node('SETTLED_DEFAULT_CACHE').parm('reload').pressButton()
for note in obj.stickyNotes():
    note.setText('GRAVITY-SETTLED SCRAP PILE\nEdit Length, Width, Height, Density on OUTER GEO.\nDimensions in cm, min 50.\nBarrel remains upright on the ground (when it fits).\nNative Bullet + detailed convex compounds.\n20 substeps / 80 iterations / 0 bounce.\nSETTLED_FRAME evaluates up to 20 seconds.\nCurrent settings have a verified fast cache.\nOther settings recalculate automatically.')
obj.setSelected(True,clear_all_selected=True);hou.setFrame(1)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('SETTLED_SAVED',settings,flush=True)
