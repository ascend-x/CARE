#!/bin/bash

CONTAINER_ROLE=$(cat /tmp/container-role)
if [[ "$CONTAINER_ROLE" = "api" ]]; then
    curl -fsS http://localhost:9000/ping/ || exit 1
elif [[ "$CONTAINER_ROLE" == "celery-beat" ]]; then
    ls /tmp/healthy || exit 1
elif [[ "$CONTAINER_ROLE" == celery* ]]; then
    ps -C celery > /dev/null || exit 1
else
    echo "Unknown container role: $CONTAINER_ROLE"
    exit 1
fi
