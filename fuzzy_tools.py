# SPDX-License-Identifier: GPL-2.0-or-later

bl_info = {
    "name" : "Fuzzy Tools",
    "author" : "Sacha Goedegebure",
    "version" : (1,2),
    "blender" : (3,6,0),
    "location" : "View3d > Sidebar > Fuzzy. Alt+M to move keyframes and markers",
    "description" : "Tools for an efficient 1-person pipeline and multi-camera workflow",
    "doc_url" : "https://github.com/sagotoons/fuzzytools/wiki",
    "tracker_url" : "https://github.com/sagotoons/fuzzytools/issues",
    "category" : "User Interface",
}


import bpy

import math

from bpy.props import (BoolProperty,
                       FloatProperty,
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


# find 'sunset.exr' when used in World shader nodes during start up
@persistent
def reload_image(dummy):
    if bpy.context.scene.world.name != 'Fuzzy World':
        return
    node = bpy.data.worlds['Fuzzy World'].node_tree.nodes['Environment Texture']   
    if not node.image.name.startswith("sunset"):
        return    
    if node.image.file_format == 'OPEN_EXR':
        return
    node.image.name = "sunset_old"
    hdri = bpy.data.images.load(
        bpy.context.preferences.studio_lights['sunset.exr'].path, check_existing=True)
    node.image = hdri


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


# LIST CHARACTERS 
## can ignore when not working with 'Project Fuzzy' characters
## to avoid Error, do not remove list. Optional to replace or remove content of list
character_list = {
    'B': 'COLORSET_04_VEC',
    'Bo': 'COLORSET_03_VEC',
    'Bob': 'COLORSET_11_VEC',
    'Bobi': 'COLORSET_05_VEC'
}

 
# ------------------------------------------------------------------------
#    SCENE PROPERTIES
# ------------------------------------------------------------------------

def update_fuzzy(self, context):
    scene = context.scene
    
    try:
        HDR_node = scene.world.node_tree.nodes
        
    except AttributeError:
        pass
        
    try:
        node = bpy.data.node_groups['Fuzzy BG'].nodes
        node["BG Color 1"].outputs[0].default_value[0:3] = self.bgcolor1
        node["BG Color 2"].outputs[0].default_value[0:3] = self.bgcolor2

        node["Swap Colors 1"].mute = self.bgcolor_swap
        node["Swap Colors 2"].mute = self.bgcolor_swap

        node["Flat to Gradient"].mute = not self.gradient

        if self.gradient_type == 'OP1':
            node["Radial to Linear"].mute = True
        else:
            node["Radial to Linear"].mute = False

        node["Window to 3D"].mute = not self.linear_coord
        node["Linear Ease"].mute = not self.linear_coord

        node["Scale Gradient"].outputs[0].default_value = self.gradient_scale
        
    except KeyError:
        pass


def check(self):
    # update custom scene properties
    prop = self.fuzzy_props    
    prop.gradient = prop.gradient
   
    # check motion blur markers
    scene = bpy.context.scene
    frame = scene.frame_current
    markers = scene.timeline_markers
   
    if any(marker.name.startswith('mblur') for marker in markers):
        mblur = False
        # check mblur markers in reversed order
        for k, v in reversed(sorted(markers.items(), key=lambda it: it[1].frame)):
            if v.frame <= frame and v.name.startswith('mblur_on'):
                scene.eevee.use_motion_blur = True
                val = v.name.strip('mblur_on')
                try:
                    scene.eevee.motion_blur_shutter = float(val)
                except ValueError:
                    pass
                mblur = True
                break
            elif v.frame <= frame and v.name == 'mblur_off':
                scene.eevee.use_motion_blur = False
                mblur = True
                break
        # check for first mblur marker
        if not mblur:
            for k, v in sorted(markers.items(), key=lambda it: it[1].frame):
                if v.frame >= frame and v.name.startswith('mblur_on'):
                    scene.eevee.use_motion_blur = True
                    val = v.name.strip('mblur_on')
                    try:
                        scene.eevee.motion_blur_shutter = float(val)
                    except ValueError:
                        pass
                    break
                elif v.frame >= frame and v.name == 'mblur_off':
                    scene.eevee.use_motion_blur = False
                    break


def check_scene(self, context):
    if self.scene_animate:
        bpy.app.handlers.frame_change_post.append(check)
    else:
        bpy.app.handlers.frame_change_post.remove(check)
     

class FuzzyProperties(PropertyGroup):

    scene_animate: BoolProperty(
        name='Scene Animation',
        description="""Update animated Background and motion blur properties in viewport.
Enables automatically during rendering""",
        default=False,
        update=check_scene
    )

    bgcolor1: FloatVectorProperty(
        name="Background color 1",
        subtype='COLOR',
        default=(0.09, 0.17, 1.0),
        min=0.0, max=1.0,
        update=update_fuzzy
    )

    bgcolor2: FloatVectorProperty(
        name="Background color 2",
        subtype='COLOR',
        default=(0.02, 0.05, 0.40),
        min=0.0, max=1.0,
        update=update_fuzzy
    )

    bgcolor_swap: BoolProperty(
        name="Swap background colors",
        default=False,
        update=update_fuzzy
    )

    gradient: BoolProperty(
        name="Gradient",
        description="Enable gradient background",
        default=True,
        update=update_fuzzy
    )

    gradient_type: EnumProperty(
        name="Gradient Type",
        description="Type of Gradient background",
        items=[('OP1', "Radial", ""),
               ('OP2', "Linear", ""),
               ],
        update=update_fuzzy
    )

    linear_coord: BoolProperty(
        name="",
        description="Use global world coordinates for Linear Gradient",
        default=False,
        update=update_fuzzy
    )

    gradient_scale: FloatProperty(
        name="Gradient Scale",
        description="Scale gradient from horizon",
        default=0.5,
        min=0.001,
        max=1,
        update=update_fuzzy
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

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Fuzzy floor (shadow only)
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
        for name in ["Cube", "Fuzzy floor", "floor normal"]:
            if name in objects:
                bpy.data.objects.remove(bpy.data.objects[name])

        # add floor
        bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))

        # name new Plane 'Fuzzy floor'
        floor = context.active_object
        floor.name = "Fuzzy floor"

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

        # create empty as Target for floor Normal Edit modifier
        bpy.ops.object.empty_add(location=(15, -20, 20))
        empty = context.object
        empty.name = "floor normal"
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
        normal = floor.modifiers.new("Normal Direction", 'NORMAL_EDIT')
        normal.mode = 'DIRECTIONAL'
        normal.use_direction_parallel = True
        normal.target = bpy.data.objects["floor normal"]
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
        matoutput.location = (400, 80)
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

        RGB_BW = nodes.new("ShaderNodeRGBToBW")
        RGB_BW.location = (-570, 0)

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
        link(RGB_BW.outputs[0], dodge_floor.inputs[1])
        link(value.outputs[0], power.inputs[1])
        link(power.outputs[0], mixshader.inputs[0])
        link(shader_RGB.outputs[0], RGB_BW.inputs[0])
        link(diffuse.outputs[0], shader_RGB.inputs[0])
        link(dodge_floor.outputs[0], clamp_shadow.inputs[0])
        link(value_dodge.outputs[0], dodge_floor.inputs[2])
        link(value_clamp.outputs[0], clamp_shadow.inputs[1])
        if BG in groups:
            link(BG_group.outputs[0], alpha_mix.inputs[2])
        
        # material settings
        mat.use_backface_culling = True
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'NONE'

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

        # viewport settings
        space = context.space_data
        space.shading.show_backface_culling = True
        space.overlay.show_relationship_lines = False

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
            bpy.data.worlds['Fuzzy World'].name = 'Old World'
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
        worldoutput.location = (400, 50)

        mixshader = nodes.new("ShaderNodeMixShader")
        mixshader.location = (200, 60)

        BG1 = nodes.new("ShaderNodeBackground")
        BG1.location = (0, 20)
        BG1.inputs[1].default_value = (1.0)
        BG1.name = 'HDRI Strength'
        BG1.label = 'HDRI Strength'

        BG2 = nodes.new("ShaderNodeBackground")
        BG2.location = (0, -100)

        skyclamp = nodes.new("ShaderNodeMixRGB")
        skyclamp.location = (-180, 200)
        skyclamp.blend_type = 'DARKEN'
        skyclamp.inputs[2].default_value = (10,10,10, 1)
        
        lightpath = nodes.new("ShaderNodeLightPath")
        lightpath.location = (-400, 100)
        lightpath.hide = True

        skytex = nodes.new("ShaderNodeTexEnvironment")
        skytex.location = (-450, 400)

        mapskytex = nodes.new("ShaderNodeMapping")
        mapskytex.location = (-680, 440)
        mapskytex.name = "HDRI Rotation"
        mapskytex.label = "HDRI Rotation"

        mapskytex2 = nodes.new("ShaderNodeMapping")
        mapskytex2.location = (-880, 440)
        mapskytex2.inputs[2].default_value[2] = radians(90)

        texcoord1 = nodes.new("ShaderNodeTexCoord")
        texcoord1.location = (-1080, 440)        

        # connect nodes
        link = scene.world.node_tree.links.new
        link(mixshader.outputs[0], worldoutput.inputs[0])
        link(BG1.outputs[0], mixshader.inputs[1])
        link(BG2.outputs[0], mixshader.inputs[2])
        link(lightpath.outputs[0], mixshader.inputs[0])
        link(lightpath.outputs[5], skyclamp.inputs[0])
        link(skytex.outputs[0], skyclamp.inputs[1])
        link(skyclamp.outputs[0], BG1.inputs[0])
        link(mapskytex.outputs[0], skytex.inputs[0])
        link(mapskytex2.outputs[0], mapskytex.inputs[0])
        link(texcoord1.outputs[0], mapskytex2.inputs[0])

        # load the texture from Blender data folder
        hdri = bpy.data.images.load(
            context.preferences.studio_lights['sunset.exr'].path, check_existing=True)
        skytex.image = hdri

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
        group.location = (-300, -200)
        group.node_tree = BG_group
        
        # BG group nodes
        nodes = BG_group.nodes
        
        flat_gradient = nodes.new("ShaderNodeMixRGB")
        flat_gradient.location = (-180, -120)
        flat_gradient.name = "Flat to Gradient"
        flat_gradient.label = "Flat to Gradient"

        sky1 = nodes.new("ShaderNodeRGB")
        sky1.location = (-680, -440)
        sky1.name = "BG Color 1"
        sky1.label = "BG Color 1"
        sky1.outputs[0].default_value = (0.09, 0.17, 1, 1)

        sky2 = nodes.new("ShaderNodeRGB")
        sky2.location = (-680, -640)
        sky2.name = "BG Color 2"
        sky2.label = "BG Color 2"
        sky2.outputs[0].default_value = (0.02, 0.05, 0.40, 1)

        radial_linear = nodes.new("ShaderNodeMixRGB")
        radial_linear.location = (-400, -60)
        radial_linear.label = "Radial to Linear"
        radial_linear.name = "Radial to Linear"
        radial_linear.inputs[0].default_value = 1
        radial_linear.mute = True

        ramp_radial = nodes.new("ShaderNodeValToRGB")
        ramp_radial.location = (-700, 20)
        ramp_radial.color_ramp.interpolation = "EASE"

        ramp_linear = nodes.new("ShaderNodeValToRGB")
        ramp_linear.location = (-700, -200)
        ramp_linear.label = "Linear Ease"
        ramp_linear.name = "Linear Ease"
        ramp_linear.color_ramp.interpolation = "EASE"
        ramp_linear.mute = True

        swapsky1 = nodes.new("ShaderNodeMixRGB")
        swapsky1.location = (-450, -440)
        swapsky1.label = "Swap Colors 1"
        swapsky1.name = "Swap Colors 1"
        swapsky1.inputs[0].default_value = 1

        swapsky2 = nodes.new("ShaderNodeMixRGB")
        swapsky2.location = (-450, -640)
        swapsky2.label = "Swap Colors 2"
        swapsky2.name = "Swap Colors 2"
        swapsky2.inputs[0].default_value = 1

        gradsphere = nodes.new("ShaderNodeTexGradient")
        gradsphere.location = (-1050, -80)
        gradsphere.gradient_type = 'SPHERICAL'

        gradlinear = nodes.new("ShaderNodeTexGradient")
        gradlinear.location = (-880, -240)

        invert = nodes.new("ShaderNodeInvert")
        invert.location = (-880, -80)

        mapsphere = nodes.new("ShaderNodeMapping")
        mapsphere.location = (-1250, -170)
        mapsphere.vector_type = 'TEXTURE'
        mapsphere.inputs[1].default_value[0] = 0.5
        mapsphere.inputs[1].default_value[1] = 0.5
        mapsphere.inputs[3].default_value[0] = 0.71
        mapsphere.inputs[3].default_value[1] = 0.71
        mapsphere.hide = True

        maplinear = nodes.new("ShaderNodeMapping")
        maplinear.location = (-1250, -350)
        maplinear.vector_type = 'TEXTURE'
        maplinear.inputs[2].default_value[2] = 1.5708
        maplinear.hide = True

        maplinear3d = nodes.new("ShaderNodeMapping")
        maplinear3d.location = (-1250, -400)
        maplinear3d.vector_type = 'TEXTURE'
        maplinear3d.inputs[2].default_value[1] = -1.5708
        maplinear3d.inputs[1].default_value[2] = -0.5
        maplinear3d.hide = True

        window_3d = nodes.new("ShaderNodeMixRGB")
        window_3d.location = (-1050, -240)
        window_3d.label = "Window to 3D"
        window_3d.name = "Window to 3D"
        window_3d.inputs[0].default_value = 1
        window_3d.mute = True

        divide = nodes.new("ShaderNodeMixRGB")
        divide.location = (-1450, -350)
        divide.blend_type = 'DIVIDE'
        divide.inputs[0].default_value = 1

        grad_scale = nodes.new("ShaderNodeValue")
        grad_scale.location = (-1860, -500)
        grad_scale.label = "Scale Gradient"
        grad_scale.name = "Scale Gradient"

        power = nodes.new("ShaderNodeMath")
        power.location = (-1650, -480)
        power.operation = 'POWER'
        power.inputs[1].default_value = 2

        texcoord2 = nodes.new("ShaderNodeTexCoord")
        texcoord2.location = (-1860, -100)

        vec_trans = nodes.new("ShaderNodeVectorTransform")
        vec_trans.location = (-1650, -300)
        vec_trans.vector_type = 'NORMAL'
        vec_trans.convert_from = 'CAMERA'

        output = nodes.new("NodeGroupOutput")
        output.location = (60, -100)

        # connect nodes
        link(group.outputs[0], BG2.inputs[0])
        # connect group nodes
        link = BG_group.links.new
        link(flat_gradient.outputs[0], output.inputs[0])
        link(swapsky1.outputs[0], flat_gradient.inputs[1])
        link(swapsky2.outputs[0], flat_gradient.inputs[2])
        link(sky1.outputs[0], swapsky1.inputs[2])
        link(sky1.outputs[0], swapsky2.inputs[1])
        link(sky2.outputs[0], swapsky1.inputs[1])
        link(sky2.outputs[0], swapsky2.inputs[2])
        link(radial_linear.outputs[0], flat_gradient.inputs[0])
        link(gradsphere.outputs[0], invert.inputs[1])
        link(gradlinear.outputs[0], ramp_linear.inputs[0])
        link(ramp_radial.outputs[0], radial_linear.inputs[1])
        link(ramp_linear.outputs[0], radial_linear.inputs[2])
        link(invert.outputs[0], ramp_radial.inputs[0])
        link(mapsphere.outputs[0], gradsphere.inputs[0])
        link(maplinear.outputs[0], window_3d.inputs[1])
        link(texcoord2.outputs[5], mapsphere.inputs[0])
        link(texcoord2.outputs[5], maplinear.inputs[0])
        link(window_3d.outputs[0], gradlinear.inputs[0])
        link(maplinear3d.outputs[0], window_3d.inputs[2])
        link(texcoord2.outputs[4], vec_trans.inputs[0])
        link(vec_trans.outputs[0], divide.inputs[1])
        link(divide.outputs[0], maplinear3d.inputs[0])
        link(grad_scale.outputs[0], power.inputs[0])
        link(power.outputs[0], divide.inputs[2])

        # check for Fuzzy Floor and set Fuzzy BG node group
        obj = bpy.data.objects
        if 'Fuzzy floor' in obj:
            tree = bpy.data.materials['floor_shadow'].node_tree
            floor_group = tree.nodes['Floor Group']
            floor_alpha = tree.nodes['Floor Alpha']
            floor_group.node_tree = BG_group
            tree.links.new(floor_group.outputs[0], floor_alpha.inputs[2])
            floor_alpha.inputs[0].default_value = 1.0
            
        # reset Fuzzy properties
        try:
            scene['fuzzy_props'].clear()
        except KeyError:
            pass

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
        ob.data.use_contact_shadow = True
        
        # make new Sun active
        objects = context.view_layer.objects
        try:
            if ob.name in objects:
                objects.active = ob
        except RuntimeError:
            pass
        
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
        ob.rotation_euler = (radians(65), 0, radians(-155))
        
        # light settings
        ob.data.energy = 5
        ob.data.specular_factor = 0.1
        # cycles specular
        ob.visible_glossy = False

        ob.data.angle = radians(10)
        ob.data.use_contact_shadow = True

        # make new Rim Light active
        objects = context.view_layer.objects
        try:
            if ob.name in objects:
                objects.active = ob
        except RuntimeError:
            pass
        
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - EEVEE optimizing
# ------------------------------------------------------------------------

