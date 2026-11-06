"""
Dobot XYZ control with a Nintendo Switch Pro Controller (pygame).

Push a stick -> the robot moves along that axis toward the + or - limit.
Release it   -> the robot stops immediately.
The robot also stops by itself when it reaches the predefined limit, and
stops at once if the controller disconnects.

The whole straight-line path is checked with InverseKin before moving. If part
of the path is unreachable (out of reach, too close to the base, or needs a
wrist flip / big joint swing), the robot moves only up to the last safe point
instead of triggering an alarm.

Controls (defaults, see the controller mapping section below):
  Left stick up/down    -> X+ / X-
  Left stick right/left -> Y+ / Y-
  Right stick up/down   -> Z+ / Z-
  Right stick right/left -> R+ / R- (tool rotation = joint 6)
  A -> safe pose     B -> drop pose     X -> stop     Plus -> quit
  Y -> swap outputs: DO1 off + DO2 on, next press DO1 on + DO2 off (never both ON)

Stall handling (non-blocking, so releasing a stick is always handled instantly):
if the robot has not started moving within MOVE_CHECK_TIMEOUT seconds, the
script reads RobotMode / ErrorID and only recovers when there is a real problem
(alarm, paused, unknown state). An idle robot means "already at target".

Requires:  python -m pip install pygame
Find your controller's axis/button numbers with:  python <this_file>.py --test
"""

import os
import re
import sys
import time
import traceback

# Keep receiving controller input even when this window is not focused
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from dobot_sdk import DobotRobot, CoordinateType

# --- Configuration -----------------------------------------------------------
ROBOT_IP = "192.168.5.1"
PAYLOAD_KG = 1.0
SPEED_PERCENT = 40          # Keep low for manual jogging
SAFE_POSE_JOINT = [-90, -00, -90, 0, 90, 45]
DROP_POSE_JOINT = [-180, 00, -90, 0, 90, 0]
SAFE_POSE_WAIT = 2          # Seconds to wait for the initial move

# Predefined XYZ range (mm) -- ADJUST to your workspace!
# The robot moves toward the "min" end for the - key and the "max" end for + key.
XYZ_LIMITS = {
    "y": (-300.0, 150.0),
    "x": (-500.0, -200.0),
    "z": (220.0, 600.0),
}
LIMIT_TOLERANCE_MM = 0.5    # Consider "at limit" within this distance

# Tool rotation "R" = joint 6 (degrees). Pushing the stick rotates toward the
# min / max end. ADJUST to your robot's joint 6 range and what your tool allows.
R_LIMITS = (-170.0, 170.0)
R_TOLERANCE_DEG = 0.5       # Consider "at limit" within this angle

# If True, jogging is refused while the robot is outside XYZ_LIMITS
# (use key 1 / 2 to get back inside first).
REQUIRE_INSIDE_LIMITS = True

# Reach checking along the path
REACH_SAMPLE_STEP_MM = 20.0   # Check a point every this many mm along the path
REACH_MARGIN_MM = 5.0         # Stop this far before the first unreachable point
JOINT_JUMP_LIMIT_DEG = 45.0   # Treat a bigger joint change between two samples as
                              # a wrist flip / singularity (path not safe)

AXIS_INDEX = {"x": 1, "y": 0, "z": 2}

# --- Controller mapping (Nintendo Switch Pro Controller via pygame) -----------
# Run `python <this_file>.py --test` to see the axis / button numbers of YOUR
# controller, then adjust the values below.
STICK_AXES = {
    # robot axis: (pygame axis index, sign)   -- use sign -1 to flip a direction
    "x": (1, -1),    # left stick up/down    -> X+ / X-
    "y": (0, +1),    # left stick right/left -> Y+ / Y-
    "z": (3, -1),    # right stick up/down   -> Z+ / Z-
    "r": (2, +1),    # right stick right/left -> R+ / R- (tool rotation)
}
STICK_PUSH = 0.5     # push farther than this to start moving
STICK_RELEASE = 0.3  # return below this to stop (hysteresis avoids chatter)

BTN_SAFE = 0         # A    -> go to safe pose
BTN_DROP = 1         # B    -> go to drop pose
BTN_STOP = 2         # X    -> stop motion
BTN_QUIT = 6         # Plus -> quit (robot is disabled on exit)
BTN_DO_SWAP = 3      # Y    -> swap the two digital outputs

