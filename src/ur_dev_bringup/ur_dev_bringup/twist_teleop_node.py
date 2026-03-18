#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class TwistTeleopNode(Node):
    def __init__(self):
        super().__init__('twist_teleop_node')

        self.cmd_topic = self.declare_parameter('cmd_topic', '/cmd_vel').value
        self.pub = self.create_publisher(Twist, self.cmd_topic, 10)

        self.get_logger().info(f'Publishing control commands to: {self.cmd_topic}')

    def send_twist(self, lx=0.0, ly=0.0, lz=0.0, ax=0.0, ay=0.0, az=0.0):
        msg = Twist()
        msg.linear.x = float(lx)
        msg.linear.y = float(ly)
        msg.linear.z = float(lz)
        msg.angular.x = float(ax)
        msg.angular.y = float(ay)
        msg.angular.z = float(az)
        self.pub.publish(msg)
        self.get_logger().info(
            f'Sent Twist | linear=({lx}, {ly}, {lz}) angular=({ax}, {ay}, {az})'
        )


def main(args=None):
    rclpy.init(args=args)
    node = TwistTeleopNode()

    try:
        node.send_twist(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
