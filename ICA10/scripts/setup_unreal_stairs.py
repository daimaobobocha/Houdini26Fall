import unreal,os,json,time,traceback
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
REPORT=ROOT+'/unreal_validation.json'
STATE={'stage':'starting','started':time.time()}
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
def record(**kwargs):
    STATE.update(kwargs)
    with open(REPORT,'w') as f:json.dump(STATE,f,indent=2,default=str)
    unreal.log('ICA10_PROGRESS '+json.dumps(kwargs,default=str))
def fail(error):
    record(stage='error',error=repr(error),traceback=traceback.format_exc())
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
def guarded(fn):
    def invoke(*args):
        try:return fn(*args)
        except Exception as e:fail(e)
    # Unreal delegates validate the callable's explicit positional signature.
    if fn.__code__.co_argcount==0:
        def wrapped0():return invoke()
        return wrapped0
    if fn.__code__.co_argcount==1:
        def wrapped1(arg):return invoke(arg)
        return wrapped1
    def wrapped2(arg1,arg2):return invoke(arg1,arg2)
    return wrapped2

@guarded
def run():
    global API,WRAPPER,CURVE_INPUT,CURVE_OBJECT,CAMERA,TICK_HANDLE,PROCESS_COUNT
    API=unreal.HoudiniPublicAPIBlueprintLib.get_api()
    API.create_session()
    record(stage='session',session_valid=API.is_session_valid())
    if not API.is_session_valid():raise RuntimeError('Houdini Engine session could not start')
    level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    map_path='/Game/ICA10_Stairs/ICA10_StairDemo'
    if unreal.EditorAssetLibrary.does_asset_exist(map_path):
        assert level.load_level(map_path)
        actor_subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for old in actor_subsystem.get_all_level_actors():
            if old.get_actor_label().startswith('ICA10_'):
                actor_subsystem.destroy_actor(old)
    else:
        assert level.new_level(map_path)
    task=unreal.AssetImportTask()
    task.set_editor_property('filename',ROOT+'/hda/ICA10_Stairs.hdanc')
    task.set_editor_property('destination_path','/Game/ICA10_Stairs/HDA')
    task.set_editor_property('destination_name','ICA10_Stairs')
    task.set_editor_property('automated',True)
    task.set_editor_property('save',True)
    task.set_editor_property('replace_existing',True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    assets=task.get_editor_property('imported_object_paths')
    record(stage='imported',hda_assets=list(assets))
    assert assets,'HDA import did not return an asset'
    hda=unreal.load_asset(assets[0])
    CURVE_INPUT=API.create_empty_input(unreal.HoudiniPublicAPICurveInput)
    CURVE_INPUT.set_editor_property('cook_on_curve_changed',True)
    CURVE_OBJECT=unreal.new_object(unreal.HoudiniPublicAPICurveInputObject)
    CURVE_OBJECT.set_curve_type(unreal.HoudiniPublicAPICurveType.POLYGON)
    # Polygon input uses the plugin's default CV method.
    CURVE_OBJECT.set_closed(False)
    set_curve(False)
    WRAPPER=unreal.HoudiniPublicAPIAssetWrapper.create_empty_wrapper(API)
    WRAPPER.on_post_instantiation_delegate.add_callable(post_instantiation)
    WRAPPER.on_post_cook_delegate.add_callable(post_cook)
    WRAPPER.on_post_processing_delegate.add_callable(post_processing)
    PROCESS_COUNT=0
    assert API.instantiate_asset_with_existing_wrapper(WRAPPER,hda,unreal.Transform(),None,None,True)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    light=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,3000),unreal.Rotator(-45,-25,0))
    light.set_actor_label('ICA10_KeyLight')
    light.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(3)
    fill=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,2000),unreal.Rotator(-20,140,0))
    fill.set_actor_label('ICA10_FillLight')
    fill.get_component_by_class(unreal.DirectionalLightComponent).set_intensity(1)
    floor=actors.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(0,-1400,-35))
    floor.set_actor_label('ICA10_DisplayFloor')
    floor.static_mesh_component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube.Cube'))
    floor.set_actor_scale3d(unreal.Vector(55,70,.5))
    CAMERA=actors.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(4200,2800,2900))
    CAMERA.set_actor_label('ICA10_PreviewCamera')
    camera_target=unreal.Vector(0,-1400,950)
    rotation=unreal.MathLibrary.find_look_at_rotation(CAMERA.get_actor_location(),camera_target)
    CAMERA.set_actor_rotation(rotation,False)
    CAMERA.get_component_by_class(unreal.CameraComponent).set_editor_property('field_of_view',44)
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(CAMERA.get_actor_location(),rotation)
    TICK_HANDLE=unreal.register_slate_post_tick_callback(tick)
    record(stage='instantiating')

