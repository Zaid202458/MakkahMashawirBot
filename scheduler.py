import asyncio
import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from moderation import ModerationSystem
from database import Database

logger = logging.getLogger(__name__)

class MessageScheduler:
    def __init__(self, application: Application):
        self.application = application
        self.moderation = ModerationSystem()
        self.database = Database()
        self.is_running = False

    async def start_scheduler(self):
        """Start the message scheduler"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Message scheduler started")

        while self.is_running:
            try:
                await self.send_scheduled_messages()
                await self.cleanup_expired_subscriptions()
                # فحص كل 10 دقائق
                await asyncio.sleep(600)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(600)

    async def stop_scheduler(self):
        """Stop the message scheduler"""
        self.is_running = False
        logger.info("Message scheduler stopped")

    async def send_scheduled_messages(self):
        """Send pending scheduled messages"""
        try:
            pending_messages = self.moderation.get_pending_scheduled_messages()

            for message_data in pending_messages:
                try:
                    await self.application.bot.send_message(
                        chat_id=message_data['chat_id'],
                        text=message_data['message_text']
                    )

                    # تحديث آخر إرسال
                    self.moderation.mark_message_sent(message_data['schedule_id'])

                    logger.info(f"Sent scheduled message to chat {message_data['chat_id']}")

                except Exception as e:
                    logger.error(f"Failed to send scheduled message {message_data['schedule_id']}: {e}")

        except Exception as e:
            logger.error(f"Error getting scheduled messages: {e}")

    async def cleanup_expired_subscriptions(self):
        """تنظيف الاشتراكات المنتهية الصلاحية"""
        try:
            # الحصول على الاشتراكات المنتهية قبل إلغائها
            expired_subscriptions = self.database.get_expired_subscriptions()

            # إلغاء الاشتراكات المنتهية
            deactivated_count = self.database.deactivate_expired_subscriptions()

            if deactivated_count > 0:
                logger.info(f"Deactivated {deactivated_count} expired subscriptions")

                # إشعار المستخدمين بانتهاء الاشتراك
                for subscription in expired_subscriptions:
                    try:
                        await self.application.bot.send_message(
                            chat_id=subscription['user_id'],
                            text="⚠️ انتهت صلاحية اشتراكك\n\n"
                            "لا يمكنك الآن الوصول للرحلات المتاحة.\n"
                            "للتجديد، يرجى التواصل مع الإدارة.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("للتجديد تواصل مع الإدارة 💳", url="https://t.me/novacompnay")
                            ]])
                        )
                        logger.info(f"Notified user {subscription['user_id']} about expired subscription")
                    except Exception as e:
                        logger.error(f"Failed to notify user {subscription['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning up expired subscriptions: {e}")