# SPDX-License-Identifier: GPL-2.0-or-later

bl_info = {
    "name" : "Fuzzy Tools",
    "author" : "Sacha Goedegebure",
    "version" : (3,0,2),
    "blender" : (3,6,0),
    "location" : "View3d > Sidebar > Fuzzy. Alt+M to move keyframes and markers",
    "description" : "Tools for an efficient 1-person pipeline and multi-camera workflow",
    "doc_url" : "https://github.com/sagotoons/fuzzytools/wiki",
    "tracker_url" : "https://github.com/sagotoons/fuzzytools/issues",
    "category" : "Interface",
}


import bpy

import math

from bpy.props import (BoolProperty,
                       FloatProperty, 
                       IntProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
from math import radians, degrees

from bpy.app.handlers import persistent


# check blender version for Eevee Next
def is_next_version(min_version=(4, 2, 0)):
    current_version = bpy.app.version
    return current_version >= min_version


# find HDRI studio light when used in Fuzzy World shader during start up
@persistent
def reload_image(_):
    world = bpy.context.scene.world
    nodes = world.node_tree.nodes
    if world.name != 'Fuzzy World':
        return 
    try:
        node = nodes['World HDRI']
    except KeyError: ## for files created with Fuzzy Tools 2.0.0 or older
        nodes['Environment Texture'].name = 'World HDRI'
        node = nodes['World HDRI']
    # remove suffix
    name = node.image.name.rsplit('.', 1)[0]
    valid_names = {'city', 'courtyard', 'forest', 'interior', 'night', 'studio', 'sunrise', 'sunset'}
    if name not in valid_names or node.image.file_format == 'OPEN_EXR':
        return
    node.image.name = name + "_old"
    try:
        hdri = bpy.data.images.load(
            bpy.context.preferences.studio_lights[name + '.exr'].path, check_existing=True
        )
        node.image = hdri
    except Exception as e:
        print(f"Error loading HDRI: {e}")


# handler initialized during render
@persistent
def auto_animate_scene(scene, context):
    prop = bpy.context.scene.fuzzy_props
    prop.scene_animate = True
bpy.app.handlers.render_init.append(auto_animate_scene)

# handler for removing previous handler during canceling or completing render
@persistent
def disable_animate_scene(scene, context):
    prop = bpy.context.scene.fuzzy_props
    
    handlers = bpy.app.handlers.frame_change_post
    check_handlers = [handler for handler in handlers if 'check' in str(handler)]
    # method below due to unique functions for handlers
    if len(check_handlers) == 1:
        prop.scene_animate = False
    if len(check_handlers) == 2:
        prop.scene_animate = False
        prop.scene_animate = False
        prop.scene_animate = True
bpy.app.handlers.render_cancel.append(disable_animate_scene)
bpy.app.handlers.render_complete.append(disable_animate_scene)


# fix naming after upgrades in v3.0.2
@persistent
def name_fix(_):
    objs = bpy.data.objects
    if 'Fuzzy floor' in objs:
        floor = objs['Fuzzy floor']
        floor.name = 'FuzzyFloor'
        mods = floor.modifiers
        if 'Normal Direction' in mods:
            mods['Normal Direction'].name = 'NormalDirection'
    if 'floor normal' in objs:
        objs['floor normal'].name = 'FloorNormal'


# ------------------------------------------------------------------------
#    SCENE PROPERTIES
# ------------------------------------------------------------------------

def check(self):
    # check motion blur markers
    scene = bpy.context.scene
    frame = scene.frame_current
    markers = scene.timeline_markers

    if is_next_version():
        version = scene.render
    else:
        version = scene.eevee
   
    if any(marker.name.startswith('mblur') for marker in markers):
        mblur = False
        # check mblur markers in reversed order
        for k, v in reversed(sorted(markers.items(), key=lambda it: it[1].frame)):
            if v.frame <= frame and v.name.startswith('mblur_on'):
                version.use_motion_blur = True
                val = v.name.strip('mblur_on')
                try:
                    version.motion_blur_shutter = float(val)
                except ValueError:
                    pass
                mblur = True
                break
            elif v.frame <= frame and v.name == 'mblur_off':
                version.use_motion_blur = False
                mblur = True
                break
        # check for first mblur marker
        if not mblur:
            for k, v in sorted(markers.items(), key=lambda it: it[1].frame):
                if v.frame >= frame and v.name.startswith('mblur_on'):
                    version.use_motion_blur = True
                    val = v.name.strip('mblur_on')
                    try:
                        version.motion_blur_shutter = float(val)
                    except ValueError:
                        pass
                    break
                elif v.frame >= frame and v.name == 'mblur_off':
                    version.use_motion_blur = False
                    break


def check_scene(self, context):
    if self.scene_animate:
        bpy.app.handlers.frame_change_post.append(check)
    else:
        bpy.app.handlers.frame_change_post.remove(check)
     

class FuzzyProperties(PropertyGroup):

    scene_animate: BoolProperty(
        name='Update Motion Blur',
        description="""Update animated motion blur properties in viewport.
Enables automatically during rendering""",
        default=False,
        update=check_scene
    )

    fuzzy_color1: FloatVectorProperty(
        name="Palette Color 1",
        subtype='COLOR',
        default=(0.09, 0.17, 1.0),
        min=0.0, max=1.0,
    )

    fuzzy_color2: FloatVectorProperty(
        name="Palette Color 2",
        subtype='COLOR',
        default=(0.02, 0.05, 0.40),
        min=0.0, max=1.0,
    )


# ------------------------------------------------------------------------
#    OPERATOR - Build All
# ------------------------------------------------------------------------

class SCENE_OT_build_all(Operator):
    """Place a camera, floor, sun light and rim light. Create a new Fuzzy World. Optimize Eevee settings.
Replace existing floor and active world, if available.
Delete the default cube, camera, and light"""
    bl_idname = "scene.build_all"
    bl_label = "Build All"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        ops = bpy.ops
        ops.object.fuzzy_camera()
        ops.mesh.fuzzy_floor()
        ops.world.fuzzy_sky()
        ops.object.fuzzy_sun()
        ops.object.fuzzy_rimlight()
        ops.scene.fuzzy_eevee()
        
        self.report({'INFO'}, "POP!")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Camera
# ------------------------------------------------------------------------

class OBJECT_OT_fuzzy_camera(Operator):
    """Place an optimized camera.
Delete the default camera"""
    bl_idname = "object.fuzzy_camera"
    bl_label = "Build Camera"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        objects = scene.objects
        objs = bpy.data.objects

        # CAMERA PROPERTIES
        loc_y = -25
        loc_z = 2.5
        rot_x = 90
        lens = 85
        clip_start = 1
        clip_end = 250

        # Delete default camera
        if 'Camera' in objects:
            objs.remove(objs["Camera"])

        # Add new camera and set rotation
        bpy.ops.object.camera_add(rotation=(radians(rot_x), 0, 0))
        ob = context.active_object

        # List all objects with "CAM." prefix
        cams = [obj for obj in objs if obj.name.startswith("CAM.")]

        if not cams:
            ob.name = "CAM.001"
            ob.location = (0, loc_y, loc_z)
        else:
            # Remove "CAM." from names to leave only numbers + letter
            cams_ABC = [s[4:] for s in [obj.name for obj in cams]]
            # Remove possible letter suffix
            cams_no_ABC = [s[:3] for s in cams_ABC]
            # Find the smallest available number
            available_numbers = set(range(1, max(map(int, cams_no_ABC)) + 2))
            used_numbers = set(map(int, cams_no_ABC))
            i = min(available_numbers - used_numbers)
            # Change name of camera with increasing number
            ob.name = f"CAM.{i:03}"
            # Place camera distance away from previous camera's origin
            ob.location = (1.5*(-1 + i), loc_y, loc_z)

        # create collection 'Cameras' if it doesn't exist yet
        link_to_name = 'Cameras'
        link_to = scene.collection.children.get(link_to_name)
        if link_to is None:
            link_to = bpy.data.collections.new(link_to_name)
            scene.collection.children.link(link_to)

        # link new camera to collection 'Cameras'
        oldcoll = ob.users_collection[0]
        if oldcoll.name == 'Scene Collection':
            context.collection.objects.unlink(ob)
        else:
            oldcoll.objects.unlink(ob)        
        bpy.data.collections['Cameras'].objects.link(ob)

        ob.show_name = True
        data = ob.data
        data.name = ob.name

        # optimize camera settings
        data.show_limits = False
        data.show_name = True
        data.clip_start = clip_start
        data.clip_end = clip_end
        data.lens = lens
        data.passepartout_alpha = 0.8
        data.dof.focus_distance = abs(loc_y)

        # make new camera active
        objects = context.view_layer.objects
        try:
            if ob.name in objects:
                objects.active = ob
        except RuntimeError:
            pass

        self.report({'INFO'}, f"Camera '{ob.name}' added to scene")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Fuzzy Floor (shadow only)
# ------------------------------------------------------------------------

class MESH_OT_fuzzy_floor(Operator):
    """Place a floor with shadow only and replace the old one.
Delete the default cube"""
    bl_idname = "mesh.fuzzy_floor"
    bl_label = "Build Floor"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        objects = scene.objects

        # delete objects
        for name in ["Cube", "FuzzyFloor", "FloorNormal"]:
            if name in objects:
                obj = bpy.data.objects[name]
                if name == "Cube":
                    if hasattr(obj.data, 'polygons') and len(obj.data.polygons) == 6:
                        bpy.data.objects.remove(obj)
                else:
                    bpy.data.objects.remove(obj)

        # add floor
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))

        # name new Plane 'FuzzyFloor'
        floor = context.active_object
        floor.name = "FuzzyFloor"

        # create collection 'Set' if it doesn't exist yet
        link_to_name = 'Set'
        try:
            link_to = scene.collection.children[link_to_name]
        except KeyError:
            link_to = bpy.data.collections.new(link_to_name)
            scene.collection.children.link(link_to)

        # link floor to collection 'Set'
        oldcoll = floor.users_collection[0]
        if oldcoll.name == 'Scene Collection':
            context.collection.objects.unlink(floor)
        else:
            oldcoll.objects.unlink(floor)        
        bpy.data.collections['Set'].objects.link(floor)

        # create empty as Target for FloorNormal Edit modifier
        bpy.ops.object.empty_add(location=(15, -20, 20))
        empty = context.object
        empty.name = "FloorNormal"
        empty.empty_display_size = 6
        empty.empty_display_type = 'SINGLE_ARROW'
        link_to_name = 'Set'
        track = empty.constraints.new('DAMPED_TRACK')
        track.target = floor
        track.track_axis = 'TRACK_Z'
        
        # link empty to collection 'Set'
        oldcoll = empty.users_collection[0].name
        if oldcoll == 'Scene Collection':
            context.collection.objects.unlink(empty)
        else:       
            bpy.data.collections[oldcoll].objects.unlink(empty)
        bpy.data.collections['Set'].objects.link(empty)

        # objects settings ## error exception added for blender 4.1
        try:
            floor.data.use_auto_smooth = True
        except AttributeError:
            pass
        
        # create modifier 'Normal Edit' and set empty as Target
        normal = floor.modifiers.new("NormalDirection", 'NORMAL_EDIT')
        normal.mode = 'DIRECTIONAL'
        normal.use_direction_parallel = True
        normal.target = bpy.data.objects["FloorNormal"]
        normal.no_polynors_fix = True

        # object settings
        floor.hide_select = True
        floor.show_wire = True

        # Get material
        oldmat = bpy.data.materials.get("floor_shadow")
        if oldmat is not None:
            oldmat.name = "floor_shadow_old"

        # create material
        mat = bpy.data.materials.new(name="floor_shadow")
        # Assign it to object
        if floor.data.materials:
            # assign to 1st material slot
            floor.data.materials[0] = mat
        else:
            # no slots
            floor.data.materials.append(mat)

        mat.use_nodes = True

        # build node shader
        nodes = bpy.data.materials['floor_shadow'].node_tree.nodes
        nodes.remove(nodes.get('Principled BSDF'))

        matoutput = nodes.get("Material Output")
        matoutput.location = (600, 80)
        matoutput.target = 'EEVEE'

        mixshader = nodes.new("ShaderNodeMixShader")
        mixshader.location = (200, 60)

        shadow = nodes.new("ShaderNodeBsdfDiffuse")
        shadow.location = (0, 10)
        shadow.inputs[0].default_value = (0, 0, 0, 1)

        holdout = nodes.new("ShaderNodeHoldout")
        holdout.location = (-200, -160)

        clamp_shadow = nodes.new("ShaderNodeClamp")
        clamp_shadow.location = (-200, 240)

        mix_AO = nodes.new("ShaderNodeMixRGB")
        mix_AO.location = (-570, 100)
        mix_AO.inputs[0].default_value = 0.7
        mix_AO.blend_type = 'MULTIPLY'
        mix_AO.mute = True

        shader_RGB = nodes.new("ShaderNodeShaderToRGB")
        shader_RGB.location = (-770, 0)

        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        diffuse.location = (-970, -100)
        diffuse.inputs[0].default_value = (1, 1, 1, 1)

        dodge_floor = nodes.new("ShaderNodeMixRGB")
        dodge_floor.location = (-380, 60)
        dodge_floor.inputs[0].default_value = 1
        dodge_floor.blend_type = 'DODGE'

        power = nodes.new("ShaderNodeMath")
        power.location = (0, 180)
        power.operation = 'POWER'
        power.use_clamp = True

        value = nodes.new("ShaderNodeMath")
        value.name = "Shadow Value"
        value.location = (-200, 60)
        value.operation = 'MULTIPLY_ADD'
        value.inputs[0].default_value = 0
        value.inputs[1].default_value = -1
        value.inputs[2].default_value = 1

        value_dodge = nodes.new("ShaderNodeMix")
        value_dodge.name = "Dodge Value"
        value_dodge.location = (-570, -150)
        value_dodge.inputs[0].default_value = 0.1
        value_dodge.inputs[3].default_value = 1

        value_clamp = nodes.new("ShaderNodeMix")
        value_clamp.name = "Clamp Value"
        value_clamp.location = (-380, 260)
        value_clamp.inputs[0].default_value = 0.1
        value_clamp.inputs[3].default_value = 1

        alpha_mix = nodes.new("ShaderNodeMixShader")
        alpha_mix.name = "Floor Alpha"
        alpha_mix.location = (0, -160)

        BG_group = nodes.new("ShaderNodeGroup")
        BG_group.name = "Floor Group"
        BG_group.location = (-200, -260)

        # check for Fuzzy BG node group
        BG = 'Fuzzy BG'
        groups = bpy.data.node_groups
        if BG not in groups:
            alpha_mix.inputs[0].default_value = 0.0
        else:
            alpha_mix.inputs[0].default_value = 1.0
            BG_group.node_tree = groups[BG]

        # link nodes
        link = mat.node_tree.links.new
        link(mixshader.outputs[0], matoutput.inputs[0])
        link(shadow.outputs[0], mixshader.inputs[1])
        link(holdout.outputs[0], alpha_mix.inputs[1])
        link(alpha_mix.outputs[0], mixshader.inputs[2])
        link(clamp_shadow.outputs[0], power.inputs[0])
        link(mix_AO.outputs[0], dodge_floor.inputs[1])
        link(value.outputs[0], power.inputs[1])
        link(power.outputs[0], mixshader.inputs[0])
        link(shader_RGB.outputs[0], mix_AO.inputs[1])
        link(diffuse.outputs[0], shader_RGB.inputs[0])
        link(dodge_floor.outputs[0], clamp_shadow.inputs[0])
        link(value_dodge.outputs[0], dodge_floor.inputs[2])
        link(value_clamp.outputs[0], clamp_shadow.inputs[1])
        if BG in groups:
            link(BG_group.outputs[0], alpha_mix.inputs[2])
        
        # material settings
        mat.use_backface_culling = True
        mat.blend_method = 'BLEND'

        # cycles material nodes
        matoutput2 = nodes.new("ShaderNodeOutputMaterial")
        matoutput2.location = (400, -80)
        matoutput2.target = 'CYCLES'
        link(diffuse.outputs[0], matoutput2.inputs[0])
        # cycles material settings
        floor.is_shadow_catcher = True
        floor.visible_diffuse = False
        floor.visible_glossy = False
        floor.visible_transmission = False

        # viewport & outliner settings
        screens = bpy.data.screens
        for scr in screens:
            for area in scr.areas:
                if area.type == 'VIEW_3D':
                    area.spaces[0].overlay.show_relationship_lines = False
                    area.spaces[0].clip_start = 0.1
                # elif area.type == 'OUTLINER':
                #     area.spaces[0].show_restrict_column_viewport = True
                #     area.spaces[0].show_restrict_column_select = True
        
        # 4.2 or above
        if is_next_version():
            mix_AO.mute = False
            mix_AO.name = "AO Factor"
            
            AO = nodes.new("ShaderNodeAmbientOcclusion")
            AO.name = "AO"
            AO.location = (-770, 230)
            AO.inputs[1].default_value = 1.6
            link(AO.outputs[1], mix_AO.inputs[2])
            
            mixshader2 = nodes.new("ShaderNodeMixShader")
            mixshader2.location = (400, 60)
            link(mixshader.outputs[0], mixshader2.inputs[1])
            link(mixshader2.outputs[0], matoutput.inputs[0])
            
            lightpath = nodes.new("ShaderNodeLightPath")
            lightpath.location = (200, 140)
            for output in lightpath.outputs:
                output.hide = True
            link(lightpath.outputs[1], mixshader2.inputs[0])
            
            transp = nodes.new("ShaderNodeBsdfTransparent")
            transp.location = (200, -80)
            link(transp.outputs[0], mixshader2.inputs[2])
        else:
            mat.shadow_method = 'NONE'

        self.report({'INFO'}, f"'{floor.name}' and '{empty.name}' added to scene")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - World (Sky)
