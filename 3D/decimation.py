bl_info = {
    "name" : "Decimation",
    "author" : "Andrey Cherkasov", 
    "blender" : (3, 3, 1),
    "version" : (1, 0, 0),
    "location" : "View3D > Tools > Misc > Vertex Clustering",
    "description" : "Simplifies mesh",
    "category" : "Object",
}

import sys
import bpy
import bmesh
import math
from time import time
from math import radians
from mathutils import Vector

# MeshVertex class wrapper to use it in VertexClustering 
class D_Vertex():
    def __init__ ( self, vertex : bpy.types.MeshVertex ):
        self.v_info = vertex
        self.cell_index = -1
        self.weight = 0
# Cell class to use it in creation of Cell grids in vertex clustering 
class Cell():
    def __init__ ( self ): 

        self.cell_index : int = -1
        self.connected_cells : list[Cell] = []
        self.vertices : list[D_Vertex] = []
        self.representative_vertex_location : Vector = None

    def get_representative_vertex_location ( self ): 
        if self.representative_vertex_location is None: 
            self.update_representative_vertex_location()
            return self.representative_vertex_location
        return self.representative_vertex_location

    def update_representative_vertex_location ( self ): 
        weight_sum = 0
        location = Vector()
        # If cell contains only one verticle, it becomes the representative
        if len( self.vertices ) == 1:
            self.representative_vertex_location = Vector (self.vertices[0].v_info.co)
            return self.representative_vertex_location

        for vertex in self.vertices:
            location += vertex.weight * Vector(vertex.v_info.co)  
            weight_sum += vertex.weight
        self.representative_vertex_location = location / weight_sum
        return self.representative_vertex_location

