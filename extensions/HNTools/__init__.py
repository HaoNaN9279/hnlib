import bpy
from .operators import generate_ORG_bones
from .operators import bspsd

bl_info = {
    'name': 'HN Tools',
    'description': 'A set of useful tools',
    'author': 'HaoNaN9279',
    'version': (0, 0, 1),
    'blender': (4, 3, 0)
}


def register():
    '''Register all classes in the module'''
    generate_ORG_bones.register()
    bspsd.register()

def unregister():
    '''Unregister all classes in the module'''
    bspsd.register()
    generate_ORG_bones.unregister()

if __name__ == '__main__':
    register()