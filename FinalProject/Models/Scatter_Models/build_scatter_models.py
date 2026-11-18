"""Build the eleven requested scatter assets with Maya 2022 (centimeters)."""
import os
import math
import json
import traceback
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as c
import maya.api.OpenMaya as om

ROOT = os.path.dirname(os.path.abspath(__file__))
TAU = math.pi * 2
c.file(new=True, force=True)
c.currentUnit(linear='cm', angle='deg')
c.upAxis(axis='y')

def material(name, color, rust=False, metal=False):
    s = c.shadingNode('blinn', asShader=True, name=name)
    sg = c.sets(renderable=True, noSurfaceShader=True, empty=True, name=name+'SG')
    c.connectAttr(s+'.outColor', sg+'.surfaceShader')
    c.setAttr(s+'.color', *color, type='double3')
    c.setAttr(s+'.eccentricity', .38 if metal else .7)
    c.setAttr(s+'.specularColor', *([.28]*3 if metal else [.08]*3), type='double3')
    c.setAttr(s+'.diffuse', .8)
    if rust:
        tex = c.shadingNode('solidFractal', asTexture=True, name=name+'_Corrosion')
        place = c.shadingNode('place3dTexture', asUtility=True, name=name+'_TextureSpace')
        c.setAttr(place+'.scale', 7,7,7,type='double3')
        c.connectAttr(place+'.worldInverseMatrix[0]', tex+'.placementMatrix')
        c.setAttr(tex+'.ratio', .62)
        c.setAttr(tex+'.threshold', .08)
        blend = c.shadingNode('blendColors', asUtility=True, name=name+'_PaintAndRust')
        c.setAttr(blend+'.color1', .20,.065,.025,type='double3')
        c.setAttr(blend+'.color2', *color,type='double3')
        c.connectAttr(tex+'.outAlpha',blend+'.blender')
        c.connectAttr(blend+'.output',s+'.color')
        bump = c.shadingNode('bump3d', asUtility=True, name=name+'_Pitting')
        c.setAttr(bump+'.bumpDepth', .035)
        c.connectAttr(tex+'.outAlpha',bump+'.bumpValue')
        c.connectAttr(bump+'.outNormal',s+'.normalCamera')
    return sg

PAINT = material('MAT_OxideRedPaint',(.36,.105,.055),True,True)
STEEL = material('MAT_AgedSteel',(.29,.31,.30),True,True)
DARK = material('MAT_DarkSteel',(.105,.12,.125),True,True)
RUST = material('MAT_RustedIron',(.30,.14,.065),True,True)
RUBBER = material('MAT_TireRubber',(.028,.031,.034))
BRIGHT = material('MAT_WornMetalEdges',(.43,.44,.42),False,True)

def assign(obj, mat):
    c.sets(obj, edit=True, forceElement=mat)
    return obj

def mesh(name, vertices, faces, mat, smooth=40):
    used=sorted(set(i for f in faces for i in f))
    remap={old:new for new,old in enumerate(used)}
    vertices=[vertices[i] for i in used]
    faces=[[remap[i] for i in f] for f in faces]
    fn = om.MFnMesh()
    fn.create([om.MPoint(*v) for v in vertices], [len(f) for f in faces], [i for f in faces for i in f])
    obj=c.rename(c.listRelatives(fn.fullPathName(),parent=True,fullPath=True)[0],name)
    assign(obj,mat)
    c.polySoftEdge(obj,angle=smooth,constructionHistory=False)
    return obj

def bevel(obj, amount=.15, segments=2):
    c.polyBevel3(obj,offset=amount,segments=segments,autoFit=True,angleTolerance=35,
                 mergeVertices=True,constructionHistory=False)
    c.polySoftEdge(obj,angle=45,constructionHistory=False)
    return obj

def lathe(name, profile, mat, n=64, closed=True):
    vertices=[(r*math.cos(TAU*i/n),y,r*math.sin(TAU*i/n)) for r,y in profile for i in range(n)]
    faces=[]
    for j in range(len(profile) if closed else len(profile)-1):
        k=(j+1)%len(profile)
        for i in range(n):
            a=j*n+i; b=j*n+(i+1)%n; d=k*n+i; e=k*n+(i+1)%n
            faces.append([a,d,e,b])
    return mesh(name,vertices,faces,mat)

def torus(name,r,t,y,mat,n=64,s=10):
    return lathe(name,[(r+t*math.cos(TAU*j/s),y+t*math.sin(TAU*j/s)) for j in range(s)],mat,n)