class SCENE_OT_fuzzy_eevee(Operator):
    """Set the render engine to EEVEE and optimize render settings.
Enable and adjust settings for ambient occlussion, bloom and color management"""
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
        render.engine = 'BLENDER_EEVEE'
        # ambient occlusion
        eevee.use_gtao = True
        eevee.gtao_distance = 1.6
        eevee.gtao_factor = 0.7
        eevee.use_gtao_bent_normals = False
        # bloom
        eevee.use_bloom = True
        eevee.bloom_threshold = 1.0
        eevee.bloom_radius = 5
        # depth of field
        eevee.bokeh_max_size = 3
        eevee.use_bokeh_jittered = True
        # screen space reflection
        eevee.use_ssr_refraction = True
        eevee.use_ssr_halfres = False
        eevee.ssr_quality = 1
        # hair
        render.hair_type = 'STRIP'
        # shadow
        eevee.shadow_cascade_size = '4096'
        eevee.shadow_cube_size = '2048'
        eevee.use_soft_shadows = True
        # color management
        view.view_transform = 'Filmic'
        view.exposure = 1.4
        view.gamma = 0.6
        # overlay
        space.shading.use_scene_world = True
        space.overlay.show_look_dev = True
               
        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Show all Hair
# ------------------------------------------------------------------------

