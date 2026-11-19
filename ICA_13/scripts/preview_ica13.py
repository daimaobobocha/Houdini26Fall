import hou,os,numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
hou.hipFile.load(ROOT+'/ICA_13.hipnc',suppress_save_prompt=True,ignore_load_warnings=True)
os.makedirs(ROOT+'/preview',exist_ok=True)
def aim(n,eye,target):
    eye=np.array(eye,dtype=float);back=eye-np.array(target,dtype=float);back/=np.linalg.norm(back)
    right=np.cross([0,1,0],back);right/=np.linalg.norm(right);up=np.cross(back,right)
    n.parmTuple('t').set(eye.tolist());n.parmTuple('r').set(hou.Matrix3(np.array([right,up,back]).flatten().tolist()).extractRotates())
for objname,col in [('VELLUM_GHOST',(.82,.85,.9)),('RBD_FRACTURE',(.42,.39,.34))]:
    mat=hou.node('/mat').createNode('principledshader::2.0',objname+'_material')
    mat.parmTuple('basecolor').set(col);mat.parm('rough').set(.8)
    hou.node('/obj/'+objname).parm('shop_materialpath').set(mat.path())
camera=hou.node('/obj').createNode('cam','PREVIEW_CAMERA')
camera.parm('projection').set('ortho');camera.parmTuple('res').set((1000,800))
for name,pos,power in [('Key',(-10,18,15),.95),('Fill',(15,8,5),.45),('Rim',(0,10,-15),.7)]:
    light=hou.node('/obj').createNode('hlight','PREVIEW_'+name)
    light.parm('light_type').set('distant');light.parm('light_intensity').set(power);aim(light,pos,(0,0,0))
rop=hou.node('/out').createNode('ifd','PREVIEW_RENDER')
rop.parm('camera').set(camera.path());rop.parm('vm_renderengine').set('pbrraytrace')
rop.parm('vm_samplesx').set(3);rop.parm('vm_samplesy').set(3);rop.parm('vm_diffuselimit').set(0);rop.parm('vm_maxraysamples').set(4)
for key,frame,target,eye,width in [('ghost',72,(-8,.2,0),(2,6,17),13),('rbd',48,(8,1,0),(24,17,22),25)]:
    aim(camera,eye,target);camera.parm('orthowidth').set(width)
    rop.parm('vm_picture').set(ROOT+'/preview/'+key+'.png')
    rop.parm('vobject').set('VELLUM_GHOST' if key=='ghost' else 'RBD_FRACTURE')
    print('RENDER',key,flush=True);rop.render(frame_range=(frame,frame))
print('PREVIEWS_COMPLETE',flush=True)