def cylinder(name,r,h,pos,mat,n=48):
    obj=c.polyCylinder(name=name,radius=r,height=h,subdivisionsX=n,constructionHistory=False)[0]
    c.move(*pos,obj)
    return assign(obj,mat)

def box(name,size,pos,mat,b=.15):
    obj=c.polyCube(name=name,width=size[0],height=size[1],depth=size[2],constructionHistory=False)[0]
    if b: bevel(obj,b)
    c.move(*pos,obj)
    return assign(obj,mat)

ASSETS=[]
def finish(name,parts,position,description):
    name='SM_'+name
    # One independently selectable mesh per asset; retain per-face materials.
    obj=c.polyUnite(parts,name=name+'_GEO',constructionHistory=False,mergeUVSets=1)[0] if len(parts)>1 else c.rename(parts[0],name+'_GEO')
    c.delete(obj,constructionHistory=True)
    c.makeIdentity(obj,apply=True,t=True,r=True,s=True,normal=1)
    c.polyAutoProjection(obj,layoutMethod=0,planes=6,scaleMode=1,layout=2,percentageSpace=.3,constructionHistory=False)
    bb=c.exactWorldBoundingBox(obj)
    c.move(0,-bb[1],0,obj,relative=True)
    c.makeIdentity(obj,apply=True,t=True,r=True,s=True,normal=1)
    c.xform(obj,pivots=(0,0,0),worldSpace=True)
    grp=c.group(obj,name=name+'_GRP')
    c.xform(grp,pivots=(0,0,0),worldSpace=True)
    c.addAttr(grp,longName='assetDescription',dataType='string')
    c.setAttr(grp+'.assetDescription',description,type='string')
    c.addAttr(grp,longName='units',dataType='string')
    c.setAttr(grp+'.units','centimeters; Y up; bottom pivot',type='string')
    bounds=c.exactWorldBoundingBox(obj)
    dimensions=[round(bounds[i+3]-bounds[i],3) for i in range(3)]
    c.move(*position,grp)
    ASSETS.append({'name':name,'group':grp,'mesh':obj,'dimensions_cm':dimensions,'description':description})
    print('BUILT',name,dimensions,flush=True)
    return grp

def barrel():
    profile=[(.01,0),(27.8,0),(28.7,.6),(29.2,1.4),(29.2,2.5),(28.5,3.1),
             (28.4,23),(28.9,25),(29.6,25.7),(29.6,27.3),(28.7,28.2),
             (28.4,57),(28.9,59),(29.6,59.7),(29.6,61.3),(28.7,62.2),
             (28.4,84),(29.1,85),(29.1,87),(28.3,88),(27.5,88),(27.5,86.6),(.01,86.6)]
    p=[lathe('Barrel_RibbedShell',profile,PAINT,96)]
    p += [torus('Barrel_TopRolledLip',28.25,.7,87.6,DARK,96),torus('Barrel_BaseRolledLip',28.3,.65,1.2,DARK,96)]
    for x,z,r in [(17,7,3.3),(-17,-7,1.7)]:
        cap=lathe('Barrel_BungCollar',[(r,86.6),(r,87.6),(r-.5,88.0),(r-.9,88.0),(r-.9,86.6)],DARK,32)
        c.move(x,0,z,cap);p.append(cap)
        p.append(cylinder('Barrel_HexPlug',r-.9,.6,(x,87.2,z),STEEL,6))
        p.append(box('Barrel_PlugSlot',(.22,.09,r*.8),(x,87.55,z),DARK,.02))
    p.append(box('Barrel_WeldSeam',(.28,81,.2),(0,43,-28.45),DARK,.04))
    finish('01_OilBarrel',p,(-135,0,-90),'200 L style steel drum, rolled rims, two reinforcing ribs, two bung plugs')

def spring(name,r,wire,h,turns,pos):
    steps=int(turns*64);sides=12
    pts=[]
    # Close-wound end turns, with eased pitch through the active coils.
    def height(t):
        u=t*turns
        if u<1: return wire*2*u
        if u>turns-1: return h-wire*2-wire*2*(turns-u)
        return wire*2+(h-wire*6)*(u-1)/(turns-2)
    for i in range(steps+1):
        t=i/float(steps);a=TAU*turns*t
        da=.0001
        dydt=(height(min(1,t+da))-height(max(0,t-da)))/(min(1,t+da)-max(0,t-da))
        tangent=om.MVector(-r*math.sin(a)*TAU*turns,dydt,r*math.cos(a)*TAU*turns).normal()
        radial=om.MVector(math.cos(a),0,math.sin(a))
        cross=tangent^radial
        center=om.MVector(r*math.cos(a),height(t)+wire,r*math.sin(a))
        for j in range(sides):
            v=center+wire*(math.cos(TAU*j/sides)*radial+math.sin(TAU*j/sides)*cross)
            pts.append((v.x,v.y,v.z))
    faces=[]
    for i in range(steps):
        for j in range(sides):
            faces.append([i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j])
    faces += [list(reversed(range(sides))),[steps*sides+j for j in range(sides)]]
    finish(name,[mesh(name+'_Coil',pts,faces,RUST)],pos,'Closed end automotive compression spring; continuous round wire')

