
import sqlite3
import uuid
from datetime import datetime, timezone

def register():
    conn = sqlite3.connect('uhi_switch.db')
    cursor = conn.cursor()

    hospitals = [
        ("HOSP-CITYCARE-A", "CityCare Multispeciality Hospital", "http://localhost:9001", "Chennai", "Tamil Nadu"),
        ("HOSP-METRO-B", "Metro Radiology & Diagnostics Center", "http://localhost:9002", "Mumbai", "Maharashtra")
    ]

    for h_id, name, url, city, state in hospitals:
        # Check if exists
        cursor.execute("SELECT 1 FROM hospitals WHERE hospital_id = ?", (h_id,))
        if cursor.fetchone():
            print(f"Hospital {name} already registered.")
            continue
        
        cursor.execute(
            "INSERT INTO hospitals (hospital_id, name, endpoint_url, city, state, registered_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (h_id, name, url, city, state, datetime.now(timezone.utc).isoformat(), 1)
        )
        print(f"Registered {name} ({h_id}) at {url}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    register()