# ------------------------------------------------------------------------

class WORLD_OT_fuzzy_sky(Operator):
    """Create a new world and replace the active one"""
    bl_idname = "world.fuzzy_sky"
    bl_label = "New Fuzzy Sky"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        # rename "Fuzzy World" if it exists
        if "Fuzzy World" in bpy.data.worlds:
            bpy.data.worlds['Fuzzy World'].name = 'World_old'
        else:
            pass

        # create "Fuzzy World", make it scene world & enable Use Nodes
        bpy.data.worlds.new("Fuzzy World")
        scene.world = bpy.data.worlds['Fuzzy World']
        scene.world.use_nodes = True

        # build node shader
        nodes = scene.world.node_tree.nodes

        nodes.remove(nodes.get('Background'))

        # HDR nodes
        worldoutput = nodes.get("World Output")
        worldoutput.location = (900, 50)
        
        # dictionary
        ref = {}
        # list with ref_name, name, type, locx, locy
        node_list = [
            ('texcoord1', "Texture Coordinate", "TexCoord", -1000, 440), # row 1
            ('mapskytex1',"HDRI Delta Rot", "Mapping", -800, 440), # row 2
            ('mapskytex2',"HDRI Rotation", "Mapping", -600, 440), # row 3
            ('clamprefl', "Clamp Reflection", "Value", -600, 60),
            ('multiply', "Multiply", "Math", -600, -40),
            ('skytex', "World HDRI", "TexEnvironment", -400, 400), # row 4
            ('greater', "Greater Than", "Math", -400, 160),
            ('lightpath', "Light Path", "LightPath", -400, -40),
            ('sepHSV', "Separate Color", "SeparateColor", -100, 400), # row 5
            ('darken', "Darken", "MixRGB", -100, 240),
            ('mixrefl', "Mix Reflection", "MixRGB", 100, 400), #row6
            ('comHSV', "Combine Color", "CombineColor", 300, 400), #row7
            ('BG1', "HDRI Strength", "Background", 500, 160), #row8
            ('BG2', "Background", "Background", 500, -100),
            ('mixshader',"Mix Shader", "MixShader", 700, 60), #row9
        ]

        # create nodes
        for ref_name, name, type, locx, locy in node_list:
            node = nodes.new("ShaderNode"+type)
            node.location = (locx, locy)
            node.label = name
            node.name = name
        
            # Save ref_name in dictionary
            ref[ref_name] = node
     
        # extra node properties    
        ref['mapskytex1'].inputs[2].default_value[2] = radians(90)
        ref['clamprefl'].outputs[0].default_value = 2
        ref['multiply'].operation = 'MULTIPLY'
        ref['multiply'].inputs[1].default_value = 10
        ref['greater'].operation = 'GREATER_THAN'
        ref['greater'].inputs[1].default_value = 0
        for output in ref['lightpath'].outputs:
            output.hide = True
        ref['sepHSV'].mode = 'HSV'
        ref['darken'].blend_type = 'DARKEN'
        ref['comHSV'].mode = 'HSV'

        # connect nodes
        link = scene.world.node_tree.links.new
        link(ref['texcoord1'].outputs[0], ref['mapskytex1'].inputs[0])
        link(ref['mapskytex1'].outputs[0], ref['mapskytex2'].inputs[0])
        link(ref['mapskytex2'].outputs[0], ref['skytex'].inputs[0])
        link(ref['clamprefl'].outputs[0], ref['multiply'].inputs[0])
        link(ref['clamprefl'].outputs[0], ref['greater'].inputs[0])
        link(ref['multiply'].outputs[0], ref['darken'].inputs[2])
        link(ref['skytex'].outputs[0], ref['sepHSV'].inputs[0])
        link(ref['greater'].outputs[0], ref['mixrefl'].inputs[0])
        link(ref['lightpath'].outputs[3], ref['darken'].inputs[0])
        link(ref['lightpath'].outputs[0], ref['mixshader'].inputs[0])
        for i in range(2):
            link(ref['sepHSV'].outputs[i], ref['comHSV'].inputs[i])
        link(ref['sepHSV'].outputs[2], ref['darken'].inputs[1])
        link(ref['sepHSV'].outputs[2], ref['mixrefl'].inputs[1])
        link(ref['darken'].outputs[0], ref['mixrefl'].inputs[2])
        link(ref['mixrefl'].outputs[0], ref['comHSV'].inputs[2])
        link(ref['comHSV'].outputs[0], ref['BG1'].inputs[0])
        link(ref['BG1'].outputs[0], ref['mixshader'].inputs[1])
        link(ref['BG2'].outputs[0], ref['mixshader'].inputs[2])
        link(ref['mixshader'].outputs[0], worldoutput.inputs[0])

        # load the texture from Blender data folder
        hdri = bpy.data.images.load(
            context.preferences.studio_lights['sunset.exr'].path, check_existing=True)
        ref['skytex'].image = hdri

        # check for Fuzzy BG node group and remove
        BG = 'Fuzzy BG'
        groups = bpy.data.node_groups
        if BG in groups:
            groups.remove(groups[BG])

        # create Fuzzy BG node group
        BG_group = groups.new(BG, 'ShaderNodeTree')
        if bpy.app.version_string.startswith('3'):
            BG_group.outputs.new('NodeSocketColor', "Color")
        else:
            BG_group.interface.new_socket("Color", in_out='OUTPUT',
                                          socket_type='NodeSocketColor')

        # create empty group node and apply Fuzzy BG
        group = nodes.new("ShaderNodeGroup")
        group.location = (300, -100)
        group.name = "BG Group"
        group.node_tree = BG_group
        
        # BG group nodes
        nodes = BG_group.nodes
        
        # dictionary
        ref = {}
        # list with ref_name, name, type, locx, locy
        node_list = [
            ('texcoord2', "Tex Coord", "TexCoord", -1860, -100), # row 1
            ('gradscale', "Scale Gradient", "Mix", -1860, -500),
            ('radialloc', "Radial Location", "VectorMath", -1650, 220), # row 2
            ('radialscale', "Radial Scale", "VectorMath", -1650, -40),
            ('vectrans', "", "VectorTransform", -1650, -300),
            ('power', "", "Math", -1650, -480),
            ('mapsphere', "", "Mapping", -1450, 50), # row 3
            ('divide', "", "MixRGB", -1450, -350),
            ('maplinear3d', "", "Mapping", -1250, -400), # row 4
            ('maplinear', "", "Mapping", -1250, -30),
            ('gradsphere', "", "TexGradient", -1050, -80), #row5
            ('window3d', "Window to 3D", "MixRGB", -1050, -240),
            ('invert', "", "Invert", -880, -80), #row6
            ('gradlinear', "Gradient Linear", "TexGradient", -880, -240),
            ('rampradial', "Radial Ease", "ValToRGB", -700, 20), #row7
            ('ramplinear', "Linear Ease", "ValToRGB", -700, -200),
            ('col1', "BG Color 1", "RGB", -680, -440),
            ('col2', "BG Color 2", "RGB", -680, -640),
            ('linear2ease', "Linear Ease", "Mix", -420, -200), #row8
            ('swapcol1', "Swap Colors 1", "MixRGB", -420, -440),
            ('swapcol2', "Swap Colors 2", "MixRGB", -420, -640),
            ('radial2linear', "Radial to Linear", "MixRGB", -220, -80), #row9
            ('colgradient', "Color Gradient", "MixRGB",-40, -300), #row10
            ('flat2gradient', "Flat to Gradient", "MixRGB", 140, -100), #row11   
        ]
         
        # create nodes
        for ref_name, name, type, locx, locy in node_list:
            node = nodes.new("ShaderNode"+type)
            node.location = (locx, locy)
            node.label = name
            node.name = name
            
            # Save ref_name in dictionary
            ref[ref_name] = node
     
        # extra node properties    
        ref['radialloc'].inputs[1].default_value = (0.5, 0.5, 0)
        ref['radialscale'].operation = 'MULTIPLY'
        ref['radialscale'].inputs[0].default_value = (1, 1, 0)
        ref['radialscale'].inputs[1].default_value = (0.71, 0.71, 1)
        ref['divide'].blend_type = 'DIVIDE'
        ref['divide'].inputs[0].default_value = 1
        ref['gradscale'].inputs[2].default_value = 0.001
        ref['gradscale'].inputs[3].default_value = 1
        ref['gradsphere'].gradient_type = 'SPHERICAL'
        ref['maplinear'].inputs[2].default_value[2] = 1.5708
        ref['maplinear'].vector_type = 'TEXTURE'
        ref['maplinear3d'].inputs[1].default_value[2] = -0.5
        ref['maplinear3d'].inputs[2].default_value[1] = -1.5708
        ref['maplinear3d'].vector_type = 'TEXTURE'
        ref['mapsphere'].vector_type = 'TEXTURE'
        ref['power'].inputs[1].default_value = 2
        ref['power'].operation = 'POWER'
        ref['ramplinear'].color_ramp.interpolation = "EASE"
        ref['rampradial'].color_ramp.interpolation = "EASE"
        ref['col1'].outputs[0].default_value = (0.09, 0.17, 1, 1)
        ref['col2'].outputs[0].default_value = (0.02, 0.05, 0.40, 1)
        ref['vectrans'].convert_from = 'CAMERA'
        ref['vectrans'].convert_to = 'WORLD'
        ref['vectrans'].vector_type = 'NORMAL'

        # output node
        output = nodes.new("NodeGroupOutput")
        output.location = (340, -100)

        switches = [
            ("Color Swap", -880, -600, True),
            ("Flat Gradient", -40, -100, True),
            ("Radial Linear", -420, -40, False),
            ("Window Global", -1450, -560, False),
        ]
        
        for name, locx, locy, clamp in switches:
            switch = nodes.new("ShaderNodeMix")
            switch.location = (locx, locy)
            switch.name = name
            switch.label = name
            switch.clamp_factor = clamp
            switch.inputs[0].default_value = -1
            switch.inputs[2].default_value = 1
            switch.inputs[3].default_value = 2
            for input in switch.inputs:
                input.hide = True
            
        # connect nodes
        link(group.outputs[0], scene.world.node_tree.nodes['Background'].inputs[0])
        # connect group nodes
        link = BG_group.links.new
        node_links = {
            'radialloc': [('mapsphere', 1)],
            'radialscale': [('mapsphere', 3)],
            'colgradient': [('flat2gradient', 2)],
            'divide': [('maplinear3d', 0)],
            'gradlinear': [('ramplinear', 0), ('linear2ease', 2)],
            'gradsphere': [('invert', 1)],
            'gradscale': [('power', 0)],
            'invert': [('rampradial', 0)],
            'linear2ease': [('radial2linear', 2)],
            'maplinear': [('window3d', 1)],
            'maplinear3d': [('window3d', 2)],
            'mapsphere': [('gradsphere', 0)],
            'power': [('divide', 2)],
            'radial2linear': [('colgradient', 0)],
            'ramplinear': [('linear2ease', 3)],
            'rampradial': [('radial2linear', 1)],
            'col1': [('swapcol1', 2), ('swapcol2', 1)],
            'col2': [('swapcol1', 1), ('swapcol2', 2)],
            'swapcol1': [('colgradient', 1), ('flat2gradient', 1)],
            'swapcol2': [('colgradient', 2)],
            'vectrans': [('divide', 1)],
            'window3d': [('gradlinear', 0)],
        }
        
        for name, targets in node_links.items():
            for target, input_index in targets:
                link(ref[name].outputs[0], ref[target].inputs[input_index])
       
        # remaining links
        link(ref['flat2gradient'].outputs[0], output.inputs[0])
        link(ref['texcoord2'].outputs[4], ref['vectrans'].inputs[0])
        link(ref['texcoord2'].outputs[5], ref['mapsphere'].inputs[0])
        link(ref['texcoord2'].outputs[5], ref['maplinear'].inputs[0])

        switch_links = {
            'Color Swap': ['swapcol1', 'swapcol2'],
            'Flat Gradient': ['flat2gradient'],
            'Radial Linear': ['radial2linear'],
            'Window Global': ['linear2ease', 'window3d'],
        }
        for name, targets in switch_links.items():
            for target in targets:
                link(nodes[name].outputs[0], ref[target].inputs[0])
        
        # check for FuzzyFloor and set Fuzzy BG node group
        obj = bpy.data.objects
        if 'FuzzyFloor' in obj:
            tree = bpy.data.materials['floor_shadow'].node_tree
            floor_group = tree.nodes['Floor Group']
            floor_alpha = tree.nodes['Floor Alpha']
            floor_group.node_tree = BG_group
            tree.links.new(floor_group.outputs[0], floor_alpha.inputs[2])
            floor_alpha.inputs[0].default_value = 1.0
            
        self.report({'INFO'}, "World 'Fuzzy World' created")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Sun
