import os,json,sys,time
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');ctrl=obj.node('CONTROLS')
defaults={k:ctrl.evalParm(k) for k in ['length_cm','width_cm','height_cm','density']}
pg=obj.parmTemplateGroup()
folder=hou.FolderParmTemplate('scatter_controls','Scatter Controls')
for name,label,low,high in [('length_cm','Length (cm)',50,1000),('width_cm','Width (cm)',50,1000),('height_cm','Height (cm)',50,500),('density','Scatter Density (%)',0,100)]:
    p=hou.FloatParmTemplate(name,label,1,default_value=(defaults[name],),min=low,max=high,min_is_strict=True,max_is_strict=name=='density')
    p.setHelp('Gravity-settled pile. Dimensions in cm, minimum 50. Parameter changes recalculate the settling simulation. Barrels stay upright on the ground when they fit.')
    folder.addParmTemplate(p)
if pg.find('scatter_controls'):pg.replace('scatter_controls',folder)
else:pg.insertBefore(pg.entries()[0].name(),folder)
obj.setParmTemplateGroup(pg)
for name,value in defaults.items():
    obj.parm(name).set(value)
    ctrl.parm(name).setExpression('ch("../%s")'%name)
ctrl.setComment('Controls are now on the outer SCATTER_PILE geometry object. These are linked readouts.')
obj.setComment('Select this GEO to edit Length / Width / Height / Density. Native Bullet gravity settling with compound colliders. Upright barrels are fixed on the floor.')
obj.setGenericFlag(hou.nodeFlag.DisplayComment,True)
initial=obj.node('COLLISION_SAFE_DROP_SCATTER') or obj.node('INITIAL_SAFE_LAYOUT')
if initial is None:initial=next(n for n in obj.children() if n.type().name()=='python')
visual_copy=obj.node('OUT_SCATTER').inputs()[0]
if visual_copy.type().name().startswith('copytopoints'):visual_copy.setName('INSTANCE_ASSETS',unique_name=True)
initial.inputs()[0].setName('SOURCE_15_LOW_POLY_ASSETS',unique_name=True)
visual_copy.inputs()[0].setName('PACK_BY_ASSET_NAME',unique_name=True)
old=initial.parm('python').unexpandedString();driver=old[old.index('\nimport hou,json\n'):]
driver=driver.replace("ctrl=node.parent().node('CONTROLS')","ctrl=node.parent()")
driver=driver.replace('generate(assets,length,width,height,density)','generate(assets,length,width,height,density,upright_barrels=True)')
with open(ROOT+'/scripts/pile_engine.py') as f:engine=f.read()
initial.parm('python').set(engine+'\n'+driver);initial.setName('INITIAL_SAFE_LAYOUT')
initial.setComment('Non-intersecting initial arrangement only. Bullet below provides gravity, rotation, contact and final settling. One upright barrel is fixed to the floor.')
for name in ['BULLET_COMPOUND_LIBRARY','PACK_BULLET_COMPOUNDS','COPY_BULLET_COMPOUNDS','RBD_VISUAL_INITIAL','RBD_PROXY_INITIAL',
             'CONTAINER_WALLS','GRAVITY_SETTLE','SETTLED_FRAME','SETTLED_DEFAULT_CACHE','FINAL_OR_CACHED']:
    n=obj.node(name)
    if n:n.destroy()
