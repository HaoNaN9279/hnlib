""" rig script.some code from Rigify.
    Author:HaoNaN
    1207185592@qq.com
    SPDX-License-Identifier: GPL-2.0-or-later
"""

"""
骨骼绑定自定义UI模板代码
一般情况下包含3个固定的面板：
Visiable：将控制器和骨骼按照肢体部位和功能分类，面板上的每一个toggle button控制每一类控制器或骨骼的显示
Tools：提供一些简单工具的面板，目前包括FK与IK的骨骼同步功能
Properties：参数面板，用于显示一些可动画的参数
其他面板可按需另行添加

使用流程：
1、制作好完整的骨骼绑定并正确命名和分组
2、打开scripting面板，在template中选择Hn_rig_ui
3、在绑定的Armature Object下创建一个string类型的property，命名为hn_rig_id，并赋予一个有意义的值，脚本将通过此property找到目标Armature
4、修改代码：
    修改hn_rig_id的值与property中的值相同
    按需添加UI和面板
5、修改完成后，点击勾选Scripting上方的菜单Text->Register，以便下次重启工程文件时自动执行该脚本
6、保存
"""

import bpy
import math
import json
from math import pi
from mathutils import Euler, Matrix, Quaternion, Vector

#create a string type custom property called "hn_rig_id" on target armature and match the value.
hn_rig_id = "knight"


def match_bone(obj, bone_name, target_bone_name):
    bone = obj.pose.bones[bone_name]
    target_bone = obj.pose.bones[target_bone_name]
    if bone is not None and target_bone is not None:
        target_bone_matrix = obj.convert_space(pose_bone = bone, matrix = target_bone.matrix, from_space = 'POSE', to_space = 'LOCAL')
        bone.matrix_basis = target_bone_matrix
        
def match_pole_target(context, ik_first_bone_name, ik_last_bone_name, match_bone_matrix, ik_pole_bone_name):
    ik_first = context.active_object.pose.bones[ik_first_bone_name]
    ik_last = context.active_object.pose.bones[ik_last_bone_name]
    ik_pole = context.active_object.pose.bones[ik_pole_bone_name]
    
    a = ik_first.matrix.to_translation()
    b = ik_last.matrix.to_translation() + ik_last.vector
    ikv = b - a
    length = ik_first.length + ik_last.length
    
    def perpendicular_vector(v):
        if abs(v[0]) < abs(v[1]):
            tv = Vector((1, 0, 0))
        else:
            tv = Vector((0, 1, 0))
        return v.cross((tv))
    
    pv = perpendicular_vector(ikv).normalized() * length
    
    def set_pole(pvi):
        pole_loc = a + (ikv / 2) + pvi
        mat = ik_pole.id_data.convert_space(matrix = Matrix.Translation(pole_loc), pose_bone = ik_pole, from_space = 'POSE', to_space = 'LOCAL')
        ik_pole.location = mat.to_translation()
        context.view_layer.update()
        
    set_pole(pv)
    
    def rotation_difference(mat1, mat2):
        q1 = mat1.to_quaternion()
        q2 = mat2.to_quaternion()
        angle = math.acos(min(1, max(-1, q1.dot(q2)))) * 2
        if angle > pi:
            angle = -angle + (2 * pi)
        return angle
    
    angle = rotation_difference(ik_first.matrix, match_bone_matrix)
    
    pv1 = Matrix.Rotation(angle, 4, ikv) @ pv
    set_pole(pv1)
    ang1 = rotation_difference(ik_first.matrix, match_bone_matrix)
    
    pv2 = Matrix.Rotation(-angle, 4, ikv) @ pv
    set_pole(pv2)
    ang2 = rotation_difference(ik_first.matrix, match_bone_matrix)
    
    if ang1 < ang2:
        set_pole(pv1)
        
def fk_to_ik(context, fk_bone_names, ik_bone_names):
    if len(fk_bone_names) == len(ik_bone_names):
        for i in range(len(fk_bone_names)):
            match_bone(context.active_object, fk_bone_names[i], ik_bone_names[i])
            context.view_layer.update()
            
def ik_to_fk(context, fk_first_bone_name, fk_last_bone_name, ik_first_bone_name, ik_last_bone_name, ik_pole_bone_name):
    match_bone(context.active_object, ik_last_bone_name, fk_last_bone_name)
    context.view_layer.update()
            
            
class FK2IKOperator(bpy.types.Operator):
    bl_idname = "pose.hn_rig_fk2ik_" + hn_rig_id
    bl_label = "[HN] fk to ik"
    bl_options = {'REGISTER'}
    
    #fk bone chain names,from parent to child.
    fk_bone_list: bpy.props.StringProperty(name = "FK Bones")
    #fk bone chain names, from parent to child,last one should be ik target.
    ik_bone_list: bpy.props.StringProperty(name = "IK Bones")
    
    def execute(self, context):
        fk_bone_names = json.loads(self.fk_bone_list)
        ik_bone_names = json.loads(self.ik_bone_list)
        
        fk_to_ik(context, fk_bone_names, ik_bone_names)
        
        return {'FINISHED'}
    
    
class IK2FKOperator(bpy.types.Operator):
    bl_idname = "pose.hn_rig_ik2fk_" + hn_rig_id
    bl_label = "[HN] ik to fk"
    bl_options = {'REGISTER'}
    
    #two bones name,first should be the first bone in fk chain,second should be the last bone in fk chain.
    fk_bone_list: bpy.props.StringProperty(name = "FK Bones")
    #two bones name,first should be the first bone in ik chain,second should be the ik target.
    ik_bone_list: bpy.props.StringProperty(name = "IK Bones")
    #ik pole bone name.
    ik_pole_bone: bpy.props.StringProperty(name = "IK Pole Bone")
    
    def execute(self, context):
        fk_bone_names = json.loads(self.fk_bone_list)
        ik_bone_names = json.loads(self.ik_bone_list)
        ik_pole_name = self.ik_pole_bone
        
        ik_to_fk(context, fk_bone_names[0], fk_bone_names[1], ik_bone_names[0], ik_bone_names[1], ik_pole_name)
        context.view_layer.update()
        
        match_bone_matrix = context.active_object.pose.bones[fk_bone_names[0]].matrix
        match_pole_target(context, ik_bone_names[0], ik_bone_names[1], match_bone_matrix, ik_pole_name)
        
        return {'FINISHED'}


class RiggingPanel():
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "[HN]" + bpy.context.active_object.name
    
    @classmethod
    def poll(self, context):
        poll = context.active_object is not None \
            and context.active_object.type == 'ARMATURE' \
            and context.active_object.data.get("hn_rig_id") == hn_rig_id
            
        return poll
    
class VisiblePanel(bpy.types.Panel, RiggingPanel):
    #panel to visualize bone collection.
    bl_idname = "VIEW3D_PT_hn_rig_visible_panel_" + hn_rig_id
    bl_label = "Visible"
    
    def draw(self, context):
#############################################################################################
        bone_col = context.active_object.data.collections_all
        self.layout.label(text = "Bone Collections")
        bc_box = self.layout.box()
        
        bc_box.prop(bone_col["HEAD"], "is_visible", text = "HEAD", toggle = True)
        bc_box.prop(bone_col["TORSO"], "is_visible", text = "TORSO", toggle = True)
        
        arm_row = bc_box.row(align = True)
        arm_row.prop(bone_col["ARM_L"], "is_visible", text = "ARM_L", toggle = True)
        arm_row.prop(bone_col["ARM_R"], "is_visible", text = "ARM_R", toggle = True)
        
        hand_row = bc_box.row(align = True)
        hand_row.prop(bone_col["HAND_L"], "is_visible", text = "HAND_L", toggle = True)
        hand_row.prop(bone_col["HAND_R"], "is_visible", text = "HAND_R", toggle = True)
        
        leg_row = bc_box.row(align = True)
        leg_row.prop(bone_col["LEG_L"], "is_visible", text = "LEG_L", toggle = True)
        leg_row.prop(bone_col["LEG_R"], "is_visible", text = "LEG_R", toggle = True)
        
        foot_row = bc_box.row(align = True)
        foot_row.prop(bone_col["FOOT_L"], "is_visible", text = "FOOT_L", toggle = True)
        foot_row.prop(bone_col["FOOT_R"], "is_visible", text = "FOOT_R", toggle = True)
        
        bc_box.prop(bone_col["ROOT"], "is_visible", text = "ROOT", toggle = True)
        
        bc_box.split(align = True)
        
        bc_box.prop(bone_col["TWEAK"], "is_visible", text = "TWEAK", toggle = True)
