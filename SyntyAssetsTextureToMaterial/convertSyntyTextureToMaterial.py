import bpy
import os
import bmesh
from os import listdir
from os.path import isfile, join
from PIL import Image
    
# Synty Assets texture to material conversion - Created by RustyPrime

texture = "D:\_Projects\Assets\SyntyAssets\Polygon_Samurai\SourceFiles\Textures\PolygonSamurai_Tex_01.png"
texture_background_color = (113, 113, 113)
path_of_objects_to_convert = "D:\_Projects\Assets\SyntyAssets\Polygon_Samurai\SourceFiles\FBX"
output_path = "D:\_Projects\Assets\SyntyAssets\Polygon_Samurai\SourceFiles\RS"

def convertUnwrapAndExport(objectName):
    
    # import the object
    objectPath = os.path.join(path_of_objects_to_convert, objectName)
    importedObject = importAndSelect(objectPath)

    # enter object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # set the scale
    bpy.ops.transform.resize(value=(1, 1, 1))
    
    # change the texture from fileXYZ to actual texture
    mat = bpy.context.view_layer.objects.active.active_material
    texture_node = changeTexture(mat)
    if not texture_node:
        # skipping this object because it doesnt have a texture node that we could read the color from
        # altough you could add a node here
        return False;
    
    # convert the texture uv mapped color to a material color
    couldAssign = assignColorToFaces(importedObject, texture_node.image)
    if not couldAssign:
        return False;
    
    # smart uv unwrap objects
    unwrapObjects()
    
    # export to gltf with name
    export(importedObject.name)
    
    bpy.context.view_layer.update()
    return True

def importAndSelect(objectPath):
    # import the fbx
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.import_scene.fbx(filepath=objectPath)
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.context.selected_objects[0].select_set(True)
    return bpy.context.selected_objects[0]

def changeTexture(mat):
    mat.use_nodes = True
    texture_nodes = find_nodes_by_type(mat, "TEX_IMAGE")
    if not texture_nodes:
        return False
    texture_node = texture_nodes[0]
    texture_node.image.name = texture
    texture_node.image.filepath = texture
    return texture_node

def find_nodes_by_type(material, node_type):
    node_list = []
    if material.use_nodes and material.node_tree:
            for n in material.node_tree.nodes:
                #print(n.type)
                if n.type == node_type:
                    node_list.append(n)
   
    return node_list

def assignColorToFaces(importedObject, image):
    #switch to edit mode
    bpy.ops.object.mode_set(mode='EDIT')
    
    # get the bmesh data
    me = importedObject.data
    importedObjectBM = bmesh.from_edit_mesh(me)
    if not importedObjectBM:
        return False
    # get the colors used in the mesh
    colorToFacesDict = uvPointsToColors(importedObjectBM, image)
    
    # uv point is over background of image
    if texture_background_color in colorToFacesDict:
        return False
    
    print("found " + str(len(colorToFacesDict.items())) + " colors on " + importedObject.name)
    
    if len(colorToFacesDict.items()) >= 1:
        index = 0
        # assign the materials by color
        for color, faces in colorToFacesDict.items():
            if(index != 0):
                bpy.ops.object.material_slot_add()
            
            #create a new material 
            materialName = importedObject.name + "_Mat_%i" % index
            material = createMaterialWithColor(materialName, color)
            
            # enter face select mode
            bpy.context.tool_settings.mesh_select_mode = [False, False, True]
            #deselect all
            bpy.ops.mesh.select_all(action='DESELECT')
            
            for face in faces:
                # select faces per color
                face.select = True
            
            print ("assigning material '" + materialName + "' to Slot " + str(index+1))
            bpy.context.object.active_material_index = index
            bpy.context.object.active_material = material
            
            print ("assigning selected faces to Slot " + str(index+1))
            bpy.ops.object.material_slot_assign()
            index += 1
    else:
        print("no colors found, skipping")
        return False
     
    # return to object mode
    bpy.ops.object.mode_set(mode='OBJECT')
    return True

    
