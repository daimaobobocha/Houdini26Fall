import os,json
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE')
debug=obj.node('OUT_COLLISION_HULLS')
old_chain=[];n=debug.inputs()[0] if debug.inputs() else None
while n is not None and n.name() not in ['INITIAL_SAFE_LAYOUT','SOURCE_15_LOW_POLY_ASSETS']:
    if n.name().startswith(('SETTLED_','FINAL_')):break
    old_chain.append(n)
    inputs=n.inputs();n=inputs[0] if inputs else None
proxyframe=obj.node('SETTLED_PROXY_FRAME') or obj.createNode('timeshift','SETTLED_PROXY_FRAME')
proxyframe.setInput(0,obj.node('GRAVITY_SETTLE'),2)
proxyframe.parm('frame').deleteAllKeyframes();proxyframe.parm('frame').setExpression('ch("../SETTLED_FRAME/frame")')
cache=obj.node('SETTLED_PROXY_CACHE') or obj.createNode('file','SETTLED_PROXY_CACHE')
cache.parm('file').set('$HIP/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
switch=obj.node('FINAL_PROXY_OR_CACHED') or obj.createNode('switch','FINAL_PROXY_OR_CACHED')
switch.setInput(0,proxyframe);switch.setInput(1,cache)
switch.parm('input').setExpression('ch("../FINAL_OR_CACHED/input")')
debug.setInput(0,switch)
for n in old_chain:
    if not n.outputs():n.destroy()
debug.setComment('Actual compound collision geometry at the settled frame. This matches OUT_SCATTER, including hollow-part details.')
obj.node('SETTLED_DEFAULT_CACHE').parm('reload').pressButton()
for note in obj.stickyNotes():
    note.setText('GRAVITY-SETTLED SCRAP PILE\nControls: select OUTER SCATTER_PILE GEO.\nLength / Width / Height in cm; minimum 50.\nDensity 0-100%; 0 gives an empty result.\nOil barrel: upright, fixed directly on ground.\nA barrel is omitted if it cannot fit upright.\nNative Bullet + detailed compound colliders.\nCurrent settings use a verified cached result.\nChanging controls recalculates the fall/settling.\nOUT_SCATTER: static final pose.\nGRAVITY_SETTLE: live fall simulation.\nOUT_COLLISION_HULLS: matching collision debug.')
obj.node('OUT_SCATTER').setDisplayFlag(True);obj.node('OUT_SCATTER').setRenderFlag(True)
obj.layoutChildren();obj.setSelected(True,clear_all_selected=True)
hou.setFrame(1)
settings={k:obj.evalParm(k) for k in ['length_cm','width_cm','height_cm','density']}
settings['output_piece_count']=len(obj.node('OUT_SCATTER').geometry().prims())
settings['barrel_mode']='upright, inactive rigid body, bottom at y=0'
settings['settled_frame']=481
with open(ROOT+'/geo/gravity_settings.json','w') as f:json.dump(settings,f,indent=2)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('FINAL_GEO_CONTROLS',settings,flush=True)