# One button swaps two outputs, and they are never ON at the same time:
#   1st press: DO1 OFF, DO2 ON      2nd press: DO1 ON, DO2 OFF      ...
DO_PAIR = (1, 2)            # (first, second) digital output numbers
DO_PAIR_START = 0           # ON at start: 0 = first output (DO1), 1 = second (DO2)
DO_APPLY_AT_START = True    # Send the start state to the robot when the script starts
DO_SWITCH_GAP = 0.05        # Seconds between switching one output OFF and the other ON
# Method of robot.io used to set an output. "DO" is a queued command on Dobot
# controllers (it may wait for a running move to finish). If your SDK also has
# an immediate version (DOInstant), set DO_METHOD = "DOInstant".
DO_METHOD = "DO"

POSE_BUTTONS = {
    BTN_SAFE: ("safe pose", SAFE_POSE_JOINT),
    BTN_DROP: ("drop pose", DROP_POSE_JOINT),
}

POLL_INTERVAL = 0.03     # Seconds between controller reads
RECONNECT_DELAY = 1.0    # Seconds between reconnect attempts

# Stall detection
MOVE_CHECK_TIMEOUT = 1.5    # Seconds to wait for the robot to start moving
MOVE_THRESHOLD_MM = 0.2     # Position change that counts as "moving"
MOVE_THRESHOLD_DEG = 0.2    # Rotation change that counts as "moving"

# RobotMode values (Dobot TCP/IP protocol -- verify against your manual)
MODE_ENABLED = 5            # Enabled and idle
MODE_RUNNING = 7            # Executing a motion
MODE_ERROR = 9              # Alarm active
MODE_PAUSED = 10            # Paused

# Cartesian coordinate type used by MovL. Adjust if your SDK names it differently.
CARTESIAN = next(
    (getattr(CoordinateType, name) for name in ("POSE", "CARTESIAN")
     if getattr(CoordinateType, name, None) is not None),
    None,
)
if CARTESIAN is None:
    raise AttributeError("CoordinateType has no POSE/CARTESIAN member - set CARTESIAN manually")

HELP_TEXT = """
Controller (push = move, release = stop)
----------------------------------------
  Left stick  up/down    : X  +/-
  Left stick  right/left : Y  +/-
  Right stick up/down    : Z  +/-
  Right stick right/left : R  +/-  (rotate tool)

  A : go to safe pose
  B : go to drop pose
  X : stop motion
  Y : swap outputs (DO1 off + DO2 on, then DO1 on + DO2 off, ...)
  Plus : quit (robot is disabled on exit)
"""


# --- Robot helpers -------------------------------------------------------------
def setup_robot(robot) -> None:
    control = robot.robot_control
    control.RequestControl()
    control.ClearError()
    control.EnableRobot(load=PAYLOAD_KG)
    control.SpeedFactor(SPEED_PERCENT)

    robot.StartFeedbackMonitor()
    time.sleep(1)


def get_pose(robot):
    """Return the current tool pose [x, y, z, rx, ry, rz] from the feedback."""
    status = robot.GetStatus()
    if not status:
        raise RuntimeError("No robot status available yet")
    v = status.tool_vector_actual
    return [v.x, v.y, v.z, v.rx, v.ry, v.rz]


def command_ok(response) -> bool:
    """Dobot replies start with the ErrorID; 0 means success."""
    if not isinstance(response, str):
        return True   # Unknown response type: don't treat as failure
    return response.strip().startswith("0")


def read_mode(robot):
    """Return RobotMode as an int (e.g. 5 for idle), or None if unparsable."""
    match = re.search(r"\{(-?\d+)\}", str(robot.robot_control.RobotMode()))
    return int(match.group(1)) if match else None


def active_alarms(robot):
    """Return the list of active (non-zero) alarm IDs from GetErrorID()."""
    response = str(robot.robot_control.GetErrorID())
    match = re.search(r"\{\[(.*?)\]\}", response)
    if not match:
        return []
    return [a for a in re.findall(r"\d+", match.group(1)) if a != "0"]


