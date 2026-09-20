"""独立测试骨骼、约束、UV 和节点的原子命令，而不只测试复合 recipe。"""
import bpy
from scripts.harness.runtime import build_registry

registry = build_registry(bpy)


def call(command, **arguments):
    return registry.dispatch(command, arguments)["result"]


mesh = call("object.create_mesh", name="AtomicMesh", primitive="cube")
ref = {"objectId": mesh["objectId"]}
selection = call("mesh.select", **ref, method="indices", vertices=list(range(8)),
                 edges=list(range(12)), faces=list(range(6)))
call("object.set_display", **ref, displayType="WIRE", showInFront=True)
call("collection.create", name="AtomicCollection")
call("collection.set_visibility", name="AtomicCollection", viewport=False, render=False)
call("uv.mark_seams", selection=selection)
call("uv.unwrap", selection=selection)
call("uv.pack", selection=selection)
assert call("uv.inspect", **ref)["hasUV"]
arm = call("rig.create_armature", name="AtomicRig", bones=[
    {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
])
arm_ref = {"objectId": arm["objectId"]}
control = call("rig.create_control", name="AtomicControl", location=[0, 0, 0], shape="CUBE")
call("rig.bind", mesh=ref, armature=arm_ref)
call("rig.assign_weights", mesh=ref, selection=selection, bone="Root", weight=1)
assert "AtomicMesh" in call("rig.inspect", **arm_ref)["boundMeshes"]
call("constraint.add_bone", armatureId=arm["objectId"], bone="Root",
     type="COPY_TRANSFORMS", name="Follow", targetObjectId=control["objectId"])
call("constraint.add_object", owner=ref, target=arm_ref, bone="Root", type="CHILD_OF", name="Grip")
call("constraint.keyframe_influence", owner=ref, constraintName="Grip", frame=1, influence=1)
assert bpy.data.objects["AtomicMesh"].constraints["Grip"].influence == 1
call("animation.set_frame_range", start=1, end=48)
assert bpy.context.scene.frame_end == 48
call("geometry_nodes.create_group", object=ref, groupName="AtomicNodes", modifierName="AtomicGeometry",
     inputs=[{"name": "Amount", "type": "FLOAT", "default": 1.0}])
call("geometry_nodes.add_node", groupName="AtomicNodes", nodeType="GeometryNodeMeshCube", name="Cube")
call("geometry_nodes.set_node_input", groupName="AtomicNodes", node="Cube", socket="Size", value=[2, 2, 2])
call("geometry_nodes.connect", groupName="AtomicNodes", fromNode="Cube", fromSocket="Mesh",
     toNode="Group Output", toSocket="Geometry")
call("geometry_nodes.set_modifier_input", object=ref, modifierName="AtomicGeometry", socket="Amount", value=2.0)
assert len(call("geometry_nodes.inspect", groupName="AtomicNodes")["links"]) == 1
call("render.inspect")
print("SUPPLEMENTAL_LOCAL=passed")