class OBJECT_OT_hair_show(Operator):
    """Show all hair in scene"""
    bl_idname = "object.hair_show"
    bl_label = "Show Hair"

    def execute(self, context):
        # particle system modifiers
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if (modifier.type == 'PARTICLE_SYSTEM' and 
                        modifier.particle_system.particles.data.settings.type == 'HAIR'):
                    modifier.show_viewport = True
                            
        # new CURVES hair 
        objs_curves = [obj for obj in bpy.data.objects if obj.type == 'CURVES']
        
        for obj in objs_curves:
            obj.hide_viewport = False

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Hide all Hair
# ------------------------------------------------------------------------

class OBJECT_OT_hair_hide(Operator):
    """Hide all hair in scene"""
    bl_idname = "object.hair_hide"
    bl_label = "Hide Hair"

    def execute(self, context):
        # particle system modifiers
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                if (modifier.type == 'PARTICLE_SYSTEM' and 
                        modifier.particle_system.particles.data.settings.type == 'HAIR'):
                    modifier.show_viewport = False
        
        # new CURVES hair 
        objs_curves = [obj for obj in bpy.data.objects if obj.type == 'CURVES']

        for obj in objs_curves:
            obj.hide_viewport = True

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
       
        for m in marker:
            if m.frame == fr and m.name.startswith("mblur"):
                marker.remove(m)
                break

        if self.blur == 'on':
            marker.new('mblur_on', frame=fr)
            scene.eevee.use_motion_blur = True
        elif self.blur == 'off':
            marker.new('mblur_off', frame=fr)
            scene.eevee.use_motion_blur = False

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

        for marker in markers:
            if marker.select and marker.name.startswith("mblur_on"):
                base_name = marker.name[:8]
                v = round(scene.eevee.motion_blur_shutter, 2)
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