def ensure_no_alarm(robot) -> bool:
    """Clear active alarms. Returns False if an alarm could not be cleared."""
    alarms = active_alarms(robot)
    if not alarms:
        return True
    print(f"⚠️  Active alarm(s): {alarms}. Clearing...")
    robot.robot_control.ClearError()
    time.sleep(0.2)
    alarms = active_alarms(robot)
    if alarms:
        print(f"❌ Alarm(s) {alarms} did not clear. Look up the code in your manual "
              f"and reset it in DobotStudio / on the controller.")
        return False
    return True


def report_state(robot) -> None:
    """Print RobotMode and ErrorID (read BEFORE ClearError wipes the alarm)."""
    control = robot.robot_control
    print(f"   RobotMode: {control.RobotMode()}")
    print(f"   ErrorID:   {control.GetErrorID()}")


def recover(robot) -> None:
    control = robot.robot_control
    print("   Recovering: Stop -> ClearError -> Continue -> retry")
    control.Stop()
    control.ClearError()
    time.sleep(0.1)
    control.Continue()


def moved_since(robot, before) -> bool:
    now = get_pose(robot)
    if any(abs(now[i] - before[i]) > MOVE_THRESHOLD_MM for i in range(3)):
        return True
    return any(abs(now[i] - before[i]) > MOVE_THRESHOLD_DEG for i in range(3, 6))


# --- Reachability along a path ---------------------------------------------------
def parse_floats(response, count: int = 6):
    """Extract the first {a,b,c,...} list of numbers from a Dobot reply."""
    match = re.search(r"\{([^{}]*)\}", str(response))
    if not match:
        return None
    try:
        values = [float(v) for v in match.group(1).split(",")]
    except ValueError:
        return None
    return values if len(values) == count else None


def get_joints(robot):
    """Current joint angles [j1..j6] in degrees, or None if unparsable."""
    return parse_floats(robot.robot_control.GetAngle())


def ik_check(robot, pose, near):
    """
    Inverse kinematics near the given joint angles (so the solution matches the
    arm's current configuration). Returns (reachable, joints_or_None).
    """
    control = robot.robot_control
    if near:
        response = control.InverseKin(pose, use_joint_near=1, joint_near=near)
    else:
        response = control.InverseKin(pose)
    if not command_ok(response):
        return False, None
    return True, parse_floats(response)


def farthest_reachable(robot, pose, index: int, goal: float, direction: int):
    """
    Walk from the current position toward `goal` in REACH_SAMPLE_STEP_MM steps.
    Each step is solved near the previous solution, so wrist flips and fast
    joint swings (e.g. near the base) are detected, not just out-of-reach points.
    Returns (last_reachable_value, whole_path_reachable).
    """
    distance = abs(goal - pose[index])
    offsets, d = [], REACH_SAMPLE_STEP_MM
    while d < distance:
        offsets.append(d)
        d += REACH_SAMPLE_STEP_MM
    offsets.append(distance)            # Always test the goal itself

    near = get_joints(robot)
    target = list(pose)
    last_good = pose[index]
    for offset in offsets:
        value = pose[index] + direction * offset
        target[index] = value

        ok, joints = ik_check(robot, target, near)
        if not ok:
            return last_good, False
        if joints and near:
            jump = max(abs(a - b) for a, b in zip(joints, near))
            if jump > JOINT_JUMP_LIMIT_DEG:
                return last_good, False
        if joints:
            near = joints
        last_good = value
    return goal, True


# --- Motion with a non-blocking watchdog ---------------------------------------------
def send_and_watch(robot, label: str, send_fn):
    """Send a motion command and return a watch record to check later."""
    control = robot.robot_control
    control.Continue()                      # Resume if the robot was paused
    before = get_pose(robot)
    response = send_fn()
    retried = False

    if not command_ok(response):
        print(f"⚠️  {label}: command rejected (response: {response})")
        report_state(robot)
        recover(robot)
        before = get_pose(robot)
        send_fn()
        retried = True

    return {
        "label": label,
        "send_fn": send_fn,
        "before": before,
        "deadline": time.time() + MOVE_CHECK_TIMEOUT,
        "retried": retried,
        "resumed": False,
    }


