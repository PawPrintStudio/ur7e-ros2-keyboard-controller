from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='ur_dev_bringup',
            executable='robot_state_node',
            name='robot_state_node',
            output='screen',
            parameters=[{
                'joint_topic': '/joint_states',
            }],
        ),
        Node(
            package='ur_dev_bringup',
            executable='camera_view_node',
            name='camera_view_node',
            output='screen',
            parameters=[{
                'image_topic': '/camera/color/image_raw',
                'window_name': 'UR Camera Stream',
            }],
        ),
    ])