def set_curve(extended=False):
    coords=[(0,0,0),(0,-855.5993,855.5664),(0,-1485.4986,855.5664),(0,-2230.5519,1600.6197),(0,-2817.1569,1600.6197)]
    if extended:coords[-1]=(0,-3217.1569,1600.6197)
    CURVE_OBJECT.set_curve_points([unreal.Transform(location=unreal.Vector(*v)) for v in coords])
    assert CURVE_INPUT.set_input_objects([CURVE_OBJECT])

@guarded
def post_instantiation(wrapper):
    actor=wrapper.get_houdini_asset_actor();actor.set_actor_label('ICA10_Editable_Staircase')
    wrapper.set_proxy_mesh_enabled(False)
    assert wrapper.set_input_at_index(0,CURVE_INPUT)
    record(stage='curve_input_set',actor=actor.get_path_name())

@guarded
def post_cook(wrapper,success):
    record(last_cook_success=success)
    if not success:raise RuntimeError('Houdini Engine cook failed')

@guarded
def post_processing(wrapper):
    global PROCESS_COUNT
    PROCESS_COUNT+=1
    actor=wrapper.get_houdini_asset_actor()
    if wrapper.has_any_current_proxy_output():
        wrapper.refine_all_current_proxy_outputs(True)
    components=actor.get_components_by_class(unreal.StaticMeshComponent)
    meshes=[c.static_mesh.get_path_name() for c in components if c.static_mesh]
    bounds=[[v.x,v.y,v.z] for v in actor.get_actor_bounds(False)]
    record(stage='cooked',cook_count=PROCESS_COUNT,meshes=meshes,bounds=bounds)
    if not meshes:raise RuntimeError('Cook produced no static mesh output')
    if PROCESS_COUNT==1:
        STATE['original_bounds']=bounds
        STATE['next_action']='extend'
    elif PROCESS_COUNT==2:
        STATE['extended_bounds']=bounds
        assert STATE['original_bounds']!=STATE['extended_bounds'],'Curve edit did not change the generated staircase'
        STATE['next_action']='restore'
    else:
        STATE['next_action']='finish'
    STATE['action_after']=time.time()+2

@guarded
def tick(delta):
    if time.time()-STATE['started']>480 and STATE['stage'] not in ('complete','error'):
        fail('Timed out waiting for staircase cooking');return
    action=STATE.get('next_action')
    if not action or time.time()<STATE.get('action_after',0):return
    STATE['next_action']=None
    if action in ('extend','restore'):
        set_curve(action=='extend')
        assert WRAPPER.set_input_at_index(0,CURVE_INPUT)
        record(stage='testing_curve_edit' if action=='extend' else 'restoring_original_curve')
    elif action=='finish':
        actor=WRAPPER.get_houdini_asset_actor()
        unreal.get_editor_subsystem(unreal.EditorActorSubsystem).set_selected_level_actors([actor])
        unreal.EditorAssetLibrary.save_directory('/Game/ICA10_Stairs',only_if_is_dirty=False,recursive=True)
        unreal.EditorAssetLibrary.save_directory('/Game/HoudiniEngine',only_if_is_dirty=False,recursive=True)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        record(stage='saved',map='/Game/ICA10_Stairs/ICA10_StairDemo',curve_edit_verified=True)
        STATE['next_action']='screenshot';STATE['action_after']=time.time()+15
    elif action=='screenshot':
        unreal.AutomationLibrary.take_high_res_screenshot(1400,1000,ROOT+'/render/ICA10_Unreal.png',camera=CAMERA)
        STATE['next_action']='done';STATE['action_after']=time.time()+8
    elif action=='done':
        record(stage='complete',screenshot=ROOT+'/render/ICA10_Unreal.png')
        unreal.unregister_slate_post_tick_callback(TICK_HANDLE)

run()
