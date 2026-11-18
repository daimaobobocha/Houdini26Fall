import os,json,sys,time
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
sys.path.insert(0,os.path.dirname(__file__))
from pile_engine import make_proxy,generate,validate
with open(ROOT+'/geo/scatter_asset_library.json') as f:assets=json.load(f)
for a in assets:a['proxy']=make_proxy(a['vertices'])
meta=[{k:a[k] for k in ['name','source_mesh','center_m','proxy']} for a in assets]
with open(ROOT+'/geo/scatter_collision_library.json','w') as f:json.dump(meta,f,separators=(',',':'))

palette={'MAT_OxideRedPaintSG':(.32,.085,.035),'MAT_AgedSteelSG':(.28,.22,.17),
         'MAT_DarkSteelSG':(.12,.095,.07),'MAT_RustedIronSG':(.31,.12,.045),
         'MAT_TireRubberSG':(.025,.028,.03),'MAT_WornMetalEdgesSG':(.48,.46,.4)}

def library_geometry(collision=False):
    g=hou.Geometry()
    name=g.addAttrib(hou.attribType.Prim,'name','')
    cd=g.addAttrib(hou.attribType.Prim,'Cd',(0.3,0.2,0.1))
    material=g.addAttrib(hou.attribType.Prim,'source_material','')
    uv=g.addAttrib(hou.attribType.Vertex,'uv',(0.,0.,0.))
    g.addAttrib(hou.attribType.Global,'asset_metadata','')
    g.setGlobalAttribValue('asset_metadata',json.dumps(meta,separators=(',',':')))
    for a in assets:
        points=a['proxy']['vertices'] if collision else a['vertices']
        faces=a['proxy']['faces'] if collision else a['faces']
        hp=g.createPoints(points)
        for i,face in enumerate(faces):
            poly=g.createPolygon()
            for j,index in enumerate(face):
                v=poly.addVertex(hp[index])
                if not collision:
                    u,w=a['uvs'][i][j];v.setAttribValue(uv,(u,w,0.))
            poly.setAttribValue(name,a['name'])
            mat=a['materials'][a['material_ids'][i]] if not collision else 'MAT_AgedSteelSG'
            poly.setAttribValue(material,mat);poly.setAttribValue(cd,palette.get(mat,(.3,.2,.1)))
    return g

library_geometry().saveToFile(ROOT+'/geo/scatter_assets.bgeo.sc')
library_geometry(True).saveToFile(ROOT+'/geo/scatter_collision_proxies.bgeo.sc')
hou.hipFile.clear(suppress_save_prompt=True)
hou.hipFile.setName(ROOT+'/Scatter_Pile.hipnc')
hou.setFps(24)
obj=hou.node('/obj').createNode('geo','SCATTER_PILE')
for n in obj.children():n.destroy()
obj.setColor(hou.Color((.7,.38,.12)))
ctrl=obj.createNode('null','CONTROLS')
ctrl.setColor(hou.Color((.2,.65,.35)))
ctrl.setComment('Adjust these four controls. Dimensions are centimeters. Minimum 50 cm. Density requests up to 32 parts per square meter; capacity and collisions may reduce the actual count.')
ctrl.setGenericFlag(hou.nodeFlag.DisplayComment,True)
ptg=ctrl.parmTemplateGroup()
for name,label,default,low,high in [('length_cm','Length (cm)',220.,50.,1000.),('width_cm','Width (cm)',180.,50.,1000.),
                                  ('height_cm','Height (cm)',100.,50.,500.),('density','Scatter Density (%)',65.,0.,100.)]:
    p=hou.FloatParmTemplate(name,label,1,default_value=(default,),min=low,max=high,min_is_strict=True,max_is_strict=name=='density')
    p.setHelp('Minimum is 50 cm. Objects retain their original size.' if name!='density' else '0 = empty. 100 = highest requested packing density. Actual count respects available collision-free space.')
    ptg.append(p)
