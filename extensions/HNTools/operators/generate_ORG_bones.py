import bpy

class GenerateORGBonesOperator(bpy.types.Operator):
    """
    角色骨骼与绑定的一般做法为三层骨骼：
    DEF：直接控制模型的骨骼，存储蒙皮信息，最终导出到游戏引擎中的骨骼，有且只有一个Copy Transform的约束用来与ORG骨骼同步，根骨骼为角色根骨骼；
    ORG：直接控制DEF骨骼的骨骼，一般数量与位置与DEF骨骼相同，被DEF骨骼的Copy Transform约束引用，使用各种约束主动与MCH骨骼同步或者被MCH骨骼控制，根骨骼为角色根骨骼；
    MCH：用于生成IK,FK等各种功能的控制骨骼，有自己的父子关系，直接或间接通过约束控制ORG骨骼；
    除了以上三层骨骼外，还有一层控制器，一般使用简单几何形状或线条制作，直接通过约束控制MCH骨骼，是最终用于制作动画的object。

    此工具用于一键从做好的前缀为DEF_的骨骼生成ORG骨骼，生成的ORG骨骼位置，父子关系与DEF骨骼完全相同，并自动在DEF骨骼上配置好对应的Copy Transform约束。
    
    使用方法：
    1、创建好DEF骨骼并正确命名（骨骼名称前缀为DEF_）;
    2、在Pose Mode下，选择需要生成ORG骨骼的DEF骨骼；
    3、在顶部菜单点击：Pose->[HN] Generate ORG Bones；
    4、在左下角的浮动菜单上填写ORG骨骼的前缀，默认为ORG；
    5、生成完成。
    """

    bl_idname = 'pose.generate_org_bones'
    bl_label = '[HN] Generate ORG Bones'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "通过前缀为DEF_的骨骼在相同位置生成ORG_骨骼"

    org_bone_collection_name: bpy.props.StringProperty(name = "ORG Bone Collection Name", default = "ORG")

    @classmethod
    def poll(cls, context):
        '''Check if the operator can be called'''
        poll = context.active_object is not None \
            and context.active_object.type == 'ARMATURE'\
            and context.active_object.mode == 'POSE' \
            and len(context.selected_pose_bones) > 0
        
        has_def_pose_bones = False
        if(len(context.selected_pose_bones)) > 0:
            for bone in context.selected_pose_bones:
                if bone.name.startswith('DEF_'):
                    has_def_pose_bones = True
                    break

        return poll and has_def_pose_bones


    def add_constraint(self, context, def_pose_bone, org_pose_bone):
        '''Add a copy transform constraint to the bone'''
        if org_pose_bone is not None:
            constraint = def_pose_bone.constraints.new('COPY_TRANSFORMS')
            constraint.name = "Copy Transforms from ORG"
            constraint.target = context.active_object
            constraint.subtarget = org_pose_bone.name
            constraint.target_space = 'WORLD'
            constraint.owner_space = 'WORLD'

    def add_org_bone(self, context, def_edit_bone, org_bone_name):
        '''Add a new bone to the armature'''
        org_edit_bone = context.active_object.data.edit_bones.new(org_bone_name)
        org_edit_bone.head = def_edit_bone.head
        org_edit_bone.tail = def_edit_bone.tail
        org_edit_bone.roll = def_edit_bone.roll
    
    def execute(self, context):
        '''Execute the operator'''
        if(len(context.selected_pose_bones)) == 0:
            return {'CANCELLED'}
        org_bone_collection = None
        if self.org_bone_collection_name not in bpy.data.collections:
            org_bone_collection = context.active_object.data.collections.new(name = self.org_bone_collection_name)
        else:
            org_bone_collection = context.active_object.data.collections[self.org_bone_collection_name]
        target_bones = context.selected_pose_bones
        for def_pose_bone in target_bones:
            if def_pose_bone.name.startswith('DEF_'):
                org_bone_name = def_pose_bone.name.replace('DEF_', 'ORG_')
                org_pose_bone = None
                if org_bone_name in context.active_object.pose.bones:
                    org_pose_bone = context.active_object.pose.bones[org_bone_name]
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    org_edit_bone = context.active_object.data.edit_bones[org_bone_name]
                    if org_bone_name not in org_edit_bone.collections:
                        org_bone_collection.assign(org_pose_bone)
                    bpy.ops.object.mode_set(mode = 'POSE')
                    if len(def_pose_bone.constraints) == 0:
                        self.add_constraint(context, def_pose_bone, org_pose_bone)
                    else:
                        need_add_constraint = True
                        for constraint in def_pose_bone.constraints:
                            if constraint.type == 'COPY_TRANSFORMS' and constraint.target == context.active_object and constraint.subtarget == org_bone_name:
                                need_add_constraint = False
                                break
                        if need_add_constraint:
                            self.add_constraint(context, def_pose_bone, org_pose_bone)
                else:
                    bpy.ops.object.mode_set(mode = 'EDIT')
                    def_edit_bone = context.active_object.data.edit_bones[def_pose_bone.name]
                    self.add_org_bone(context, def_edit_bone, org_bone_name)

                    bpy.ops.object.mode_set(mode = 'POSE')
                    org_pose_bone = context.active_object.pose.bones[org_bone_name]
                    self.add_constraint(context, def_pose_bone, org_pose_bone)

        bpy.ops.object.mode_set(mode = 'EDIT')
        root_edit_bone = context.active_object.data.edit_bones['ROOT']
        for def_pose_bone in target_bones:
            if def_pose_bone.name.startswith('DEF_'):
                def_bone_name = def_pose_bone.name
                def_edit_bone = context.active_object.data.edit_bones[def_bone_name]
                def_parent_edit_bone = def_edit_bone.parent
                org_edit_bone = context.active_object.data.edit_bones[def_bone_name.replace("DEF_", "ORG_")]
                if def_parent_edit_bone is not None:
                    if def_parent_edit_bone.name is not "ROOT":
                        org_parent_edit_bone = context.active_object.data.edit_bones[def_parent_edit_bone.name.replace("DEF_", "ORG_")]
                        org_edit_bone.parent = org_parent_edit_bone
                    else:
                        if root_edit_bone is not None:
                            org_edit_bone.parent = root_edit_bone
                org_bone_collection.assign(org_edit_bone)
        bpy.ops.object.mode_set(mode = 'POSE')
        

        return {'FINISHED'}
    
def menu_func(self, context):
    '''Add the operator to the menu'''
    self.layout.operator(GenerateORGBonesOperator.bl_idname, text = GenerateORGBonesOperator.bl_label)
    
def register():
    '''Register class'''
    bpy.utils.register_class(GenerateORGBonesOperator)
    bpy.types.VIEW3D_MT_pose.append(menu_func)

def unregister():
    '''Unregister class'''
    bpy.types.VIEW3D_MT_pose.remove(menu_func)
    bpy.utils.unregister_class(GenerateORGBonesOperator)