# ------------------------------------------------------------------------

class OBJECT_OT_fuzzy_sun(Operator):
    """Place an optimized sun light.
Delete the default light"""
    bl_idname = "object.fuzzy_sun"
    bl_label = "Build Sun"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        objects = scene.objects
        objs = bpy.data.objects
        
        # list of current Sun lights
        suns = [obj for obj in objects if obj.type == 'LIGHT' and obj.name.startswith('Sun')]

        if 'Light' in objects:
            objs.remove(objs["Light"])

        # add sun light
        bpy.ops.object.light_add(
            type='SUN', align='WORLD', location=(20+len(suns), -10, 10))

        # name new light 'Sun'
        ob = context.active_object
        if len(suns) == 0:
            ob.name = "Sun"
        else:
            v = str(len(suns)).zfill(3)
            ob.name = f"Sun.{v}"
        ob.data.name = ob.name

        # create collection 'Set' if it doesn't exist yet
        link_to_name = 'Set'
        try:
            link_to = scene.collection.children[link_to_name]
        except KeyError:
            link_to = bpy.data.collections.new(link_to_name)
            scene.collection.children.link(link_to)
        # link new light to collection 'Set'
        oldcoll = ob.users_collection[0].name
        if oldcoll == 'Scene Collection':
            context.collection.objects.unlink(ob)
        else:
            bpy.data.collections[oldcoll].objects.unlink(ob)        
        bpy.data.collections['Set'].objects.link(ob)

        # light rotation
        ob.rotation_euler = (radians(50), 0, radians(40))
        
        # light settings
        ob.data.energy = 1.5
        ob.data.angle = radians(15)

        ## EEVEE NEXT
        if is_next_version():
            ob.data.use_shadow_jitter = True
        else:
            ob.data.use_contact_shadow = True
        
        # make new Sun active
        objects = context.view_layer.objects
        try:
            if ob.name in objects:
                objects.active = ob
        except RuntimeError:
            pass

        self.report({'INFO'}, f"'{ob.name}' added to scene")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Rim Light
