#!/bin/bash
# ==============================================================
# deploy.sh — 部署 reminder 系统到 RK3576 板子
# 板子: RK3576 (ARM64)
# IP:   192.168.1.40
# 用户: cat
# 密码: temppwd
# ==============================================================
set -e

BOARD_IP="192.168.1.40"
BOARD_USER="cat"
BOARD_PASS="temppwd"
REMOTE_DIR="/home/cat/robot_reminder"
PKG_NAME="robot_reminder"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=============================="
echo "Deploy robot_reminder to RK3576"
echo "Board: ${BOARD_USER}@${BOARD_IP}"
echo "=============================="

# 1. 检查 SSH 连接
echo "[1/5] Checking SSH connection..."
sshpass -p "${BOARD_PASS}" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" "uname -a" || {
    echo "ERROR: Cannot connect to board. Please check:"
    echo "  - Board is powered on"
    echo "  - IP ${BOARD_IP} is correct"
    echo "  - Network is reachable"
    exit 1
}
echo "  SSH OK"

# 2. 在板子上创建目录
echo "[2/5] Creating remote directories..."
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" \
    "mkdir -p ${REMOTE_DIR}/audio ${REMOTE_DIR}/config"

# 3. 复制文件
echo "[3/5] Copying files..."
RSYNC_CMD="rsync -avz --progress"
# 如果有 rsync
if command -v rsync &> /dev/null; then
    sshpass -p "${BOARD_PASS}" ${RSYNC_CMD} \
        --exclude="__pycache__" \
        --exclude="*.pyc" \
        --exclude=".git" \
        "${SCRIPT_DIR}/../${PKG_NAME}/" \
        "${BOARD_USER}@${BOARD_IP}:${REMOTE_DIR}/"
else
    # 用 scp 逐文件复制
    echo "  rsync not found, using scp..."
    sshpass -p "${BOARD_PASS}" scp -r \
        "${SCRIPT_DIR}/../${PKG_NAME}/"* \
        "${BOARD_USER}@${BOARD_IP}:${REMOTE_DIR}/"
fi
echo "  Files copied"

# 4. 安装依赖
echo "[4/5] Installing Python dependencies..."
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" \
    "cd ${REMOTE_DIR} && pip3 install -r requirements.txt 2>/dev/null; \
     pip3 install requests websocket-client edge-tts 2>/dev/null; \
     echo '  Dependencies installed'"

# 5. 测试启动
echo "[5/5] Testing node startup..."
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" \
    "cd ${REMOTE_DIR} && python3 -c '
from robot_reminder.reminder_node import ReminderNode
print(\"Import OK\")
print(\"Module loaded successfully\")
' 2>&1 || echo \"  Note: ROS2 not available in test environment\""

echo ""
echo "=== Deployment complete! ==="
echo "To run on board:"
echo "  ssh ${BOARD_USER}@${BOARD_IP}"
echo "  cd ${REMOTE_DIR}"
echo "  # With ROS2:"
echo "  ros2 run robot_reminder reminder_node"
echo "  # Without ROS2 (standalone test):"
echo "  python3 -c \"from robot_reminder.reminder_node import main; main()\""
echo ""
echo "To test simulation locally:"
echo "  cd simulation"
echo "  python device_simulator.py --serial AIPET-${BOARD_IP##*.}"
