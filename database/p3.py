from p1 import add_lost_item, add_found_item, session_lf
from datetime import datetime

# Simulated user info from Google or manual input
user_info = {
    "id": "google_test_id_001",
    "name": "Test User",
    "email": "testuser@vit.student.ac.in"
}

add_lost_item("Wallet", "Black leather wallet", "Cafeteria", datetime.now(), user_info)
add_found_item("Wallet", "Found black wallet near Cafeteria", "Cafeteria", datetime.now(), user_info)
from p1 import list_all_lost_items, list_all_found_items
list_all_lost_items()
list_all_found_items()
# List items

session_lf.close()
