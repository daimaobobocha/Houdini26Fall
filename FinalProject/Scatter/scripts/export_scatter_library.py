"""Export the current Maya low-poly meshes in meters, including UVs and material IDs."""
import os,json
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as c
import maya.api.OpenMaya as om
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE=os.path.join(os.path.dirname(ROOT),'Models','Scatter_Models','Scatter_Models_LowPoly.ma')
try:
    c.file(SOURCE,open=True,force=True)
    assets=[]
    for obj in sorted(c.ls('SM_*_GEO',type='transform')):
        shape=c.listRelatives(obj,shapes=True,fullPath=True)[0]
        sl=om.MSelectionList();sl.add(shape);fn=om.MFnMesh(sl.getDagPath(0))
        pts=[[v.x*.01,v.y*.01,v.z*.01] for v in fn.getPoints(om.MSpace.kObject)]
        center=[(min(p[i] for p in pts)+max(p[i] for p in pts))*.5 for i in range(3)]
        pts=[[p[i]-center[i] for i in range(3)] for p in pts]
        shaders,indices=fn.getConnectedShaders(0)
        mats=[om.MFnDependencyNode(s).name() for s in shaders]
        us,vs=fn.getUVs()
        faces=[];uvs=[]
        for i in range(fn.numPolygons):
            face=list(fn.getPolygonVertices(i));faces.append(face)
            uv=[]
            for j in range(len(face)):
                k=fn.getPolygonUVid(i,j);uv.append([us[k],vs[k]])
            uvs.append(uv)
        assets.append({'name':obj[:-4],'source_mesh':obj,'center_m':center,'vertices':pts,'faces':faces,
                       'uvs':uvs,'materials':mats,'material_ids':list(indices)})
    path=os.path.join(ROOT,'geo','scatter_asset_library.json')
    with open(path,'w') as f:json.dump(assets,f,separators=(',',':'))
    print('EXPORTED',len(assets),'assets',sum(len(a['faces']) for a in assets),'faces',path)
finally:maya.standalone.uninitialize()
