from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from rapidfuzz import process, fuzz
import uuid
import re
BaseOAuth = declarative_base()
engine_oauth = create_engine("sqlite:///oauth.db", echo=False)
engine = create_engine("sqlite:///lost_and_found.db", echo=True)
Base = declarative_base()
class User(BaseOAuth):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reg_no = Column(String, unique=True, nullable=True)
    google_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
BaseOAuth.metadata.create_all(engine_oauth)
SessionOAuth = sessionmaker(bind=engine_oauth)
session_oauth = SessionOAuth()
class LostItem(Base):
    __tablename__ = "lost_items"
    row_number = Column(Integer, primary_key=True, autoincrement=True)
    item_name = Column(String, nullable=False)
    description = Column(String)
    location = Column(String, nullable=False)
    date_lost = Column(DateTime, default=datetime.utcnow)
    owner_name = Column(String, nullable=False)
    id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    image_path = Column(String, nullable=True)

class FoundItem(Base):
    __tablename__ = "found_items"
    row_number = Column(Integer, primary_key=True, autoincrement=True)
    item_name = Column(String, nullable=False)
    description = Column(String)
    location = Column(String)
    date_found = Column(DateTime, default=datetime.utcnow)
    finder_name = Column(String, nullable=False)
    id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    image_path = Column(String, nullable=True)
Base.metadata.create_all(engine)
SessionLF = sessionmaker(bind=engine)
session_lf = SessionLF()

def get_user_info(google_user=None):
    """
    Collects and validates user info from Google or manual input.
    Returns a user info dictionary if valid, otherwise returns None.
    """
    user_data = {}
    if google_user:
        user_data = {
            "id": google_user.get('sub'),
            "name": google_user.get('name'),
            "email": google_user.get('email')
        }
    else:
        while True:
            id_input = input("Enter your ID (letters/numbers only): ")
            if re.fullmatch(r'^[a-zA-Z0-9]+$', id_input):
                break
            print("Invalid ID. Please use only letters and numbers.")
        
        while True:
            name_input = input("Enter your Name (letters/spaces only): ")
            if re.fullmatch(r'^[a-zA-Z\s]+$', name_input):
                break
            print("Invalid name. Please use only letters and spaces.")

        while True:
            email_input = input("Enter your Gmail Address: ")
            if re.search(r'@gmail\.com$', email_input.strip()):
                break
            print("Invalid email. Must be a @gmail.com address.")
        
        user_data = {"id": id_input, "name": name_input, "email": email_input}
    if not user_data.get('id') or not re.fullmatch(r'^[a-zA-Z0-9_]+$', user_data['id']):
        print(f"Validation Error: ID '{user_data.get('id')}' is invalid.")
        return None
    if not user_data.get('name') or not re.fullmatch(r'^[a-zA-Z\s]+$', user_data['name']):
        print(f"Validation Error: Name '{user_data.get('name')}' is invalid.")
        return None
    if not user_data.get('email') or not re.search(r'(@gmail\.com|@vitstudent\.ac\.in)$', user_data['email']):
        print(f"Validation Error: Email '{user_data.get('email')}' is not a Gmail address.")
        return None
    if google_user:
        user = session_oauth.query(User).filter_by(email=user_data['email']).first()
        if not user:
            user = User(google_id=user_data['id'], email=user_data['email'], name=user_data['name'])
            try:
                session_oauth.add(user)
                session_oauth.commit()
            except Exception as e:
                session_oauth.rollback()
                print(f"Error adding user to OAuth DB: {e}")
                return None
    
    return user_data

def add_lost_item(item_name, description, location, date_lost, user_info, image_path=None):
    # Validation is now handled by get_user_info.
    new_item = LostItem(
        item_name=item_name,
        description=description,
        location=location,
        date_lost=date_lost,
        owner_name=user_info['name'],
        id=user_info['id'],
        email=user_info['email'],
        image_path=image_path
    )
    try:
        session_lf.add(new_item)
        session_lf.commit()
        print(f"Lost item '{item_name}' added for {user_info['name']}")
    except Exception as e:
        session_lf.rollback()
        print(f"Error adding lost item: {e}")