class OBJECT_OT_rename_camera_alpha(Operator):
    """Rename selected cameras as alphabetic variants of active camera"""
    bl_idname = "object.rename_camera_alpha"
    bl_label = "Rename as Variant"
    bl_options = {'UNDO'}
 
    @classmethod
    def poll(cls, context):
        if len(context.selected_objects) < 2:
            return False
        cameras_selected = all(obj.type == 'CAMERA' for obj in context.selected_objects)
        return cameras_selected

    def execute(self, context):
        scene = context.scene
        objects = scene.objects
        objs = bpy.data.objects

        active_cam = context.active_object
        selected_cams = context.selected_objects

        # Use ord and chr to generate alphabet dynamically
        ABC = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

        # List all objects with "CAM." prefix
        cams = [obj for obj in objs if obj.name.startswith("CAM.")]

        if active_cam in cams:
            for cam in selected_cams:
                if cam != active_cam:
                    for letter in ABC:
                        if active_cam.name[-1:].isalpha():
                            remove_ABC = active_cam.name[:-1]
                            name_ABC = f"{remove_ABC}{letter}"
                        else:
                            name_ABC = f"{active_cam.name}{letter}"
                        
                        if name_ABC not in str(cams):
                            cam.name = name_ABC
                            break  

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - 3D Cursor to Focus Distance
# ------------------------------------------------------------------------