proxy=obj.createNode('file','BULLET_COMPOUND_LIBRARY');proxy.parm('file').set('$HIP/geo/scatter_bullet_compounds.bgeo.sc')
pack=obj.createNode('pack','PACK_BULLET_COMPOUNDS');pack.setInput(0,proxy)
pack.parm('packbyname').set(1);pack.parm('packedfragments').set(0);pack.parm('pivot').set(0);pack.parm('transfer_attributes').set('name')
copy=obj.createNode('copytopoints','COPY_BULLET_COMPOUNDS');copy.setInput(0,pack);copy.setInput(1,initial)
copy.parm('useidattrib').set(1);copy.parm('idattrib').set('name')
prep_code='''
import hou,json
g=hou.pwd().geometry()
original_names=[p.stringAttribValue('name') for p in g.prims()]
for kind in [hou.attribType.Prim,hou.attribType.Point]:
    finder=g.findPrimAttrib if kind==hou.attribType.Prim else g.findPointAttrib
    for key in ['name','asset_name']:
        if finder(key) is None:g.addAttrib(kind,key,'')
int_attrs={'active':1,'animated':0,'deforming':0,'bullet_groupconnected':1,'bullet_adjust_geometry':0,
           'bullet_want_deactivate':1,'computecom':1,'computemass':0}
float_attrs={'bullet_collision_margin':.0008,'friction':.55,'bounce':0.,'bullet_linear_sleep_threshold':.004,
             'bullet_angular_sleep_threshold':.008,'mass':2.0,'density':1000.}
for k,v in dict(int_attrs,**float_attrs,bullet_georep='convexhull',v=(0.,0.,0.),w=(0.,0.,0.)).items():
    if g.findPointAttrib(k) is None:g.addAttrib(hou.attribType.Point,k,v)
masses=[18.,3.,1.5,12.,6.,3.6,5.,2.,1.8,18.,8.,6.,3.,4.,.8]
for i,prim in enumerate(g.prims()):
    pt=prim.points()[0];asset=original_names[i];name='piece_%04d'%i
    prim.setAttribValue('name',name);prim.setAttribValue('asset_name',asset)
    pt.setAttribValue('name',name);pt.setAttribValue('asset_name',asset)
    for k,v in int_attrs.items():pt.setAttribValue(k,v)
    for k,v in float_attrs.items():pt.setAttribValue(k,v)
    pt.setAttribValue('mass',masses[int(asset.split('_')[1])-1])
    pt.setAttribValue('bullet_georep','convexhull')
    pt.setAttribValue('v',(0.,0.,0.));pt.setAttribValue('w',(0.,0.,0.))
    if 'OilBarrel' in asset:
        pt.setAttribValue('active',0);pt.setAttribValue('bullet_groupconnected',0)
'''
visual=obj.createNode('python','RBD_VISUAL_INITIAL');visual.setInput(0,visual_copy);visual.parm('python').set(prep_code)
proxyinit=obj.createNode('python','RBD_PROXY_INITIAL');proxyinit.setInput(0,copy);proxyinit.parm('python').set(prep_code)
walls=obj.createNode('python','CONTAINER_WALLS')
walls.parm('python').set('''
import hou
node=hou.pwd();g=node.geometry();g.clear();parent=node.parent()
L=max(.5,parent.evalParm('length_cm')*.01);W=max(.5,parent.evalParm('width_cm')*.01);H=max(.5,parent.evalParm('height_cm')*.01)
name=g.addAttrib(hou.attribType.Prim,'name','')
positions=[((-L/2-.05,H/2,0),(.1,H+.3,W+.2)),((L/2+.05,H/2,0),(.1,H+.3,W+.2)),
           ((0,H/2,-W/2-.05),(L+.2,H+.3,.1)),((0,H/2,W/2+.05),(L+.2,H+.3,.1)),((0,H+.05,0),(L+.2,.1,W+.2))]
faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[3,7,6,2],[0,4,7,3],[1,2,6,5]]
for i,(p,s) in enumerate(positions):
    corners=[(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    points=g.createPoints([(p[0]+a*s[0]/2,p[1]+b*s[1]/2,p[2]+c*s[2]/2) for a,b,c in corners])
    for f in faces:
        poly=g.createPolygon()
        for j in f:poly.addVertex(points[j])
        poly.setAttribValue(name,'wall_%d'%i)
''')
wallpack=obj.node('PACK_WALLS') or obj.createNode('pack','PACK_WALLS');wallpack.setInput(0,walls)
wallpack.parm('packbyname').set(1);wallpack.parm('packedfragments').set(0);wallpack.parm('transfer_attributes').set('name')
solver=obj.createNode('rbdbulletsolver','GRAVITY_SETTLE');solver.setInput(0,visual);solver.setInput(2,proxyinit);solver.setInput(3,wallpack)
settings={'substeps':20,'numiteration':80,'overwritefromsop':0,'useground':1,'ground_margin':.0005,'ground_bounce':0.,'ground_friction':.6,
          'ground_dynamicfriction':.6,'collision_margin':.0008,'collision_bounce':0.,'collision_friction':.5,
          'bounce':0.,'friction':.55,'bullet_linear_sleep_threshold':.004,'bullet_angular_sleep_threshold':.008,
          'sleepingtime':2.,'showground':0,'showcollision':0}
