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

            # Subscriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    subscription_type TEXT CHECK(subscription_type IN ('captain_monthly', 'captain_weekly')),
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    payment_amount REAL,
                    payment_method TEXT,
                    created_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)

            # Payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    ride_id INTEGER,
                    subscription_id INTEGER,
                    payment_type TEXT CHECK(payment_type IN ('ride_payment', 'subscription_payment')),
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'SAR',
                    payment_method TEXT CHECK(payment_method IN ('cash', 'bank', 'stc', 'urpay', 'mada')),
                    payment_status TEXT CHECK(payment_status IN ('pending', 'completed', 'failed', 'refunded')) DEFAULT 'pending',
                    transaction_id TEXT,
                    payment_proof_url TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (ride_id) REFERENCES rides (ride_id),
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions (subscription_id)
                )
            """)

            # Payment requests table for handling payment flows
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payment_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    payment_type TEXT CHECK(payment_type IN ('ride_payment', 'subscription_payment')),
                    amount REAL NOT NULL,
                    description TEXT,
                    status TEXT CHECK(status IN ('pending', 'awaiting_proof', 'completed', 'cancelled')) DEFAULT 'pending',
                    ride_id INTEGER,
                    subscription_days INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (ride_id) REFERENCES rides (ride_id)
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

    def get_ride_by_id(self, ride_id: int) -> Optional[Dict[str, Any]]:
        """Get ride details by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*,
                           c.username as client_username, c.first_name as client_name,
                           cap.username as captain_username, cap.first_name as captain_name
                    FROM rides r
                    LEFT JOIN users c ON r.client_id = c.user_id
                    LEFT JOIN users cap ON r.captain_id = cap.user_id
                    WHERE r.ride_id = ?
                """, (ride_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def cancel_ride(self, ride_id: int, user_id: int) -> bool:
        """Cancel a ride"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rides SET status = 'cancelled', updated_at = ?
                    WHERE ride_id = ? AND (client_id = ? OR captain_id = ?)
                    AND status IN ('pending', 'accepted')
                """, (datetime.now(), ride_id, user_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def complete_ride(self, ride_id: int, captain_id: int) -> bool:
        """Mark ride as completed"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rides SET status = 'completed', updated_at = ?
                    WHERE ride_id = ? AND captain_id = ? AND status = 'in_progress'
                """, (datetime.now(), ride_id, captain_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def start_ride(self, ride_id: int, captain_id: int) -> bool:
        """Start an accepted ride"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE rides SET status = 'in_progress', updated_at = ?
                    WHERE ride_id = ? AND captain_id = ? AND status = 'accepted'
                """, (datetime.now(), ride_id, captain_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_captain_active_rides(self, captain_id: int) -> List[Dict[str, Any]]:
        """Get captain's active rides"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*, u.username, u.first_name
                    FROM rides r
                    JOIN users u ON r.client_id = u.user_id
                    WHERE r.captain_id = ? AND r.status IN ('accepted', 'in_progress')
                    ORDER BY r.created_at DESC
                """, (captain_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def add_rating(self, ride_id: int, rater_id: int, rated_id: int,
                   rating: int, comment: str = None) -> bool:
        """Add a rating for a completed ride"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ratings (ride_id, rater_id, rated_id, rating, comment)
                    VALUES (?, ?, ?, ?, ?)
                """, (ride_id, rater_id, rated_id, rating, comment))
                conn.commit()

                # Update user's average rating
                cursor.execute("""
                    UPDATE users SET rating = (
                        SELECT AVG(rating) FROM ratings WHERE rated_id = ?
                    ) WHERE user_id = ?
                """, (rated_id, rated_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def add_subscription(self, user_id: int, subscription_type: str,
                        end_date: str, payment_amount: float = None,
                        payment_method: str = None, created_by: int = None) -> bool:
        """Add a subscription for captain"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # إلغاء الاشتراكات النشطة السابقة
                cursor.execute("""
                    UPDATE subscriptions SET is_active = 0
                    WHERE user_id = ? AND is_active = 1
                """, (user_id,))

                # إضافة الاشتراك الجديد
                cursor.execute("""
                    INSERT INTO subscriptions
                    (user_id, subscription_type, end_date, payment_amount, payment_method, created_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, subscription_type, end_date, payment_amount, payment_method, created_by))

                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def is_captain_subscribed(self, user_id: int) -> bool:
        """Check if captain has active subscription"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM subscriptions
                    WHERE user_id = ? AND is_active = 1
                    AND datetime(end_date) > datetime('now')
                """, (user_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_subscription_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's subscription information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM subscriptions
                    WHERE user_id = ? AND is_active = 1
                    AND datetime(end_date) > datetime('now')
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (user_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_expired_subscriptions(self) -> List[Dict[str, Any]]:
        """Get expired subscriptions that need to be deactivated"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.*, u.username, u.first_name
                    FROM subscriptions s
                    JOIN users u ON s.user_id = u.user_id
                    WHERE s.is_active = 1
                    AND datetime(s.end_date) <= datetime('now')
                """)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def deactivate_expired_subscriptions(self) -> int:
        """Deactivate expired subscriptions and return count"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE subscriptions SET is_active = 0
                    WHERE is_active = 1 AND datetime(end_date) <= datetime('now')
                """)
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return 0

    def create_payment_request(self, user_id: int, payment_type: str, amount: float,
                             description: str, ride_id: int = None,
                             subscription_days: int = None) -> Optional[int]:
        """Create a payment request"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO payment_requests
                    (user_id, payment_type, amount, description, ride_id, subscription_days)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, payment_type, amount, description, ride_id, subscription_days))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_payment_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """Get payment request by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT pr.*, u.first_name, u.username
                    FROM payment_requests pr
                    JOIN users u ON pr.user_id = u.user_id
                    WHERE pr.request_id = ?
                """, (request_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def update_payment_request_status(self, request_id: int, status: str) -> bool:
        """Update payment request status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE payment_requests SET status = ?
                    WHERE request_id = ?
                """, (status, request_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def create_payment_record(self, user_id: int, payment_type: str, amount: float,
                            payment_method: str, ride_id: int = None,
                            subscription_id: int = None, transaction_id: str = None,
                            payment_proof_url: str = None, notes: str = None) -> Optional[int]:
        """Create a payment record"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO payments
                    (user_id, ride_id, subscription_id, payment_type, amount,
                     payment_method, transaction_id, payment_proof_url, notes, payment_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (user_id, ride_id, subscription_id, payment_type, amount,
                      payment_method, transaction_id, payment_proof_url, notes))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Database error in create_payment_record: {e}")
            import logging
            logging.error(f"Database error in create_payment_record: {e}")
            return None

    def update_payment_status(self, payment_id: int, status: str) -> bool:
        """Update payment status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE payments SET payment_status = ?, updated_at = ?
                    WHERE payment_id = ?
                """, (status, datetime.now(), payment_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def get_pending_payments(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get pending payments for admin review"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.*, u.first_name, u.username
                    FROM payments p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.payment_status = 'pending'
                    ORDER BY p.created_at DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_user_payments(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's payment history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM payments
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (user_id, limit))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []