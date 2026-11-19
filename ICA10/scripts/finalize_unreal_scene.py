import unreal,os,time,json,traceback
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace('\\','/')
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
level=unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/ICA10_Stairs/ICA10_StairDemo')
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
stair=existing['ICA10_Editable_Staircase']
components=stair.get_components_by_class(unreal.StaticMeshComponent)
assert components and all(c.static_mesh for c in components),'Reopened map lost staircase mesh'
sky=existing.get('ICA10_AmbientLight') or actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,2200))
sky.set_actor_label('ICA10_AmbientLight')
skyc=sky.get_component_by_class(unreal.SkyLightComponent)
skyc.set_editor_property('source_type',unreal.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
skyc.set_cubemap(unreal.load_asset('/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap'))
skyc.set_intensity(1.4)
skyc.set_editor_property('lower_hemisphere_is_black',False)
atmos=existing.get('ICA10_Sky') or actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector())
atmos.set_actor_label('ICA10_Sky')
key=existing['ICA10_KeyLight'].get_component_by_class(unreal.DirectionalLightComponent)
key.set_editor_property('atmosphere_sun_light',True)
key.set_intensity(3)
key.set_editor_property('light_source_angle',2)
fill=existing['ICA10_FillLight'].get_component_by_class(unreal.DirectionalLightComponent)
fill.set_intensity(1.5)
fill.set_cast_shadows(False)
camera=existing['ICA10_PreviewCamera']
camera.get_component_by_class(unreal.CameraComponent).set_editor_property('constrain_aspect_ratio',False)
exposure=existing.get('ICA10_Exposure') or actors.spawn_actor_from_class(unreal.PostProcessVolume,unreal.Vector())
exposure.set_actor_label('ICA10_Exposure')
exposure.set_editor_property('unbound',True)
settings=exposure.get_editor_property('settings')
for field,value in [('override_auto_exposure_min_brightness',True),('override_auto_exposure_max_brightness',True),('auto_exposure_min_brightness',1.0),('auto_exposure_max_brightness',1.0),('override_auto_exposure_bias',True),('auto_exposure_bias',0.0)]:
    settings.set_editor_property(field,value)
exposure.set_editor_property('settings',settings)
# Use simple neutral matte material so the geometry is clear in the submission view.
mat_path='/Game/ICA10_Stairs/M_StairSteel'
mat=unreal.load_asset(mat_path)
if not mat:
    mat=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_StairSteel','/Game/ICA10_Stairs',unreal.Material,unreal.MaterialFactoryNew())
    color=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-300,0)
    color.set_editor_property('constant',unreal.LinearColor(.28,.32,.36,1))
    unreal.MaterialEditingLibrary.connect_material_property(color,'',unreal.MaterialProperty.MP_BASE_COLOR)
    rough=unreal.MaterialEditingLibrary.create_material_expression(mat,unreal.MaterialExpressionConstant,-300,160)
    rough.set_editor_property('r',.75)
    unreal.MaterialEditingLibrary.connect_material_property(rough,'',unreal.MaterialProperty.MP_ROUGHNESS)
    unreal.MaterialEditingLibrary.recompile_material(mat)
for component in components:
    for idx in range(component.get_num_materials()):component.set_material(idx,mat)
unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera.get_actor_location(),camera.get_actor_rotation())
actors.set_selected_level_actors([])
unreal.EditorAssetLibrary.save_directory('/Game/ICA10_Stairs',only_if_is_dirty=False,recursive=True)
level.save_current_level()
report={'reopen_verified':True,'static_mesh_components':len(components),'actor':stair.get_path_name(),'mesh_assets':[c.static_mesh.get_path_name() for c in components]}
api=unreal.HoudiniPublicAPIBlueprintLib.get_api()
wrapper=unreal.HoudiniPublicAPIAssetWrapper.create_empty_wrapper(api)
assert wrapper.wrap_houdini_asset_object(stair)
curve_input=wrapper.get_input_at_index(0)
curve_objects=curve_input.get_input_objects()
curve_points=curve_objects[0].get_curve_points()
assert len(curve_points)==5
report.update(curve_input_persisted=True,curve_points=len(curve_points))
with open(ROOT+'/unreal_reopen_validation.json','w') as f:json.dump(report,f,indent=2)
start=time.time();phase=0;capture_task=None;capture_started=None
def tick(delta):
    global phase,capture_task,capture_started
    try:
        if phase==0 and time.time()-start>20:
            capture_task=unreal.AutomationLibrary.take_high_res_screenshot(1400,1000,ROOT+'/render/ICA10_Unreal.png',camera=camera)
            capture_started=time.time()
            phase=1
        elif phase==1 and time.time()-capture_started>30:
            actors.set_selected_level_actors([stair])
            level.save_current_level()
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    except Exception:
        with open(ROOT+'/unreal_finalize_error.txt','w') as f:f.write(traceback.format_exc())
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
handle=unreal.register_slate_post_tick_callback(tick)