# ------------------------------------------------------------------------

class OBJECT_OT_fuzzy_rimlight(Operator):
    """Place an optimized rim light"""
    bl_idname = "object.fuzzy_rimlight"
    bl_label = "Build Rim Light"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        objects = scene.objects
        objs = bpy.data.objects

        # list of current rim lights
        rimlights = [obj for obj in objects if obj.type == 'LIGHT' and obj.name.startswith('RimLight')]
   
        # add sun light
        bpy.ops.object.light_add(
            type='SUN', align='WORLD', location=(-20-len(rimlights), 10, 10))

        # name new light 'RimLight'
        ob = context.active_object
        if len(rimlights) == 0:
            ob.name = "RimLight"
        else:
            v = str(len(rimlights)).zfill(3)
            ob.name = f"RimLight.{v}"
        ob.data.name = ob.name
        
        # create collection 'Set' if it doesn't exist yet
        link_to_name = 'Set'
        link_to = scene.collection.children.get(link_to_name)
        if link_to is None:
            link_to = bpy.data.collections.new(link_to_name)
            scene.collection.children.link(link_to)

        oldcoll = ob.users_collection[0].name
        if oldcoll == 'Scene Collection':
            context.collection.objects.unlink(ob)
        else:
            bpy.data.collections[oldcoll].objects.unlink(ob)
        bpy.data.collections['Set'].objects.link(ob)
        
        # light rotation
        ob.rotation_euler = (radians(70), 0, radians(-150))
        
        # light settings
        ob.data.energy = 10
        ob.data.specular_factor = 0.1
        ob.data.angle = radians(10)

        ## EEVEE NEXT
        if is_next_version():
            ob.data.use_shadow_jitter = True
        else:
            ob.data.use_contact_shadow = True

        # make new Rim Light active
        objects = context.view_layer.objects
        try:
            if ob.name in objects:
                objects.active = ob
        except RuntimeError:
            pass

        self.report({'INFO'}, f"'{ob.name}' added to scene")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - EEVEE optimizing
