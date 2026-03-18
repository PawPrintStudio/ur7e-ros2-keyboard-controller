#!/usr/bin/env python3

import sys
import termios
import tty
import threading
from copy import deepcopy
from typing import Optional, Dict

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from sensor_msgs.msg import JointState
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


HELP = """
UR Keyboard Joint Teleop
------------------------------------------------
q/a : shoulder_pan_joint     + / -
w/s : shoulder_lift_joint    + / -
e/d : elbow_joint            + / -
r/f : wrist_1_joint          + / -
t/g : wrist_2_joint          + / -
y/h : wrist_3_joint          + / -

z   : decrease step
x   : increase step
space: print current joints
c   : resend hold position
ESC : quit
------------------------------------------------
"""

KEY_TO_JOINT_DELTA = {
    'q': ("shoulder_pan_joint", +1.0),
    'a': ("shoulder_pan_joint", -1.0),
    'w': ("shoulder_lift_joint", +1.0),
    's': ("shoulder_lift_joint", -1.0),
    'e': ("elbow_joint", +1.0),
    'd': ("elbow_joint", -1.0),
    'r': ("wrist_1_joint", +1.0),
    'f': ("wrist_1_joint", -1.0),
    't': ("wrist_2_joint", +1.0),
    'g': ("wrist_2_joint", -1.0),
    'y': ("wrist_3_joint", +1.0),
    'h': ("wrist_3_joint", -1.0),
}

# This is the order the trajectory controller should receive.
CONTROL_JOINT_ORDER = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]


