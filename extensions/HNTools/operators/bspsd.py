import bpy
import json
from bpy.props import IntProperty
from mathutils import Matrix, Vector, Quaternion

"""
pose space deformation
未完成
需要获取在应用完所有约束计算后的骨骼的matrix

工作原理：
给做好骨骼绑定的mesh注册选定的shape key与在pose mode下有变化的骨骼的对应关系，存储为blend文件内的json文件，
然后生成driver使用的python函数的脚本；
这两个文件有且只有一份，json文件中的内容会更新；
然后在armature上创建自定义的float property，一个shape key对应一个；
并添加driver通过调用python脚本中的函数，计算该shape key的value值；
再在shape key的value值上添加driver，直接引用前面创建好的property的值；
（shape key的driver如果直接计算，该driver不会实时更新）

使用方法：
准备好做好绑定的模型；
在pose mode下调整姿势；
在object mode下创建一个shape key，命名前缀必须为“BSPSD_”，将value设置为1，启用编辑；
在edit mode或者sculpt mode下编辑当前姿势下的shape key；
编辑完成后，确保当前shape key被选择，点击Regist按钮注册，然后关闭shape key编辑；
如果需要调整当前shape key对应的姿势，先调整好新姿势，重新点击regist按钮即可；
点击unregist删除当前选定的shape key的数据
"""

bspsd_id_property_name = "hn_bspsd_id"
bspsd_data_file_name = "hn_bspsd_data.json"
bspsd_driver_file_name = "hn_bspsd_driver.py"
bspsd_driver_file = f"""
import bpy
import json

def hn_bspsd_driver(obj_name, shape_key_name):
    # 需要获取在应用完所有约束计算后的骨骼的matrix，但是在driver中执行下面这句会卡死
    # depsgraph = bpy.context.evaluated_depsgraph_get()
    obj = bpy.data.objects[obj_name]
    # armature = obj.parent.evaluated_get(depsgraph)
    armature = obj.parent
    shape_key = obj.data.shape_keys.key_blocks[shape_key_name]
    json_data = json.loads(bpy.data.texts['{bspsd_data_file_name}'].as_string())
    shape_key_data = json_data[1]['data'][obj_name][shape_key_name]

    weight = 0.0
    sqr_sum = 0.0
    diff = 0.0
    if shape_key_data is not None:
        print(shape_key_data)
        for bone in armature.pose.bones:
            if bone.name in shape_key_data:
                diff = bone.location[0] - (shape_key_data[bone.name]['px'] if 'px' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.location[1] - (shape_key_data[bone.name]['py'] if 'py' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.location[2] - (shape_key_data[bone.name]['pz'] if 'pz' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.rotation_euler[0] - (shape_key_data[bone.name]['rx'] if 'rx' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.rotation_euler[1] - (shape_key_data[bone.name]['ry'] if 'ry' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.rotation_euler[2] - (shape_key_data[bone.name]['rz'] if 'rz' in shape_key_data[bone.name] else 0.0)
                sqr_sum += diff * diff
                diff = bone.scale[0] - (shape_key_data[bone.name]['sx'] if 'sx' in shape_key_data[bone.name] else 1.0)
                sqr_sum += diff * diff
                diff = bone.scale[1] - (shape_key_data[bone.name]['sy'] if 'sy' in shape_key_data[bone.name] else 1.0)
                sqr_sum += diff * diff
                diff = bone.scale[2] - (shape_key_data[bone.name]['sz'] if 'sz' in shape_key_data[bone.name] else 1.0)
                sqr_sum += diff * diff
        s = 1.0
        def hn_sqrt(n, eps=1e-6):
            if n < 0.0:
                return 0.0
            if n == 0.0 or n == 1.0:
                return n
            left, right = 0.0, n
            while right - left > eps:
                mid = (left + right) / 2.0
                if mid * mid > n:
                    right = mid
                else:
                    left = mid
            return (left + right) / 2.0
        dis = hn_sqrt(sqr_sum)
        p = -(dis * dis) / (2.0 * s * s)
        def hn_exp(x):
            x = 1.0 + x / 1024.0
            x *= x; x *= x; x *= x; x *= x;
            x *= x; x *= x; x *= x; x *= x;
            x *= x; x *= x;
            return x
        weight = hn_exp(p)
    return weight

bpy.app.driver_namespace['hn_bspsd_driver'] = hn_bspsd_driver
"""

