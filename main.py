import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import Database
from moderation import ModerationSystem

# تحميل متغيرات البيئة من ملف .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# إعداد قاعدة البيانات ونظام الإشراف
db = Database()
moderation = ModerationSystem()

# إعداد نظام السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# هذا هو الأمر الذي سيتم تشغيله عند إضافة البوت إلى مجموعة أو عند كتابة /start
async def start_command(update: Update, context):
    logger.info(f"Start command received from user {update.effective_user.id}")

    keyboard = [
        [InlineKeyboardButton("إذا كنت عميل اضغط هنا", callback_data='client_button')],
        [InlineKeyboardButton("كابتن اضغط هنا", callback_data='captain_button')],
        [InlineKeyboardButton("الاشتراك", callback_data='subscribe_button'), InlineKeyboardButton("تنبيه ⚠️", callback_data='warning_button')],
        [InlineKeyboardButton("الإدارة المباشرة", url="https://t.me/novacompnay")],
        [InlineKeyboardButton("الاستفسار عن باقات إعلاناتكم", callback_data='ads_button')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # إضافة المستخدم إلى قاعدة البيانات
    user = update.effective_user
    try:
        db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        logger.info(f"User {user.id} added to database")
    except Exception as e:
        logger.error(f"Failed to add user to database: {e}")

    await update.message.reply_text(
        'أهلاً بكم في مجموعة "مشاوير مكة اليومية"!\n\nاختر نوع حسابك للمتابعة:',
        reply_markup=reply_markup
    )

# معالج الأزرار التفاعلية
async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data
    logger.info(f"Button callback received: {data} from user {user_id}")

    if data == 'client_button':
        db.update_user_type(user_id, 'client')

        # إرسال رسالة خاصة للعميل مع النموذج
        client_form = """حياك الله عميلنا العزيز،

قم بتعبئة النموذج التالي لوضوح التفاصيل وتوفير سائق مناسب:

مطلوب سائق (شهري)

👥 عدد الأشخاص:
🏠 مكان المنزل:
🏢 مكان الدوام:
🕐 وقت حضور السائق للمنزل:
🕘 وقت بداية الدوام:
🕕 وقت انتهاء الدوام:
🔄 دوام ثابت ولا شفتات:
📅 عدد أيام الدوام:
💰 السعر المقترح:

المواقع:
📍 لوكيشن العمل:
📍 لوكيشن البيت:

➡️ ملاحظات إضافية:"""

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=client_form
            )
            await query.edit_message_text(
                "تم إرسال نموذج طلب السائق إلى رسائلك الخاصة 📩\n\nقم بتعبئة النموذج وإرساله في المجموعة بعد التعبئة."
            )
        except Exception as e:
            await query.edit_message_text(
                "عذراً، لم أتمكن من إرسال رسالة خاصة لك.\n\nتأكد من أنك بدأت محادثة مع البوت أولاً بالضغط على /start في الرسائل الخاصة."
            )

    elif data == 'captain_button':
        db.update_user_type(user_id, 'captain')

        captain_rules = """عزيزي الكابتن، لا تعرض نفسك للكتم أو الحظر.

❌ ممنوع عرض مكان تواجدك (يُستثنى من ذلك المشتركون في خدمة "كابتن مشترك").
❌ ممنوع الإعلانات داخل المجموعة.
❌ ممنوع النقاشات الجانبية.
❌ الاتفاق يتم مع العميل في الخاص فقط.
❌ المنسقين: ممنوع إعطاء أي مشوار لسائق ما لم يؤشر على المشوار بكلمة "هات" أو "خاص".

✅ الاشتراك في القروب (10 ريال) لمدة شهر.

برجاء الالتزام بالقوانين حتى لا تعرض نفسك للحظر."""

        keyboard = [
            [InlineKeyboardButton("للاشتراك اضغط هنا 💳", url="https://t.me/novacompnay")],
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            captain_rules,
            reply_markup=reply_markup
        )

    elif data == 'request_ride':
        await query.edit_message_text(
            "لطلب رحلة، يرجى إرسال موقع الانطلاق أولاً 📍\n\nيمكنك إرسال الموقع من خلال:\n1. الضغط على رمز المشبك 📎\n2. اختيار 'الموقع' 📍\n3. اختيار موقعك الحالي أو البحث عن موقع آخر"
        )
        context.user_data['step'] = 'waiting_pickup'

    elif data == 'view_rides':
        rides = db.get_pending_rides()
        if not rides:
            await query.edit_message_text("لا توجد رحلات متاحة حالياً 😔")
            return

        message = "الرحلات المتاحة 🚗:\n\n"
        keyboard = []

        for ride in rides[:5]:  # عرض أول 5 رحلات
            message += f"🔹 من: {ride['pickup_location']}\n"
            message += f"   إلى: {ride['destination']}\n"
            if ride['price']:
                message += f"   السعر: {ride['price']} ريال\n"
            message += f"   العميل: {ride['first_name']}\n\n"

            keyboard.append([InlineKeyboardButton(
                f"قبول الرحلة من {ride['pickup_location'][:20]}...",
                callback_data=f"accept_ride_{ride['ride_id']}"
            )])

        keyboard.append([InlineKeyboardButton("تحديث القائمة 🔄", callback_data='view_rides')])
        keyboard.append([InlineKeyboardButton("العودة ↩️", callback_data='captain_button')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif data.startswith('accept_ride_'):
        ride_id = int(data.split('_')[2])
        if db.accept_ride(ride_id, user_id):
            await query.edit_message_text("تم قبول الرحلة بنجاح! ✅\n\nسيتم التواصل معك قريباً.")
            # إشعار العميل
            # TODO: إضافة إشعار للعميل
        else:
            await query.edit_message_text("عذراً، هذه الرحلة لم تعد متاحة 😔")

    elif data == 'subscribe_button':
        subscription_message = """لالشتراك في المجموعة، يرجى التواصل مع الإدارة عبر المعرف التالي:

@novacompnay"""

        keyboard = [
            [InlineKeyboardButton("التواصل مع الإدارة 📞", url="https://t.me/novacompnay")],
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            subscription_message,
            reply_markup=reply_markup
        )

    elif data == 'warning_button':
        warning_message = """⚠️ تنبيه الأسعار ⚠️

نتمنى من جميع العملاء عدم بخس الأسعار في الخاص أو العام.

ونتمنى من جميع السائقين عدم استقبال المشاوير بأسعار بخسة. إذا كان لك رزق ستأخذه. حتى وإن كنت متجهاً على نفس الطريق، لا تأخذ المشوار بسعر بخس، لأن العميل قد يعتقد أن هذا هو السعر المعتاد في المرات القادمة.

نأمل الالتزام من الجميع وشاكرين ومقدرين لتعاونكم."""

        keyboard = [
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            warning_message,
            reply_markup=reply_markup
        )

    elif data == 'ads_button':
        ads_message = """الاستفسار عن باقات إعلاناتكم 📢

للاستفسار عن باقات الإعلانات المدفوعة والأسعار، يرجى التواصل مع الإدارة مباشرة."""

        keyboard = [
            [InlineKeyboardButton("التواصل مع الإدارة 📞", url="https://t.me/novacompnay")],
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            ads_message,
            reply_markup=reply_markup
        )

    elif data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("إذا كنت عميل اضغط هنا", callback_data='client_button')],
            [InlineKeyboardButton("كابتن اضغط هنا", callback_data='captain_button')],
            [InlineKeyboardButton("الاشتراك", callback_data='subscribe_button'), InlineKeyboardButton("تنبيه ⚠️", callback_data='warning_button')],
            [InlineKeyboardButton("الإدارة المباشرة", url="t.me/novacompnay")],
            [InlineKeyboardButton("الاستفسار عن باقات إعلاناتكم", callback_data='ads_button')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            'أهلاً بكم في مجموعة "مشاوير مكة اليومية"!\n\nاختر نوع حسابك للمتابعة:',
            reply_markup=reply_markup
        )

# معالج المواقع
async def location_handler(update: Update, context):
    user_id = update.effective_user.id
    location = update.message.location

    step = context.user_data.get('step', '')

    if step == 'waiting_pickup':
        context.user_data['pickup_lat'] = location.latitude
        context.user_data['pickup_lon'] = location.longitude
        context.user_data['pickup_location'] = f"موقع ({location.latitude:.4f}, {location.longitude:.4f})"
        context.user_data['step'] = 'waiting_destination'

        await update.message.reply_text(
            "تم تسجيل موقع الانطلاق ✅\n\nالآن أرسل موقع الوجهة 📍"
        )

    elif step == 'waiting_destination':
        destination_location = f"موقع ({location.latitude:.4f}, {location.longitude:.4f})"
        pickup_location = context.user_data.get('pickup_location')

        # إنشاء الرحلة
        ride_id = db.create_ride(
            client_id=user_id,
            pickup_location=pickup_location,
            destination=destination_location
        )

        if ride_id:
            await update.message.reply_text(
                f"تم إنشاء طلب الرحلة بنجاح! ✅\n\n"
                f"رقم الرحلة: {ride_id}\n"
                f"من: {pickup_location}\n"
                f"إلى: {destination_location}\n\n"
                f"سيتم إشعارك عند قبول أحد الكباتن للرحلة 🚖"
            )
            # مسح البيانات المؤقتة
            context.user_data.clear()
        else:
            await update.message.reply_text("حدث خطأ في إنشاء الرحلة. يرجى المحاولة مرة أخرى.")

# معالج الرسائل النصية
async def text_handler(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text

    step = context.user_data.get('step', '')

    if step == 'waiting_pickup':
        context.user_data['pickup_location'] = text
        context.user_data['step'] = 'waiting_destination'

        await update.message.reply_text(
            f"تم تسجيل موقع الانطلاق: {text} ✅\n\nالآن أرسل موقع الوجهة أو اسم المكان 📍"
        )

    elif step == 'waiting_destination':
        pickup_location = context.user_data.get('pickup_location')

        # إنشاء الرحلة
        ride_id = db.create_ride(
            client_id=user_id,
            pickup_location=pickup_location,
            destination=text
        )

        if ride_id:
            await update.message.reply_text(
                f"تم إنشاء طلب الرحلة بنجاح! ✅\n\n"
                f"رقم الرحلة: {ride_id}\n"
                f"من: {pickup_location}\n"
                f"إلى: {text}\n\n"
                f"سيتم إشعارك عند قبول أحد الكباتن للرحلة 🚖"
            )
            # مسح البيانات المؤقتة
            context.user_data.clear()
        else:
            await update.message.reply_text("حدث خطأ في إنشاء الرحلة. يرجى المحاولة مرة أخرى.")

# معالج رسائل المجموعة للإشراف على المحتوى
async def group_message_handler(update: Update, context):
    """معالج رسائل المجموعة للإشراف على المحتوى"""
    if not update.message or not update.message.text:
        return

    message = update.message
    user_id = message.from_user.id
    chat_id = message.chat_id
    message_text = message.text

    # فحص المحتوى المخالف
    if moderation.check_message_content(message_text):
        try:
            # حذف الرسالة المخالفة
            await message.delete()

            # إضافة تحذير للمستخدم
            moderation.add_user_warning(
                user_id=user_id,
                reason="محتوى مخالف",
                warned_by=context.bot.id
            )

            # فحص إذا كان يجب حظر المستخدم
            if moderation.should_ban_user(user_id):
                try:
                    await context.bot.ban_chat_member(chat_id, user_id)
                    await context.bot.send_message(
                        chat_id,
                        f"تم حظر المستخدم {message.from_user.first_name} لانتهاك قوانين المجموعة متكرراً."
                    )
                except Exception as e:
                    logger.error(f"Failed to ban user {user_id}: {e}")
            else:
                # إرسال تحذير للمستخدم
                warnings_count = moderation.get_user_warnings_count(user_id)
                await context.bot.send_message(
                    chat_id,
                    f"تحذير: {message.from_user.first_name}\n"
                    f"تم حذف رسالتك لانتهاك قوانين المجموعة.\n"
                    f"عدد التحذيرات: {warnings_count}/3"
                )

        except Exception as e:
            logger.error(f"Moderation error: {e}")

# أوامر الإدارة
async def add_banned_word_command(update: Update, context):
    """إضافة كلمة محظورة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("استخدم: /add_banned_word <الكلمة>")
        return

    word = " ".join(context.args)
    if moderation.add_banned_word(word, update.effective_user.id):
        await update.message.reply_text(f"تم إضافة الكلمة '{word}' إلى قائمة الكلمات المحظورة.")
    else:
        await update.message.reply_text("حدث خطأ في إضافة الكلمة.")

async def remove_banned_word_command(update: Update, context):
    """إزالة كلمة من قائمة المحظورات"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("استخدم: /remove_banned_word <الكلمة>")
        return

    word = " ".join(context.args)
    if moderation.remove_banned_word(word):
        await update.message.reply_text(f"تم إزالة الكلمة '{word}' من قائمة الكلمات المحظورة.")
    else:
        await update.message.reply_text("الكلمة غير موجودة في القائمة.")

async def list_banned_words_command(update: Update, context):
    """عرض قائمة الكلمات المحظورة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    banned_words = moderation.get_banned_words_list()
    if banned_words:
        words_list = "\n".join(f"• {word}" for word in banned_words)
        await update.message.reply_text(f"الكلمات المحظورة:\n\n{words_list}")
    else:
        await update.message.reply_text("لا توجد كلمات محظورة.")

async def schedule_message_command(update: Update, context):
    """جدولة رسالة متكررة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "استخدم: /schedule <ساعات_التكرار> <أيام_المدة> <نص_الرسالة>\n"
            "مثال: /schedule 5 7 مرحباً بكم في مجموعة مشاوير مكة"
        )
        return

    try:
        interval_hours = int(context.args[0])
        duration_days = int(context.args[1])
        message_text = " ".join(context.args[2:])

        if moderation.schedule_message(
            chat_id=update.effective_chat.id,
            message_text=message_text,
            interval_hours=interval_hours,
            duration_days=duration_days,
            created_by=update.effective_user.id
        ):
            await update.message.reply_text(
                f"تم جدولة الرسالة بنجاح!\n"
                f"التكرار: كل {interval_hours} ساعة\n"
                f"المدة: {duration_days} يوم"
            )
        else:
            await update.message.reply_text("حدث خطأ في جدولة الرسالة.")

    except ValueError:
        await update.message.reply_text("يرجى إدخال أرقام صحيحة للساعات والأيام.")

async def error_handler(update: Update, context):
    """معالج الأخطاء العام"""
    logger.error(f"Exception while handling an update: {context.error}")

    # إرسال رسالة خطأ ودود للمستخدم
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة مرة أخرى أو التواصل مع الإدارة."
        )

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        print("Error: BOT_TOKEN not found. Please set it in your .env file.")
        return

    try:
        logger.info("Bot is starting...")
        print("Bot is starting...")

        app = Application.builder().token(BOT_TOKEN).build()

        # إضافة الأوامر والمعالجات
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.LOCATION, location_handler))

        # أوامر الإدارة
        app.add_handler(CommandHandler("add_banned_word", add_banned_word_command))
        app.add_handler(CommandHandler("remove_banned_word", remove_banned_word_command))
        app.add_handler(CommandHandler("list_banned_words", list_banned_words_command))
        app.add_handler(CommandHandler("schedule", schedule_message_command))

        # معالج رسائل المجموعة (للإشراف)
        app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_message_handler))

        # معالج الرسائل الخاصة
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_handler))

        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)

        # تعطيل المجدولة مؤقتاً للتركيز على الوظائف الأساسية
        logger.info("Scheduled messages feature temporarily disabled")

        # تشغيل البوت
        logger.info("Bot started polling...")
        print("Polling...")

        app.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Fatal error: {e}")
    finally:
        logger.info("Bot shutdown")

if __name__ == '__main__':
    main()