class OBJECT_OT_cursor_to_focus_distance(Operator):
    """Set distance to 3D Cursor as camera focus distance"""
    bl_idname = "object.cursor_to_focus_distance"
    bl_label = "3D Cursor to Focus Distance"
    bl_options = {'UNDO'}
 
    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'CAMERA'

    def execute(self, context):
        scene = context.scene
        cam = context.active_object

        # camera and 3dcursor location
        cam_loc = cam.matrix_world.to_translation()
        cursor_loc = scene.cursor.matrix.to_translation()

        # calculate distance
        length = math.dist(cursor_loc, cam_loc)

        # set new focus distance
        cam.data.dof.focus_distance = length

        return {'FINISHED'}


# ------------------------------------------------------------------------
#    OPERATOR - Move Keyframes and Markers
# ------------------------------------------------------------------------

class TRANSFORM_OT_keyframes_markers(bpy.types.Operator):
    """Move keyframes and markers from current frame"""
    bl_idname = "transform.keyframes_markers"
    bl_label = "Move Keyframes and Markers"
    bl_options = {'REGISTER', 'UNDO'}
    
    frame_shift: bpy.props.IntProperty(
        name="Frames",
        description="Amount of frames to move",
        default=0,
        options={'SKIP_SAVE'}
    )
    
    before_current: bpy.props.BoolProperty(
        name="Before Current Frame",
        description="Move before current frame instead of after",
        default=False,
        options={'SKIP_SAVE'}
    )

    fake_user: bpy.props.BoolProperty(
        name="Fake User",
        description="Include actions with Fake User",
        default=False,
        options={'SKIP_SAVE'}
    )
  
    def execute(self, context):
        scene = context.scene
        fr = scene.frame_current
        frames = self.frame_shift
        a = bpy.data.actions
        
        for action in a:
            if (self.fake_user or not action.use_fake_user):
                f = action.fcurves
                for curve in f:
                    kfp = curve.keyframe_points
                    for point in kfp:
                        if self.before_current == False:
                            if point.co.x > fr:
                                    point.co_ui.x += frames
                        else:
                            if point.co.x < fr:
                                point.co_ui.x += frames

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

    def draw_header_preset(self, context):
        scene = context.scene
        fuzzyprops = scene.fuzzy_props
        animated = False
        
        # check for animated Sky properties in Sky Panel
        if scene.animation_data is not None:
            action = scene.animation_data.action
            if action is not None:
                for fcurve in action.fcurves:
                    if 'fuzzy_props' in fcurve.data_path:
                        animated = True          
                        break
       
        if animated:
            layout = self.layout
            layout.scale_x = 1.2
            layout.prop(fuzzyprops, "scene_animate", text="", icon='ACTION')
    
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
        row = col.row(align=True)
        row.operator("object.fuzzy_rimlight", text="Rim Light", icon='LIGHT')
        row = col.row(align=True)
        row.operator("scene.fuzzy_eevee", text="Optimize EEVEE", icon='CAMERA_STEREO')


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
        node = scene.world.node_tree.nodes

        layout = self.layout
        row = layout.row(align=True)
        row.use_property_split = True
        row.use_property_decorate = False
        if fuzzyprops.bgcolor_swap:
            row.prop(fuzzyprops, "bgcolor2", text='Colors')
            row.prop(fuzzyprops, "bgcolor1", text='')
        else:
            row.prop(fuzzyprops, "bgcolor1", text='Colors')
            row.prop(fuzzyprops, "bgcolor2", text='')
        row.separator()
        row.prop(fuzzyprops, "bgcolor_swap", text='',
                 icon='FILE_REFRESH', emboss=False)

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(fuzzyprops, "gradient")

        col.separator(factor=0.2)
        row = col.row(align=True)
        r1 = row.row(align=True)
        r2 = row.row(align=True)
        r1.enabled = fuzzyprops.gradient
        r1.prop(fuzzyprops, "gradient_type", expand=True)
        r2.enabled = fuzzyprops.gradient and fuzzyprops.gradient_type != 'OP1'
        r2.prop(fuzzyprops, "linear_coord", text='', icon='WORLD')

        col = layout.column(align=True)
        col.enabled = fuzzyprops.linear_coord and fuzzyprops.gradient and fuzzyprops.gradient_type != 'OP1'
        if fuzzyprops.linear_coord == True:
            col.prop(fuzzyprops, "gradient_scale", text='Scale from Horizon')