# ------------------------------------------------------------------------

class SCENE_OT_fuzzy_eevee(Operator):
    """Set the render engine to EEVEE and optimize render settings.
AO and Bloom for Legacy, Raytracing for Next, Color Management for both, and more"""
    bl_idname = "scene.fuzzy_eevee"
    bl_label = "Optimize Eevee"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        render = scene.render
        eevee = scene.eevee
        view = scene.view_settings
        space = context.space_data

        # EEVEE RENDER PROPERTIES
        if is_next_version():
            render.engine = 'BLENDER_EEVEE_NEXT'
            version = render
        else:
            render.engine = 'BLENDER_EEVEE'
            version = eevee
            
        ## GENERAL
        # depth of field
        eevee.bokeh_max_size = 3
        eevee.use_bokeh_jittered = True
        # hair
        render.hair_type = 'STRIP'
        # color management
        view.view_transform = 'Filmic'
        view.exposure = 2.0
        view.gamma = 0.5
        # overlay
        space.shading.use_scene_world = True
        space.overlay.show_look_dev = True
        
        ## EEVEE LEGACY
        if version == eevee:
            # ambient occlusion
            eevee.use_gtao = True
            eevee.gtao_distance = 1.6
            eevee.gtao_factor = 0.7
            eevee.use_gtao_bent_normals = False
            # bloom
            eevee.use_bloom = True
            eevee.bloom_threshold = 1.0
            eevee.bloom_radius = 5
            # screen space reflection
            eevee.use_ssr_refraction = True
            eevee.use_ssr_halfres = False
            eevee.ssr_quality = 1
            # motion blur
            version.motion_blur_position = 'START' # other options will crash blender with animated motion blur
            # shadow
            eevee.shadow_cascade_size = '4096'
            eevee.shadow_cube_size = '2048'
            eevee.use_soft_shadows = True
        
        ## EEVEE NEXT
        if version == render:
            # shadows
            eevee.use_shadows = True
            eevee.use_shadow_jitter_viewport = True
            # ray tracing
            eevee.use_raytracing = True
            eevee.ray_tracing_options.resolution_scale = '1'
            eevee.ray_tracing_options.trace_max_roughness = 0.5
            # fast GI
            eevee.fast_gi_resolution = '1'

        self.report({'INFO'}, "EEVEE settings optimized")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Show/hide all Hair in viewport
# ------------------------------------------------------------------------

class OBJECT_OT_hair_viewport(Operator):
    """Viewport hair visibility"""
    bl_idname = "object.hair_viewport"
    bl_label = "Show or Hide Hair"
    bl_options = {'UNDO'}

    hide: bpy.props.BoolProperty()
    
    def execute(self, context):
        # particle system modifiers
        for obj in bpy.data.objects:
            # Check for particle system hair modifiers
            for modifier in obj.modifiers:
                if (modifier.type == 'PARTICLE_SYSTEM' and 
                        modifier.particle_system.particles.data.settings.type == 'HAIR'):
                    modifier.show_viewport = not self.hide

            # Check for CURVES type objects
            if obj.type == 'CURVES':
                obj.hide_viewport = self.hide

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Copy passepartout of Active Camera to all cameras
# ------------------------------------------------------------------------

class OBJECT_OT_copy_passepartout(Operator):
    """Copy the Passepartout Alpha of Active Camera to all cameras"""
    bl_idname = "object.copy_passepartout"
    bl_label = "Copy Passepartout"
    bl_options = {'UNDO', 'INTERNAL'}

    def execute(self, context):
        scene = context.scene
        active_cam = scene.camera
        alpha = active_cam.data.passepartout_alpha

        cams = bpy.data.cameras

        for cam in cams:
            cam.passepartout_alpha = alpha

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - add Marker for Motion Blur
# ------------------------------------------------------------------------

class MARKER_OT_add_motionblur_marker(Operator):
    """Add a marker to enable or disable motion blur at current frame"""
    bl_idname = "marker.add_motionblur_marker"
    bl_label = "Add Motion Blur Marker"
    bl_options = {'UNDO', 'INTERNAL'}

    blur: bpy.props.StringProperty()

    def execute(self, context):
        scene = context.scene
        fr = scene.frame_current
        marker = scene.timeline_markers

        if is_next_version():
            version = scene.render
        else:
            version = scene.eevee
       
        for m in marker:
            if m.frame == fr and m.name.startswith("mblur"):
                marker.remove(m)
                break

        if self.blur == 'on':
            marker.new('mblur_on', frame=fr)
            version.use_motion_blur = True
        elif self.blur == 'off':
            marker.new('mblur_off', frame=fr)
            version.use_motion_blur = False

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Copy Shutter to Markers
# ------------------------------------------------------------------------

class MARKER_OT_shutter_to_markers(Operator):
    """Copy current shutter time to selected 'mblur_on' markers"""
    bl_idname = "marker.shutter_to_markers"
    bl_label = "Copy Shutter to Markers"
    bl_options = {'UNDO'}

    def execute(self, context):
        scene = context.scene
        markers = scene.timeline_markers
        count = 0

        if is_next_version():
            version = scene.render
        else:
            version = scene.eevee

        for marker in markers:
            if marker.select and marker.name.startswith("mblur_on"):
                base_name = marker.name[:8]
                v = round(version.motion_blur_shutter, 2)
                marker.name = f"{base_name} {v}"
                count += 1

        if count == 0:
            self.report({'WARNING'}, "Selection of 'mblur_on' marker required")
            return {'CANCELLED'}

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Set active Camera
# ------------------------------------------------------------------------

class VIEW3D_OT_set_active_camera(Operator):
    """Set camera as the active camera for this scene"""
    bl_idname = "view3d.set_active_camera"
    bl_label = "Set active camera"
    bl_options = {'UNDO'}
 
    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CAMERA'

    def execute(self, context):
        cam = context.active_object
        
        context.scene.camera = cam

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Camera Bind
# ------------------------------------------------------------------------

class MARKER_OT_camera_bind_new(Operator):
    """Bind the selected camera to a marker on the current frame.
Requires an animation editor to be open"""
    bl_idname = "marker.camera_bind_new"
    bl_label = "Bind Camera to Marker"
    bl_options = {'UNDO'}
 
    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CAMERA'

    def execute(self, context):
        screen = context.window.screen
        count = 0

        for area in screen.areas:
            if area.type == 'DOPESHEET_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with context.temp_override(
                                window=context.window, 
                                screen=screen, area=area, 
                                region=region):
                            bpy.ops.marker.camera_bind()
                            count += 1
                            break
        if count == 0:
            self.report({'WARNING'}, "Open Animation Editor required")
            return {'CANCELLED'}

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Rename Camera as variant
# ------------------------------------------------------------------------

