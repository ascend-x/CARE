#!/bin/bash
echo "Starting ADB Auto-Tunnel Daemon..."
echo "This script ensures the phone always has network access to the backend APIs."

while true; do
    # Check if any device is connected
    DEVICE_STATE=$(/home/ascend-x/.android-sdk/platform-tools/adb get-state 2>/dev/null)
    
    if [ "$DEVICE_STATE" = "device" ]; then
        # Silently re-apply the reverse tunnels. 
        # This is idempotent, so running it repeatedly is safe and extremely fast.
        /home/ascend-x/.android-sdk/platform-tools/adb reverse tcp:8080 tcp:8080 >/dev/null 2>&1
        /home/ascend-x/.android-sdk/platform-tools/adb reverse tcp:9000 tcp:9000 >/dev/null 2>&1
        /home/ascend-x/.android-sdk/platform-tools/adb reverse tcp:9005 tcp:9005 >/dev/null 2>&1
    fi
    
    # Check every 3 seconds
    sleep 3
done
