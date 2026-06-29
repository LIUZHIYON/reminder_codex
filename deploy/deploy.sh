#!/bin/bash
set -e
BOARD_IP="192.168.1.64"
BOARD_USER="cat"
BOARD_PASS="temppwd"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
echo "=== Deploy all packages ==="
echo "[1] SSH check..."
sshpass -p "${BOARD_PASS}" ssh -o StrictHostKeyChecking=no "${BOARD_USER}@${BOARD_IP}" "uname -a" || exit 1
echo "[2] robot_reminder..."
REMOTE_DIR="/home/cat/robot_reminder"
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" "mkdir -p ${REMOTE_DIR}/audio ${REMOTE_DIR}/config"
sshpass -p "${BOARD_PASS}" rsync -avz --exclude=__pycache__ --exclude=*.pyc --exclude=.git "${PROJECT_DIR}/robot_reminder/" "${BOARD_USER}@${BOARD_IP}:${REMOTE_DIR}/" 2>/dev/null || sshpass -p "${BOARD_PASS}" scp -r "${PROJECT_DIR}/robot_reminder/"* "${BOARD_USER}@${BOARD_IP}:${REMOTE_DIR}/"
echo "[3] robot_reminder_bt..."
REMOTE_BT="/home/cat/ros2_ws/src/robot_reminder_bt"
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" "mkdir -p ${REMOTE_BT}/robot_reminder_bt ${REMOTE_BT}/launch"
sshpass -p "${BOARD_PASS}" rsync -avz --exclude=__pycache__ --exclude=*.pyc --exclude=.git "${PROJECT_DIR}/robot_reminder_bt/" "${BOARD_USER}@${BOARD_IP}:${REMOTE_BT}/" 2>/dev/null || sshpass -p "${BOARD_PASS}" scp -r "${PROJECT_DIR}/robot_reminder_bt/"* "${BOARD_USER}@${BOARD_IP}:${REMOTE_BT}/"
echo "[4] robot_aipet_relay..."
REMOTE_RELAY="/home/cat/ros2_ws/src/robot_aipet_relay"
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" "mkdir -p ${REMOTE_RELAY}/robot_aipet_relay ${REMOTE_RELAY}/launch ${REMOTE_RELAY}/resource"
sshpass -p "${BOARD_PASS}" rsync -avz --exclude=__pycache__ --exclude=*.pyc --exclude=.git "${PROJECT_DIR}/robot_aipet_relay/" "${BOARD_USER}@${BOARD_IP}:${REMOTE_RELAY}/" 2>/dev/null || sshpass -p "${BOARD_PASS}" scp -r "${PROJECT_DIR}/robot_aipet_relay/"* "${BOARD_USER}@${BOARD_IP}:${REMOTE_RELAY}/"
echo "[5] Build..."
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" 'source /opt/ros/humble/setup.bash; cd /home/cat/ros2_ws; colcon build --packages-select robot_reminder_bt robot_aipet_relay --symlink-install 2>&1 | tail -5'
echo "[6] Verify..."
sshpass -p "${BOARD_PASS}" ssh "${BOARD_USER}@${BOARD_IP}" 'source /opt/ros/humble/setup.bash; source /home/cat/ros2_ws/install/setup.bash; ros2 pkg list | grep -E "robot_reminder_bt|robot_aipet_relay"'
echo "=== Done ==="
