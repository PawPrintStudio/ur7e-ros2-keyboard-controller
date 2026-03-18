from setuptools import setup
from glob import glob

package_name = 'ur_dev_bringup'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='you',
    maintainer_email='you@example.com',
    description='Minimal Python scaffold for UR robot controls and camera stream access.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'robot_state_node = ur_dev_bringup.robot_state_node:main',
            'twist_teleop_node = ur_dev_bringup.twist_teleop_node:main',
            'camera_view_node = ur_dev_bringup.camera_view_node:main',
            'keyboard_teleop = ur_dev_bringup.keyboard_teleop:main',
        ],
    },
)