def list_all_lost_items():
    items = session_lf.query(LostItem).all()
    print("\nLost Items:")
    for i in items:
        print(f"{i.item_name} - {i.location} (Owner: {i.owner_name})")

def list_all_found_items():
    items = session_lf.query(FoundItem).all()
    print("\nFound Items:")
    for i in items:
        print(f"{i.item_name} - {i.location} (Finder: {i.finder_name})")

def add_found_item(item_name, description, location, date_found, user_info, image_path=None):
    # Validation is now handled by get_user_info.
    new_item = FoundItem(
        item_name=item_name,
        description=description,
        location=location,
        date_found=date_found,
        finder_name=user_info['name'],
        id=user_info['id'],
        email=user_info['email'],
        image_path=image_path
    )
    try:
        session_lf.add(new_item)
        session_lf.commit()
        print(f"Found item '{item_name}' added for {user_info['name']}")
    except Exception as e:
        session_lf.rollback()
        print(f"Error adding found item: {e}")

Campus_Zones = [
    "Library", "Admin Block", "AB1", "AB2", "AB3", "A-Block", "B-Block",
    "C-Block", "D1-Block", "D2-Block", "E-Block", "Auditorium",
    "Main Gate", "Gazebo", "NORTH SQUARE", "GYMKHANA"
]

def s_location(location):
    l = location.lower()
    for zone in Campus_Zones:
        if zone.lower() in l:
            return zone
    return "Other"

def search_matches(item_name):
    lost_items = session_lf.query(LostItem).filter(LostItem.item_name.ilike(f"%{item_name}%")).all()
    found_items = session_lf.query(FoundItem).filter(FoundItem.item_name.ilike(f"%{item_name}%")).all()
    matches = []
    for l in lost_items:
        for f in found_items:
            loc_l = s_location(l.location).lower()
            loc_f = s_location(f.location).lower()
            if loc_l != loc_f:
                continue
            name_score = fuzz.ratio(l.item_name.lower(), f.item_name.lower())
            desc_score = fuzz.ratio((l.description or "").lower(), (f.description or "").lower())
            days_diff = abs((l.date_lost - f.date_found).days)
            time_score = max(0, 100 - (days_diff * 10))
            similarity = (0.5 * name_score) + (0.3 * desc_score) + (0.2 * time_score)
            if similarity > 70:  # threshold
                matches.append((l, f, similarity))
    if matches:
        print("Potential Matches Found:")
        for l, f, sim in matches:
            print(f"[{sim}% match] Lost: {l.item_name} @ {l.location} | Found: {f.item_name} @ {f.location}")
    else:
        print("No matches found.")

if __name__ == "__main__":
    try:
        use_google = input("Login via Google? (y/n): ").lower() == 'y'
        if use_google:
            # Use test data that passes validation
            google_user_info = {
                "sub": "google_unique_id_123",
                "email": "ishani.test@gmail.com",
                "name": "Ishani"
            }
            user_info = get_user_info(google_user_info)
        else:
            user_info = get_user_info()

        # Only proceed if user_info is valid
        if user_info:
            print("\nUser validated. Proceeding to add items...")
            add_lost_item("Wallet", "Black leather wallet", "Cafeteria", datetime.now(), user_info)
            add_found_item("ID Card", "Blue lanyard found near Library desk", "AB1 PORTICO", datetime.now(), user_info)
            
            print("\n--- Current Items ---")
            list_all_lost_items()
            list_all_found_items()

            print("\n--- Searching for Matches ---")
            search_matches("Wallet")
            search_matches("ID Card")
        else:
            print("\nCould not proceed due to invalid user information.")

    finally:
        session_lf.close()
        session_oauth.close()