def triangulate_mesh ( bm : bmesh.types.BMesh ):
        bmesh.ops.triangulate ( bm, faces = bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY' )

# Use a blener obj.bound_box and pick all neccesary stuff from it 
def get_object_bounds ( object : bpy.types.Object):

    bb = object.bound_box 
    minX = bb[0][0] # LoX 
    minY = bb[0][1] # LoY
    minZ = bb[0][2] # LoZ 
    maxX = bb[6][0] # HiX
    maxY = bb[6][1] # HiY
    maxZ = bb[6][2] # HiZ 
    
    return ( (minX, maxX), (minY, maxY), (minZ, maxZ ) )

def clamp ( val : float, lo : float, hi : float ): 
    if val > hi: 
        return hi 
    elif val < lo: 
        return lo
    return val 

def GetAngleBetweenVectors ( v1 : Vector, v2 : Vector ):
    v1_l = v1.length
    v2_l = v2.length
    if math.isclose(0, v1_l) or math.isclose(0, v2_l): # prevent divide by zero 
        return 0
    cos_theta = clamp ( ( v1 . dot  ( v2 ) ) / ( v1_l * v2_l ), -1, 1 ) # prevent acos in undefined region 
    return math.acos(cos_theta)  

# Claculate max angle between vertex and all vertex linked edges 
def CalculateVertexMaxAngle ( vertex : D_Vertex ) -> float: 
    res = sys.float_info.min
    linked_edges = vertex.v_info.link_edges
    count = len( linked_edges )
    # Find the maximum angle between all pairs of vectors bounded by vertex
    for i in range( count-1 ):
        for j in range( i+1, count ):
            v1 = Vector ( (linked_edges[i].verts[0].co.x, linked_edges[i].verts[0].co.y, linked_edges[i].verts[0].co.z) )
            v2 = Vector ( (linked_edges[i].verts[1].co.x, linked_edges[i].verts[1].co.y, linked_edges[i].verts[1].co.z) )
            v3 = Vector ( (linked_edges[j].verts[0].co.x, linked_edges[j].verts[0].co.y, linked_edges[j].verts[0].co.z) )
            v4 = Vector ( (linked_edges[j].verts[1].co.x, linked_edges[j].verts[1].co.y, linked_edges[j].verts[1].co.z) )     
            s1 = v1 - v2 
            s2 = v3 - v4 
            angle = GetAngleBetweenVectors ( s1, s2 )
            if angle > res: 
                res = angle             
    return res

class Decimation_Logger: 
    def Log ( self, message : str ) -> None: 
        print ( message )  

    def ShowMessageBox(self,message= "", title = "Message box", icon = 'INFO') -> None: 
        def draw (self, context): 
            self.layout.label (text=message)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


class Decimation_Profiler:
    
    m_StartTime : float = None
    m_IsProfiling : bool = False
    m_TotalTime = 0  
    def StatBegin( self ):
        if not self.m_IsProfiling: 
            self.m_StartTime = time() 
            self.m_IsProfiling = True
    def StatEnd ( self ) -> float:
        if self.m_IsProfiling: 
            self.m_IsProfiling = False
            time_passed = time() - self.m_StartTime
            self.m_TotalTime += time_passed 
            return time_passed
    def GetTotalTime ( self ) -> float: 
        return self.m_TotalTime

    def Reset( self ): 
        self.m_IsProfiling = False 
        self.m_StartTime = 0
        self.m_TotalTime = 0

class Decimation_UI ( bpy.types.Panel ): 
    bl_label = "Decimation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_context = "objectmode"

    def draw ( self, context ): 
        layout = self.layout
        scene = context.scene
        row = layout.row(align=True)
        row.prop ( scene, "Unit" )
        row = layout.row(align=True)
        row.prop ( scene, "DecimationThreshold")
        row = layout.row(align=True)
        row.operator ( "mesh.simplification" )

class Decimation (bpy.types.Operator):
    """Mesh simplification script"""      # Use this as a tooltip for menu items and buttons.
    bl_idname = "mesh.simplification"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Decimate"         # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    bpy.types.Scene.Unit = bpy.props.FloatProperty ( 
        name = "Unit", 
        description = "Decimation level ( cell size )", 
        default = 5, 
       min = 0.1, 
        max = 100 
    )
    bpy.context.scene.Unit = 5

    bpy.types.Scene.DecimationThreshold = bpy.props.FloatProperty (
        name = "DecimationThreshold", 
        description = "Amount of vertices per sqr m for mesh to be decimated", 
        default = 10, 
        min = 0,
        max = 100
    )
    bpy.context.scene.DecimationThreshold = 10

    m_unit = 0.1 
    m_decimation_threshold = 20
    m_logger = Decimation_Logger()
    m_profiler = Decimation_Profiler() 

    def execute(self, context):        # execute() is called when running the operator.

        # The original script
        scene = context.scene
        if "Unit" in scene: 
            self.m_unit = scene['Unit']/100 # convert from meters to centimeters 
        if "DecimationThreshold" in scene: 
            self.m_decimation_threshold = scene['DecimationThreshold'] # convert from meters to centimeters 
        self.m_logger.Log ( "-------------Starting decimation with unit = " + str ( self.m_unit ) + " and threshold = " + str ( self . m_decimation_threshold ) )
        selected_objects = bpy.context.selected_editable_objects
        # Filter out objects that won't be decimated 
        filtered_objects = self.filter_objects_to_decimate( selected_objects )
        if len ( filtered_objects ) == 0:
            self.m_profiler.Reset()
            return {'FINISHED'}
        # Convert objects to meshes
        meshes = self.objects_to_meshes ( filtered_objects )
        # Vertex clustering works only on triangulated objects
        self.triangulate_meshes ( meshes )
        # We should know objects bounds to make a grid cell
        objects_bounds = self.get_objects_bounds ( filtered_objects )
        # Make a wrapper for all vertecis of all objects for weightening and synthesize
        vertex_lists = self.create_vertex_lists ( meshes )
        # Create a cell grid for each mesh. Each cell will be trimmed to single vertex 
        cell_grids = self.create_cell_grids ( vertex_lists, objects_bounds )
        # Create objects to push decimated geometry to 
        decimated_objects = self.create_decimated_objects ( filtered_objects )
        # Push geometry from cell grids to objects
        self.push_simplified_geometry_to_objects ( decimated_objects, meshes, cell_grids, vertex_lists )
        self.free_meshes ( meshes )
        self.m_logger.Log ("-------------Finished decimation. Total time: " + str ( self.m_profiler.GetTotalTime() ) )
        self.m_profiler.Reset() 
        return {'FINISHED'}        # Lets Blender know the operator finished successfully. 

    def free_meshes ( self, meshes : list[bmesh.types.BMesh] ): 
        for mesh in meshes:
            mesh.free()  

    # Connects decimated mesh vertices into faces. 
    def connect_mesh_simplified_geometry ( self, mesh : bmesh.types.BMesh, orig_mesh : bmesh.types.BMesh, orig_vertex_list : list [ D_Vertex], mapped_cells ):
        new_faces_cell_indecis = []
        for face in orig_mesh.faces: 
            face_orig_indecis = [ v.index for v in face.verts]
            face_orig_vertices = [ orig_vertex_list [ i ] for i in face_orig_indecis ]
            face_cell_indecis = [ v.cell_index for v in face_orig_vertices ]
            face_cell_indecis_sorted = face_cell_indecis
            # spent here 2 hours figuring out that ( list_sorted = list.sort() ) == None (:
            face_cell_indecis_sorted.sort()
            if len ( set ( face_cell_indecis ) ) != len ( face_cell_indecis ) or face_cell_indecis_sorted in new_faces_cell_indecis: 
                continue
            face_new_vertices = [ mapped_cells[i] for i in face_cell_indecis ] 
            new_faces_cell_indecis . append ( face_cell_indecis_sorted )
            mesh.faces . new ( face_new_vertices ) 
                

    # Generates new mesh and pushes all representative vertices of the mesh cell grid into mesh, then connects it into faces 
    def push_simplified_geometry_to_object ( self, decimated_object : bpy.types.Object, orig_mesh : bmesh.types.BMesh, cell_grid, vertex_list : list [ D_Vertex ] ): 
        bm = bmesh.new()
        bm.from_mesh ( decimated_object.data )
        mapped_cells = {} 
        for key in cell_grid:
            vertex_location = cell_grid[key].get_representative_vertex_location()
            vertex = bm.verts.new( vertex_location )
            d_vertex = D_Vertex ( vertex )
            d_vertex.cell_index = cell_grid[key].cell_index
            mapped_cells [ cell_grid[key].cell_index ] = vertex # used to find cells while connecting geometry 
        self.connect_mesh_simplified_geometry ( bm, orig_mesh, vertex_list, mapped_cells )
        bm.to_mesh ( decimated_object.data )
        bm.free() 
        return vertex_list
    
    # Generates new meshes and pushes all representative vertices of all meshes cell grids into new meshes, then connects it into faces 
    def push_simplified_geometry_to_objects ( self, decimated_objects : list[bpy.types.Object], orig_meshes : list[bmesh.types.BMesh], cell_grids, vertex_lists : list[list [ D_Vertex ]] ):

        assert ( len ( decimated_objects ) == len ( orig_meshes ) == len ( cell_grids ) == len ( vertex_lists ) )
        self.m_profiler.StatBegin()
        for decimated_object, orig_mesh, cell_grid, vertex_list in zip(decimated_objects, orig_meshes, cell_grids, vertex_lists): 
            self. push_simplified_geometry_to_object ( decimated_object, orig_mesh, cell_grid, vertex_list )
        self.m_logger.Log ( "Pushing simplified geometry took: " + str ( self.m_profiler.StatEnd() ) + " seconds" )

    # Allocate new blender scene objcect and give at correct transform and name 
    def create_decimated_object ( self, object ): 
        mesh = bpy.data.meshes.new ( object.name )
        obj = bpy.data.objects.new ( mesh.name + "_decimated", mesh )
        obj.location = object.location
        obj.rotation_euler = object.rotation_euler
        obj.scale = object.scale
        return obj

    # Create new collection for the decimated objects and create them by one 
    def create_decimated_objects ( self, objects : list[bpy.types.Object] ) -> list[object]:
        self.m_profiler.StatBegin() 
        decimated_objects = []
        collection = bpy.data.collections.new( name = "Decimated Objects")
        bpy.context.scene.collection.children.link(collection)
        for object in objects:
            obj = self.create_decimated_object ( object )
            collection.objects.link ( obj ) 
            decimated_objects . append ( obj )
        self.m_logger.Log ("Objects creation took: " + str ( self.m_profiler.StatEnd() ) + " seconds" )
        return decimated_objects


    # Construct a BMesh object from object geometry     
    def object_to_mesh ( self, object : bpy.types.Object ) -> bmesh.types.BMesh: 
        bm = bmesh.new()
        bm . from_mesh ( object. data )
        return bm  
    
    # Constructs a list of BMesh objects from objects 
    def objects_to_meshes ( self, objects : list[bpy.types.Object] ) -> list[bmesh.types.BMesh]:
        self.m_profiler.StatBegin()
        meshes = [] 
        for object in objects:
            mesh = self.object_to_mesh ( object ) 
            meshes.append ( mesh )
        self.m_logger.Log ( "Converting objects to meshes took: " + str (self.m_profiler.StatEnd()) + " seconds") 
        return meshes

    # Calculates a cell location by truncating the vertex coordinates using object bounderies 
    def calculate_cell_location ( self, vertex : D_Vertex, unit : float, object_bounds : tuple ):
        x_min = object_bounds[0][1] # min X 
        y_min = object_bounds[1][1] # min Y 
        z_min = object_bounds[2][1] # min Z 
        x_len = vertex.v_info.co.x - x_min
        y_len = vertex.v_info.co.y - y_min
        z_len = vertex.v_info.co.z - z_min
        x_component = x_min + unit * int( math.floor( x_len / unit ) )
        y_component = y_min + unit * int( math.floor( y_len / unit ) )
        z_component = z_min + unit * int( math.floor( z_len / unit ) )
        return Vector ( ( round( x_component, 10 ), round( y_component, 10 ), round( z_component, 10 ) ) )


    # Creates a cell grid in form of a dictionary where key is the cell coordinates and value is Cell object. 
    def create_cell_grid ( self, vertex_list : list [D_Vertex], object_bounds ): 
        cell_grid = {}
        cell_idx = 0
        max_bound_length = max( [object_bounds[0][1] - object_bounds[0][0], object_bounds[1][1] - object_bounds[1][0], object_bounds[2][0] - object_bounds[2][1]] )
        object_unit = self.m_unit * max_bound_length
        for vertex in vertex_list: 
            cell_location = self.calculate_cell_location ( vertex, object_unit, object_bounds )
            # Makes vector immutable. Without it it can be used in dict
            cell_location.freeze() 
            if cell_location not in cell_grid:
                new_cell = Cell() 
                new_cell.cell_index = cell_idx 
                cell_idx += 1
                cell_grid [ cell_location ] = new_cell 
            vertex.cell_index = cell_grid [ cell_location ] . cell_index
            cell_grid [ cell_location ].vertices.append ( vertex )
        return cell_grid

    # Creates a list of cell grids for each vertex list in entry list 
    def create_cell_grids ( self, vertex_lists : list[list[D_Vertex]], objects_bounds ): 
        self.m_profiler.StatBegin() 
        cell_grids = [] 
        for vertex_list, object_bounds  in zip ( vertex_lists, objects_bounds ) :
            cell_grids . append ( self.create_cell_grid ( vertex_list, object_bounds ) )
        self.m_logger.Log ( "Cell grids building took: " + str ( self.m_profiler.StatEnd() ) + " seconds" ) 
        return cell_grids

    # Propability to see a vertex from random angle 
    def grade_vertex_impl ( self, vertex : D_Vertex ): 
        return math.cos ( CalculateVertexMaxAngle ( vertex ) / 2 )

    # Grade vertex using pimpl 
    def grade_vertex ( self, vertex : D_Vertex ): 
        vertex.weight = self.grade_vertex_impl ( vertex )    

    # Grade each vertex in list 
    def grade_vertex_list ( self, vertex_list : list[D_Vertex] ): 
        for vert in vertex_list: 
            self.grade_vertex ( vert ) 
    # Grade each vertex in each list of vertex_lists 
    def grade_vertex_lists ( self, vertex_lists ): 
        for vertex_list in vertex_lists: 
            self.grade_vertex_list ( vertex_list )


    # sum-up the areas of all faces in the mseh
    def get_object_surface_area ( self, object : bpy.types.Object ):
        bm = bmesh.new()
        bm.from_mesh ( object.data )
        area = sum ( f.calc_area() for f in bm.faces ) # to square meters
        bm.free() 
        return area  

    # heuristics: count number of vertices on square cm of surface area of the mesh      
    def is_object_should_be_decimated ( self, object : bpy.types.Object ):
        surface_area = self.get_object_surface_area ( object )
        self.m_logger.Log ("Object: " + str ( object.name ) + " surface area = " + str ( surface_area ) )
        self.m_logger.Log ("Object: " + str ( object.name ) + " # of vertices = " + str ( len ( object.data.vertices ) ) )
        ratio =  ( len (object.data.vertices) / ( surface_area ) )  # To verts / square cm  
        self.m_logger.Log ("Object: " + str ( object.name ) + " vertecis/surface ratio = " + str ( ratio ) )
        return ratio >= self.m_decimation_threshold

    # filter out all objects that won't be decimated 
    def filter_objects_to_decimate ( self, objects : list[bpy.types.Object] ):
        self.m_profiler.StatBegin()  
        objects_to_decimate = [] 
        for object in objects: # object must be mesh and should pass heuristic criteria
            if object.type != 'MESH':
                self.m_logger.ShowMessageBox ("Object: " + object.name + " won't be decimated. Reason: not a mesh")
                continue 
            if not self.is_object_should_be_decimated ( object ):
                self.m_logger.ShowMessageBox ("Object: " + object.name + " won't be decimated. Reason: to simplified with given parameters")
                continue
            objects_to_decimate . append ( object )
        self.m_logger.Log ( "Filtering took: " + str ( self.m_profiler.StatEnd() )+ " seconds" )
        return objects_to_decimate

    # Create a list of wrapper D_Vertex around MeshVertex to use it for distribution into cells 
    def create_vertex_list ( self, mesh : bmesh.types.BMesh ): 
        vertex_list = []
        for vert in mesh.verts:
            d_v = D_Vertex ( vert )
            vertex_list . append ( d_v )
        return vertex_list

    # Create vertex list wrapper for each mesh then grade them 
    def create_vertex_lists ( self, meshes : list[bmesh.types.BMesh] ):
        self.m_profiler.StatBegin() 
        vertex_lists = []
        for mesh in meshes: 
            vertex_lists . append ( self.create_vertex_list ( mesh ) )
        self.grade_vertex_lists ( vertex_lists )
        self.m_logger. Log ( "Vertex lists building took: " + str ( self.m_profiler.StatEnd() ) + " seconds") 
        return vertex_lists

    # Create a list of object bounds for each mesh in entry list 
    def get_objects_bounds ( self, objects_meshes ):
        objects_bounds = [] 
        for object in objects_meshes:
            objects_bounds.append ( get_object_bounds ( object ) ) 
        return objects_bounds

    # Use blender function to triangualte each mesh in entry list 
    def triangulate_meshes ( self, meshes : list[bmesh.types.BMesh] ):
        self.m_profiler.StatBegin()
        for mesh in meshes: 
            triangulate_mesh ( mesh )
        self.m_logger.Log ( "Meshes triangulationg took: " + str ( self.m_profiler.StatEnd() ) + " seconds" )


classes = [Decimation, Decimation_UI]
def register():
    for cl in classes: 
        bpy.utils.register_class( cl )

def unregister():
    for cl in classes:
        bpy.utils.unregister_class( cl )
    
    

# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