def UpdateJsonData(org_data, new_data):
    '''递归更新json数据'''
    if type(org_data) is list and type(new_data) is list:
        for data in new_data:
            if data in org_data:
                UpdateJsonData(org_data.data, data)
            else:
                org_data.append(data)
    elif type(org_data) is dict and type(new_data) is dict:
        for key in new_data:
            if key in org_data:
                if type(org_data[key]) is not dict and type(org_data[key]) is not list:
                    org_data[key] = new_data[key]
                else:
                    UpdateJsonData(org_data[key], new_data[key])
            else:
                org_data[key] = new_data[key]

def FloatAlmostEqual(x, y, tolerance = 1e-5):
    '''容错内比较float值'''
    return True if abs(x - y) < tolerance else False

def TryCreateBSPSDData(obj, shape_key):
    '''创建或更新所需的property，json文件，py文件'''
    #获取或创建hn_bspsd_id
    if bspsd_id_property_name in obj:
        id = obj.get(bspsd_id_property_name)
    else:
        id = "bspsd_id_" + str(obj.as_pointer())
        obj[bspsd_id_property_name] = id
    
    #获取或创建对应json文件
    if bspsd_data_file_name not in bpy.data.texts:
        bspsd_data_file = bpy.data.texts.new(bspsd_data_file_name)
        bspsd_data = []
        bspsd_data.append({'Author' : 'HaoNaN'})
    else:
        bspsd_data_file = bpy.data.texts[bspsd_data_file_name]
        bspsd_data = json.loads(bspsd_data_file.as_string())
    bspsd_obj_data = {}
    bspsd_shape_key_data = {}
    target_pose = obj.parent.pose
    for bone in target_pose.bones:
        bspsd_bone_data = {}
        if not FloatAlmostEqual(bone.location[0], 0):
            bspsd_bone_data["px"] = bone.location[0]
        if not FloatAlmostEqual(bone.location[1], 0):
            bspsd_bone_data["py"] = bone.location[1]
        if not FloatAlmostEqual(bone.location[2], 0):
            bspsd_bone_data["pz"] = bone.location[2]
        if not FloatAlmostEqual(bone.rotation_euler[0], 0):
            bspsd_bone_data["rx"] = bone.rotation_euler[0]
        if not FloatAlmostEqual(bone.rotation_euler[1], 0):
            bspsd_bone_data["ry"] = bone.rotation_euler[1]
        if not FloatAlmostEqual(bone.rotation_euler[2], 0):
            bspsd_bone_data["rz"] = bone.rotation_euler[2]
        if not FloatAlmostEqual(bone.scale[0], 1):
            bspsd_bone_data["sx"] = bone.scale[0]
        if not FloatAlmostEqual(bone.scale[1], 1):
            bspsd_bone_data["sy"] = bone.scale[1]
        if not FloatAlmostEqual(bone.scale[2], 1):
            bspsd_bone_data["sz"] = bone.scale[2]
        if len(bspsd_bone_data) > 0:
            bspsd_shape_key_data[bone.name] = bspsd_bone_data
    bspsd_obj_data[shape_key.name] = bspsd_shape_key_data
    new_data = {obj.name : bspsd_obj_data}
    if len(bspsd_data) > 1:
        data = bspsd_data[1]['data']
        UpdateJsonData(data, new_data)
        bspsd_data[1]['data'] = data
    else:
        data = {}
        UpdateJsonData(data, new_data)
        bspsd_data.append({'data' : data}) 
    bspsd_data_file.clear()
    bspsd_data_file.write(json.dumps(bspsd_data, indent = 4))

    #如果没有，创建driver函数python文件
    if bspsd_driver_file_name not in bpy.data.texts:
        file = bpy.data.texts.new(bspsd_driver_file_name)
        file.write(bspsd_driver_file)
    else:
        file = bpy.data.texts[bspsd_driver_file_name]
        if bspsd_driver_file != file.as_string():
            file.clear()
            file.write(bspsd_driver_file)
    exec(file.as_string())

def CreateShapeKeyDriver(obj, shape_key):
    '''在shape key的value参数上创建driver'''
    armature = obj.parent.data
    prop_name = shape_key.name + '_weight'
    armature[prop_name] = 0.0
    driver = armature.driver_add(f'["{prop_name}"]').driver
    driver.type = 'SCRIPTED'
    driver.expression = f"hn_bspsd_driver(\"{obj.name}\", \"{shape_key.name}\")"

    driver = shape_key.driver_add('value').driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.type = 'SINGLE_PROP'
    var.name = shape_key.name + '_weight'
    var.targets[0].id_type = 'ARMATURE'
    var.targets[0].id = obj.parent.data
    var.targets[0].data_path = f'["{var.name}"]'
    driver.expression = var.name

