"""Replace the three oversized chassis with compact low-poly suspension parts."""
import os
import json
import math
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as c
import maya.api.OpenMaya as om

ROOT=os.path.dirname(os.path.abspath(__file__))
SCENE=os.path.join(ROOT,'Scatter_Models_LowPoly.ma')
TAU=math.pi*2
STEEL='MAT_AgedSteelSG'
DARK='MAT_DarkSteelSG'
RUST='MAT_RustedIronSG'
ADDED=[]

def mesh(name,vertices,faces,mat,smooth=35):
    fn=om.MFnMesh()
    fn.create([om.MPoint(*v) for v in vertices],[len(f) for f in faces],[i for f in faces for i in f])
    obj=c.rename(c.listRelatives(fn.fullPathName(),parent=True,fullPath=True)[0],name)
    c.sets(obj,edit=True,forceElement=mat)
    c.polySoftEdge(obj,angle=smooth,constructionHistory=False)
    return obj

def box(name,dimensions,position,mat):
    obj=c.polyCube(name=name,width=dimensions[0],height=dimensions[1],depth=dimensions[2],constructionHistory=False)[0]
    c.move(*position,obj)
    c.sets(obj,edit=True,forceElement=mat)
    return obj

def cylinder(name,radius,height,pos,mat,n=6):
    obj=c.polyCylinder(name=name,radius=radius,height=height,subdivisionsX=n,constructionHistory=False)[0]
    c.move(*pos,obj)
    c.sets(obj,edit=True,forceElement=mat)
    return obj

def tube(name,profile,mat,n=24):
    # Revolved profile around Z. The winding gives outward exterior and inward bore normals.
    vertices=[(r*math.cos(TAU*i/n),r*math.sin(TAU*i/n),z) for r,z in profile for i in range(n)]
    faces=[]
    for j in range(len(profile)):
        k=(j+1)%len(profile)
        for i in range(n):
            q=(i+1)%n
            faces.append([j*n+i,j*n+q,k*n+q,k*n+i])
    return mesh(name,vertices,faces,mat)

def rectangle(name,width,height,thickness,depth,mat):
    outer=[(-width/2,0),(width/2,0),(width/2,height),(-width/2,height)]
    inner=[(-width/2+thickness,thickness),(width/2-thickness,thickness),
           (width/2-thickness,height-thickness),(-width/2+thickness,height-thickness)]
    verts=[(x,y,z) for z in [-depth/2,depth/2] for x,y in outer+inner]
    faces=[]
    for i in range(4):
        j=(i+1)%4
        faces += [[i,4+i,4+j,j],[8+i,8+j,12+j,12+i],
                  [i,j,8+j,8+i],[4+i,12+i,12+j,4+j]]
    return mesh(name,verts,faces,mat,30)

def bar_between(name,start,end,width,depth,mat):
    a=om.MVector(*start);b=om.MVector(*end);delta=b-a
    mid=(a+b)*.5
    obj=box(name,(width,delta.length(),depth),(0,0,0),mat)
    quat=om.MVector(0,1,0).rotateTo(delta.normal())
    euler=quat.asEulerRotation()
    c.rotate(math.degrees(euler.x),math.degrees(euler.y),math.degrees(euler.z),obj)
    c.move(mid.x,mid.y,mid.z,obj)
    return obj