class OBJECT_OT_rename_camera_alphabet(Operator):
    """Rename selected cameras as alphabetic variants of active camera"""
    bl_idname = "object.rename_camera_alphabet"
    bl_label = "Rename as Variant"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        # Ensure at least two cameras are selected and they are all of type 'CAMERA'
        if len(context.selected_objects) < 2:
            return False
        cameras_selected = all(obj.type == 'CAMERA' for obj in context.selected_objects)
        return cameras_selected

    def execute(self, context):
        scene = context.scene
        objs = bpy.data.objects

        active_cam = context.active_object
        selected_cams = context.selected_objects

        # Use ord and chr to generate alphabet dynamically
        ABC = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

        # Get all objects of type 'CAMERA'
        cams = [obj for obj in objs if obj.type == 'CAMERA']

        # Detect if active camera name ends with a capital letter and has no numbers before it
        if active_cam.name[-1:].isupper():
            if len(active_cam.name) > 1:
                # Check the second last character
                second_last_char = active_cam.name[-2]
                if second_last_char.isupper() and not any(char.isdigit() for char in active_cam.name[:-1]):
                    # If second last character is uppercase and no digits, trigger the error
                    self.report({'ERROR'}, 
                            'Naming convention not valid. Use number or single upper case as suffix')
                    return {'CANCELLED'}

        if active_cam in cams:
            base_name = active_cam.name.rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
            last_char = active_cam.name[len(base_name):]

            # If the last character is alphabetic, we will increment from that point
            if last_char and last_char[-1:].isalpha():
                base_name = active_cam.name[:-1]

            for cam in selected_cams:
                if cam != active_cam:
                    for letter in ABC:
                        name_ABC = f"{base_name}{letter}"
                        # Check if the new name already exists among cameras
                        if not any(existing_cam.name == name_ABC for existing_cam in cams):
                            cam.name = name_ABC
                            break  

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Move Keyframes and Markers
# ------------------------------------------------------------------------

class TRANSFORM_OT_keyframes_markers(Operator):
    """Move keyframes and markers from current frame, regardless of selection or visibility"""
    bl_idname = "transform.keyframes_markers"
    bl_label = "Move Keyframes and Markers"
    bl_options = {'REGISTER', 'UNDO'}
    
    frame_shift: IntProperty(
        name="Frames",
        description="Amount of frames to move",
        default=0,
        options={'SKIP_SAVE'}
    )
    
    before_current: BoolProperty(
        name="Before Current Frame",
        description="Move before current frame instead of after",
        default=False,
        options={'SKIP_SAVE'}
    )

    keys: BoolProperty(
        name="Keyframes",
        description="Move Keyframes (NOT linked actions and locked curves)",
        default=True
    )
    
    markers: BoolProperty(
        name="Markers",
        description="Move Markers",
        default=True
    )
    
    fake_user: BoolProperty(
        name="Fake User",
        description="Include actions with Fake User",
        default=False
    )
  
    def execute(self, context):
        scene = context.scene
        fr = scene.frame_current
        frames = self.frame_shift
        a = bpy.data.actions
        
        if self.keys:
            for action in a:
                if not action.library and (self.fake_user or not action.use_fake_user):
                    fcurves = action.fcurves
                    for curve in fcurves:
                        if not curve.lock:  # Check if the curve is not locked
                            kfp = curve.keyframe_points
                            for point in kfp:
                                if not self.before_current and point.co.x > fr:
                                    point.co_ui.x += frames
                                elif self.before_current and point.co.x < fr:
                                    point.co_ui.x += frames
        
        if self.markers:
            m = scene.timeline_markers
            for marker in m:
                if self.before_current == False:
                    if marker.frame > fr:
                        marker.frame += frames
                else:
                    if marker.frame < fr:
                        marker.frame += frames
        
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_popup(self, event)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'frame_shift')
        layout.prop(self, 'before_current')
        layout.separator(factor=0.5)
        row = layout.row(heading="Target")
        row.prop(self, 'keys')
        row.prop(self, 'markers')
        row = layout.row()
        if not self.keys:
            row.enabled = False
        row.prop(self, 'fake_user')
        layout.separator(factor=0.5)
        layout.label(icon='INFO', text="Target is regardless of selection or visibility")
    

# ------------------------------------------------------------------------
#    OPERATOR - add light parent for Sun, Rimlight and FloorNormal
# ------------------------------------------------------------------------

class OBJECT_OT_light_parent(Operator):
    """Add empty as parent for Sun, RimLight and FloorNormal"""
    bl_idname = "object.light_parent"
    bl_label = "Add Light Parent"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        objs = context.scene.objects
        return context.mode == 'OBJECT' and 'LightParent' not in objs
    
    def execute(self, context):
        objs = bpy.data.objects

        # create empty
        light_parent = objs.new('LightParent', None)
        light_parent.empty_display_type = 'SPHERE'
        light_parent.empty_display_size = 3
        
        # add empty to collection 'Set'
        colls = bpy.data.collections
        set = colls.get('Set')
        if set:
            coll = set
        else:
            coll = context.scene.collection
        
        coll.objects.link(light_parent)

        sun = objs.get('Sun')
        rim = objs.get('RimLight')
        normal = objs.get('FloorNormal')

        for item in [sun, rim, normal]:
            if item:
                item.parent = light_parent
        
        self.report({'INFO'}, f"'LightParent' added to collection {coll.name}")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - rotate LightParent or HDRI according to Active Camera
# ------------------------------------------------------------------------

class OBJECT_OT_rotate_lighting(Operator):
    """Match Z-rotation of lighting to active camera.
If target is HDRI, rotation is applied to secondary rotation"""
    bl_idname = "object.rotate_lighting"
    bl_label = "Rotate Lighting"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    
    @classmethod
    def poll(cls, context):
        objs = context.scene.objects
        return context.mode == 'OBJECT'
    
    hdri: BoolProperty(
        name="Include HDRI",
        description="Rotate HDRI",
        options={'SKIP_SAVE', 'HIDDEN'}
    )
    
    parent: BoolProperty(
        name="Include LightParent",
        description="Rotate LightParent",
        options={'SKIP_SAVE', 'HIDDEN'}
    )
    
    def execute(self, context):
        scene = context.scene
        fr = scene.frame_current

        # active camera Z rotation
        cam_rot = scene.camera.rotation_euler[2]

        if self.parent:
            # get LightParent and apply Z rotation
            parent = scene.objects.get('LightParent')
            if parent:
                parent.rotation_euler[2] = cam_rot

        if self.hdri:
            # find HDRI and apply Z rotation
            if scene.world.name == 'Fuzzy World':
                nodes = scene.world.node_tree.nodes
                HDRI = nodes.get("HDRI Delta Rot")
                if HDRI:
                    HDRI.inputs[2].default_value[2] = cam_rot * -1 + radians(90)
        
        if self.parent:
            target = "LightParent"
        elif self.hdri:
            target = "HDRI"
        self.report({'INFO'}, f"{target} rotated on Z-axis")
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    PANELS - Scene Builder
# ------------------------------------------------------------------------

class BuildScenePanel(Panel):
    bl_label = "Scene Builder"
    bl_idname = "VIEW3D_PT_build_scene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Fuzzy'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 0
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        pass


class BuildSceneChild:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "VIEW3D_PT_build_scene"


class BuildAllPanel(BuildSceneChild, Panel):
    bl_label = "Build All"
    bl_idname = "VIEW3D_PT_build_all"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.scale_y = 2
        row.operator("scene.build_all", text='POP!', icon='SHADERFX')


class BuildPartsPanel(BuildSceneChild, Panel):
    bl_label = "Build in Parts"
    bl_idname = "VIEW3D_PT_build_parts"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("object.fuzzy_camera", text='Camera', icon='CAMERA_DATA')
        row.operator("mesh.fuzzy_floor", text="Floor", icon='GRID')

        col = layout.column(align=True)
        col.scale_y = 1.2
        row = col.row(align=True)
        row.operator("world.fuzzy_sky", text="Sky", icon='MAT_SPHERE_SKY')
        row.operator("object.fuzzy_sun", text="Sun", icon='LIGHT_SUN')
        col.operator("object.fuzzy_rimlight", text="Rim Light", icon='LIGHT')
        col.operator("scene.fuzzy_eevee", text="Optimize EEVEE", icon='CAMERA_STEREO')