#############################################################################################
        

class ToolsPanel(bpy.types.Panel, RiggingPanel):
    #panel to display useful tools.
    bl_idname = "VIEW3D_PT_hn_rig_tools_panel_" + hn_rig_id
    bl_label = "Tools"
    
    def draw(self, context):
#############################################################################################
        tools_box = self.layout.box()
        
        arm_fk2ik_row = tools_box.row(align = True)
        props = arm_fk2ik_row.operator('pose.hn_rig_fk2ik_' + hn_rig_id, text = "FK->IK(ARM_L)", icon = 'SNAP_ON')
        props.fk_bone_list = '["UPPERARM_FK_L", "FOREARM_FK_L", "MCH_FK_HAND_L"]'
        props.ik_bone_list = '["MCH_UPPERARM_IK_L", "MCH_FOREARM_IK_L", "ARM_IK_TARGET_L"]'
        props = arm_fk2ik_row.operator('pose.hn_rig_fk2ik_' + hn_rig_id, text = "FK->IK(ARM_R)", icon = 'SNAP_ON')
        props.fk_bone_list = '["UPPERARM_FK_R", "FOREARM_FK_R", "MCH_FK_HAND_R"]'
        props.ik_bone_list = '["MCH_UPPERARM_IK_R", "MCH_FOREARM_IK_R", "ARM_IK_TARGET_R"]'
        
        arm_ik2fk_row = tools_box.row(align = True)
        props = arm_ik2fk_row.operator('pose.hn_rig_ik2fk_' + hn_rig_id, text = "IK->FK(ARM_L)", icon = 'SNAP_ON')
        props.fk_bone_list = '["UPPERARM_FK_L", "MCH_FK_HAND_L"]'
        props.ik_bone_list = '["MCH_UPPERARM_IK_L", "ARM_IK_TARGET_L"]'
        props.ik_pole_bone = "ARM_IK_POLE_L"
        props = arm_ik2fk_row.operator('pose.hn_rig_ik2fk_' + hn_rig_id, text = "IK->FK(ARM_R)", icon = 'SNAP_ON')
        props.fk_bone_list = '["UPPERARM_FK_R", "MCH_FK_HAND_R"]'
        props.ik_bone_list = '["MCH_UPPERARM_IK_R", "ARM_IK_TARGET_R"]'
        props.ik_pole_bone = "ARM_IK_POLE_R"
#############################################################################################
        
        
class PropertiesPanel(bpy.types.Panel, RiggingPanel):
    #panel to display custom properties.
    bl_idname = "VIEW3D_PT_hn_rig_properties_panel_" + hn_rig_id
    bl_label = "Properties"
    
    def draw(self, context):
#############################################################################################
        pose_bones = context.active_object.pose.bones
        prop_box = self.layout.box()
        
        prop_box.prop(pose_bones["ROOT"], '["head_look"]')
        prop_box.prop(pose_bones["ROOT"], '["head_target_parent"]')
        
        arm_row = prop_box.row(align = True)
        arm_row.prop(pose_bones["ROOT"], '["left_arm_fk_ik"]')
        arm_row.prop(pose_bones["ROOT"], '["right_arm_fk_ik"]')
        
        hand_row = prop_box.row(align = True)
        hand_row.prop(pose_bones["ROOT"], '["left_hand_ik_parent"]')
        hand_row.prop(pose_bones["ROOT"], '["right_hand_ik_parent"]')
        
        leg_row = prop_box.row(align = True)
        leg_row.prop(pose_bones["ROOT"], '["left_leg_fk_ik"]')
        leg_row.prop(pose_bones["ROOT"], '["right_leg_fk_ik"]')
#############################################################################################


classes = (
    FK2IKOperator,
    IK2FKOperator,
    VisiblePanel,
    ToolsPanel,
    PropertiesPanel
)

for cls in classes:
    bpy.utils.register_class(cls)