def finish(name,parts,position,description):
    obj=c.polyUnite(parts,name=name+'_GEO',constructionHistory=False,mergeUVSets=1)[0] if len(parts)>1 else c.rename(parts[0],name+'_GEO')
    c.delete(obj,constructionHistory=True)
    c.makeIdentity(obj,apply=True,t=True,r=True,s=True,normal=1)
    bounds=c.exactWorldBoundingBox(obj)
    c.move(0,-bounds[1],0,obj,relative=True)
    c.makeIdentity(obj,apply=True,t=True,r=True,s=True,normal=1)
    c.xform(obj,pivots=(0,0,0),worldSpace=True)
    c.polyAutoProjection(obj,planes=6,layout=2,scaleMode=1,percentageSpace=.3,constructionHistory=False)
    grp=c.group(obj,name=name+'_GRP')
    c.xform(grp,pivots=(0,0,0),worldSpace=True)
    c.addAttr(grp,longName='assetDescription',dataType='string')
    c.setAttr(grp+'.assetDescription',description,type='string')
    c.addAttr(grp,longName='units',dataType='string')
    c.setAttr(grp+'.units','centimeters; Y up; bottom pivot',type='string')
    count=c.polyEvaluate(obj,face=True)
    c.addAttr(obj,longName='lowPolyFaceCount',attributeType='long',defaultValue=count)
    c.move(*position,grp)
    c.parent(grp,MASTER)
    ADDED.append(grp)
    print('ADDED',grp,count,'polygons',flush=True)

def motor():
    p=[tube('Motor_HollowCastHousing',[(12,-19),(16,-19),(16,-16),(13.5,-15),
                                      (13.5,15),(16,16),(16,19),(12,19)],STEEL)]
    # Longitudinal cast cooling ribs are six-face prisms, not bevelled geometry.
    for i in range(16):
        a=TAU*i/16
        obj=box('Motor_CoolingRib',(.65,2.6,29),(0,0,0),RUST)
        c.rotate(0,0,math.degrees(a)-90,obj)
        c.move(14.7*math.cos(a),14.7*math.sin(a),0,obj)
        p.append(obj)
    for x in [-11,11]:
        p.append(box('Motor_MountingFoot',(9,2.2,32),(x,-18,0),DARK))
        p.append(box('Motor_FootWeb',(2,7,23),(x,-14,0),STEEL))
        for z in [-12,12]:p.append(cylinder('Motor_FootHexBolt',1.0,1.1,(x,-16.35,z),DARK))
    p.append(box('Motor_TerminalBox',(10,4.5,12),(0,16,0),STEEL))
    p.append(box('Motor_TerminalLid',(10.6,.8,12.6),(0,18.65,0),DARK))
    for i in range(6):
        a=TAU*i/6
        bolt=cylinder('Motor_FlangeHexBolt',.72,.8,(0,0,0),DARK)
        c.rotate(90,0,0,bolt)
        c.move(14*math.cos(a),14*math.sin(a),19.3,bolt)
        p.append(bolt)
    finish('SM_12_MotorHousing',p,(-145,0,150),'Low-poly hollow motor casing; 16 cooling ribs, mounting feet, terminal box and hex bolts; no rotor')

def hollow_rail(name,path,width,height,wall,mat):
    outer=[(-width/2,-height/2),(width/2,-height/2),(width/2,height/2),(-width/2,height/2)]
    inner=[(-width/2+wall,-height/2+wall),(width/2-wall,-height/2+wall),
           (width/2-wall,height/2-wall),(-width/2+wall,height/2-wall)]
    vertices=[(x+dx,y+dy,z) for x,y,z in path for dx,dy in outer+inner]
    faces=[]
    for k in range(len(path)-1):
        a=k*8;b=(k+1)*8
        for i in range(4):
            j=(i+1)%4
            faces.extend([[a+i,a+j,b+j,b+i],[a+4+i,b+4+i,b+4+j,a+4+j]])
    last=(len(path)-1)*8
    for i in range(4):
        j=(i+1)%4
        faces.extend([[i,4+i,4+j,j],[last+i,last+j,last+4+j,last+4+i]])
    return mesh(name,vertices,faces,mat,25)

def pipe_between(name,a,b,r=1.35,mat=STEEL):
    a=om.MVector(*a);b=om.MVector(*b);d=b-a
    obj=cylinder(name,r,d.length(),(0,0,0),mat,6)
    e=om.MVector(0,1,0).rotateTo(d.normal()).asEulerRotation()
    c.rotate(math.degrees(e.x),math.degrees(e.y),math.degrees(e.z),obj)
    p=(a+b)*.5;c.move(p.x,p.y,p.z,obj)
    c.polySoftEdge(obj,angle=65,constructionHistory=False)
    return obj