class HDRIPanel(BuildSceneChild, Panel):
    bl_label = "HDRI"
    bl_idname = "VIEW3D_PT_hdri"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene.world
        if scene is not None:
            return scene.name == "Fuzzy World"

    def draw(self, context):
        scene = context.scene
        nodes = scene.world.node_tree.nodes

        layout = self.layout
        col = layout.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        
        properties = [
            (nodes.get("HDRI Rotation", None), 2, 2, 'Rotation'),
            (nodes.get("HDRI Strength", None), 1, -1, 'Strength')
        ]

        for node, index1, index2, label in properties:
            if node is not None:
                col.prop(node.inputs[index1], 'default_value', index=index2, text=label)
                

class FloorPanel(BuildSceneChild, Panel):
    bl_label = "Floor Shadow"
    bl_idname = "VIEW3D_PT_floor"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        objects = scene.objects
        return 'Fuzzy floor' in objects and context.engine == 'BLENDER_EEVEE'

    def draw(self, context):
        scene = context.scene

        try:
            nodes = bpy.data.materials['floor_shadow'].node_tree.nodes
            val = 'default_value'
            
            layout = self.layout
            layout.use_property_split = True
            layout.use_property_decorate = False
            
            col = layout.column(align=True)
            col.prop(nodes['Clamp Value'].inputs[0], val, text="Clamp Dark")
            col.prop(nodes['Dodge Value'].inputs[0], val, text="Dodge Bright") 
            layout.prop(nodes['Shadow Value'].inputs[0], val, text="Value Fix")
            
            if 'Fuzzy BG' in bpy.data.node_groups:
                col = layout.column(heading="Floor", align=True)
                col.prop(nodes['Floor Alpha'], 'mute', text="Holdout")
                col = col.column(heading="Film")
                col.prop(scene.render, "film_transparent")
                
        except KeyError:
            pass


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
        
        if context.engine == 'BLENDER_EEVEE':
            row = layout.row(align=True)
            row.use_property_split = True
            row.use_property_decorate = False
            row.prop(rd, "hair_type", text = "Type", expand=True)

        col = layout.column(align=True)
        row = col.row(align=True)
        row.label(text="Visibility")
        row = col.row(align=True)
        row.operator("object.hair_show", text="Show All", icon='HIDE_OFF')
        row.operator("object.hair_hide", text="Hide All", icon='HIDE_ON')
        
        hair = bpy.data.objects
        col = layout.grid_flow(row_major=True, columns=2)
        
        # reference to LIST CHARACTERS
        for char, icon in character_list.items():
            char_hair = char + "_hair"
            if char_hair in hair:
                try:        
                    row = col.row(align=True)
                    row.label(icon=icon)
                    row.prop(hair[char_hair].modifiers[char_hair], "show_viewport", 
                            text="", icon='HIDE_ON', emboss=False)
                except KeyError:
                    pass


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
        col1 = split.column(align=True)
        col1.prop(overlay, "show_relationship_lines")
        col1.prop(shade, "show_backface_culling")
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
    bl_context = 'objectmode'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3

    def draw_header_preset(self, context):
        scene = context.scene
        fuzzyprops = scene.fuzzy_props
        animated = False
       
       # check for 'mblur' marker
        markers = scene.timeline_markers
        if markers is not None:
            for m in markers:
                if m.name.startswith('mblur'):
                    animated = True
                    break
       
        if animated:
            layout = self.layout
            layout.scale_x = 1.2
            layout.prop(fuzzyprops, "scene_animate", text="", icon='ACTION')

    def draw(self, context):
        pass


