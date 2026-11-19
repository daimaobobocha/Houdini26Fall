import hou, os, json, time
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
os.makedirs(ROOT+'/geo/ghost',exist_ok=True)
os.makedirs(ROOT+'/geo/rbd',exist_ok=True)
hou.hipFile.clear(suppress_save_prompt=True)
hou.hipFile.setName(ROOT+'/ICA_13.hipnc')
hou.setFps(24)
hou.playbar.setFrameRange(1,96)
hou.playbar.setPlaybackRange(1,96)
hou.setFrame(1)

def node(parent,typ,name,inputs=(),parms=None,comment=None):
    n=parent.createNode(typ,name)
    for i,x in enumerate(inputs):
        if isinstance(x,tuple):n.setInput(i,x[0],x[1])
        elif x:n.setInput(i,x)
    if parms:n.setParms(parms)
    if comment:
        n.setComment(comment);n.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    return n
def obj(name,tx,color):
    g=node(hou.node('/obj'),'geo',name,parms={'tx':tx})
    for c in g.children():c.destroy()
    g.setColor(hou.Color(color))
    return g
def cached_output(g,sim,folder,name):
    f=node(g,'file','READ_BAKED_ANIMATION',parms={'file':'$HIP/geo/'+folder+'/'+folder+'.$F4.bgeo.sc'},comment='96 cached frames for immediate playback. Switch to live simulation after editing upstream nodes.')
    sw=node(g,'switch','CACHE_OR_LIVE',(sim,f),{'input':0},'0 = live simulation; 1 = supplied disk cache. Rebuild caches after editing the simulation.')
    out=node(g,'null',name,(sw,))
    out.setColor(hou.Color((.2,.75,.4)));out.setDisplayFlag(True);out.setRenderFlag(True)
    return sw,out

ghost=obj('VELLUM_GHOST',-8,(.35,.62,.85))
grid=node(ghost,'grid','grid_sheet',parms={'rows':50,'cols':50,'ty':5},comment='Lecture: 10 x 10 sheet, 50 x 50 grid, center Y = 5.')
remesh=node(ghost,'remesh','remesh_triangles',(grid,),{'targetsize':.18},'Triangulated cloth. Target size inferred from the transcript.')
uv=node(ghost,'attribwrangle','sheet_uv',(remesh,),{'snippet':'v@uv = set((@P.x+5)/10, (@P.z+5)/10, 0);'})
sphere=node(ghost,'sphere','sphere_collider',parms={'type':2,'radx':3,'rady':3,'radz':3,'rows':64,'cols':96})
cloth=node(ghost,'vellumconstraints','vellumconfigurecloth',(uv,None,sphere),{'constrainttype':3},'Cloth stretch and bend constraints; sphere enters collision input 3.')
solver=node(ghost,'vellumsolver','vellumsolver',[(cloth,0),(cloth,1),(cloth,2)],{'substeps':3})
forces=solver.node('dopnet1/forces')
pop=node(forces,'popforce','popforce_sheet_motion')
print('POPFORCE_PARMS',[(p.name(),p.eval()) for p in pop.parms() if any(s in p.name() for s in ['amp','swirl','noise'])],flush=True)
pop.setParms({'amp':1.2,'swirlsize':3})
forces.node('FORCE').setInput(0,pop)
forces.layoutChildren()
normal=node(ghost,'normal','cloth_normals',(solver,))
gsw,gout=cached_output(ghost,normal,'ghost','OUT_VELLUM')
ghost.layoutChildren()