def gusset(name,x,z,side=1):
    # Thick triangular strengthening plate, five polygons.
    triangle=[(x,10,z),(x+side*9,10,z),(x,10,z+10)]
    verts=triangle+[(a,b+.6,d) for a,b,d in triangle]
    faces=[[0,1,2],[5,4,3],[0,3,4,1],[1,4,5,2],[2,5,3,0]]
    return mesh(name,verts,faces,DARK,20)

def mounting_eye(name,position,axis='z'):
    obj=tube(name,[(2.3,-1.4),(4,-1.4),(4,1.4),(2.3,1.4)],DARK,8)
    if axis=='y':c.rotate(90,0,0,obj)
    c.move(*position,obj)
    return obj

def legacy_chassis_unused():
    # 1. Ladder chassis: continuous hollow rails, tapered ends and axle kick-ups.
    p=[]
    for side in [-1,1]:
        path=[(side*x,y,z) for x,y,z in [(24,14,-80),(24,14,-58),(31,5,-36),
                                             (31,5,34),(25,14,57),(25,14,80)]]
        p.append(hollow_rail('Ladder_KickedLongitudinalRail',path,4.5,9,.6,STEEL))
    for z,x,y in [(-70,24,14),(-35,31,5),(0,31,5),(34,31,5),(70,25,14)]:
        p.append(bar_between('Ladder_Crossmember',(-x,y,z),(x,y,z),4,6,STEEL))
    for side in [-1,1]:
        p.append(bar_between('Ladder_CentralDiagonal',(side*29,5,-34),(-side*29,5,34),2.5,2.5,DARK))
        for z in [-47,47]:
            p.append(box('Ladder_Outrigger',(16,3,8),(side*34,7,z),STEEL))
            p.append(mounting_eye('Ladder_BodyMount',(side*40,9,z),'y'))
        for z in [-34,24]:p.append(gusset('Ladder_CornerGusset',side*28,z,-side))
    finish('SM_13_Chassis_Ladder',p,(-125,0,275),
           '160 cm salvaged ladder chassis; hollow kicked rails, five crossmembers, X brace, outriggers, four open mounting eyes')

    # 2. Triangulated space frame: low nose, cockpit rails, roll hoop and rear engine bay.
    p=[]
    stations=[(22,10,12,-75),(34,4,24,-40),(38,4,49,-8),(35,7,57,33),(25,14,25,72)]
    for side in [-1,1]:
        lower=[(side*w,y,z) for w,y,top,z in stations]
        upper=[(side*(w-4),top,z) for w,y,top,z in stations]
        for i in range(4):
            p.append(pipe_between('Space_LowerSill',lower[i],lower[i+1],1.6))
            p.append(pipe_between('Space_UpperRail',upper[i],upper[i+1],1.4))
            p.append(pipe_between('Space_SideTriangle',lower[i],upper[i+1],1.05,DARK))
        for i in [1,2,3,4]:p.append(pipe_between('Space_Upright',lower[i],upper[i],1.25))
    for i,(w,y,top,z) in enumerate(stations):
        p.append(pipe_between('Space_FloorCrossmember',(-w,y,z),(w,y,z),1.4))
        if i in [0,2,3,4]:p.append(pipe_between('Space_UpperCrossmember',(-w+4,top,z),(w-4,top,z),1.4))
    p.append(pipe_between('Space_FloorX',(-34,4,-40),(35,7,33),1.05,DARK))
    p.append(pipe_between('Space_FloorX',(34,4,-40),(-35,7,33),1.05,DARK))
    # Raised, tapered hoop gives the cage a recognisable vehicle silhouette.
    for side in [-1,1]:
        p.append(pipe_between('Space_RollHoopLeg',(side*31,57,33),(side*25,78,23),1.6))
        p.append(pipe_between('Space_RollHoopStay',(side*25,78,23),(side*21,25,72),1.25,DARK))
        for z in [-43,60]:
            p.append(box('Space_SuspensionTab',(8,4,6),(side*33,8,z),RUST))
    p.append(pipe_between('Space_RollHoopTop',(-25,78,23),(25,78,23),1.6))
    finish('SM_14_Chassis_Tubular',p,(0,0,245),
           '147 cm six-sided tube spaceframe; triangulated side bays, tapered nose, floor bracing, cockpit hoop and rear stays')

    # 3. Compact suspension/engine cradle with dog-leg rails and an open center.
    p=[]
    for side in [-1,1]:
        path=[(side*x,y,z) for x,y,z in [(35,15,-48),(35,15,-31),(26,7,-19),(26,7,19),(38,16,35),(38,16,48)]]
        p.append(hollow_rail('Cradle_DoglegRail',path,6,8,.7,RUST))
        p.append(bar_between('Cradle_EngineSupport',(side*25,7,-17),(side*12,14,0),5,5,STEEL))
        p.append(box('Cradle_EngineMountPlate',(13,2,14),(side*12,15,0),DARK))
        for z,x in [(-43,35),(43,38)]:
            p.append(box('Cradle_MountEar',(12,2,11),(side*(x+4),18,z),STEEL))
            p.append(mounting_eye('Cradle_OpenBushing',(side*(x+5),20,z),'y'))
        p.append(bar_between('Cradle_TriangularBrace',(side*25,7,-18),(side*10,7,27),3,3,DARK))
    for z,y,x in [(-29,11,32),(27,11,32)]:
        p.append(bar_between('Cradle_Crossmember',(-x,y,z),(x,y,z),6,7,STEEL))
    p.append(bar_between('Cradle_RackCrossTube',(-26,7,0),(26,7,0),3,3,DARK))
    finish('SM_15_Chassis_Subframe',p,(132,0,237),
           '96 cm compact automotive subframe; hollow dog-leg rails, offset crossmembers, engine-mount shelves and four bored bushing eyes')