def check_watch(robot, watch):
    """
    Call regularly. Returns the watch while still waiting, or None when done.
    Only recovers when something is really wrong (alarm / paused / unknown).
    """
    if moved_since(robot, watch["before"]):
        return None
    if time.time() < watch["deadline"]:
        return watch

    label = watch["label"]
    mode = read_mode(robot)
    alarms = active_alarms(robot)

    if not alarms and mode == MODE_RUNNING:
        return None                         # Moving, just slow to start
    if not alarms and mode == MODE_ENABLED:
        print(f"{label}: robot is idle (already at target, or move finished).")
        return None
    if not alarms and mode == MODE_PAUSED and not watch["resumed"]:
        print(f"{label}: robot is paused -> Continue")
        robot.robot_control.Continue()
        watch["resumed"] = True
        watch["deadline"] = time.time() + MOVE_CHECK_TIMEOUT
        return watch

    print(f"⚠️  {label}: robot has not started moving (mode={mode}, alarms={alarms})")
    report_state(robot)

    if watch["retried"]:
        print(f"❌ {label}: still not moving after retry. Check the ErrorID above.")
        return None

    recover(robot)
    watch["before"] = get_pose(robot)
    watch["send_fn"]()
    watch["retried"] = True
    watch["deadline"] = time.time() + MOVE_CHECK_TIMEOUT
    return watch


def start_jog(robot, axis: str, direction: int):
    """Start a move toward the axis limit. Returns a watch record or None."""
    pose = get_pose(robot)
    index = AXIS_INDEX[axis]
    low, high = XYZ_LIMITS[axis]
    goal = high if direction > 0 else low
    label = f"{axis.upper()}{'+' if direction > 0 else '-'}"

    # Refuse to jog while outside the allowed box
    if REQUIRE_INSIDE_LIMITS:
        outside = [
            a.upper() for a, (lo, hi) in XYZ_LIMITS.items()
            if not lo - LIMIT_TOLERANCE_MM <= pose[AXIS_INDEX[a]] <= hi + LIMIT_TOLERANCE_MM
        ]
        if outside:
            print(f"Robot is outside XYZ_LIMITS on {', '.join(outside)} "
                  f"(X={pose[0]:.1f} Y={pose[1]:.1f} Z={pose[2]:.1f}). "
                  f"Press 1/2 to move to a pose, or adjust XYZ_LIMITS.")
            return None

    if abs(goal - pose[index]) <= LIMIT_TOLERANCE_MM:
        print(f"{label}: already at {'max' if direction > 0 else 'min'} limit ({goal:.1f})")
        return None

    # An active alarm makes InverseKin and MovL fail, so clear it first
    if not ensure_no_alarm(robot):
        return None

    # Check the whole path; stop before the first unreachable point
    safe_value, full_path = farthest_reachable(robot, pose, index, goal, direction)
    travel = abs(safe_value - pose[index]) - (0.0 if full_path else REACH_MARGIN_MM)
    if travel <= LIMIT_TOLERANCE_MM:
        print(f"{label}: nothing reachable in this direction from {pose[index]:.1f} "
              f"(out of reach, too close to the base, or needs a large joint swing).")
        return None

    goal = pose[index] + direction * travel
    if not full_path:
        print(f"{label}: path is not fully reachable; moving up to {goal:.1f} only.")

    target = list(pose)
    target[index] = goal
    print(f"Moving {label} from {pose[index]:.1f} toward {goal:.1f} ...")
    return send_and_watch(robot, label, lambda: robot.motion.MovL(target, CARTESIAN))


def start_rotate(robot, direction: int):
    """Rotate the tool (joint 6) toward R_LIMITS. Returns a watch record or None."""
    label = f"R{'+' if direction > 0 else '-'}"
    joints = get_joints(robot)
    if joints is None:
        print(f"{label}: could not read the joint angles.")
        return None

    low, high = R_LIMITS
    goal = high if direction > 0 else low
    if (goal - joints[5]) * direction <= R_TOLERANCE_DEG:
        print(f"{label}: already at {'max' if direction > 0 else 'min'} limit "
              f"(J6 = {joints[5]:.1f}, limit {goal:.1f})")
        return None

    if not ensure_no_alarm(robot):
        return None

    target = list(joints)
    target[5] = goal
    print(f"Moving {label} from {joints[5]:.1f} toward {goal:.1f} ...")
    return send_and_watch(
        robot, label, lambda: robot.motion.MovJ(target, CoordinateType.JOINT)
    )


