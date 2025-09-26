import asyncio
import logging
from datetime import datetime
from telegram.ext import Application
from moderation import ModerationSystem

logger = logging.getLogger(__name__)

class MessageScheduler:
    def __init__(self, application: Application):
        self.application = application
        self.moderation = ModerationSystem()
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