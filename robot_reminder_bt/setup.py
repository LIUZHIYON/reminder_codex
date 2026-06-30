from setuptools import setup
import os, glob

package_name = "robot_reminder_bt"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    data_files=[
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"),
         glob.glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="cat",
    maintainer_email="cat@robot.local",
    description="提醒系统行为树节点",
    license="MIT",
    entry_points={
        "console_scripts": [
            "reminder_bt_driver = robot_reminder_bt.reminder_bt_driver:main",
            "aipet_reminder_node = robot_reminder_bt.aipet_reminder_node:main",
            "groot2_server = robot_reminder_bt.groot2_server:main",
        ],
    },
)
