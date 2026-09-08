import mujoco
import numpy as np

ROBOT_XML = r"D:\GMR_WORK\assets\unitree_g1\g1_29dof.xml"

model = mujoco.MjModel.from_xml_path(ROBOT_XML)

print("model.nq =", model.nq)
print("model.nv =", model.nv)
print("model.njnt =", model.njnt)
print()

for j in range(model.njnt):
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j)
    jtype = model.jnt_type[j]
    qadr = model.jnt_qposadr[j]
    axis = model.jnt_axis[j]
    limited = model.jnt_limited[j]
    jrng = model.jnt_range[j]

    print(f"{j:02d} | name={name:35s} | type={jtype} | qpos_adr={qadr:2d} | axis={axis} | limited={limited} | range={jrng}")