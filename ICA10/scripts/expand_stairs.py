import hou, os, shutil, json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hip=ROOT+'/ICA10.hipnc'
backup=ROOT+'/backup/ICA10_before_node_expansion.hipnc'
if not os.path.exists(backup): shutil.copy2(hip,backup)
hou.hipFile.load(hip,suppress_save_prompt=True,ignore_load_warnings=True)
g=hou.node('/obj/STAIRCASE')
asset=g.node('ICA10_Stairs')
assert asset is not None,'Stair asset is already expanded or missing'
baseline=asset.geometry().freeze()
control=g.createNode('null','STAIR_CONTROLS')
control.setParmTemplateGroup(asset.parmTemplateGroup())
for p in asset.parms():
    target=control.parm(p.name())
    if target:
        try: target.set(p.eval())
        except hou.Error: pass
control.setColor(hou.Color((1,.65,.15)))
control.setComment('Staircase controls. All original modeling nodes are expanded alongside this node.')
control.setGenericFlag(hou.nodeFlag.DisplayComment,True)
asset.allowEditingOfContents()
items=asset.extractAndDelete()
refs={
 'box1':{'sizex':'sizex','sizey':'sizey','sizez':'sizez'},
 'resample1':{'length':'length'},
 'grouprange2':{'start1':'offset1','end1':'offset2'},
 'pointwrangle1':{'length':'railheight'},
 'copy3_midrails':{'ncy':'midrailcount'},
 'grid1':{'sizex':'stringersizex','sizey':'stringersizey'},
}
for name,parms in refs.items():
    node=g.node(name)
    for dst,src in parms.items():
        node.parm(dst).setExpression('ch("../STAIR_CONTROLS/'+src+'")',hou.exprLanguage.Hscript)
out=g.node('OUT_STAIRCASE')
out.setDisplayFlag(True);out.setRenderFlag(True)
g.node('EXPORT_STAIR_FBX').setInput(0,out)
g.layoutChildren()
control.setPosition(g.node('curve1').position()+hou.Vector2(-4,0))
geo=out.geometry().freeze()
assert not out.errors(),out.errors()
assert len(geo.points())==len(baseline.points()) and len(geo.prims())==len(baseline.prims())
max_delta=max((a.position()-b.position()).length() for a,b in zip(geo.points(),baseline.points()))
assert max_delta<1e-6,max_delta
width=control.parm('sizex');original=width.eval();width.set(original+2)
assert out.geometry().boundingBox().sizevec()[0]>geo.boundingBox().sizevec()[0]+1
width.set(original)
errors={n.path():n.errors() for n in g.children() if n.errors()}
assert not errors,errors
out.setCurrent(True,clear_all_selected=True)
hou.hipFile.save(hip)
report={'expanded':True,'network':g.path(),'nodes':len(g.children()),'points':len(out.geometry().points()),'primitives':len(out.geometry().prims()),'max_position_difference':max_delta,'width_parameter_verified':True}
with open(ROOT+'/node_expansion_validation.json','w') as f:json.dump(report,f,indent=2)
print(json.dumps(report),flush=True)