rbd=obj('RBD_FRACTURE',8,(.9,.54,.24))
ball=node(rbd,'sphere','sphere_to_fracture',parms={'type':2,'radx':3,'rady':3,'radz':3,'ty':7,'rows':32,'cols':48},comment='Lecture: radius 3; height raised to 7 for a stronger ground impact.')
frac=node(rbd,'rbdmaterialfracture','rbdmaterialfracture',(ball,),{'concrete_scatterpts1':13,'concrete_primarystrength':10,'concrete_enablechipping':0,'concrete_interiordetail':0},'Concrete; 13 primary cells, weak glue strength 10. Chipping and interior detail remain available, as demonstrated.')
pack=node(rbd,'pack','pack_named_fragments',(frac,),{'packbyname':1,'nameattribute':'name','packedfragments':0,'transfer_attributes':'name'},'Preserve one packed primitive per named fragment for rigid VAT.')
vel=node(rbd,'attribwrangle','initial_velocity',(pack,),{'snippet':'// Signed random velocity, as discussed in class.\n@v = (rand(@ptnum + 13.0) - 0.5) * 0.3;'},'Small signed initial velocity. Edit amplitude here to explore the classroom velocity exercise.')
bullet=node(rbd,'rbdbulletsolver','rbdbulletsolver',[vel,(frac,1),(frac,2)],{'useground':1,'transferattributes':'age v w orient pivot','transfertogeo':1},'Transfer real Bullet orientation, pivot and angular velocity to packed points for VAT.')
rsw,rout=cached_output(rbd,bullet,'rbd','OUT_RBD')
exploded=node(rbd,'explodedview','EXPLODED_VIEW',(frac,),comment='Optional inspection branch: display this node to inspect fractured pieces.')
rbd.layoutChildren()

rop=node(hou.node('/obj'),'ropnet','VAT_EXPORTS')
for name,mode,path,folder,end in [('VAT_GHOST',0,gout.path(),'ghost',96),('VAT_RBD',1,rout.path(),'rbd',90)]:
    vat=node(rop,'labs::vertex_animation_textures::3.0',name,parms={'mode':mode,'engine':'unreal','soppath':path,'exportpath':'$HIP/export/'+folder,'assetname':name,'enable_datafile':1,'exportlegacydatafile':1})
    for pn,val in [('f1',1),('f2',end)]:vat.parm(pn).deleteAllKeyframes();vat.parm(pn).set(val)
    vat.setComment('Unreal VAT export. Render All writes FBX mesh and EXR textures. Input reads supplied relative disk cache.');vat.setGenericFlag(hou.nodeFlag.DisplayComment,True)
rop.layoutChildren()
note=hou.node('/obj').createStickyNote('READ_ME')
note.setText('ICA_13 | Houdini to Unreal: VAT\n\nLEFT: Vellum sheet ghost (frames 1-96)\nRIGHT: Concrete sphere fracture (frames 1-90)\nVAT_EXPORTS: Soft and Rigid export nodes\n\nInside each object: CACHE_OR_LIVE\n1 = supplied cache / immediate playback\n0 = editable live simulation\n\nClass transcript reconstruction. Unstated settings inferred.\nObject translations only separate the previews.')
note.setSize(hou.Vector2(6,4))
hou.node('/obj').layoutChildren()
hou.hipFile.save()
print('SCENE_CREATED',hou.hipFile.path(),flush=True)

report={'version':hou.applicationVersionString(),'frames':96,'ghost':{},'rbd':{}}
start=time.time()
for frame in range(1,97):
    hou.setFrame(frame)
    for key,n in [('ghost',normal),('rbd',bullet)]:
        geo=n.geometry()
        if n.errors():raise RuntimeError(n.path()+str(n.errors()))
        if not geo.points():raise RuntimeError('Empty geometry '+n.path())
        geo.saveToFile(ROOT+'/geo/'+key+'/'+key+'.%04d.bgeo.sc'%frame)
        if frame in (1,24,48,72,90,96):
            report[key][str(frame)]={'points':len(geo.points()),'primitives':len(geo.prims()),'bbox':[list(geo.boundingBox().minvec()),list(geo.boundingBox().maxvec())],'point_attributes':[a.name() for a in geo.pointAttribs()],'primitive_type':str(geo.prim(0).type())}
    if frame==1 or frame%12==0:print('CACHED_FRAME',frame,'SECONDS',round(time.time()-start,1),flush=True)
gsw.parm('input').set(1);rsw.parm('input').set(1)
hou.setFrame(48)
ghost.setSelected(True,clear_all_selected=True)
hou.hipFile.save()
with open(ROOT+'/validation.json','w') as f:json.dump(report,f,indent=2)
print('CACHE_COMPLETE',hou.hipFile.path(),flush=True)
