#!/bin/bash
# run_board.sh — 板子上部署/运行行为树节点
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "================================"
echo " 行为树 — 板子部署脚本"
echo "================================"

# 1. 选择版本
echo ""
echo "选择运行版本:"
echo "  1) Python 版 (直接 ros2 run)"
echo "  2) C++ 版 (需 colcon build)"
echo "  3) 测试模式"
read -p "请选择 (1/2/3): " VERSION

case $VERSION in
    1)
        echo ""
        echo "▶ 启动 Python 版..."
        cd ~/ros2_ws
        source install/setup.bash
        ros2 run robot_reminder_bt reminder_bt_node \
            --ros-args \
            -p reminder_api_url:=http://192.168.1.70:5000 \
            -p tick_interval_ms:=100
        ;;

    2)
        echo ""
        echo "▶ 编译 C++ 版..."
        cd ~/ros2_ws
        if [ ! -d "src/robot_reminder_bt" ]; then
            echo "拷贝项目到板子..."
            # 假设项目已通过 SCP 传输到 ~/ros2_ws/src/robot_reminder_bt
        fi
        colcon build --packages-select robot_reminder_bt
        source install/setup.bash
        echo "▶ 启动 C++ 版..."
        ros2 run robot_reminder_bt reminder_bt_node \
            --ros-args \
            -p api_url:=http://192.168.1.70:5000 \
            -p bt_xml:=$(ros2 pkg prefix robot_reminder_bt)/share/robot_reminder_bt/config/trees/reminder_bt_v3.xml
        ;;

    3)
        echo ""
        echo "▶ 测试模式 - 查看 TTS 日志..."
        tail -f ~/tts_log.log
        ;;
esac