def uvPointsToColors(importedObjectBM, image):
    im = Image.open(texture)
    px = im.load()
    im = im.convert('RGB')

    uv_layer = importedObjectBM.loops.layers.uv.verify()
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.data.scenes["Scene"].tool_settings.use_uv_select_sync = True
    bpy.ops.mesh.select_mode(type='FACE')
        
    colorToFacesDict = {}
    for face in importedObjectBM.faces:
        for loop in face.loops:
            uv = loop[uv_layer]
            color = uvToColor(uv.uv, image, im)
            
            if color in colorToFacesDict:
                values = colorToFacesDict[color]
                if values.count(face) == 0:
                    values.append(face)
                    colorToFacesDict[color] = values
            else:
                colorToFacesDict[color] = [face]
    #bpy.ops.object.mode_set(mode='OBJECT')
    return colorToFacesDict

def uvToColor(uv, image, im):
    width = image.size[0]
    height = image.size[1]
    
    x = width * uv.x
    y = height - (height * uv.y)
    
    if x < 0:
        x = 0
    if x >= width:
        x = width - 1
        
    if y < 0:
        y = 0
    if y >= height:
        y = height - 1
    
    coord = x,y
    
    color = im.getpixel(coord)
    return color


def createMaterialWithColor(materialName, color):
    print("creating material: "+ materialName)
    color = normalizeColor(color)
    
    material = bpy.data.materials.new(name=materialName)
    material.use_nodes = True            
    principled_node = material.node_tree.nodes['Principled BSDF']            
    # set color
    principled_node.inputs[0].default_value = color
    # set metallic to 0.5
    principled_node.inputs[6].default_value = 0.5
    # set specular to 1
    principled_node.inputs[7].default_value = 1
    # set roughness to 0.735495
    principled_node.inputs[9].default_value = 0.735495
    return material


def normalizeColor(color):
    color = tuple(ti/255 for ti in color)
    color = tuple(srgb_to_linearrgb(ti) for ti in color)
    color = color + (1,)
    return color

def srgb_to_linearrgb(c):
    if   c < 0:       
        return 0
    elif c < 0.04045: 
        return c/12.92
    else:             
        return ((c+0.055)/1.055)**2.4

def unwrapObjects():
    print("uv unwrapping object")
    
    # Select all objects
    bpy.ops.object.select_all(action='SELECT')
    
    # Get all objects in selection
    selection = bpy.context.selected_objects

    # Get the active object
    active_object = bpy.context.active_object

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    for obj in selection:
        # Select each object
        obj.select_set(True)
        # Make it active
        bpy.context.view_layer.objects.active = obj
        # Toggle into Edit Mode
        bpy.ops.object.mode_set(mode='EDIT')
        # Select the geometry
        bpy.ops.mesh.select_all(action='SELECT')
        # Call the smart project operator
        bpy.ops.uv.smart_project()
        # Toggle out of Edit Mode
        bpy.ops.object.mode_set(mode='OBJECT')
        # Deselect the object
        obj.select_set(False)

    # Restore the selection
    for obj in selection:
        obj.select_set(True)

    # Restore the active object
    bpy.context.view_layer.objects.active = active_object
    
def export(objectName):
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    exportPath = os.path.join(output_path, objectName)
    bpy.ops.export_scene.gltf(filepath=exportPath)


conversions = 0
failedConversions = []
objects_to_convert = [f for f in listdir(path_of_objects_to_convert) if isfile(join(path_of_objects_to_convert, f))]
for object in objects_to_convert:
    # cleanup workspace    
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    
    
    print("converting: " + object)
    couldConvert = convertUnwrapAndExport(object)
    if not couldConvert:
        failedConversions.append(object)
    else:
        conversions += 1
        
print("converted " + str(conversions) + "/" + str(len(objects_to_convert)) + " objects")
    
# display any conversions that failed
if failedConversions != []:   
    print("failed to convert: " +  str(failedConversions))




    