from setuptools import setup
import os, glob

package_name = 'robot_reminder'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    include_package_data=True,
    package_data={package_name: ['*.so', '*.pyi']},
    data_files=[
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob.glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
         glob.glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cat',
    maintainer_email='cat@rk3576.local',
    description='待办事提醒 ROS2 节点',
    license='MIT',
    entry_points={
        'console_scripts': [
            'reminder_node = robot_reminder.reminder_node:main',
        ],
    },
)
