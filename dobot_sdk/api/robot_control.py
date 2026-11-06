# Copyright (c) 2026 Dobot
# Licensed under the MIT License

"""Robot Control module - status queries, kinematics calculations, reachability checks, and robot control"""

from typing import Tuple, Sequence
from ..core.connection import DobotConnection


class RobotControl:
    """Robot control module - status queries, kinematics calculations, reachability checks, logging, and script control"""

    def __init__(self, connection: DobotConnection):
        self.connection = connection

    def _send_cmd(self, command: str) -> str:
        """Send a command and receive the response"""
        return self.connection.send_receive_text(command)

    # ==================== Control mode and power====================

    def RequestControl(self) -> str:
        """
        RequestControl switches the device control mode to TCP mode (immediate command)
        
        Notes:
        - Other TCP commands can only be executed in TCP mode
        - TCP mode can only be selected when the robot is powered off or disabled, and is not paused or in a brake-released state
        - After calling this interface, commands such as EnableRobot and motion commands can be executed
        
        Returns:
            str: ErrorID,{},RequestControl();
        """
        return self._send_cmd("RequestControl()")

    def PowerOn(self) -> str:
        """PowerOn powers on the robot (immediate command)"""
        return self._send_cmd("PowerOn()")

    def EnableRobot(self, load: float = 0.0, **kwargs) -> str:
        """
        EnableRobot enables the robot (immediate command)

        Signature: EnableRobot(load,centerX,centerY,centerZ,isCheck)

        Args:
            load: Payload weight (kg)
            centerX: Payload center-of-gravity X coordinate (mm)
            centerY: Payload center-of-gravity Y coordinate (mm)
            centerZ: Payload center-of-gravity Z coordinate (mm)
            isCheck: Whether to check the payload (0 = do not check, 1 = check)
        """
        if load == 0.0:
            cmd = "EnableRobot()"
        elif 'centerX' not in kwargs:
            cmd = f"EnableRobot({load:.6f})"
        else:
            cx = kwargs.get('centerX', 0.0)
            cy = kwargs.get('centerY', 0.0)
            cz = kwargs.get('centerZ', 0.0)
            check = kwargs.get('isCheck', 0)
            cmd = f"EnableRobot({load:.6f},{cx:.6f},{cy:.6f},{cz:.6f},{check})"
        return self._send_cmd(cmd)

    def DisableRobot(self) -> str:
        """DisableRobot disables the robot (immediate command)"""
        return self._send_cmd("DisableRobot()")

    def ClearError(self) -> str:
        """ClearError clears robot alarms (immediate command)"""
        return self._send_cmd("ClearError()")

    # ==================== Motion control ====================

    def RunScript(self, script_name: str) -> str:
        """
        RunScript runs the specified project (immediate command)
        
        Args:
            script_name: Script file name        """
        return self._send_cmd(f"RunScript(\"{script_name}\")")

    def Stop(self) -> str:
        """Stop stops motion (or the currently running project) (immediate command)"""
        return self._send_cmd("Stop()")

    def Pause(self) -> str:
        """Pause pauses motion (or the currently running project) (immediate command)"""
        return self._send_cmd("Pause()")

    def Continue(self) -> str:
        """Continue resumes motion (or a paused project) (immediate command)"""
        return self._send_cmd("Continue()")

    def EmergencyStop(self, mode: int) -> str:
        """
        EmergencyStop triggers an emergency stop (immediate command)
        
        Args:
            mode: Emergency-stop mode: 1 engages the emergency stop; 0 releases it.
        """
        if mode not in [0, 1]:
            raise ValueError("mode must be 0 or 1")
        return self._send_cmd(f"EmergencyStop({mode})")

    # ==================== Brakes and drag mode====================

    def BrakeControl(self, axis_id: int, value: int) -> str:
        """
        BrakeControl controls the brake of the specified joint (immediate command)        
        Args:
            axis_id: Joint number (1-6)
            value: 0 = brake engaged, 1 = brake released
        """
        if not 1 <= axis_id <= 6:
            raise ValueError("Joint number must be between 1 and 6")
        if value not in [0, 1]:
            raise ValueError("value must be 0 or 1")
        return self._send_cmd(f"BrakeControl({axis_id},{value})")

    def StartDrag(self) -> str:
        """StartDrag puts the robot into joint drag mode (immediate command)"""
        return self._send_cmd("StartDrag()")

    def StopDrag(self) -> str:
        """StopDrag exits drag mode (immediate command)"""
        return self._send_cmd("StopDrag()")

    def DragSensitivity(self, index: int, value: int) -> str:
        """
        DragSensitivity sets drag sensitivity (immediate command)
        
        Args:
            index: Axis index, range [0, 6]. 0 sets the same sensitivity for all axes. 1–6 set the sensitivity for axes J1–J6, respectively.
            value: Drag sensitivity. Lower values result in greater resistance during dragging. Range: [1, 90].
        """
        if not 0 <= index <= 6:
            raise ValueError("Axis index must be between 0 and 6")
        if not 1 <= value <= 90:
            raise ValueError("Drag sensitivity must be between 1 and 90")
        return self._send_cmd(f"DragSensitivity({index},{value})")

    # ==================== Speed and acceleration settings ====================

    def SpeedFactor(self, factor: int) -> str:
        """
        SpeedFactor sets the global speed factor (immediate command)
        
        Args:
            factor: Speed factor (1-100)
        """
        if not 1 <= factor <= 100:
            raise ValueError("Speed factor must be between 1 and 100")
        return self._send_cmd(f"SpeedFactor({factor})")

    def AccJ(self, acc: int) -> str:
        """
        AccJ sets the acceleration factor for joint motion (immediate command)
        
        Args:
            acc: Acceleration factor (1-100)
        """
        if not 1 <= acc <= 100:
            raise ValueError("Acceleration factor must be between 1 and 100")
        return self._send_cmd(f"AccJ({acc})")

    def AccL(self, acc: int) -> str:
        """
        AccL sets the acceleration factor for linear and circular motion (immediate command)
        
        Args:
            acc: Acceleration factor (1-100)
        """
        if not 1 <= acc <= 100:
            raise ValueError("Acceleration factor must be between 0 and 100")
        return self._send_cmd(f"AccL({acc})")

    def VelJ(self, vel: int) -> str:
        """
        VelJ sets the speed factor for joint motion (immediate command)
        
        Args:
            vel: Speed factor (1-100)
        """
        if not 1 <= vel <= 100:
            raise ValueError("Speed factor must be between 0 and 100")
        return self._send_cmd(f"VelJ({vel})")

    def VelL(self, vel: int) -> str:
        """
        VelL sets the speed factor for linear and circular motion (immediate command)
        
        Args:
            vel: Speed factor (1-100)
        """
        if not 1 <= vel <= 100:
            raise ValueError("Speed factor must be between 0 and 100")
        return self._send_cmd(f"VelL({vel})")

    def CP(self, value: int) -> str:
        """
        CP sets the blending factor (immediate command)
        
        Args:
            value: Blending factor (0-100)
        """
        if not 0 <= value <= 100:
            raise ValueError("Blending factor must be between 0 and 100")
        return self._send_cmd(f"CP({value})")

    # ==================== Coordinate system settings====================

    def User(self, index: int) -> str:
        """
        User sets the global user coordinate system (queued command)        
        Args:
            index: User coordinate system index(0-50)
        """
        if not 0 <= index <= 50:
            raise ValueError("User coordinate system index must be between 0 and 50")
        return self._send_cmd(f"User({index})")

    def SetUser(self, index: int, pose: Sequence[float], type: int = None) -> str:
        """
        SetUser modifies the specified user coordinate system (immediate command)
        
        Args:
            index: User coordinate system index(1-50)
            pose: six coordinate values[x,y,z,rx,ry,rz]
            type: Whether the coordinate-system change takes effect globally. 0: the change applies only while the current project is running. 1: the controller saves the changed coordinate system.
        """
        if not 1 <= index <= 50:
            raise ValueError("User coordinate system index must be between 1 and 50")
        if len(pose) != 6:
            raise ValueError("pose must contain 6 values")
        pose_str = "{" + ",".join([f"{v:.6f}" for v in pose]) + "}"
        if type is not None:
            if type not in [0, 1]:
                raise ValueError("type must be 0 or 1")
            return self._send_cmd(f"SetUser({index},{pose_str},{type})")
        return self._send_cmd(f"SetUser({index},{pose_str})")

    def CalcUser(self, index: int, matrix_direction: int, offset: Sequence[float]) -> str:
        """
        CalcUser calculates the user coordinate system (immediate command)
        Args:
            index: User coordinate system index(0-50)
            matrix_direction: Calculation direction (1 = left multiplication, rotate relative to the base coordinate system; 0 = right multiplication, rotate relative to the coordinate system itself)
            offset: Offset values [x,y,z,rx,ry,rz]
        """
        if not 0 <= index <= 50:
            raise ValueError("User coordinate system index must be between 0 and 50")
        if matrix_direction not in [0, 1]:
            raise ValueError("matrix_direction must be 0 or 1")
        if len(offset) != 6:
            raise ValueError("offset must contain 6 values")
        offset_str = "{" + ",".join([f"{v:.6f}" for v in offset]) + "}"
        return self._send_cmd(f"CalcUser({index},{matrix_direction},{offset_str})")

    def Tool(self, index: int) -> str:
        """
        Tool sets the global tool coordinate system (queued command)        
        Args:
            index: Tool coordinate system index(0-50)
        """
        if not 0 <= index <= 50:
            raise ValueError("Tool coordinate system index must be between 0 and 50")
        return self._send_cmd(f"Tool({index})")

    def SetTool(self, index: int, pose: Sequence[float], type: int = None) -> str:
        """
        SetTool modifies the specified tool coordinate system (immediate command)
        
        Args:
            index: Tool coordinate system index(1-50)
            pose: six coordinate values[x,y,z,rx,ry,rz]
            type: Whether the coordinate-system change takes effect globally. 0: the change applies only while the current project is running. 1: the controller saves the changed coordinate system.
        """
        if not 1 <= index <= 50:
            raise ValueError("Tool coordinate system index must be between 1 and 50")
        if len(pose) != 6:
            raise ValueError("pose must contain 6 values")
        pose_str = "{" + ",".join([f"{v:.6f}" for v in pose]) + "}"
        if type is not None:
            if type not in [0, 1]:
                raise ValueError("type must be 0 or 1")
            return self._send_cmd(f"SetTool({index},{pose_str},{type})")
        return self._send_cmd(f"SetTool({index},{pose_str})")

    def CalcTool(self, index: int, matrix_direction: int, offset: Sequence[float]) -> str:
        """
        CalcTool calculates the tool coordinate system (immediate command)
        Args:
            index: Tool coordinate system index(0-50)
            matrix_direction: Calculation direction (1 = left multiplication, rotate relative to the flange coordinate system; 0 = right multiplication, rotate relative to the coordinate system itself)
            offset: Offset values [x,y,z,rx,ry,rz]
        """
        if not 0 <= index <= 50:
            raise ValueError("Tool coordinate system index must be between 0 and 50")
        if matrix_direction not in [0, 1]:
            raise ValueError("matrix_direction must be 0 or 1")
        if len(offset) != 6:
            raise ValueError("offset must contain 6 values")
        offset_str = "{" + ",".join([f"{v:.6f}" for v in offset]) + "}"
        return self._send_cmd(f"CalcTool({index},{matrix_direction},{offset_str})")

    # ==================== Payload settings ====================

    def SetPayload(self, load_or_name, *args, **kwargs) -> str:
        """
        SetPayload sets the robot end-effector payload (queued command)

        Supports two calling formats (matching the documentation):
        Method 1: SetPayload(load, x, y, z)
        Method 2: SetPayload(name)

        Backward compatibility is also maintained:SetPayload(load, center=[x,y,z])

        Args:
            load_or_name:
                - float: Payload weight (kg) → method 1
                - str: Name of a preset payload configuration → method 2
            x (optional, float): End-effector payload offset along the X axis (mm)
            y (optional, float): End-effector payload offset along the Y axis (mm)
            z (optional, float): End-effector payload offset along the Z axis (mm)
            center (optional, Sequence[float]): For backward compatibility, payload center of gravity [x, y, z]
            preset_name (optional, str): For backward compatibility, If provided, the previous two arguments are ignored; equivalent to method 2
        """
        center = kwargs.get('center', None)
        preset_name = kwargs.get('preset_name', None)

        if isinstance(load_or_name, str):
            return self._send_cmd(f'SetPayload("{load_or_name}")')

        if preset_name is not None:
            return self._send_cmd(f'SetPayload("{preset_name}")')

        load = float(load_or_name)

        x = y = z = None
        if len(args) == 3:
            x, y, z = args
        elif len(args) == 1 and isinstance(args[0], (list, tuple)):
            if len(args[0]) != 3:
                raise ValueError("center list must contain 3 values [x, y, z]")
            x, y, z = args[0]
        elif center is not None:
            if len(center) != 3:
                raise ValueError("center must contain 3 values [x, y, z]")
            x, y, z = center
        elif len(args) != 0:
            raise ValueError("Positional arguments support only SetPayload(load, x, y, z) or SetPayload(load, [x, y, z])")

        if x is not None and y is not None and z is not None:
            return self._send_cmd(f"SetPayload({load:.6f},{float(x):.6f},{float(y):.6f},{float(z):.6f})")
        return self._send_cmd(f"SetPayload({load:.6f})")

    # ==================== Collision detection settings====================

    def SetCollisionLevel(self, level: int) -> str:
        """
        SetCollisionLevel sets the collision detection level (queued command)        
        Args:
            level: Collision detection level (0–5): 0 disables collision detection; from 1 to 5, higher values mean greater sensitivity
        """
        if not 0 <= level <= 5:
            raise ValueError("Collision detection level must be between 0 and 5")
        return self._send_cmd(f"SetCollisionLevel({level})")

    def SetBackDistance(self, distance: float) -> str:
        """
        SetBackDistance sets the retreat distance after a collision (queued command)
        
        Args:
            distance: Retreat distance after a collision (mm), range [0, 50]
        """
        if not 0 <= distance <= 50:
            raise ValueError("distance must be between 0 and 50 mm")
        return self._send_cmd(f"SetBackDistance({distance:.6f})")

    def SetPostCollisionMode(self, mode: int) -> str:
        """
        SetPostCollisionMode sets the post-collision behavior (queued command)
        Args:
            mode: Post-collision mode
                  0: Disable the robot and stop motion  (defined in the official V4.6.6 documentation)
                  1: Pause motion          (defined in the official V4.6.6 documentation)
                  2: Ignore the collision and continue moving  （⚠️ Extended mode supported by some firmware; not defined in the official V4.6.6 documentation）
        """
        if mode not in [0, 1, 2]:
            raise ValueError("Post-collision mode must be 0, 1, or 2")
        return self._send_cmd(f"SetPostCollisionMode({mode})")

    # ==================== Safety skin and safety zones====================

    def EnableSafeSkin(self, status: int) -> str:
        """
        EnableSafeSkin enables or disables the safety skin function (queued command)
        
        Args:
            status: 0-disabled, 1-enabled        """
        if status not in [0, 1]:
            raise ValueError("status must be 0 or 1")
        return self._send_cmd(f"EnableSafeSkin({status})")

    def SetSafeSkin(self, part: int, sensitivity: int) -> str:
        """
        SetSafeSkin sets the sensitivity of each safety-skin section (queued command)
        
        Args:
            part: Safety-skin section index: 3 = forearm; 4–6 = J4–J6
            sensitivity: Sensitivity level [0, 3]: 0 = off, 1 = low, 2 = medium, 3 = high
        """
        if not (part == 3 or 4 <= part <= 6):
            raise ValueError("part must be 3 (forearm) or 4–6 (J4–J6)")
        if not 0 <= sensitivity <= 3:
            raise ValueError("sensitivity must be between 0 and 3")
        return self._send_cmd(f"SetSafeSkin({part},{sensitivity})")

    def SetSafeWallEnable(self, index: int, status: int) -> str:
        """
        SetSafeWallEnable enables or disables the specified safety wall (queued command)
        
        Args:
            index: Safety wall index            status: 0-disabled, 1-enabled        """
        if status not in [0, 1]:
            raise ValueError("status must be 0 or 1")
        return self._send_cmd(f"SetSafeWallEnable({index},{status})")

    def SetWorkZoneEnable(self, index: int, status: int) -> str:
        """
        SetWorkZoneEnable enables or disables the specified work zone (queued command)        
        Args:
            index: Work zone index
            status: 0-disabled, 1-enabled        """
        if status not in [0, 1]:
            raise ValueError("status must be 0 or 1")
        return self._send_cmd(f"SetWorkZoneEnable({index},{status})")

    # ==================== Status queries====================

    def RobotMode(self) -> str:
        """RobotMode gets the robot's current mode (immediate command)"""
        return self._send_cmd("RobotMode()")

    def GetPose(self, user: int = None, tool: int = None) -> str:
        """
        GetPose gets the robot's current Cartesian coordinates in the specified coordinate system (immediate command)
        
        Args:
            user: User coordinate system index(0-50)
            tool: Tool coordinate system index(0-50)
        """
        has_coord = user is not None or tool is not None
        if has_coord and (user is None or tool is None):
            raise ValueError("user and tool must either both be set or both be omitted")

        if has_coord:
            if not (0 <= user <= 50):
                raise ValueError("user must be between 0 and 50")
            if not (0 <= tool <= 50):
                raise ValueError("tool must be between 0 and 50")
            return self._send_cmd(f"GetPose(user={user},tool={tool})")
        else:
            return self._send_cmd("GetPose()")

    def GetAngle(self) -> str:
        """GetAngle gets the robot's current joint angles (immediate command)"""
        return self._send_cmd("GetAngle()")

    def GetErrorID(self) -> str:
        """GetErrorID gets the current robot error code (immediate command)"""
        return self._send_cmd("GetErrorID()")

    def GetScrName(self) -> str:
        """GetScrName gets the name of the script currently running on the robot (immediate command)"""
        return self._send_cmd("GetScrName()")

    # ==================== Kinematics calculations====================

    def PositiveKin(self, joints: Sequence[float], user: int = -1, tool: int = -1) -> str:
        """
        PositiveKin performs forward kinematics (immediate command)
        
        Args:
            joints: six joint angles[j1,j2,j3,j4,j5,j6] (°)
            user: User coordinate system index. Defaults to -1, meaning the current user coordinate system.
            tool: Tool coordinate system index. Defaults to -1, meaning the current tool coordinate system.
        """
        if len(joints) != 6:
            raise ValueError("Six joint angles are required")
        joint_str = ",".join([f"{j:.6f}" for j in joints])
        if user != -1 and tool != -1:
            return self._send_cmd(f"PositiveKin({joint_str},user={user},tool={tool})")
        return self._send_cmd(f"PositiveKin({joint_str})")

    def InverseKin(self, pose: Sequence[float], use_joint_near: int = 0, joint_near: Sequence[float] = None, user: int = -1, tool: int = -1) -> str:
        """
        InverseKin performs inverse kinematics (immediate command)
        
        Args:
            pose: six Cartesian coordinates [x,y,z,rx,ry,rz]
            use_joint_near: Whether to use the joint-proximity constraint. 0: no; 1: yes.
            joint_near: Joint-proximity reference values [j1,j2,j3,j4,j5,j6]。Used when useJointNear is 1.
            user: User coordinate system index. Defaults to -1, meaning the current user coordinate system.
            tool: Tool coordinate system index. Defaults to -1, meaning the current tool coordinate system.
        """
        if len(pose) != 6:
            raise ValueError("Six pose values are required")
        pose_str = ",".join([f"{p:.6f}" for p in pose])
        params = [pose_str]
        if use_joint_near != 0:
            params.append(f"useJointNear={use_joint_near}")
            if joint_near is not None:
                if len(joint_near) != 6:
                    raise ValueError("joint_near must contain 6 joint angles")
                joint_near_str = "jointNear={" + ",".join([f"{j:.6f}" for j in joint_near]) + "}"
                params.append(joint_near_str)
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        return self._send_cmd(f"InverseKin({','.join(params)})")

    # ==================== Reachability checks====================

    def CheckOddMovL(self, p1: Sequence[float], p2: Sequence[float],
                     point_type: str = "joint",
                     user: int = -1, tool: int = -1,
                     a: float = -1, v: float = -1,
                     cp: float = None, r: float = None) -> str:
        """
        CheckOddMovL checks point reachability for linear motion (immediate command)
        
        Args:
            p1: Start point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            p2: End point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            point_type: Point type "joint"(joint) or "pose" (Cartesian)
            user: User coordinate system index. -1 means unspecified
            tool: Tool coordinate system index. -1 means unspecified
            a: Acceleration. -1 uses the default value
            v: Velocity. -1 uses the default value
            cp: Continuity (mutually exclusive with r)
            r: Blending radius (mutually exclusive with cp, in mm)
        """
        if len(p1) != 6:
            raise ValueError("p1 must contain 6 values")
        if len(p2) != 6:
            raise ValueError("p2 must contain 6 values")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type must be 'joint' or 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        params = [f"{point_type}={{{p_values1}}}", f"{point_type}={{{p_values2}}}"]
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        elif r is not None:
            params.append(f"r={r:.6f}")
        return self._send_cmd(f"CheckOddMovL({','.join(params)})")

    def CheckOddMovJ(self, p1: Sequence[float], p2: Sequence[float],
                     point_type: str = "joint",
                     a: float = -1, v: float = -1,
                     cp: float = None) -> str:
        """
        CheckOddMovJ checks point reachability for joint motion (immediate command)
        
        Args:
            p1: Start point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            p2: End point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            point_type: Point type "joint"(joint) or "pose" (Cartesian)
            a: Acceleration. -1 uses the default value
            v: Velocity. -1 uses the default value
            cp: Continuity
        """
        if len(p1) != 6:
            raise ValueError("p1 must contain 6 values")
        if len(p2) != 6:
            raise ValueError("p2 must contain 6 values")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type must be 'joint' or 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        params = [f"{point_type}={{{p_values1}}}", f"{point_type}={{{p_values2}}}"]
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        return self._send_cmd(f"CheckOddMovJ({','.join(params)})")

    def CheckOddMovC(self, p1: Sequence[float], p2: Sequence[float], p3: Sequence[float],
                     point_type: str = "joint",
                     user: int = -1, tool: int = -1,
                     a: float = -1, v: float = -1,
                     cp: float = None, r: float = None) -> str:
        """
        CheckOddMovC checks point reachability for circular motion (immediate command)
        
        Args:
            p1: Start point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            p2: Intermediate point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            p3: End point [j1,j2,j3,j4,j5,j6] or [x, y, z, rx, ry, rz]
            point_type: Point type "joint"(joint) or "pose" (Cartesian)
            user: User coordinate system index. -1 means unspecified
            tool: Tool coordinate system index. -1 means unspecified
            a: Acceleration. -1 uses the default value
            v: Velocity. -1 uses the default value
            cp: Continuity (mutually exclusive with r)
            r: Blending radius (mutually exclusive with cp, in mm)
        """
        if len(p1) != 6:
            raise ValueError("p1 must contain 6 values")
        if len(p2) != 6:
            raise ValueError("p2 must contain 6 values")
        if len(p3) != 6:
            raise ValueError("p3 must contain 6 values")
        if point_type not in ("joint", "pose"):
            raise ValueError("point_type must be 'joint' or 'pose'")
        p_values1 = ",".join([f"{j:.6f}" for j in p1])
        p_values2 = ",".join([f"{j:.6f}" for j in p2])
        p_values3 = ",".join([f"{j:.6f}" for j in p3])
        params = [f"{point_type}={{{p_values1}}}",
                  f"{point_type}={{{p_values2}}}",
                  f"{point_type}={{{p_values3}}}"]
        if user != -1:
            params.append(f"user={user}")
        if tool != -1:
            params.append(f"tool={tool}")
        if a != -1:
            params.append(f"a={a:.6f}")
        if v != -1:
            params.append(f"v={v:.6f}")
        if cp is not None:
            params.append(f"cp={cp:.6f}")
        elif r is not None:
            params.append(f"r={r:.6f}")
        return self._send_cmd(f"CheckOddMovC({','.join(params)})")

    # ==================== Tray functions ====================

    def CreateTray(self, name: str, dimensions: Sequence[int],
                    points: list) -> str:
        """
        CreateTray creates a tray (immediate command)
        Supports one-dimensional, two-dimensional, and three-dimensional trays.

        Signatures (matching the documentation exactly):
        CreateTray(Trayname, {Count}, {P1},{P2}) -- 1D tray
        CreateTray(Trayname, {row,col}, {P1},{P2},{P3},{P4}) -- 2D tray
        CreateTray(Trayname, {row,col,layer}, {P1},{P2},{P3},{P4},{P5},{P6},{P7},{P8}) -- 3D tray

        Args:
            name: Tray name (string up to 32 bytes; cannot consist only of digits or spaces)
            dimensions: Dimension parameters
                - 1D: [count] number of points [2, 50]
                - 2D: [row, col] number of rows and columns
                - 3D: [row, col, layer] number of rows, columns, and layers
            points: List of endpoint poses, each in [x, y, z, rx, ry, rz] format; each point is passed as a separate argument
                - 1D: 2 endpoint poses [p1, p2]
                - 2D: 4 endpoint poses [p1, p2, p3, p4]
                - 3D: 8 endpoint poses [p1, p2, p3, p4, p5, p6, p7, p8]
        """
        dims = ",".join([str(d) for d in dimensions])
        point_strs = []
        for p in points:
            if len(p) != 6:
                raise ValueError(f"Each point must contain 6 values [x, y, z, rx, ry, rz]; received {len(p)} values")
            point_strs.append("{pose = {" + ",".join([f"{v:.6f}" for v in p]) + "}}")
        cmd = f"CreateTray({name},{{{dims}}}," + ",".join(point_strs) + ")"
        return self._send_cmd(cmd)

    def GetTrayPoint(self, trayname: str, index: int) -> str:
        """
        GetTrayPoint gets a tray point (immediate command)
        
        Args:
            trayname: Tray name (string matching the name used when calling CreateTray)
            index: Tray point index (1-based)
        """
        if not trayname or not trayname.strip():
            raise ValueError("trayname cannot be empty")
        if index < 1:
            raise ValueError("index must be greater than or equal to 1")
        return self._send_cmd(f"GetTrayPoint({trayname},{index})")

    # ==================== Log export ====================

    def LogExportUSB(self, log_range: int = None) -> str:
        """
        LogExportUSB exports robot logs to a USB drive (immediate command)

        Args:
            log_range: Log export range.
                0: Export logs/all and logs/user
                1: Export all contents of the logs folder
        """
        if log_range is not None:
            if log_range not in [0, 1]:
                raise ValueError("log_range must be 0 or 1")
            return self._send_cmd(f"LogExportUSB({log_range})")
        return self._send_cmd("LogExportUSB()")

    def GetExportStatus(self) -> str:
        """GetExportStatus gets the log export status (immediate command)"""
        return self._send_cmd("GetExportStatus()")