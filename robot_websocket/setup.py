from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'robot_websocket'

setup(
    name=package_name,
    version='0.1.0',
    package_data={
        package_name: ['*.so', '**/*.so', '*.pyi', '**/*.pyi'],
    },
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools', 'websockets>=10.0', 'aiohttp>=3.8.0'],
    zip_safe=True,
    maintainer='suchuan',
    maintainer_email='suchuan@todo.todo',
    description='AI Pet Robot WebSocket Client Module',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'websocket_node = robot_websocket.websocket_node:main',
        ],
    },
)
