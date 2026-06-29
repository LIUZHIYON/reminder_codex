from setuptools import setup
import os, glob

package_name = "robot_aipet_relay"

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
    description="AI Pet 板端 WebSocket 传话节点",
    license="MIT",
    entry_points={
        "console_scripts": [
            "relay_node = robot_aipet_relay.relay_node:main",
        ],
    },
)
