import os,time,json
import hou
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.clear(suppress_save_prompt=True)
obj=hou.node('/obj').createNode('geo','proxy_build')
source=obj.createNode('file','Source');source.parm('file').set(ROOT+'/geo/scatter_assets.bgeo.sc')
decomp=obj.createNode('convexdecomposition','Detailed_Compound_Shapes');decomp.setInput(0,source)
decomp.parm('maxconcavity').set(.002)
decomp.parm('geometryoutput').set(1)
decomp.parm('mergesegments').set(1)
print('DECOMP_START',flush=True);t=time.time()
geo=decomp.geometry()
print('DECOMP',len(geo.points()),len(geo.prims()),'sec',time.time()-t,flush=True)
geo=geo.freeze()
# Exact three-box I sections avoid n-gon decomposition filling the web recesses.
beams={'SM_04_IBeam_100cm':1.,'SM_05_IBeam_50cm':.5,'SM_06_IBeam_30cm':.3}
geo.deletePrims([p for p in geo.prims() if p.stringAttribValue('name') in beams],True)
segment=100000
for name,length in beams.items():
    for size,position in [((.12,.012,length),(0,-.074,0)),((.12,.012,length),(0,.074,0)),((.008,.136,length),(0,0,0))]:
        box=obj.createNode('box');box.parmTuple('size').set(size);box.parmTuple('t').set(position)
        part=box.geometry().freeze()
        part.addAttrib(hou.attribType.Prim,'name',name);part.addAttrib(hou.attribType.Prim,'segment',segment)
        for p in part.prims():p.setAttribValue('name',name);p.setAttribValue('segment',segment)
        geo.merge(part);segment+=1;box.destroy()
geo.saveToFile(ROOT+'/geo/scatter_bullet_compounds.bgeo.sc')
stats={}
for p in geo.prims():
    name=p.stringAttribValue('name');stats.setdefault(name,set()).add(p.intAttribValue('segment'))
print('SEGMENTS',{k:len(v) for k,v in stats.items()},flush=True)
with open(ROOT+'/geo/bullet_proxy_stats.json','w') as f:json.dump({k:len(v) for k,v in stats.items()},f,indent=2)