def start_motion(robot, axis: str, direction: int):
    """Start a jog on x / y / z (Cartesian) or r (tool rotation)."""
    if axis == "r":
        return start_rotate(robot, direction)
    return start_jog(robot, axis, direction)


def go_to_pose(robot, name: str, joints):
    print(f"Moving to {name}: {joints}")
    ensure_no_alarm(robot)
    return send_and_watch(
        robot, name, lambda: robot.motion.MovJ(joints, CoordinateType.JOINT)
    )


def stop_motion(robot) -> None:
    robot.robot_control.Stop()
    pose = get_pose(robot)
    print(f"Stopped at X={pose[0]:.1f}  Y={pose[1]:.1f}  Z={pose[2]:.1f}")
    alarms = active_alarms(robot)
    if alarms:
        print(f"⚠️  Alarm(s) {alarms} raised during this move "
              f"(cleared automatically on the next move).")


def set_output(robot, index: int, value: int) -> bool:
    """Set digital output `index` to 0/1. Returns True on success."""
    try:
        response = getattr(robot.io, DO_METHOD)(index, value)
    except Exception as e:
        print(f"⚠️  DO{index}: failed ({e})")
        return False
    if not command_ok(response):
        print(f"⚠️  DO{index}: command rejected (response: {response})")
        return False
    print(f"DO{index} -> {'ON' if value else 'OFF'}")
    return True


def switch_outputs(robot, current, new):
    """
    Switch between D1 ON, ALL OFF, and D2 ON.

    States:
        0 = D1 ON, D2 OFF
        1 = D1 OFF, D2 OFF
        2 = D1 OFF, D2 ON
        3 = D1 OFF, D2 OFF

    Returns:
        New active state if successful.
        Current state if the first OFF command fails.
        None if the second command fails.
    """

    # Always switch both outputs OFF first
    d1_index = DO_PAIR[0]
    d2_index = DO_PAIR[1]

    if not set_output(robot, d1_index, 0):
        return current

    if not set_output(robot, d2_index, 0):
        return None

    time.sleep(DO_SWITCH_GAP)

    # State 0: D1 ON
    if new == 0:
        if not set_output(robot, d1_index, 0):
            return None

    # State 1: Both OFF
    elif new == 1:
        if not set_output(robot, d1_index, 1):
                    return None

    # State 2: D2 ON
    elif new == 2:
        set_output(robot, d1_index, 0)
        if not set_output(robot, d2_index, 1):
            return None

    # State 3: Both OFF
    elif new == 3:
        pass

    return new


# --- Controller input ------------------------------------------------------------
def connect_controller():
    """Return the first connected joystick, or None."""
    if pygame.joystick.get_count() == 0:
        return None
    try:
        joy = pygame.joystick.Joystick(0)
        print(f"Controller connected: {joy.get_name()} | "
              f"Axes: {joy.get_numaxes()} | Buttons: {joy.get_numbuttons()}")
        return joy
    except pygame.error as e:
        print(f"Controller not ready: {e}")
        return None


def stick_command(joy, current):
    """
    Return the wanted (axis, direction) from the sticks, or None when released.
    One axis at a time; a held axis keeps control until it drops below
    STICK_RELEASE, otherwise the most strongly pushed axis wins.
    """
    values = {
        axis: joy.get_axis(index) * sign
        for axis, (index, sign) in STICK_AXES.items()
    }

    if current:
        axis, direction = current
        if values[axis] * direction >= STICK_RELEASE:
            return current

    axis = max(values, key=lambda a: abs(values[a]))
    if abs(values[axis]) >= STICK_PUSH:
        return axis, (1 if values[axis] > 0 else -1)
    return None