def annular_triangle(name,outer,inner,thickness,mat):
    n=len(outer)
    vertices=[(x,y,z) for y in [0,thickness] for x,z in outer+inner]
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([[i,j,n+j,n+i],[2*n+i,3*n+i,3*n+j,2*n+j],
                      [i,2*n+i,2*n+j,j],[n+i,n+j,3*n+j,3*n+i]])
    return mesh(name,vertices,faces,mat,25)

def eye(name,pos,r,inner,depth,mat,axis='z',n=8):
    obj=tube(name,[(inner,-depth/2),(r,-depth/2),(r,depth/2),(inner,depth/2)],mat,n)
    if axis=='y':c.rotate(90,0,0,obj)
    if axis=='x':c.rotate(0,90,0,obj)
    c.move(*pos,obj)
    return obj

def orient_cylinder(name,r,h,pos,mat,axis='y',n=8):
    obj=cylinder(name,r,h,(0,0,0),mat,n)
    if axis=='z':c.rotate(90,0,0,obj)
    if axis=='x':c.rotate(0,0,90,obj)
    c.move(*pos,obj)
    return obj

def frames():
    # 1. Stamped lower control arm, roughly 39 cm, with a large triangular opening.
    p=[annular_triangle('ControlArm_StampedWeb',
                         [(-16,-13),(15,-13),(5,18),(-3,21)],
                         [(-9,-7),(8,-7),(2.5,11),(0,12)],2.2,STEEL)]
    for side in [-1,1]:
        p.append(bar_between('ControlArm_RaisedEdge',(side*14,2.5,-11),(side*2,2.5,17),1.5,1.5,DARK))
        p.append(eye('ControlArm_BushingShell',(side*15,2,-12),3.8,2.7,7,STEEL))
        p.append(eye('ControlArm_RubberBushing',(side*15,2,-12),2.7,1.1,6.5,'MAT_TireRubberSG'))
        p.append(eye('ControlArm_InnerSleeve',(side*15,2,-12),1.1,.7,7.4,DARK))
    p.append(orient_cylinder('ControlArm_BallJointSeat',3.5,3,(0,2,19),DARK))
    boot=tube('ControlArm_BallJointBoot',[(1,0),(2.7,0),(2.7,1),(2.1,2.1),(1,2.1)],'MAT_TireRubberSG',8)
    c.rotate(-90,0,0,boot);c.move(0,3.5,19,boot);p.append(boot)
    p.append(orient_cylinder('ControlArm_BallStud',.9,4,(0,6,19),STEEL))
    p.append(orient_cylinder('ControlArm_HexNut',1.4,1.2,(0,7.3,19),DARK,n=6))
    finish('SM_13_Suspension_ControlArm',p,(-65,0,150),
           'Compact stamped lower wishbone; approx 39 cm, open triangular web, two rubber-lined bushing sleeves and ball-joint stud')

    # 2. Compact steering knuckle: bearing bore, strut fork, lower mount and steering arm.
    p=[eye('Knuckle_MainBearingHousing',(0,0,0),6,3.5,7,STEEL,n=12),
       eye('Knuckle_BearingLip',(0,0,3.8),5.5,3.5,1.0,DARK,n=12)]
    p.append(bar_between('Knuckle_StrutNeck',(0,3.5,0),(0,13,0),5,6,STEEL))
    for z in [-4.7,4.7]:
        p.append(bar_between('Knuckle_ForkEarSupport',(0,8,z),(0,14,z),4,2,STEEL))
        p.append(eye('Knuckle_StrutBoltEye',(0,15,z),3.2,1.25,2,STEEL))
    p.append(bar_between('Knuckle_LowerBallJointArm',(-1,-3,0),(-2,-11,1),4.5,4.5,STEEL))
    p.append(eye('Knuckle_LowerJointBore',(-2,-12,1),3,1.35,3.5,DARK,axis='y'))
    p.append(bar_between('Knuckle_SteeringArmA',(4,0,0),(10,1.5,-1.5),3.6,3.5,STEEL))
    p.append(bar_between('Knuckle_SteeringArmB',(10,1.5,-1.5),(15,4,-2),2.8,3,STEEL))
    p.append(eye('Knuckle_TieRodEye',(15,4,-2),2.6,1.1,2.4,DARK,axis='y'))
    p.append(bar_between('Knuckle_CastRib',(-3,3,3.8),(-2,11,3.8),1.2,1, RUST))
    finish('SM_14_Suspension_SteeringKnuckle',p,(15,0,150),
           'Small steering knuckle, approx 32 cm; open wheel-bearing bore, two-ear strut fork, lower joint eye and offset tie-rod arm')

    # 3. Short anti-roll-bar end link with two offset ball-joint ends.
    p=[pipe_between('EndLink_SteelRod',(0,0,0),(0,27,3),.85,STEEL)]
    for y,z in [(0,0),(27,3)]:
        shell=tube('EndLink_BallSocket',[(.85,-2),(2.4,-2),(3.1,-.8),(3.1,.8),(2.2,2),(.85,2)],DARK,8)
        c.move(0,y,z,shell);p.append(shell)
        boot=tube('EndLink_DustBoot',[(1,2),(2.25,2),(2.25,3),(1,3.7)],'MAT_TireRubberSG',8)
        c.move(0,y,z,boot);p.append(boot)
        p.append(orient_cylinder('EndLink_ThreadedStud',.75,5,(0,y,z+4.2),STEEL,axis='z'))
        p.append(orient_cylinder('EndLink_HexNut',1.2,1.1,(0,y,z+5.2),DARK,axis='z',n=6))
    p.append(orient_cylinder('EndLink_AdjustmentHex',1.25,3,(0,13.5,1.5),DARK,n=6))
    finish('SM_15_Suspension_StabilizerLink',p,(83,0,150),
           'Compact 33 cm stabilizer end link; slender rod, offset ball sockets, rubber dust boots, studs and hex nuts')