ctrl.setParmTemplateGroup(ptg)
source=obj.createNode('file','SOURCE_15_LOW_POLY_ASSETS');source.parm('file').set('$HIP/geo/scatter_assets.bgeo.sc')
source.setComment('15 Maya low-poly assets. Original centimeters converted to meters; local centers at origin. UVs and material IDs preserved.')
source.setGenericFlag(hou.nodeFlag.DisplayComment,True)
pack=obj.createNode('pack','PACK_BY_ASSET_NAME');pack.setInput(0,source)
pack.parm('packbyname').set(1);pack.parm('packedfragments').set(0)
pack.parm('nameattribute').set('name');pack.parm('transfer_attributes').set('name')
# Origin pivot ensures the collision proxy and the visual piece share the same transform.
print('PIVOT_MENU',pack.parm('pivot').menuItems(),pack.parm('pivot').menuLabels(),flush=True)
pack.parm('pivot').set(0)
python=obj.createNode('python','COLLISION_SAFE_DROP_SCATTER');python.setInput(0,source)
with open(ROOT+'/scripts/pile_engine.py') as f:engine=f.read()
driver='''
import hou,json
node=hou.pwd()
source=node.inputs()[0].geometry()
assets=json.loads(source.attribValue('asset_metadata'))
ctrl=node.parent().node('CONTROLS')
length=ctrl.evalParm('length_cm')*.01
width=ctrl.evalParm('width_cm')*.01
height=ctrl.evalParm('height_cm')*.01
density=ctrl.evalParm('density')
placements,collision_bodies,stats=generate(assets,length,width,height,density)
g=node.geometry();g.clear()
name=g.addAttrib(hou.attribType.Point,'name','')
orient=g.addAttrib(hou.attribType.Point,'orient',(0.,0.,0.,1.))
identifier=g.addAttrib(hou.attribType.Point,'id',0)
for item in placements:
    p=g.createPoint();p.setPosition(item['P']);p.setAttribValue(name,item['name']);p.setAttribValue(identifier,item['id'])
    # Engine uses column-vector matrices; HOM uses row-vector matrices.
    q=hou.Quaternion(hou.Matrix3(np.asarray(item['rotation']).T.flatten().tolist()))
    p.setAttribValue(orient,tuple(q))
g.addAttrib(hou.attribType.Global,'placement_stats','');g.setGlobalAttribValue('placement_stats',json.dumps(stats))
g.addAttrib(hou.attribType.Global,'placements','');g.setGlobalAttribValue('placements',json.dumps(placements))
g.addAttrib(hou.attribType.Global,'placed_count',0);g.setGlobalAttribValue('placed_count',len(placements))
g.addAttrib(hou.attribType.Global,'collision_clearance_m',0.);g.setGlobalAttribValue('collision_clearance_m',GAP)
'''
python.parm('python').set(engine+'\n'+driver)
python.setComment('Enclosing convex proxies + complete separating-axis collision test + continuous vertical drop. 3 mm clearance. Frame-independent and deterministic. Too-large parts are skipped.')
python.setGenericFlag(hou.nodeFlag.DisplayComment,True)
copy=obj.createNode('copytopoints','INSTANCE_ASSETS');copy.setInput(0,pack);copy.setInput(1,python)
copy.parm('useidattrib').set(1);copy.parm('idattrib').set('name')
output=obj.createNode('null','OUT_SCATTER');output.setInput(0,copy)
output.setDisplayFlag(True);output.setRenderFlag(True)
output.setColor(hou.Color((.2,.7,.4)))
proxyfile=obj.createNode('file','SOURCE_COLLISION_PROXIES');proxyfile.parm('file').set('$HIP/geo/scatter_collision_proxies.bgeo.sc')
proxypack=obj.createNode('pack','PACK_COLLISION_PROXIES');proxypack.setInput(0,proxyfile)
proxypack.parm('packbyname').set(1);proxypack.parm('packedfragments').set(0);proxypack.parm('pivot').set(0)
proxypack.parm('transfer_attributes').set('name')
proxycopy=obj.createNode('copytopoints','DEBUG_COLLISION_HULLS');proxycopy.setInput(0,proxypack);proxycopy.setInput(1,python)
proxycopy.parm('useidattrib').set(1);proxycopy.parm('idattrib').set('name')
proxyout=obj.createNode('null','OUT_COLLISION_HULLS');proxyout.setInput(0,proxycopy)
proxyout.setColor(hou.Color((.8,.3,.3)))
box=obj.createNode('box','BOUNDS_GUIDE')
for axis,parm in [('x','length_cm'),('y','height_cm'),('z','width_cm')]:
    box.parm('size'+axis).setExpression('ch("../CONTROLS/%s")/100'%parm)
box.parm('ty').setExpression('ch("../CONTROLS/height_cm")/200')
box.setTemplateFlag(True)
box.setComment('Maximum pile envelope. Guide only, excluded from OUT_SCATTER.')
obj.layoutChildren()
ctrl.setPosition(hou.Vector2((-4,5)));source.setPosition(hou.Vector2((0,5)));pack.setPosition(hou.Vector2((0,3)))
python.setPosition(hou.Vector2((4,3)));copy.setPosition(hou.Vector2((1,0)));output.setPosition(hou.Vector2((1,-1.5)))
proxyfile.setPosition(hou.Vector2((8,5)));proxypack.setPosition(hou.Vector2((8,3)))
proxycopy.setPosition(hou.Vector2((8,0)));proxyout.setPosition(hou.Vector2((8,-1.5)));box.setPosition(hou.Vector2((-4,2)))
note=obj.createStickyNote();note.setText('SCRAP PILE | 15 LOW-POLY PARTS\n1. Select green CONTROLS\n2. Length / Width / Height: cm, min 50\n3. Density: 0-100 percent\nOutput: OUT_SCATTER (packed instances)\nCollision check: OUT_COLLISION_HULLS\nNo time simulation or reset needed.');note.setPosition(hou.Vector2((-5,8)))
hou.playbar.setFrameRange(1,120);hou.playbar.setPlaybackRange(1,120);hou.setFrame(1)
ctrl.setSelected(True,clear_all_selected=True)
start=time.time();g=output.geometry()
if output.errors():raise RuntimeError(output.errors())
points=python.geometry();stats=json.loads(points.attribValue('placement_stats'))
print('COOKED',stats,'packed_primitives',len(g.prims()),'seconds',time.time()-start,flush=True)
assert len(g.prims())==stats['placed_count']
placements=json.loads(points.attribValue('placements'))
# Independent recomputation of collision transforms, not just the engine's local state.
from pile_engine import oriented
import numpy as np
bodies=[]
for item in placements:
    a=oriented(meta[item['asset_index']],np.asarray(item['rotation']));pos=np.asarray(item['P'])
    a['vertices']+=pos;a['lo']+=pos;a['hi']+=pos;bodies.append(a)
stats.update(validate(bodies,2.2,1.8,1.))
assert not stats['overlapping_proxy_pairs'] and not stats['outside_bounds']
g.saveToFile(ROOT+'/geo/Scatter_Pile_Default.bgeo.sc')
with open(ROOT+'/geo/pile_preview_transforms.json','w') as f:json.dump(placements,f,indent=2)
with open(ROOT+'/geo/pile_validation.json','w') as f:json.dump(stats,f,indent=2)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('SAVED',hou.hipFile.path(),flush=True)
