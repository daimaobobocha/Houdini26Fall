"""Create a separate ~10 percent polygon-count version of each scatter asset."""
import os
import json
import math
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as c
import maya.api.OpenMaya as om

ROOT=os.path.dirname(os.path.abspath(__file__))
SOURCE=os.path.join(ROOT,'Scatter_Models.ma')
OUTPUT=os.path.join(ROOT,'Scatter_Models_LowPoly.ma')

def low_beam(old,length):
    parent=c.listRelatives(old,parent=True,fullPath=True)[0]
    w,h,t,s=12.,16.,1.2,.8
    outline=[(-w/2,0),(w/2,0),(w/2,t),(s/2,t),(s/2,h-t),(w/2,h-t),
             (w/2,h),(-w/2,h),(-w/2,h-t),(-s/2,h-t),(-s/2,t),(-w/2,t)]
    vertices=[om.MPoint(x,y,z) for z in [-length/2,length/2] for x,y in outline]
    faces=[list(reversed(range(12))),list(range(12,24))]
    faces += [[i,(i+1)%12,(i+1)%12+12,i+12] for i in range(12)]
    # 15 polygons, against the original 154; retain the exact I profile and dimensions.
    q=faces.pop();faces.extend([[q[0],q[1],q[2]],[q[0],q[2],q[3]]])
    fn=om.MFnMesh();fn.create(vertices,[len(f) for f in faces],[v for f in faces for v in f])
    obj=c.listRelatives(fn.fullPathName(),parent=True,fullPath=True)[0]
    c.delete(old)
    obj=c.rename(obj,old)
    c.parent(obj,parent,relative=True)
    c.sets(obj,edit=True,forceElement='MAT_AgedSteelSG')
    c.polySoftEdge(obj,angle=30,constructionHistory=False)
    c.polyAutoProjection(obj,planes=6,layout=2,scaleMode=1,percentageSpace=.3,constructionHistory=False)
    return obj

def reduce_copy(original,percentage):
    obj=c.duplicate(original,name='ReductionTrial')[0]
    c.polyReduce(obj,version=1,termination=0,percentage=percentage,
                 keepQuadsWeight=1.0,preserveTopology=True,
                 keepBorder=True,keepMapBorder=False,keepColorBorder=False,
                 keepFaceGroupBorder=False,keepHardEdge=False,keepCreaseEdge=False,
                 useVirtualSymmetry=0,constructionHistory=False)
    return obj

try:
    c.file(SOURCE,open=True,force=True)
    with open(os.path.join(ROOT,'asset_manifest.json')) as f:assets=json.load(f)
    report=[]
    for a in assets:
        obj=a['mesh'];before=c.polyEvaluate(obj,face=True);target=int(round(before*.1))
        bb=c.exactWorldBoundingBox(obj)
        if '_IBeam_' in obj:
            length=a['dimensions_cm'][2]
            obj=low_beam(obj,length)
        else:
            best=None;best_error=float('inf');lo=0.;hi=100.;pct=90.
            for attempt in range(10):
                trial=reduce_copy(obj,pct)
                count=c.polyEvaluate(trial,face=True);error=abs(count-target)
                print('TRIAL',obj,round(pct,4),count,'target',target,flush=True)
                if error<best_error:
                    if best:c.delete(best)
                    best=trial;best_error=error
                else:c.delete(trial)
                if error<=max(2,target*.015):break
                if count>target:lo=pct
                else:hi=pct
                pct=(lo+hi)/2
            c.delete(obj)
            obj=c.rename(best,obj)
            c.delete(obj,constructionHistory=True)
            c.polySoftEdge(obj,angle=40,constructionHistory=False)
        after=c.polyEvaluate(obj,face=True)
        issues={k:len(c.polyInfo(obj,**{k:True}) or []) for k in ['nonManifoldEdges','nonManifoldVertices','laminaFaces']}
        bbox=c.exactWorldBoundingBox(obj)
        report.append({'name':a['name'],'original_faces':before,'target_faces':target,'lowpoly_faces':after,
                       'retained_percent':round(100.*after/before,2),'triangles':c.polyEvaluate(obj,triangle=True),
                       'uvs':c.polyEvaluate(obj,uvcoord=True),'topology_issues':issues,
                       'original_dimensions_cm':[round(bb[i+3]-bb[i],3) for i in range(3)],
                       'lowpoly_dimensions_cm':[round(bbox[i+3]-bbox[i],3) for i in range(3)]})
        c.addAttr(obj,longName='originalFaceCount',attributeType='long',defaultValue=before)
        c.addAttr(obj,longName='lowPolyFaceCount',attributeType='long',defaultValue=after)
        print('FINISHED',obj,before,'->',after,issues,flush=True)
    c.select(clear=True)
    c.file(rename=OUTPUT);c.file(save=True,type='mayaAscii',force=True)
    c.file(OUTPUT,open=True,force=True)
    assert len(c.listRelatives('SCATTER_MODELS_11_ASSETS',children=True,type='transform'))==11
    for a,r in zip(assets,report):
        assert c.polyEvaluate(a['mesh'],face=True)==r['lowpoly_faces']
        assert not any(r['topology_issues'].values()),r
    with open(os.path.join(ROOT,'lowpoly_comparison.json'),'w') as f:json.dump(report,f,indent=2)
    print('SAVED_AND_REOPENED',OUTPUT,flush=True)
    print('TOTAL',sum(r['original_faces'] for r in report),'->',sum(r['lowpoly_faces'] for r in report),flush=True)
finally:
    maya.standalone.uninitialize()