class VIEW3D_PT_scene(Panel):
    bl_label = "Scene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'VIEW3D_PT_cameras'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header_preset(self, context):
        layout = self.layout
        scene = context.scene
        object = context.active_object
        layout.scale_x = 1.2        
        if object != scene.camera:
            if scene.camera.name not in context.view_layer.objects:
                layout.enabled = False
            layout.operator("object.select_camera", text="", icon='RESTRICT_SELECT_OFF')
        
    def draw(self, context):
        scene = context.scene
        layout = self.layout

        row = layout.row(align=True)
        row.prop(scene, "camera", text="Active", icon='CAMERA_DATA')
        row.operator('view3d.view_camera', text='', icon='VIEWZOOM')
        row.operator('view3d.camera_to_view', text='', icon='DECORATE_OVERRIDE')

        col = layout.column()
        col.scale_y = 1.3
        col.operator("object.fuzzy_camera", text="Build", icon='CAMERA_DATA')

        if context.space_data.lock_camera == True:
            icon = 'LOCKED'
        else:
            icon = 'UNLOCKED'
        row = layout.row(align=True)
        row.scale_x = 1.2
        row.prop(context.space_data, 'lock_camera', text='', icon=icon)
        row.label(text=' Lock to View')
   
        col = layout.column(align=True)
        col.prop(scene.eevee, 'use_motion_blur')
        row = col.row()
        row.prop(scene.eevee, 'motion_blur_shutter')
        col.separator(factor=0.5)
        row = col.row(align=True)
        row.operator('marker.add_motionblur_marker', text="On", icon='KEYFRAME_HLT').blur = 'on'
        row.operator('marker.add_motionblur_marker', text="Off", icon='KEYFRAME').blur = 'off'
        row.operator('marker.shutter_to_markers', text='', icon='MARKER_HLT')
        
        
