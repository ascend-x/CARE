#!/bin/bash
while true; do
  curl -s -X POST http://localhost:9000/api/v1/encounter/ -H "Authorization: Bearer $(curl -s -X POST http://localhost:9000/api/v1/auth/login/ -H 'Content-Type: application/json' -d '{"username":"admin","password":"admin"}' | jq -r .access)" -H "Content-Type: application/json" -d '{"patient_id": "9c242d75-1c3a-5954-a7fb-9d876125dde7", "encounter_type": "outpatient", "chief_complaint": "Live Sync Check '$RANDOM'"}' > /dev/null
  sleep 5
done