for k,v in settings.items():solver.parm(k).set(v)
solver.setColor(hou.Color((.3,.5,.85)));solver.setComment('Native Bullet: gravity -9.80665, 20 substeps, 80 iterations, 0 bounce. Compound convex collision bodies; upright floor barrels inactive.')
solver.setGenericFlag(hou.nodeFlag.DisplayComment,True)
settled=obj.createNode('timeshift','SETTLED_FRAME');settled.setInput(0,solver);settled.parm('frame').deleteAllKeyframes();settled.parm('frame').set(241)
out=obj.node('OUT_SCATTER');out.setInput(0,settled)
out.setDisplayFlag(True);out.setRenderFlag(True)
for note in obj.stickyNotes():note.destroy()
note=obj.createStickyNote();note.setText('GRAVITY-SETTLED SCRAP PILE\nEdit the four controls on the OUTER GEO node.\nLengths in cm; minimum 50.\nBarrel: upright, fixed on the ground.\nGRAVITY_SETTLE: native Bullet, frame 1-241.\nSETTLED_FRAME: final resting arrangement.\nOUT_SCATTER: final packed visual geometry.\nChanging dimensions/density recalculates gravity settling.')
obj.layoutChildren();note.setPosition(hou.Vector2((-8,8)))
obj.setSelected(True,clear_all_selected=True)
hou.playbar.setFrameRange(1,241);hou.playbar.setPlaybackRange(1,241)
hou.setFrame(1)
vg=visual.geometry();pg=proxyinit.geometry()
if vg is None or pg is None:raise RuntimeError([(n.path(),n.errors()) for n in [initial,visual_copy,copy,visual,proxyinit]])
print('INITIAL',len(vg.prims()),len(pg.prims()),solver.outputLabels(),flush=True)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
start=time.time()
for frame in range(1,242):
    hou.setFrame(frame);g=solver.geometry()
    if solver.errors():raise RuntimeError(solver.errors())
    if frame==1 or frame%24==0:print('SIM_FRAME',frame,'parts',len(g.prims()),'elapsed',round(time.time()-start,2),flush=True)
g=solver.geometry().freeze()
g.saveToFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc')
g.saveToFile(ROOT+'/geo/Scatter_Pile_Default.bgeo.sc')
proxyfinal=solver.geometry(output_index=2).freeze()
proxyfinal.saveToFile(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
cached=obj.createNode('file','SETTLED_DEFAULT_CACHE');cached.parm('file').set('$HIP/geo/Scatter_Pile_Settled.bgeo.sc')
switch=obj.createNode('switch','FINAL_OR_CACHED');switch.setInput(0,settled);switch.setInput(1,cached)
condition=' && '.join('abs(ch("../%s")-%g)<0.00001'%(key,defaults[key]) for key in defaults)
switch.parm('input').setExpression('if(%s,1,0)'%condition)
out.setInput(0,switch)
obj.layoutChildren();obj.setSelected(True,clear_all_selected=True)
hou.setFrame(1)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('GRAVITY_SCENE_SAVED',hou.hipFile.path(),'seconds',time.time()-start,flush=True)
