import hou,os,json,math
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/ICA_13.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
checks={}
for name,folder,outname in [('VELLUM_GHOST','ghost','OUT_VELLUM'),('RBD_FRACTURE','rbd','OUT_RBD')]:
    obj=hou.node('/obj/'+name);out=obj.node(outname)
    assert obj.node('CACHE_OR_LIVE').evalParm('input')==1
    counts=set();samples={}
    for frame in range(1,97):
        hou.setFrame(frame);geo=out.geometry()
        assert not out.errors(),out.errors()
        counts.add((len(geo.points()),len(geo.prims())))
        assert all(math.isfinite(x) for p in geo.points() for x in p.position())
        if frame in (1,48,96):samples[frame]=list(geo.point(0).position())
        if folder=='rbd':
            for attr in ('pivot','orient','w'):assert geo.findPointAttrib(attr),attr
    assert len(counts)==1
    assert samples[1]!=samples[48]
    checks[folder]={'frames_verified':96,'topology':list(counts)[0],'motion_samples':samples,'errors':[]}
unpack=hou.node('/obj/RBD_FRACTURE').createNode('unpack','TEMP_VALIDATE_SURFACE')
unpack.setInput(0,hou.node('/obj/RBD_FRACTURE/OUT_RBD'))
checks['rbd']['final_surface_min_y']=unpack.geometry().boundingBox().minvec()[1]
unpack.destroy()
for key in ('ghost','rbd'):
    asset='VAT_'+('GHOST' if key=='ghost' else 'RBD')
    expected=['geo/'+asset+'_mesh.fbx']+['tex/'+asset+'_'+kind+'.exr' for kind in ('pos','rot','col')]+['data/'+asset+'_data.json']
    sizes={p:os.path.getsize(ROOT+'/export/'+key+'/'+p) for p in expected}
    assert all(size>0 for size in sizes.values())
    checks[key]['vat_files']=sizes
with open(ROOT+'/verification.json','w') as f:json.dump(checks,f,indent=2)
print(json.dumps(checks,indent=2),flush=True)