class VIEW3D_PT_camera_properties(Panel):
    bl_label = ""
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'VIEW3D_PT_cameras'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        scene = context.scene
        objects = scene.objects
        return context.active_object is not None and context.object.type == 'CAMERA'

    def draw_header(self, context):
        object = context.active_object
        if object != context.scene.camera:
            self.layout.operator('view3d.set_active_camera', text=object.name, icon="CAMERA_DATA")
        else:
            self.layout.prop(object, "name", text='', emboss=False, icon="VIEW_CAMERA")
    
    def draw(self, context):
        layout = self.layout
        object = context.object   
        layout.use_property_split = True
        layout.use_property_decorate = False
        
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator('marker.camera_bind_new', text="Bind to Marker", icon='KEYFRAME_HLT')
        row.separator(factor=0.5)
        row.operator('object.rename_camera_alpha', text='', icon='SORTALPHA') 
        
        layout.prop(object.data, "lens")
        
        col = layout.column(heading="Show", align=True)        
        col.prop(object, "show_name", text="Name")
        col.prop(object.data, "show_limits", text="Limits")
        
        col = layout.column(align=True)
        col.prop(object.data, "clip_start", text="Clip Start")
        col.prop(object.data, "clip_end", text="End")
        
        col = layout.column()
        col.prop(object.data, "passepartout_alpha", text="Passepartout")
        
        col = layout.column(heading="DoF")
        col.prop(object.data.dof, "use_dof", text="")
        if object.data.dof.use_dof:
            col.prop(object.data.dof, "focus_object")
            row = col.row()
            if object.data.dof.focus_object is not None:
                row.enabled = False
            row.prop(object.data.dof, "focus_distance")
            row.operator('object.cursor_to_focus_distance', text='', icon='CURSOR')
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

    OBJECT_OT_hair_show,
    OBJECT_OT_hair_hide,
    
    MARKER_OT_add_motionblur_marker,
    MARKER_OT_shutter_to_markers,
    
    VIEW3D_OT_set_active_camera,    
    MARKER_OT_camera_bind_new,
    OBJECT_OT_rename_camera_alpha,
    OBJECT_OT_cursor_to_focus_distance,
    
    TRANSFORM_OT_keyframes_markers,

    # panels
    BuildScenePanel,
    BuildAllPanel,
    BuildPartsPanel,
    BackgroundPanel,
    HDRIPanel,
    FloorPanel,

    VIEW3D_PT_viewport,
    VIEW3D_PT_simplify,
    VIEW3D_PT_hair,
    VIEW3D_PT_miscellaneous,
    
    VIEW3D_PT_cameras,
    VIEW3D_PT_scene,
    VIEW3D_PT_camera_properties,    
    
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fuzzy_props = PointerProperty(type=FuzzyProperties)
        
    bpy.app.handlers.load_post.append(reload_image)
    bpy.app.handlers.load_post.append(auto_animate_scene)
    bpy.app.handlers.load_post.append(disable_animate_scene)
    
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

    # Remove hotkey Alt+M
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


if __name__ == "__main__":
    register()
