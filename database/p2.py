from p1 import session_oauth, User
from datetime import datetime

# Dummy Google user info (simulate OAuth callback)
google_user_info = {
    "sub": "google_test_id_001",
    "email": "testuser@vit.student.ac.in",
    "name": "Test User"
}

# Check if user exists
user = session_oauth.query(User).filter_by(email=google_user_info['email']).first()
if not user:
    user = User(
        google_id=google_user_info['sub'],
        email=google_user_info['email'],
        name=google_user_info['name']
    )
    session_oauth.add(user)
    session_oauth.commit()

print("User in oauth.db:", user.name, user.email)
session_oauth.close()