class BackgroundPanel(BuildSceneChild, Panel):
    bl_label = "Background"
    bl_idname = "VIEW3D_PT_background"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene.world
        if scene is not None:
            return scene.name == "Fuzzy World"

    def draw(self, context):
        scene = context.scene
        fuzzyprops = scene.fuzzy_props
        group_node = scene.world.node_tree.nodes
        node = group_node['BG Group'].node_tree.nodes

        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        row = col.row(align=True)
        row.prop(fuzzyprops, "fuzzy_color1", text='Palette')
        row.prop(fuzzyprops, "fuzzy_color2", text='')
        row.separator()
        row.label(icon='BLANK1')
        row = col.row(align=True)
        swap = node.get('Color Swap')
        if swap:
            row.prop(node['BG Color 1' if swap.clamp_factor else 'BG Color 2'].outputs[0], 'default_value', text='Sky Colors')
            row.prop(node['BG Color 2' if swap.clamp_factor else 'BG Color 1'].outputs[0], 'default_value', text='')
            row.separator()
            row.prop(swap, 'clamp_factor', icon='FILE_REFRESH', icon_only=True, emboss=False)
        
        flat_grad = node.get('Flat Gradient')
        rad_lin = node.get('Radial Linear')
        win_glob = node.get('Window Global')
        if flat_grad and rad_lin and win_glob:
            col = layout.column(align=True)
            col.prop(flat_grad, 'clamp_factor', text='Gradient')
            
            col = col.column(align=True)
            col.enabled = flat_grad.clamp_factor
            row = col.row(align=True)
            row.prop(rad_lin, 'clamp_factor', text='Radial', toggle=1, invert_checkbox=True)
            row.prop(rad_lin, 'clamp_factor', text='Linear', toggle=1)
            row = row.row(align=True)
            row.enabled = rad_lin.clamp_factor
            row.prop(win_glob, 'clamp_factor', text='', icon='WORLD')

            col = col.column(align=True)
            if rad_lin.clamp_factor and win_glob.clamp_factor:
                scale_grad = node.get('Scale Gradient')
                if scale_grad:
                    col.separator(factor=0.5)
                    col.prop(scale_grad.inputs[0], "default_value", text='Scale from Horizon')
            elif not rad_lin.clamp_factor:
                col.separator(factor=0.5)
                col.use_property_split = True
                col.use_property_decorate = False
                
                rad_loc = node.get('Radial Location')
                if rad_loc:
                    row = col.row(align=True)
                    row.prop(rad_loc.inputs[0], "default_value", text="Loc XY", index=0)
                    row.prop(rad_loc.inputs[0], "default_value", text="", index=1)
                
                rad_scale = node.get('Radial Scale')
                if rad_scale:
                    row = col.row(align=True)
                    row.prop(rad_scale.inputs[0], "default_value", text="Scale XY", index=0)
                    row.prop(rad_scale.inputs[0], "default_value", text="", index=1)
        
        layout.prop(scene.render, "film_transparent")
        

class HDRIPanel(BuildSceneChild, Panel):
    bl_label = "Lighting"
    bl_idname = "VIEW3D_PT_hdri"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene.world
        if scene is not None:
            return scene.name == "Fuzzy World"

    def draw(self, context):
        scene = context.scene
        objs = scene.objects
        nodes = scene.world.node_tree.nodes

        layout = self.layout
        col = layout.column()
        col.label(text="Light Parent", icon='LIGHT')
        row = col.row(align=True)
        row.scale_y = 1.2
        parent = objs.get('LightParent')
        if not parent:
            row.operator('object.light_parent', text="Create", icon='SPHERE')
        else:
            row.operator('object.rotate_lighting', text="Rotate", icon='CON_ROTLIMIT').parent = True
            row.separator(factor=0.5)
            row.prop(parent, 'hide_viewport', text='', emboss=False)
        
        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        col.label(text="HDRI", icon='IMAGE_DATA')
        HDRI_node = nodes.get("World HDRI")
        if HDRI_node:
            col.template_ID(HDRI_node, 'image', open='image.open', live_icon=True)
            col.separator()

        hdri_rot = nodes.get("HDRI Rotation")
        hdri_delta_rot = nodes.get("HDRI Delta Rot")
        hdri_str = nodes.get("HDRI Strength")
        if hdri_rot:
            row = col.row(align=True)
            row.prop(hdri_rot.inputs[2], 'default_value', index=2, text='Rotation')
            if hdri_delta_rot:
                row.operator('object.rotate_lighting', text="", icon='CON_ROTLIMIT').hdri = True
        if hdri_str:
            col.prop(hdri_str.inputs[1], 'default_value', index=-1, text='Strength')

        clamp_node = nodes.get("Clamp Reflection")
        if clamp_node:
            col.separator()
            if context.engine == 'BLENDER_EEVEE_NEXT':
                text = "Clamp"
            else:
                text = "Clamp Glossy"
            col.prop(clamp_node.outputs[0], 'default_value', text=text)
                

class FloorPanel(BuildSceneChild, Panel):
    bl_label = "Fuzzy Floor"
    bl_idname = "VIEW3D_PT_floor"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        objects = scene.objects
        engines = ['BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT']
        return 'FuzzyFloor' in objects and context.engine in engines

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        floor = bpy.data.objects.get('FuzzyFloor')
        if floor:
            mod = floor.modifiers.get('NormalDirection')
            mat = bpy.data.materials.get('floor_shadow')
            if mat and mat.node_tree:
                nodes = mat.node_tree.nodes
                val = 'default_value'

                # Check Blender version 4.2 or above
                if is_next_version():
                    col = layout.column(align=True)
                    ao_node = nodes.get('AO')
                    ao_factor_node = nodes.get('AO Factor')
                    if ao_node:
                        col.prop(ao_node.inputs[1], val, text="AO Distance")
                    if ao_factor_node:
                        col.prop(ao_factor_node.inputs[0], val, text="AO Factor")
                    col.prop(mat, 'surface_render_method', text="Method")
                    if mat.surface_render_method == 'DITHERED':
                        col.prop(mat, 'use_raytrace_refraction')

                clamp_node = nodes.get('Clamp Value')
                dodge_node = nodes.get('Dodge Value')
                shadow_node = nodes.get('Shadow Value')
                col = layout.column(align=True)

                if clamp_node:
                    col.prop(clamp_node.inputs[0], val, text="Clamp Dark")
                if dodge_node:
                    col.prop(dodge_node.inputs[0], val, text="Dodge Bright")
                if shadow_node:
                    layout.prop(shadow_node.inputs[0], val, text="Value Fix")

                fuzzy_bg = bpy.data.node_groups.get('Fuzzy BG')
                if fuzzy_bg:
                    col = layout.column(heading="Floor")
                    floor_alpha_node = nodes.get('Floor Alpha')
                    if floor_alpha_node:
                        col.prop(floor_alpha_node, 'mute', text="Holdout")

            if mod:
                split = layout.split(factor=0.4)
                split.alignment = 'RIGHT'
                split.label(text='Normal Edit')
                row = split.row(align=True)
                row.scale_x = 1.3
                row.prop(mod, 'show_viewport', text="")
                row.prop(mod, 'show_render', text="")


# ------------------------------------------------------------------------
#    PANELS - Fuzzy View
# ------------------------------------------------------------------------

class VIEW3D_PT_viewport(Panel):
    bl_label = "Fuzzy View"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Fuzzy'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 2

    def draw_header_preset(self, context):
        layout = self.layout
        layout.scale_x = 0.92
        layout.prop(context.space_data, "lens", text="")

    def draw(self, context):
        pass


class ViewportChild:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'VIEW3D_PT_viewport'

 
class VIEW3D_PT_simplify(ViewportChild, Panel):
    bl_label = "Simplify"

    def draw_header(self, context):
        rd = context.scene.render
        self.layout.prop(rd, "use_simplify", text="")

    def draw(self, context):
        layout = self.layout
        rd = context.scene.render
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.active = rd.use_simplify

        flow = layout.grid_flow()

        col = flow.column()
        col.prop(rd, "simplify_subdivision", text="Subdivision")

        col = flow.column()
        col.prop(rd, "simplify_child_particles", text="Hair")

        
class VIEW3D_PT_hair(ViewportChild, Panel):
    bl_label = "Hair"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rd = scene.render
        
        row = layout.row(align=True)
        row.use_property_split = True
        row.use_property_decorate = False
        row.prop(rd, "hair_type", text = "Type", expand=True)

        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="Visibility")
        row = col.row(align=True)
        row.operator("object.hair_viewport", text="Show All", icon='HIDE_OFF').hide = False
        row.operator("object.hair_viewport", text="Hide All", icon='HIDE_ON').hide = True
        

class VIEW3D_PT_miscellaneous(ViewportChild, Panel):
    bl_label = "Viewport Display"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        space = context.space_data
        overlay = space.overlay
        shade = space.shading
        object = context.object
        
        layout = self.layout
        split = layout.split(factor=0.25)
        split.alignment = 'RIGHT'
        split.label(text='Local')
        col = split.column(align=True)
        col.prop(overlay, "show_relationship_lines")
        col.prop(shade, "show_backface_culling")
        if object is not None:
            split = layout.split(factor=0.25)
            split.alignment = 'RIGHT'
            split.label(text='Object')
            split.prop(object, "show_in_front", text="Show in Front")


