from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'robot_reminder_bt'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    include_package_data=True,
    data_files=[
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'),
         glob('config/**/*', recursive=True)),
        (os.path.join('share', package_name, 'config/trees'),
         glob('config/trees/*.xml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cat',
    maintainer_email='cat@rk3576.local',
    description='提醒系统行为树节点 — BT.CPP / py_trees',
    license='MIT',
    entry_points={
        'console_scripts': [
            'reminder_bt_node = robot_reminder_bt.reminder_bt_node:main',
        ],
    },
)