def beam(length,name,pos):
    w=12.;h=16.;flange=1.2;web=.8
    outline=[(-w/2,0),(w/2,0),(w/2,flange),(web/2,flange),(web/2,h-flange),
             (w/2,h-flange),(w/2,h),(-w/2,h),(-w/2,h-flange),(-web/2,h-flange),(-web/2,flange),(-w/2,flange)]
    verts=[(x,y,z) for z in [-length/2,length/2] for x,y in outline]
    n=len(outline)
    faces=[list(reversed(range(n))),list(range(n,n*2))]
    faces += [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    obj=mesh(name+'_Section',verts,faces,STEEL,30)
    bevel(obj,.16,3)
    finish(name,[obj],pos,'Continuous I section: length %g cm, flange width 12 cm, depth 16 cm'%length)

def perforated_plate(name,rings,low,high,mat,holes,n=120):
    # Radial annular solid, explicitly bridge all hole boundaries for a closed mesh.
    verts=[(r*math.cos(TAU*i/n), y(r),r*math.sin(TAU*i/n))
           for y in [low,high] for r in rings for i in range(n)]
    layer=len(rings)*n;faces=[];edges={}
    for j in range(len(rings)-1):
        for i in range(n):
            if holes(j,i):continue
            ids=[j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n]
            faces.append(ids)
            faces.append([v+layer for v in reversed(ids)])
            for a,b in zip(ids,ids[1:]+ids[:1]):
                if (b,a) in edges: del edges[(b,a)]
                else:edges[(a,b)]=True
    for a,b in edges:faces.append([b,a,a+layer,b+layer])
    return mesh(name,verts,faces,mat,35)

def brake():
    p=[]
    for h in [0,2.2]:
        disc=perforated_plate('Rotor_DrilledFrictionRing',[7.6,10.2,11.1,12,12.9,14.5,15.4,16.5],lambda r:h,lambda r:h+.85,BRIGHT,
                              lambda j,i:(j==2 and i%12 in [2,3]) or (j==4 and i%12 in [7,8]))
        p.append(disc)
    for i in range(36):
        a=TAU*i/36
        obj=box('Rotor_InternalCoolingVane',(.4,1.35,8),(0,1.525,11.6),DARK,.08)
        c.rotate(0,i*10,0,obj,pivot=(0,0,0));p.append(obj)
    hat=perforated_plate('Rotor_FiveLugHat',[3.4,4.7,5.9,7.7,8.5],lambda r:3.05 if r<7.7 else 2.8,lambda r:5.8 if r<7.7 else 3.2,STEEL,
                         lambda j,i:j==1 and i%24 in [0,1,2,3,4])
    bevel(hat,.12);p.append(hat)
    finish('07_BrakeRotor',p,(-130,0,45),'Vented drilled brake rotor, open center bore, five lug holes and internal cooling vanes')

def gear():
    teeth=22;n=teeth*8
    radii=[12.6,12.6,14.6,14.6,14.6,14.6,12.6,12.6]
    verts=[]
    for y in [0,3.6]:
        for ring in [0,1]:
            for i in range(n):
                r=3.5 if ring==0 else radii[i%8]
                verts.append((r*math.cos(TAU*i/n),y,r*math.sin(TAU*i/n)))
    faces=[]
    for i in range(n):
        k=(i+1)%n
        faces += [[i,k,n+k,n+i],[2*n+i,3*n+i,3*n+k,2*n+k],
                  [n+i,n+k,3*n+k,3*n+i],[i,2*n+i,2*n+k,k]]
    obj=mesh('Gear_22Teeth',verts,faces,RUST,25);bevel(obj,.18,2)
    p=[obj,lathe('Gear_RaisedHub',[(3.5,3.6),(6,3.6),(6,5.8),(5.7,6),(3.5,6)],STEEL,64)]
    finish('08_TransmissionGear',p,(-78,0,45),'22-tooth transmission gear with raised hub and through bore')

def piston():
    p=[]
    # Piston axis Y; its hanging rod is built below it then the assembly is grounded.
    profile=[(.01,45),(4.8,45),(5,44.7),(5,43.8),(4.65,43.8),(4.65,43.2),(5,43.2),
             (5,42.5),(4.65,42.5),(4.65,41.9),(5,41.9),(5,41.1),(4.65,41.1),(4.65,40.4),
             (5,40.4),(5,34),(4.1,34),(4.1,42.6),(.01,42.6)]
    p.append(lathe('Piston_CrownAndSkirt',list(reversed(profile)),BRIGHT,64))
    for y in [43.5,42.2,40.75]:p.append(torus('Piston_CompressionRing',4.78,.18,y,DARK))
    # Rod lies in XY with open bearing bores along Z.
    for r,y,t in [(4,5,1.1),(2.2,36,.8)]:
        ring=lathe('Rod_Bearing',[(r,-1.4),(r,1.4),(r-t,1.4),(r-t,-1.4)],STEEL,48)
        c.rotate(90,0,0,ring);c.move(0,y,0,ring);p.append(ring)
    p.append(box('Rod_Web',(2,25,1.0),(0,20.5,0),STEEL,.25))
    for x in [-1.25,1.25]:p.append(box('Rod_Flange',(.65,25,2.2),(x,20.5,0),DARK,.2))
    p.append(box('Rod_BearingCap',(8.5,1.6,3),(0,2.4,0),STEEL,.22))
    for x in [-3.4,3.4]:p.append(cylinder('Rod_CapBolt',.65,2.4,(x,3.6,0),DARK,6))
    pin=cylinder('Piston_WristPin',1.1,10.5,(0,0,0),DARK,32)
    c.rotate(0,0,90,pin);c.move(0,36,0,pin);p.append(pin)
    finish('09_PistonConnectingRod',p,(-28,0,40),'Grooved piston crown, hollow skirt, wrist pin and I section connecting rod with bearing cap')

def wheel_parts(prefix):
    profile=[(18.7,1.0),(20.1,1.0),(20.7,1.6),(20.7,2.7),(19.5,3.2),(19.3,6),
             (18.5,8),(18.5,15),(19.3,17.5),(19.5,20),(20.7,20.5),(20.7,21.5),
             (20.1,22),(18.7,22),(18.5,20),(17.8,17),(17.8,8),(18.6,5),(18.7,1.0)]
    p=[lathe(prefix+'_Barrel',profile[:-1],STEEL,96)]
    def dish(r):return 17.2 if r<8 else 17.2-(r-8)*.38
    disc=perforated_plate(prefix+'_StampedVentDisc',[3.2,4.4,5.7,7.8,9.7,15.3,17.4,18.5],
                           lambda r:dish(r)-.65,lambda r:dish(r)+.65,STEEL,
                           lambda j,i:(j==1 and i%24 in [0,1,2,3,4]) or (j==4 and i%12 in [2,3,4,5,6,7,8]))
    bevel(disc,.13,2);p.append(disc)
    for y in [1.6,21.5]:p.append(torus(prefix+'_Lip',20,.45,y,BRIGHT,96))
    valve=cylinder(prefix+'_Valve',.43,2,(16.8,16.7,0),RUBBER,12);p.append(valve)
    return p

def wheels():
    p=wheel_parts('Wheel')
    profile=[(19.8,2.0),(23,1.0),(27,1.6),(30,3.3),(31.4,5.8),(31.8,8),
             (31.8,15),(31.4,17.4),(30,19.7),(27,21.4),(23,22),(19.8,21),
             (19.8,19.7),(22,19.6),(26,18.8),(28.5,17),(29.7,14),(29.7,9),
             (28.5,6),(26,4.2),(22,3.4),(19.8,3.3)]
    p.append(lathe('Tire_Carcass',profile,RUBBER,128))
    for y in [2.15,20.85]:
        for r in [24,25.2,27]:p.append(torus('Tire_SidewallRidge',r,.13,y,RUBBER,96,6))
    # Four staggered rows of actual tread blocks with open grooves.
    for row,y in enumerate([6.2,9.4,12.6,15.8]):
        for i in range(64):
            a=TAU*(i+(.45 if row%2 else 0))/64
            obj=box('Tire_TreadBlock',(2.5,2.7,.85),(0,0,0),RUBBER,.12)
            c.rotate(0,-a*180/math.pi,(-9 if row%2 else 9),obj)
            c.move(31.8*math.sin(-a),y,31.8*math.cos(a),obj)
            p.append(obj)
    finish('10_WheelWithTire',p,(50,0,40),'Steel rim with ten ventilation windows, five lug holes, hollow tire, four staggered tread rows')
    finish('11_BareWheelRim',wheel_parts('BareRim'),(130,0,40),'Matching hollow steel rim without tire; open center, five lug holes and ten ventilation windows')

def camera_and_lights():
    cam=c.rename(c.camera()[0],'AssetOverview_CAM')
    c.move(285,290,390,cam)
    target=c.spaceLocator()[0];c.move(-5,25,-25,target)
    con=c.aimConstraint(target,cam,aimVector=(0,0,-1),upVector=(0,1,0),worldUpType='scene')[0]
    c.delete(con,target)
    shape=c.listRelatives(cam,shapes=True)[0]
    c.setAttr(shape+'.orthographic',True);c.setAttr(shape+'.orthographicWidth',440)
    c.setAttr(shape+'.nearClipPlane',.1);c.setAttr(shape+'.farClipPlane',5000)
    for name,rot,intensity in [('Key',(-50,-25,0),1.15),('Fill',(-35,130,0),.65),('Rim',(-55,210,0),.8)]:
        light=c.directionalLight(name=name,intensity=intensity)
        c.rotate(*rot,c.listRelatives(light,parent=True)[0])
    ambient=c.ambientLight(name='StudioAmbient',intensity=.3)
    c.setAttr('defaultRenderGlobals.currentRenderer','mayaSoftware',type='string')
    c.setAttr('defaultResolution.width',1500);c.setAttr('defaultResolution.height',1100)
    c.setAttr('defaultResolution.deviceAspectRatio',1500/1100.)
    c.setAttr('defaultRenderGlobals.imageFormat',32)
    c.setAttr('defaultRenderQuality.edgeAntiAliasing',1)
    c.setAttr(shape+'.backgroundColor',.13,.15,.18,type='double3')
    # Default perspective opens on the same complete asset overview.
    c.xform('persp',matrix=c.xform(cam,q=True,matrix=True,worldSpace=True),worldSpace=True)
    c.setAttr('perspShape.orthographic',True);c.setAttr('perspShape.orthographicWidth',440)
    c.setAttr('perspShape.farClipPlane',5000)
    return cam

try:
    barrel()
    spring('02_SuspensionSpring_Large',8.8,1.05,40,6.5,(-70,0,-90))
    spring('03_SuspensionSpring_Small',5.7,.75,27,6,(-30,0,-90))
    beam(100,'04_IBeam_100cm',(25,0,-85))
    beam(50,'05_IBeam_50cm',(65,0,-65))
    beam(30,'06_IBeam_30cm',(100,0,-55))
    brake();gear();piston();wheels()
    master=c.group([a['group'] for a in ASSETS],name='SCATTER_MODELS_11_ASSETS')
    cam=camera_and_lights()
    c.select(clear=True)
    scene=os.path.join(ROOT,'Scatter_Models.ma')
    c.file(rename=scene);c.file(save=True,type='mayaAscii',force=True)
    with open(os.path.join(ROOT,'asset_manifest.json'),'w') as f:json.dump(ASSETS,f,indent=2)
    print('SCENE_SAVED',scene,flush=True)
    # Reopen the actual saved scene, then inspect each asset for invalid topology.
    c.file(scene,open=True,force=True)
    checks=[]
    for a in ASSETS:
        m=a['mesh']
        bad=c.polyInfo(m,nonManifoldEdges=True) or []
        lamina=c.polyInfo(m,laminaFaces=True) or []
        checks.append({'name':a['name'],'vertices':c.polyEvaluate(m,vertex=True),'faces':c.polyEvaluate(m,face=True),
                       'nonmanifold_edges':len(bad),'lamina_faces':len(lamina),'uvs':c.polyEvaluate(m,uvcoord=True)})
    with open(os.path.join(ROOT,'validation.json'),'w') as f:json.dump(checks,f,indent=2)
    print('VALIDATED',json.dumps(checks),flush=True)
    c.setAttr('defaultRenderGlobals.imageFilePrefix',os.path.join(ROOT,'Scatter_Models_Preview').replace('\\','/'),type='string')
    print('READY_FOR_BATCH_RENDER',cam,flush=True)
except Exception:
    traceback.print_exc()
    raise
finally:
    maya.standalone.uninitialize()
