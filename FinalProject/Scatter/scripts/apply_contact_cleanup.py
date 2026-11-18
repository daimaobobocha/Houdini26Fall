import os,sys,json
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
sys.path.insert(0,os.path.dirname(__file__))
from contact_cleanup_engine import clean_contacts
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE')
with open(ROOT+'/geo/bullet_hull_metadata.json') as f:metadata=json.load(f)
assert len(metadata)==15
visual=hou.Geometry();visual.loadFromFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc')
proxy=hou.Geometry();proxy.loadFromFile(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
L,W,H=[obj.evalParm(k)*.01 for k in ['length_cm','width_cm','height_cm']]
visual,proxy,report=clean_contacts(visual,proxy,metadata,L,W,H)
visual.saveToFile(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc');visual.saveToFile(ROOT+'/geo/Scatter_Pile_Default.bgeo.sc')
proxy.saveToFile(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc')
with open(ROOT+'/geo/contact_cleanup_report.json','w') as f:json.dump(report,f,indent=2)
with open(ROOT+'/scripts/contact_cleanup_engine.py') as f:engine=f.read()
for name,output in [('FINAL_CONTACT_CLEANUP','visual'),('FINAL_PROXY_CLEANUP','proxy')]:
    n=obj.node(name) or obj.createNode('python',name)
    n.setInput(0,obj.node('SETTLED_FRAME'));n.setInput(1,obj.node('SETTLED_PROXY_FRAME'))
    driver='''
import hou,json
node=hou.pwd();obj=node.parent()
v=node.inputs()[0].geometry().freeze();p=node.inputs()[1].geometry().freeze()
with open(hou.expandString('$HIP/geo/bullet_hull_metadata.json')) as f:metadata=json.load(f)
v,p,report=clean_contacts(v,p,metadata,*[max(.5,obj.evalParm(k)*.01) for k in ['length_cm','width_cm','height_cm']])
g=node.geometry();g.clear();g.merge(OUTPUT)
'''.replace('OUTPUT','v' if output=='visual' else 'p')
    n.parm('python').set(engine+'\n'+driver)
    n.setComment('Final microscopic collision cleanup after gravity. Preserves the barrel, floor, bounds and full object orientation. No whole-object convex proxy gaps.')
obj.node('FINAL_OR_CACHED').setInput(0,obj.node('FINAL_CONTACT_CLEANUP'))
obj.node('FINAL_PROXY_OR_CACHED').setInput(0,obj.node('FINAL_PROXY_CLEANUP'))
obj.node('SETTLED_DEFAULT_CACHE').parm('reload').pressButton();obj.node('SETTLED_PROXY_CACHE').parm('reload').pressButton()
obj.layoutChildren();obj.setSelected(True,clear_all_selected=True);hou.setFrame(1)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('CONTACT_CLEANUP',report,flush=True)
