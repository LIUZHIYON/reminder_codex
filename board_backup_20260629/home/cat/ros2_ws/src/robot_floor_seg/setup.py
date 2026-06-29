from setuptools import setup
import os, glob

package_name = 'robot_floor_seg'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    include_package_data=True,
    package_data={
        package_name: ['*.so', '*.pyi', 'models/*.rknn', 'templates/*.html'],
    },
    data_files=[
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
         glob.glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'),
         glob.glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cat',
    maintainer_email='liuzhiyong@52wana.com',
    description='RK3576 wall/floor segmentation ROS2 node',
    license='MIT',
    entry_points={
        'console_scripts': [
            'seg_node = robot_floor_seg.seg_node:main',
        ],
    },
)