def control_loop(robot) -> None:
    """Read the controller until the quit button is pressed."""
    joy = None
    last_connect_try = 0.0
    do_active = 3  # Initial state: D1 OFF, D2 OFF
    command = None          # (axis, direction) the sticks currently ask for
    moving = False          # A jog move is in progress
    pose_moving = False     # A pose move (A / B button) was started
    watch = None            # Stall watchdog for the latest motion

    do_active = DO_PAIR_START   # Index in DO_PAIR that is ON (None = both OFF)
    if DO_APPLY_AT_START:
        do_active = switch_outputs(robot, None, DO_PAIR_START)

    def halt(force: bool = False) -> None:
        
        """Stop any motion and reset the motion state."""
        nonlocal command, moving, pose_moving, watch
        if force or moving or pose_moving:
            stop_motion(robot)
        command, moving, pose_moving, watch = None, False, False, None

    print("Waiting for controller...")
    while True:
        quit_requested = False

        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEREMOVED:
                print("Controller disconnected - stopping the robot.")
                halt(force=True)
                joy = None

            elif event.type == pygame.JOYBUTTONDOWN and joy is not None:
                if event.button == BTN_QUIT:
                    quit_requested = True
                elif event.button == BTN_STOP:
                    halt(force=True)
                elif event.button in POSE_BUTTONS:
                    halt()
                    pose_name, joints = POSE_BUTTONS[event.button]
                    watch = go_to_pose(robot, pose_name, joints)
                    pose_moving = True
                elif event.button == BTN_DO_SWAP:
                    # Cycle through 4 states:
                    # 0 = D1 ON, D2 OFF
                    # 1 = D1 OFF, D2 OFF
                    # 2 = D1 OFF, D2 ON
                    # 3 = D1 OFF, D2 OFF

                    current_state = do_active if do_active is not None else 3
                    new = (current_state + 1) % 3

                    result = switch_outputs(robot, do_active, new)

                    if result is not None:
                        do_active = result

        if quit_requested:
            break

        if joy is None:                              # (Re)connect
            if time.time() - last_connect_try >= RECONNECT_DELAY:
                last_connect_try = time.time()
                joy = connect_controller()
            time.sleep(POLL_INTERVAL)
            continue

        try:
            desired = stick_command(joy, command)
        except pygame.error as e:
            print(f"Controller read error: {e} - stopping the robot.")
            halt(force=True)
            joy = None
            continue

        if desired != command:                       # Stick pushed, released or flipped
            if moving:
                stop_motion(robot)
                moving, watch = False, None
                time.sleep(0.1)                      # Let the Stop settle
            command = desired
            if desired is not None:
                if pose_moving:
                    robot.robot_control.Stop()       # Cancel the pose move first
                    pose_moving = False
                watch = start_motion(robot, *desired)
                moving = watch is not None

        # Non-blocking stall check (runs every loop, stick release is never delayed)
        if watch:
            watch = check_watch(robot, watch)

        time.sleep(POLL_INTERVAL)

    halt()


def test_controller() -> None:
    """Print raw axes and pressed buttons so you can fill in the mapping."""
    pygame.init()
    pygame.joystick.init()
    joy = None
    print("Controller test - move the sticks and press buttons. Ctrl+C to exit.")
    try:
        while True:
            pygame.event.pump()
            if joy is None:
                joy = connect_controller()
                if joy is None:
                    time.sleep(RECONNECT_DELAY)
                    continue
            try:
                axes = [round(joy.get_axis(i), 2) for i in range(joy.get_numaxes())]
                buttons = [i for i in range(joy.get_numbuttons()) if joy.get_button(i)]
                print(f"\rAxes: {axes} | Buttons pressed: {buttons}      ",
                      end="", flush=True)
            except pygame.error:
                print("\nController lost.")
                joy = None
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nTest ended.")
    finally:
        pygame.quit()


def main() -> None:
    pygame.init()
    pygame.joystick.init()
    try:
        with DobotRobot(ROBOT_IP) as robot:
            print("=" * 50)
            print("XYZ hold-to-move control")
            print("=" * 50)

            setup_robot(robot)

            try:
                print("Moving to safe position...")
                robot.motion.MovJ(SAFE_POSE_JOINT, CoordinateType.JOINT)
                time.sleep(SAFE_POSE_WAIT)

                pose = get_pose(robot)
                print(f"Start pose: X={pose[0]:.1f}  Y={pose[1]:.1f}  Z={pose[2]:.1f}")
                for axis, (low, high) in XYZ_LIMITS.items():
                    if not low <= pose[AXIS_INDEX[axis]] <= high:
                        print(f"⚠️  Start {axis.upper()} is outside the limit range "
                              f"({low}..{high}); adjust XYZ_LIMITS.")

                print(HELP_TEXT)
                control_loop(robot)
            finally:
                robot.robot_control.Stop()
                robot.StopFeedbackMonitor()
                robot.robot_control.DisableRobot()
                print("Robot disabled.")

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    finally:
        pygame.quit()


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_controller()
    else:
        main()