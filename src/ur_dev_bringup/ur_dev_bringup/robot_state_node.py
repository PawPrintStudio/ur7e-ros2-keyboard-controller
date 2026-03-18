#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class RobotStateNode(Node):
    def __init__(self):
        super().__init__('robot_state_node')

        self.joint_topic = self.declare_parameter('joint_topic', '/joint_states').value
        self.last_joint_state = None

        self.create_subscription(
            JointState,
            self.joint_topic,
            self.joint_cb,
            10,
        )

        self.create_timer(1.0, self.report_status)
        self.get_logger().info(f'Listening for robot joints on: {self.joint_topic}')

    def joint_cb(self, msg: JointState):
        self.last_joint_state = msg

    def report_status(self):
        if self.last_joint_state is None:
            self.get_logger().warn('No joint state received yet.')
            return

        names = list(self.last_joint_state.name)
        positions = [round(p, 4) for p in self.last_joint_state.position]
        summary = ', '.join(f'{n}: {p}' for n, p in zip(names, positions))
        self.get_logger().info(f'Joint states -> {summary}')


def main(args=None):
    rclpy.init(args=args)
    node = RobotStateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