# ------------------------------------------------------------------------
#    PANELS - Camera Control
# ------------------------------------------------------------------------

class VIEW3D_PT_cameras(Panel):
    bl_label = " Camera Control"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Fuzzy'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3

    def draw_header_preset(self, context):
        layout = self.layout
        if context.space_data.lock_camera:
            icon = 'LOCKED'
        else:
            icon = 'UNLOCKED'
        row = layout.row(align=True)
        if context.space_data.lock_camera == True:
            row.alert = True
        row.prop(context.space_data, 'lock_camera', text='', icon=icon, emboss=False)
        
        colls = bpy.data.collections
        cam_coll = colls.get('Cameras')
        if cam_coll:
            row.separator(factor=0.5)
            row.alert = False
            row.prop(cam_coll, 'hide_viewport', text="", icon='RESTRICT_VIEW_OFF', emboss=False)
            
    def draw(self, context):
        pass


class VIEW3D_PT_camera_scene(Panel):
    bl_label = "Scene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'VIEW3D_PT_cameras'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header_preset(self, context):
        layout = self.layout
        scene = context.scene
        active_obj = context.view_layer.objects.active
           
        if scene.camera and active_obj != scene.camera and context.mode == 'OBJECT':
            if scene.camera.name not in context.view_layer.objects:
                layout.enabled = False
            layout.operator("object.select_camera", text="", 
                                icon='RESTRICT_SELECT_OFF', emboss=False)
        
    def draw(self, context):
        scene = context.scene
        layout = self.layout

        if context.mode == 'OBJECT':
            col = layout.column()
            col.scale_y = 1.2
            col.operator("object.fuzzy_camera", text="Build", icon='CAMERA_DATA')

        # subpanel for blender 4.1 or higher, else box
        bl_version = bpy.app.version
        if bl_version >= (4, 1, 0):
            header, panel = layout.panel("VIEW3D_PT_camera_scene", default_closed=True)
            row = header.row(align=True)
            sub = panel
        else:
            box = layout.box()
            col = box.column(align=True)
            col.label(text='Active:')
            row = col.row(align=True)
            sub = box

        row.prop(scene, "camera", text="", icon='CAMERA_DATA')
        row.operator('view3d.view_camera', text='', icon='VIEWZOOM')
        row.operator('view3d.camera_to_view', text='', icon='DECORATE_OVERRIDE')

        if sub and scene.camera is not None:
            container = panel if bl_version >= (4, 1, 0) else box
            col = container.column(align=True)
            # camera properties
            cam = scene.camera.data
            row = col.row(align=True)
            row.prop(cam, 'lens')
            row = col.row(align=True)
            row.prop(cam, 'clip_start', text="Start")
            row.prop(cam, 'clip_end', text="End")
            col.separator()
            row = col.row(align=True)
            row.prop(cam, 'passepartout_alpha', text="Passepartout")
            row.operator('object.copy_passepartout', text='', icon='DUPLICATE')

        # Motion Blur - check render engine
        if context.engine == 'BLENDER_EEVEE_NEXT' or context.engine == 'CYCLES':
            version = scene.render
        elif context.engine == 'BLENDER_EEVEE':
            version = scene.eevee
        col = layout.column(align=True, heading="Motion Blur")
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(version, 'use_motion_blur', text="")
        col.prop(version, 'motion_blur_shutter')

        # Motion Blur Markers
        col.separator(factor=0.5)
        split = col.split(factor=0.4)
        split.scale_y = 1.2
        row = split.row()
        row.scale_x = 1.1
        row.alignment = 'RIGHT'
        row.label(text="Marker")
        # check for 'mblur' marker
        markers = scene.timeline_markers
        if markers is not None:
            for m in markers:
                if m.name.startswith('mblur'):
                    fuzzyprops = scene.fuzzy_props
                    row.prop(fuzzyprops, 'scene_animate', text="", icon='ACTION')
                    break
        row = split.row(align=True)
        row.operator('marker.add_motionblur_marker', text="On", icon='KEYFRAME_HLT').blur = 'on'
        row.operator('marker.add_motionblur_marker', text="Off", icon='KEYFRAME').blur = 'off'
        row.operator('marker.shutter_to_markers', text='', icon='MARKER_HLT')
        
        
class VIEW3D_PT_camera_selected(Panel):
    bl_label = ""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'VIEW3D_PT_cameras'
    bl_context = 'objectmode'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        return context.view_layer.objects.active is not None and context.object.type == 'CAMERA'

    def draw_header(self, context):
        active_obj = context.view_layer.objects.active
        if active_obj and active_obj != context.scene.camera:
            self.layout.operator('view3d.set_active_camera', text=active_obj.name, icon="CAMERA_DATA")
        else:
            self.layout.prop(active_obj, "name", text='', emboss=False, icon="VIEW_CAMERA")
    
    def draw(self, context):
        layout = self.layout
        object = context.object   
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator('marker.camera_bind_new', text="Bind to Marker", icon='KEYFRAME_HLT')
        row.separator(factor=0.5)
        row.scale_x = 1.2
        row.operator('object.rename_camera_alphabet', text='', icon='SORTALPHA') 
        
        layout.prop(object.data, "lens")
        
        col = layout.column(heading="Show", align=True)        
        col.prop(object, "show_name", text="Name")
        col.prop(object.data, "show_limits", text="Limits")
        
        col = layout.column(align=True)
        col.prop(object.data, "clip_start", text="Clip Start")
        col.prop(object.data, "clip_end", text="End")
        
        col = layout.column(heading="DoF")
        col.prop(object.data.dof, "use_dof", text="")
        if object.data.dof.use_dof:
            col.prop(object.data.dof, "focus_object", text="Object")
            row = col.row()
            if object.data.dof.focus_object is not None:
                row.enabled = False
            row.prop(object.data.dof, "focus_distance", text="Distance")
            row.operator('ui.eyedropper_depth', icon='EYEDROPPER', text="")
            col.prop(object.data.dof, "aperture_fstop")
                  
               
# ------------------------------------------------------------------------
#    REGISTRATION
# ------------------------------------------------------------------------

addon_keymaps = []

classes = [
    # properties
    FuzzyProperties,
    
    # operators
    SCENE_OT_build_all,
    OBJECT_OT_fuzzy_camera,
    MESH_OT_fuzzy_floor,
    WORLD_OT_fuzzy_sky,
    OBJECT_OT_fuzzy_sun,
    OBJECT_OT_fuzzy_rimlight,
    SCENE_OT_fuzzy_eevee,

    OBJECT_OT_hair_viewport,

    OBJECT_OT_copy_passepartout,    
    MARKER_OT_add_motionblur_marker,
    MARKER_OT_shutter_to_markers,
    
    VIEW3D_OT_set_active_camera,    
    MARKER_OT_camera_bind_new,
    OBJECT_OT_rename_camera_alphabet,
    
    TRANSFORM_OT_keyframes_markers,

    OBJECT_OT_light_parent,
    OBJECT_OT_rotate_lighting,

    # panels
    BuildScenePanel,
    BuildAllPanel,
    BuildPartsPanel,
    BackgroundPanel,
    FloorPanel,
    HDRIPanel,

    VIEW3D_PT_viewport,
    VIEW3D_PT_simplify,
    VIEW3D_PT_hair,
    VIEW3D_PT_miscellaneous,
    
    VIEW3D_PT_cameras,
    VIEW3D_PT_camera_scene,
    VIEW3D_PT_camera_selected,    
    
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fuzzy_props = PointerProperty(type=FuzzyProperties)
        
    bpy.app.handlers.load_post.append(reload_image)
    bpy.app.handlers.load_post.append(auto_animate_scene)
    bpy.app.handlers.load_post.append(disable_animate_scene)
    bpy.app.handlers.load_post.append(name_fix)
    
   # Add hotkey Alt+M for 'Move Keyframes and Markers'
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = wm.keyconfigs.addon.keymaps.new(name='Window', space_type='EMPTY', region_type='WINDOW')
        kmi = km.keymap_items.new(TRANSFORM_OT_keyframes_markers.bl_idname, 
            type='M', value='PRESS', alt=True)
        addon_keymaps.append((km, kmi))


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.fuzzy_props

    bpy.app.handlers.load_post.remove(reload_image)
    bpy.app.handlers.load_post.remove(auto_animate_scene)
    bpy.app.handlers.load_post.remove(disable_animate_scene)
    bpy.app.handlers.load_post.remove(name_fix)

    # Remove hotkey Alt+M
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
