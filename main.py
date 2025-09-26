import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import Database

# تحميل متغيرات البيئة من ملف .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# إعداد قاعدة البيانات
db = Database()

# إعداد نظام السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# هذا هو الأمر الذي سيتم تشغيله عند إضافة البوت إلى مجموعة أو عند كتابة /start
async def start_command(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("إذا كنت عميل اضغط هنا", callback_data='client_button')],
        [InlineKeyboardButton("كابتن اضغط هنا", callback_data='captain_button')],
        [InlineKeyboardButton("الاشتراك", callback_data='subscribe_button'), InlineKeyboardButton("تنبيه ⚠️", callback_data='warning_button')],
        [InlineKeyboardButton("الإدارة المباشرة", url="t.me/semodbwan")], # استبدل بمعرف المدير
        [InlineKeyboardButton("الاستفسار عن باقات إعلاناتكم", callback_data='ads_button')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # إضافة المستخدم إلى قاعدة البيانات
    user = update.effective_user
    db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

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

    if data == 'client_button':
        db.update_user_type(user_id, 'client')
        keyboard = [
            [InlineKeyboardButton("طلب رحلة 🚗", callback_data='request_ride')],
            [InlineKeyboardButton("رحلاتي السابقة 📋", callback_data='my_rides')],
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "مرحباً بك كعميل! 👤\n\nيمكنك الآن طلب رحلة أو مراجعة رحلاتك السابقة:",
            reply_markup=reply_markup
        )

    elif data == 'captain_button':
        db.update_user_type(user_id, 'captain')
        keyboard = [
            [InlineKeyboardButton("عرض الرحلات المتاحة 🔍", callback_data='view_rides')],
            [InlineKeyboardButton("رحلاتي ككابتن 📊", callback_data='captain_rides')],
            [InlineKeyboardButton("العودة للقائمة الرئيسية ↩️", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "مرحباً بك ككابتن! 🚖\n\nيمكنك الآن عرض الرحلات المتاحة أو مراجعة رحلاتك:",
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
        await query.edit_message_text(
            "خدمة الاشتراك 💳\n\n"
            "للاشتراك في خدماتنا المميزة:\n"
            "• رحلات مخفضة السعر\n"
            "• أولوية في قبول الرحلات\n"
            "• دعم فني متقدم\n\n"
            "للمزيد من المعلومات، تواصل مع الإدارة."
        )

    elif data == 'warning_button':
        await query.edit_message_text(
            "تنبيه مهم ⚠️\n\n"
            "• تأكد من صحة المعلومات قبل الموافقة على الرحلة\n"
            "• لا تتردد في التواصل مع الإدارة في حالة وجود مشكلة\n"
            "• احرص على سلامتك أولاً\n"
            "• تأكد من هوية الطرف الآخر\n\n"
            "مع تحيات إدارة مشاوير مكة"
        )

    elif data == 'ads_button':
        await query.edit_message_text(
            "باقات الإعلانات 📢\n\n"
            "لدينا عدة باقات إعلانية مناسبة لجميع الاحتياجات:\n\n"
            "• الباقة الأساسية: 50 ريال/أسبوع\n"
            "• الباقة المتقدمة: 150 ريال/شهر\n"
            "• الباقة المميزة: 400 ريال/3 أشهر\n\n"
            "للمزيد من التفاصيل تواصل مع الإدارة المباشرة."
        )

    elif data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("إذا كنت عميل اضغط هنا", callback_data='client_button')],
            [InlineKeyboardButton("كابتن اضغط هنا", callback_data='captain_button')],
            [InlineKeyboardButton("الاشتراك", callback_data='subscribe_button'), InlineKeyboardButton("تنبيه ⚠️", callback_data='warning_button')],
            [InlineKeyboardButton("الإدارة المباشرة", url="t.me/semodbwan")],
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
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)

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
