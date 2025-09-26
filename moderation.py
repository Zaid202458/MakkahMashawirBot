import sqlite3
import re
from datetime import datetime, timedelta
from typing import List, Set

class ModerationSystem:
    def __init__(self, db_path: str = "mashawir_bot.db"):
        self.db_path = db_path
        self.init_moderation_tables()
        self.load_banned_words()

    def init_moderation_tables(self):
        """Initialize moderation tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Banned words table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS banned_words (
                    word_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE NOT NULL,
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # User warnings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_warnings (
                    warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    reason TEXT,
                    warned_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Scheduled messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    message_text TEXT,
                    interval_hours INTEGER,
                    duration_days INTEGER,
                    created_by INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    last_sent TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert default banned words
            default_banned_words = [
                "زواج", "مسيار", "جنس", "سكس", "عري", "إباحي"
            ]

            for word in default_banned_words:
                cursor.execute("""
                    INSERT OR IGNORE INTO banned_words (word) VALUES (?)
                """, (word,))

            conn.commit()

    def load_banned_words(self) -> Set[str]:
        """Load banned words from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT word FROM banned_words")
                self.banned_words = {row[0].lower() for row in cursor.fetchall()}
                return self.banned_words
        except sqlite3.Error:
            self.banned_words = set()
            return self.banned_words

    def add_banned_word(self, word: str, added_by: int) -> bool:
        """Add a word to banned list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO banned_words (word, added_by) VALUES (?, ?)
                """, (word.lower(), added_by))
                conn.commit()
                self.banned_words.add(word.lower())
                return True
        except sqlite3.Error:
            return False

    def remove_banned_word(self, word: str) -> bool:
        """Remove a word from banned list"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM banned_words WHERE word = ?", (word.lower(),))
                conn.commit()
                self.banned_words.discard(word.lower())
                return cursor.rowcount > 0
        except sqlite3.Error:
            return False

    def check_message_content(self, message_text: str) -> bool:
        """Check if message contains banned content"""
        if not message_text:
            return False

        message_lower = message_text.lower()

        # Check for banned words
        for banned_word in self.banned_words:
            if banned_word in message_lower:
                return True

        # Check for promotional content patterns
        promo_patterns = [
            r'للبيع', r'للايجار', r'اعلان', r'اعلانات',
            r'خصم', r'عرض', r'تخفيض', r'مجانا',
            r'www\.', r'http', r'bit\.ly', r't\.me'
        ]

        for pattern in promo_patterns:
            if re.search(pattern, message_lower):
                return True

        return False

    def add_user_warning(self, user_id: int, reason: str, warned_by: int) -> bool:
        """Add warning to user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_warnings (user_id, reason, warned_by)
                    VALUES (?, ?, ?)
                """, (user_id, reason, warned_by))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def get_user_warnings_count(self, user_id: int, days: int = 30) -> int:
        """Get user warning count in last N days"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                since_date = datetime.now() - timedelta(days=days)
                cursor.execute("""
                    SELECT COUNT(*) FROM user_warnings
                    WHERE user_id = ? AND created_at > ?
                """, (user_id, since_date))
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0

    def should_ban_user(self, user_id: int) -> bool:
        """Check if user should be banned based on warnings"""
        warnings_count = self.get_user_warnings_count(user_id)
        return warnings_count >= 3

    def schedule_message(self, chat_id: int, message_text: str, interval_hours: int,
                        duration_days: int, created_by: int) -> bool:
        """Schedule a recurring message"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scheduled_messages
                    (chat_id, message_text, interval_hours, duration_days, created_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (chat_id, message_text, interval_hours, duration_days, created_by))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def get_pending_scheduled_messages(self) -> List[dict]:
        """Get messages that need to be sent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                now = datetime.now()
                cursor.execute("""
                    SELECT * FROM scheduled_messages
                    WHERE is_active = 1
                    AND (last_sent IS NULL OR
                         datetime(last_sent, '+' || interval_hours || ' hours') <= datetime('now'))
                    AND datetime(created_at, '+' || duration_days || ' days') > datetime('now')
                """)

                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def mark_message_sent(self, schedule_id: int) -> bool:
        """Mark scheduled message as sent"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scheduled_messages
                    SET last_sent = datetime('now')
                    WHERE schedule_id = ?
                """, (schedule_id,))
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def get_banned_words_list(self) -> List[str]:
        """Get list of all banned words"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT word FROM banned_words ORDER BY word")
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error:
            return []