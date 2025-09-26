import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path: str = "mashawir_bot.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone_number TEXT,
                    user_type TEXT CHECK(user_type IN ('client', 'captain')),
                    is_active BOOLEAN DEFAULT 1,
                    rating REAL DEFAULT 0.0,
                    total_rides INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Rides table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rides (
                    ride_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    captain_id INTEGER,
                    pickup_location TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    pickup_latitude REAL,
                    pickup_longitude REAL,
                    destination_latitude REAL,
                    destination_longitude REAL,
                    ride_type TEXT CHECK(ride_type IN ('request', 'offer')),
                    status TEXT CHECK(status IN ('pending', 'accepted', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
                    price REAL,
                    passenger_count INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES users (user_id),
                    FOREIGN KEY (captain_id) REFERENCES users (user_id)
                )
            """)

            # Ratings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ratings (
                    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ride_id INTEGER,
                    rater_id INTEGER,
                    rated_id INTEGER,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ride_id) REFERENCES rides (ride_id),
                    FOREIGN KEY (rater_id) REFERENCES users (user_id),
                    FOREIGN KEY (rated_id) REFERENCES users (user_id)
                )
            """)

            conn.commit()

    def add_user(self, user_id: int, username: str, first_name: str,
                 last_name: str = None, user_type: str = None) -> bool:
        """Add or update user in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO users
                    (user_id, username, first_name, last_name, user_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, user_type, datetime.now()))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by user_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def update_user_type(self, user_id: int, user_type: str) -> bool:
        """Update user type (client/captain)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users SET user_type = ?, updated_at = ?
                    WHERE user_id = ?
                """, (user_type, datetime.now(), user_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def create_ride(self, client_id: int, pickup_location: str, destination: str,
                   ride_type: str = "request", price: float = None,
                   passenger_count: int = 1, notes: str = None) -> Optional[int]:
        """Create a new ride"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO rides
                    (client_id, pickup_location, destination, ride_type, price, passenger_count, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (client_id, pickup_location, destination, ride_type, price, passenger_count, notes))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_pending_rides(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending rides"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*, u.username, u.first_name
                    FROM rides r
                    JOIN users u ON r.client_id = u.user_id
                    WHERE r.status = 'pending'
                    ORDER BY r.created_at DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def accept_ride(self, ride_id: int, captain_id: int) -> bool:
        """Accept a ride"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rides SET captain_id = ?, status = 'accepted', updated_at = ?
                    WHERE ride_id = ? AND status = 'pending'
                """, (captain_id, datetime.now(), ride_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def update_ride_status(self, ride_id: int, status: str) -> bool:
        """Update ride status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rides SET status = ?, updated_at = ?
                    WHERE ride_id = ?
                """, (status, datetime.now(), ride_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_user_rides(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's rides history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM rides
                    WHERE client_id = ? OR captain_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (user_id, user_id, limit))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []