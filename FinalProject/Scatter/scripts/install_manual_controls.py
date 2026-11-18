import os,json,hashlib,shutil,re
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(ROOT+'/Scatter_Pile.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
obj=hou.node('/obj/SCATTER_PILE');names=['length_cm','width_cm','height_cm','density']
current={k:obj.evalParm(k) for k in names}
with open(ROOT+'/geo/gravity_settings.json') as f:old_settings=json.load(f)
built={k:old_settings[k] for k in names}
# Always display the last completed cached result, regardless of slider values.
obj.node('OUT_SCATTER').setInput(0,obj.node('SETTLED_DEFAULT_CACHE'))
obj.node('OUT_COLLISION_HULLS').setInput(0,obj.node('SETTLED_PROXY_CACHE'))
for name in ['FINAL_OR_CACHED','FINAL_PROXY_OR_CACHED']:
    n=obj.node(name)
    if n:n.parm('input').deleteAllKeyframes();n.parm('input').set(1)
committed=obj.node('BUILD_SETTINGS') or obj.createNode('null','BUILD_SETTINGS')
ptg=committed.parmTemplateGroup()
for k in names:
    if ptg.find(k) is None:ptg.append(hou.FloatParmTemplate(k,k,1,default_value=(built[k],)))
committed.setParmTemplateGroup(ptg)
for k in names:committed.parm(k).set(built[k])
committed.setComment('Last explicitly generated settings. UI sliders do not drive this node. Updated only by Rebuild Pile.')
committed.setColor(hou.Color((.35,.35,.4)))
initial=obj.node('INITIAL_SAFE_LAYOUT');code=initial.parm('python').unexpandedString()
code=code.replace('ctrl=node.parent()\n',"ctrl=node.parent().node('BUILD_SETTINGS')\n")
initial.parm('python').set(code)
walls=obj.node('CONTAINER_WALLS');code=re.sub(r"parent=node\.parent\(\)(?:\.node\(['\"]BUILD_SETTINGS['\"]\))*","parent=node.parent().node('BUILD_SETTINGS')",walls.parm('python').unexpandedString())
walls.parm('python').set(code)
for name in ['FINAL_CONTACT_CLEANUP','FINAL_PROXY_CLEANUP']:
    n=obj.node(name)
    if n:n.parm('python').set(re.sub(r"obj=node\.parent\(\)(?:\.node\(['\"]BUILD_SETTINGS['\"]\))*","obj=node.parent().node('BUILD_SETTINGS')",n.parm('python').unexpandedString()))
solver=obj.node('GRAVITY_SETTLE')
for name,input_index in [('SIM_INPUT_VISUAL',0),('SIM_INPUT_PROXY',2),('SIM_INPUT_WALLS',3)]:
    stash=obj.node(name) or obj.createNode('stash',name)
    stash.parm('stash').set(hou.Geometry());stash.setColor(hou.Color((.6,.45,.2)))
    stash.setComment('Fixed data prepared once by Rebuild Pile; disconnected from live sliders.')
    solver.setInput(input_index,stash)
solver.parm('overwritefromsop').set(0)
for p in solver.parms():
    if 'cache' in p.name() and p.parmTemplate().label()=='Cache Memory (MB)':p.set(256)
# Embed the callback and cleanup engine so the button does not depend on loose Python files.
with open(ROOT+'/scripts/manual_rebuild_pile.py') as f:obj.setUserData('manual_build_code',f.read())
with open(ROOT+'/scripts/contact_cleanup_engine.py') as f:obj.setUserData('contact_cleanup_code',f.read())
changed='''
node=kwargs['node']
if node.userData('pile_build_running')!='1':
    node.parm('build_status').set('Preview only — click Rebuild Pile to apply these values. Previous pile is still displayed.')
'''
folder=hou.FolderParmTemplate('scatter_controls','Scatter Controls')
for k,label,low,high in [('length_cm','Length (cm)',50,1000),('width_cm','Width (cm)',50,1000),('height_cm','Height (cm)',50,500),('density','Scatter Density (%)',0,100)]:
    p=hou.FloatParmTemplate(k,label,1,default_value=(current[k],),min=low,max=high,min_is_strict=True,max_is_strict=k=='density')
    p.setScriptCallback(changed);p.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    p.setHelp('Editing this slider only changes the lightweight range preview. Click Rebuild Pile to generate and cache a new gravity-settled result.')
    folder.addParmTemplate(p)
button=hou.ButtonParmTemplate('rebuild_pile','Rebuild Pile / 重新生成堆积')
button.setScriptCallback("exec(kwargs['node'].userData('manual_build_code'), {'hou': hou, 'node': kwargs['node']})")
button.setScriptCallbackLanguage(hou.scriptLanguage.Python)
button.setHelp('Calculate once using these settings. Shows progress; Esc cancels. Previously completed settings reuse their cached result.')
folder.addParmTemplate(button)
p=hou.StringParmTemplate('build_status','Status',1,default_value=('Cached pile ready. Dragging sliders does not simulate.',))
p.setConditional(hou.parmCondType.DisableWhen,'{ length_cm >= 50 }');folder.addParmTemplate(p)
pg=obj.parmTemplateGroup();pg.replace('scatter_controls',folder);obj.setParmTemplateGroup(pg)
for k,v in current.items():obj.parm(k).set(v)
obj.parm('build_status').set('Cached pile ready. Sliders preview only; click Rebuild Pile to apply.')
obj.setUserData('pile_built_settings',json.dumps(built,sort_keys=True))
# Register the existing verified result in the same content-addressed cache used by the button.
fingerprints=[]
for path in ['geo/scatter_assets.bgeo.sc','geo/scatter_bullet_compounds.bgeo.sc','geo/bullet_hull_metadata.json']:
    s=os.stat(ROOT+'/'+path);fingerprints.append((path,s.st_size,s.st_mtime_ns))
key=hashlib.sha256(json.dumps(['manual-gravity-v2',built,fingerprints],sort_keys=True).encode()).hexdigest()[:20]
relative='sim/pile_cache/'+key;folder_path=ROOT+'/'+relative;os.makedirs(folder_path,exist_ok=True)
shutil.copy2(ROOT+'/geo/Scatter_Pile_Settled.bgeo.sc',folder_path+'/visual.bgeo.sc')
shutil.copy2(ROOT+'/geo/Scatter_Pile_Settled_Proxies.bgeo.sc',folder_path+'/proxy.bgeo.sc')
with open(folder_path+'/manifest.json','w') as f:json.dump({'version':'manual-gravity-v2','parameters':built,'piece_count':old_settings['output_piece_count'],'verified_existing_result':True},f,indent=2)
obj.node('SETTLED_DEFAULT_CACHE').parm('file').set('$HIP/'+relative+'/visual.bgeo.sc')
obj.node('SETTLED_PROXY_CACHE').parm('file').set('$HIP/'+relative+'/proxy.bgeo.sc')
obj.setUserData('pile_active_cache',key)
obj.setComment('FAST CONTROLS: sliders update only the bounds guide. Click Rebuild Pile for one explicit gravity calculation. Cached result stays visible; Esc cancels safely.')
for note in obj.stickyNotes():
    note.setText('FAST MANUAL BUILD\n1. Select OUTER SCATTER_PILE GEO.\n2. Drag Length / Width / Height / Density.\n   Only the bounds guide updates; no simulation.\n3. Click Rebuild Pile / 重新生成堆积.\n   Progress + Esc cancellation.\n4. Completed parameter combinations are cached.\n\nOUT_SCATTER always shows the last completed result.\nBUILD_SETTINGS changes only on an explicit build.\nSIM_INPUT stashes isolate the solver from SOP recooks.\nOriginal collision precision and upright barrel rules remain.')
obj.node('OUT_SCATTER').setDisplayFlag(True);obj.node('OUT_SCATTER').setRenderFlag(True)
obj.node('BOUNDS_GUIDE').setTemplateFlag(True)
for n in obj.children():
    if n!=obj.node('BOUNDS_GUIDE') and n.isGenericFlagSet(hou.nodeFlag.Template):n.setTemplateFlag(False)
obj.layoutChildren();obj.setSelected(True,clear_all_selected=True)
hou.setFrame(1);hou.setUpdateMode(hou.updateMode.AutoUpdate)
hou.hipFile.save(ROOT+'/Scatter_Pile.hipnc')
print('MANUAL_CONTROLS_SAVED',current,key,flush=True)