def RemoveShapeKeyDriver(obj, shape_key):
    '''移除shape key上的driver'''
    shape_key.driver_remove('value')

    armature = obj.parent.data
    prop_name = shape_key.name + '_weight'
    armature.driver_remove(prop_name)
    del armature[prop_name]

def ClearShapeKeyData(obj, shape_key):
    '''从json文件中删除选定的shape key的数据'''
    if bspsd_data_file_name in bpy.data.texts:
        bspsd_data_file = bpy.data.texts[bspsd_data_file_name]
        bspsd_data = json.loads(bspsd_data_file.as_string())
        if len(bspsd_data) > 1  \
        and 'data' in bspsd_data[1] \
        and obj.name in bspsd_data[1]['data'] \
        and shape_key.name in bspsd_data[1]['data'][obj.name]:
            del bspsd_data[1]['data'][obj.name][shape_key.name]
            if len(bspsd_data[1]['data'][obj.name]) == 0:
                del bspsd_data[1]['data'][obj.name]
            bspsd_data_file.clear()
            bspsd_data_file.write(json.dumps(bspsd_data, indent = 4))

class RegistShapeKeyOperator(bpy.types.Operator):
    '''注册选定的shape key与当前骨骼的pose的关系数据'''
    bl_idname = "object.hn_bspsd_regist_shape_key"
    bl_label = "[HN]Regist Shape Key"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(self, context):
        obj = context.active_object
        poll = obj is not None \
        and (obj.mode == 'OBJECT' or obj.mode == 'EDIT' or obj.mode == 'SCULPT') \
        and obj.type == 'MESH' \
        and obj.active_shape_key is not None \
        and obj.active_shape_key.name != 'Basis' \
        and obj.active_shape_key.name.startswith("BSPSD_") \
        and obj.parent is not None \
        and obj.parent.type == 'ARMATURE'

        return poll

    def execute(self, context):
        obj = context.active_object
        shape_key = obj.active_shape_key
        if obj is not None and shape_key is not None:
            TryCreateBSPSDData(obj, shape_key)
            CreateShapeKeyDriver(obj, shape_key)

        return {'FINISHED'}

class UnregistShapeKeyOperator(bpy.types.Operator):
    '''删除当前选定的shape key的注册数据'''
    bl_idname = "object.hn_bspsd_unregist_shape_key"
    bl_label = "[HN]Unregist Shape Key"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(self, context):
        obj = context.active_object
        poll = obj is not None \
        and (obj.mode == 'OBJECT' or obj.mode == 'EDIT' or obj.mode == 'SCULPT') \
        and obj.type == 'MESH' \
        and obj.active_shape_key is not None \
        and obj.active_shape_key.name != 'Basis' \
        and obj.active_shape_key.name.startswith("BSPSD_") \
        and obj.parent is not None \
        and obj.parent.type == 'ARMATURE'
        
        return poll

    def execute(self, context):
        obj = context.active_object
        shape_key = obj.active_shape_key
        if obj is not None and shape_key is not None:
            RemoveShapeKeyDriver(obj, shape_key)
            ClearShapeKeyData(obj, shape_key)

        return {'FINISHED'}

class BSPSDPanel(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_category = "[HN]BSPSD"
    bl_idname = "DATA_PT_hn_bspsd_panel"
    bl_label = "[HN]BSPSD"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(self, context):
        poll = context.active_object is not None \
        and context.active_object.type == 'MESH'

        return poll
    
    def draw(self, context):
        box = self.layout.box()
        btn_row = box.row(align = True)
        props = btn_row.operator('object.hn_bspsd_regist_shape_key', text = "Regist")
        props = btn_row.operator('object.hn_bspsd_unregist_shape_key', text = "Unregist")


def register():
    '''Register class'''
    bpy.utils.register_class(RegistShapeKeyOperator)
    bpy.utils.register_class(UnregistShapeKeyOperator)
    bpy.utils.register_class(BSPSDPanel)

def unregister():
    '''Unregister class'''
    bpy.utils.unregister_class(BSPSDPanel)
    bpy.utils.unregister_class(UnregistShapeKeyOperator)
    bpy.utils.unregister_class(RegistShapeKeyOperator)