try:
    c.file(SCENE,open=True,force=True)
    master_candidates=c.ls('SCATTER_MODELS_*_ASSETS',type='transform')
    assert len(master_candidates)==1
    MASTER=master_candidates[0]
    for prefix in ['SM_13_','SM_14_','SM_15_']:
        for group in c.ls(prefix+'*_GRP',type='transform'):c.delete(group)
    original={obj:c.polyEvaluate(obj,face=True) for obj in c.ls('SM_*_GEO',type='transform')}
    assert len(original)==12
    frames()
    MASTER=c.rename(MASTER,'SCATTER_MODELS_15_ASSETS')
    # Fit the expanded three-row display in both the render and opening viewport.
    camera='AssetOverview_CAM'
    c.move(285,395,490,camera)
    target=c.spaceLocator()[0];c.move(-8,24,35,target)
    con=c.aimConstraint(target,camera,aimVector=(0,0,-1),upVector=(0,1,0),worldUpType='scene')[0]
    c.delete(con,target)
    shape=c.listRelatives(camera,shapes=True)[0]
    c.setAttr(shape+'.orthographicWidth',535)
    c.xform('persp',matrix=c.xform(camera,q=True,matrix=True,worldSpace=True),worldSpace=True)
    c.setAttr('perspShape.orthographicWidth',535)
    # Close-up camera for checking the three small replacement parts.
    detail='SuspensionParts_CAM'
    if c.objExists(detail):c.delete(detail)
    detail=c.rename(c.camera()[0],detail)
    c.move(83,125,340,detail)
    target=c.spaceLocator()[0];c.move(7,8,150,target)
    con=c.aimConstraint(target,detail,aimVector=(0,0,-1),upVector=(0,1,0),worldUpType='scene')[0]
    c.delete(con,target)
    ds=c.listRelatives(detail,shapes=True)[0]
    c.setAttr(ds+'.orthographic',True);c.setAttr(ds+'.orthographicWidth',210)
    c.setAttr(ds+'.backgroundColor',.13,.15,.18,type='double3')
    c.setAttr('defaultResolution.width',1600);c.setAttr('defaultResolution.height',1250)
    c.setAttr('defaultResolution.deviceAspectRatio',1.28)
    c.select(clear=True)
    report=[]
    for group in sorted(c.listRelatives(MASTER,children=True,type='transform')):
        obj=c.listRelatives(group,children=True,type='transform')[0]
        issues={k:len(c.polyInfo(obj,**{k:True}) or []) for k in ['nonManifoldEdges','nonManifoldVertices','laminaFaces']}
        assert not any(issues.values()),(obj,issues)
        bb=c.exactWorldBoundingBox(obj)
        report.append({'group':group,'mesh':obj,'faces':c.polyEvaluate(obj,face=True),
                       'triangles':c.polyEvaluate(obj,triangle=True),'uvs':c.polyEvaluate(obj,uvcoord=True),
                       'dimensions_cm':[round(bb[i+3]-bb[i],3) for i in range(3)],'topology_issues':issues})
    assert len(report)==15
    for obj,count in original.items():assert c.polyEvaluate(obj,face=True)==count
    temporary=os.path.join(ROOT,'Scatter_Models_LowPoly_pending.ma')
    c.file(rename=temporary);c.file(save=True,type='mayaAscii',force=True)
    c.file(temporary,open=True,force=True)
    assert len(c.ls('SM_*_GEO',type='transform'))==15
    for obj,count in original.items():assert c.polyEvaluate(obj,face=True)==count
    os.replace(temporary,SCENE)
    with open(os.path.join(ROOT,'lowpoly_manifest.json'),'w') as f:json.dump(report,f,indent=2)
    print('SAVED',SCENE,'TOTAL_POLYGONS',sum(r['faces'] for r in report),flush=True)
finally:
    maya.standalone.uninitialize()