def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            return 'ESC'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__('keyboard_teleop')

        self.joint_topic = self.declare_parameter('joint_topic', '/joint_states').value
        self.action_name = self.declare_parameter(
            'action_name',
            '/scaled_joint_trajectory_controller/follow_joint_trajectory'
        ).value
        self.step = float(self.declare_parameter('step', 0.10).value)
        self.start_time = float(self.declare_parameter('start_time', 1.0).value)
        self.move_time = float(self.declare_parameter('move_time', 4.0).value)

        self.current_joint_state: Optional[JointState] = None
        self.goal_in_progress = False
        self.state_lock = threading.Lock()

        self.create_subscription(
            JointState,
            self.joint_topic,
            self.joint_state_cb,
            10,
        )

        self.action_client = ActionClient(
            self,
            FollowJointTrajectory,
            self.action_name
        )

        self.get_logger().info(f'Subscribing to joint states: {self.joint_topic}')
        self.get_logger().info(f'Using action: {self.action_name}')
        self.get_logger().info(f'Initial step size: {self.step:.3f} rad')
        self.get_logger().info('Waiting for trajectory action server...')
        self.action_client.wait_for_server()
        self.get_logger().info('Trajectory action server connected.')

    def joint_state_cb(self, msg: JointState):
        with self.state_lock:
            self.current_joint_state = msg

    def have_valid_joint_state(self) -> bool:
        with self.state_lock:
            if self.current_joint_state is None:
                return False
            if not self.current_joint_state.name:
                return False
            if len(self.current_joint_state.name) != len(self.current_joint_state.position):
                return False
            return True

    def get_current_joint_map(self) -> Optional[Dict[str, float]]:
        with self.state_lock:
            if self.current_joint_state is None:
                return None

            if len(self.current_joint_state.name) != len(self.current_joint_state.position):
                return None

            return {
                name: pos
                for name, pos in zip(
                    self.current_joint_state.name,
                    self.current_joint_state.position
                )
            }

    def get_current_positions_in_control_order(self) -> Optional[list]:
        joint_map = self.get_current_joint_map()
        if joint_map is None:
            return None

        missing = [j for j in CONTROL_JOINT_ORDER if j not in joint_map]
        if missing:
            self.get_logger().error(f'Missing joints in /joint_states: {missing}')
            self.get_logger().error(f'Available joints: {list(joint_map.keys())}')
            return None

        return [joint_map[j] for j in CONTROL_JOINT_ORDER]

    def print_current_positions(self):
        positions = self.get_current_positions_in_control_order()
        if positions is None:
            self.get_logger().warn('No valid joint state received yet.')
            return

        msg = ', '.join(
            f'{name}={pos:.4f}'
            for name, pos in zip(CONTROL_JOINT_ORDER, positions)
        )
        self.get_logger().info(msg)

    def send_hold_position(self):
        current_positions = self.get_current_positions_in_control_order()
        if current_positions is None:
            self.get_logger().warn('Cannot hold. No valid joint state received yet.')
            return

        self.send_goal(CONTROL_JOINT_ORDER, current_positions, current_positions)

    def jog_joint(self, joint_name: str, direction: float):
        current_positions = self.get_current_positions_in_control_order()
        if current_positions is None:
            self.get_logger().warn('Cannot jog. No valid joint state received yet.')
            return

        if self.goal_in_progress:
            self.get_logger().warn('Previous goal still running. Wait a moment.')
            return

        target_positions = deepcopy(current_positions)

        if joint_name not in CONTROL_JOINT_ORDER:
            self.get_logger().error(f'Joint {joint_name} not in controller order.')
            return

        idx = CONTROL_JOINT_ORDER.index(joint_name)
        old_pos = target_positions[idx]
        new_pos = old_pos + direction * self.step
        target_positions[idx] = new_pos

        self.get_logger().info(
            f'Sending jog for {joint_name}: {old_pos:.4f} -> {new_pos:.4f}'
        )
        self.send_goal(CONTROL_JOINT_ORDER, current_positions, target_positions)

    def make_point(self, positions, time_s: float) -> JointTrajectoryPoint:
        point = JointTrajectoryPoint()
        point.positions = deepcopy(positions)

        sec = int(time_s)
        nanosec = int((time_s - sec) * 1e9)
        point.time_from_start.sec = sec
        point.time_from_start.nanosec = nanosec
        return point

    def send_goal(self, joint_names, start_positions, target_positions):
        traj = JointTrajectory()
        traj.joint_names = deepcopy(joint_names)

        # Important: send current pose first, then target pose.
        traj.points.append(self.make_point(start_positions, self.start_time))
        traj.points.append(self.make_point(target_positions, self.move_time))

        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory = traj

        self.goal_in_progress = True
        send_goal_future = self.action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )
        send_goal_future.add_done_callback(self.goal_response_callback)

    def feedback_callback(self, feedback_msg):
        _ = feedback_msg

    def goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as e:
            self.goal_in_progress = False
            self.get_logger().error(f'Failed to send goal: {e}')
            return

        if not goal_handle.accepted:
            self.goal_in_progress = False
            self.get_logger().error('Goal rejected by controller.')
            return

        self.get_logger().info('Goal accepted.')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.goal_in_progress = False
        try:
            result_msg = future.result()
            result = result_msg.result
            status = result_msg.status
        except Exception as e:
            self.get_logger().error(f'Failed to get result: {e}')
            return

        if result.error_code == 0:
            self.get_logger().info(f'Motion complete. status={status}')
        else:
            self.get_logger().error(
                f'Motion failed. status={status}, '
                f'error_code={result.error_code}, '
                f'error_string="{result.error_string}"'
            )


def main(args=None):
    rclpy.init(args=args)
    node = KeyboardTeleop()

    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    print(HELP)

    try:
        while rclpy.ok():
            key = get_key()

            if key == 'ESC':
                break
            elif key in KEY_TO_JOINT_DELTA:
                joint_name, direction = KEY_TO_JOINT_DELTA[key]
                node.jog_joint(joint_name, direction)
            elif key == 'z':
                node.step = max(0.01, node.step - 0.01)
                node.get_logger().info(f'Step size: {node.step:.3f} rad')
            elif key == 'x':
                node.step = min(0.30, node.step + 0.01)
                node.get_logger().info(f'Step size: {node.step:.3f} rad')
            elif key == ' ':
                node.print_current_positions()
            elif key == 'c':
                node.send_hold_position()
                node.get_logger().info('Sent hold-current-position command.')

    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        spin_thread.join(timeout=1.0)


if __name__ == '__main__':
    main()