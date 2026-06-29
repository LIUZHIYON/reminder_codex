#!/bin/bash
cd /home/cat/reminder_system
while true; do
    python3 board_ws_client.py >> /home/cat/reminder_system/logs/ws_client.log 2>&1
    sleep 5
done
