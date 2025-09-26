import os
import logging
import sqlite3
import math
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest
from database import Database
from moderation import ModerationSystem
from scheduler import MessageScheduler

# تحميل متغيرات البيئة من ملف .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
CAPTAIN_GROUP_ID = os.getenv("CAPTAIN_GROUP_ID")

# التحقق من متغيرات البيئة الأساسية
if not all([BOT_TOKEN, ADMIN_CHAT_ID, CAPTAIN_GROUP_ID]):
    missing_vars = [var for var, val in {
        "BOT_TOKEN": BOT_TOKEN,
        "ADMIN_CHAT_ID": ADMIN_CHAT_ID,
        "CAPTAIN_GROUP_ID": CAPTAIN_GROUP_ID
    }.items() if not val]
    logger.error(f"Missing critical environment variables: {', '.join(missing_vars)}")
    exit(f"Error: Missing environment variables: {', '.join(missing_vars)}")

# تحويل المعرفات إلى أرقام
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    CAPTAIN_GROUP_ID = int(CAPTAIN_GROUP_ID)
except (ValueError, TypeError) as e:
    logger.error(f"Invalid format for ADMIN_CHAT_ID or CAPTAIN_GROUP_ID. They must be integers. Error: {e}")
    exit(f"Error: Invalid chat ID format. {e}")

# إعداد قاعدة البيانات ونظام الإشراف
db = Database()
moderation = ModerationSystem()

# إعداد نظام السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def calculate_distance(lat1, lon1, lat2, lon2):
    """حساب المسافة بين نقطتين بالكيلومتر (صيغة هافرسين)"""
    # تحويل الدرجات إلى راديان
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # صيغة هافرسين
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    # نصف قطر الأرض بالكيلومتر
    r = 6371

    return c * r

# هذا هو الأمر الذي سيتم تشغيله عند إضافة البوت إلى مجموعة أو عند كتابة /start
async def start_command(update: Update, context):
    logger.info(f"Start command received from user {update.effective_user.id}")

    keyboard = [
        [InlineKeyboardButton("🧑‍💼 أريد طلب رحلة (عميل)", callback_data='client_button')],
        [InlineKeyboardButton("🚗 أريد توصيل الناس (كابتن)", callback_data='captain_button')],
        [InlineKeyboardButton("💳 اشتراك الكباتن", callback_data='subscribe_button'), InlineKeyboardButton("⚠️ تنبيه مهم", callback_data='warning_button')],
        [InlineKeyboardButton("📞 التواصل المباشر مع الإدارة", url="https://t.me/novacompnay")],
        [InlineKeyboardButton("📢 الاستفسار عن باقات الإعلانات", callback_data='ads_button')]
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

    welcome_message = """🕋 **أهلاً وسهلاً بكم في بوت مشاوير مكة اليومية** 🕋

🚗 منصتكم المتكاملة للتنقل في مكة المكرمة
⚡ رحلات سريعة وآمنة على مدار الساعة
💯 خدمة موثوقة ومضمونة

👇 **اختر نوع حسابك للمتابعة:**"""

    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
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
            # تعيين حالة المستخدم لانتظار النموذج المعبأ
            context.user_data['step'] = 'waiting_form_response'

            await query.edit_message_text(
                "تم إرسال نموذج طلب السائق إلى رسائلك الخاصة 📩\n\n"
                "قم بتعبئة النموذج وإرساله هنا في الرسائل الخاصة، أو انسخه وأرسله في المجموعة.\n\n"
                "أو يمكنك طلب رحلة فورية:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚗 طلب رحلة فورية", callback_data='request_ride')
                ], [
                    InlineKeyboardButton("📋 متابعة رحلاتي", callback_data='my_rides')
                ]])
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
            [InlineKeyboardButton("🚖 عرض الرحلات المتاحة", callback_data='view_rides')],
            [InlineKeyboardButton("📋 رحلاتي النشطة", callback_data='my_active_rides')],
            [InlineKeyboardButton("💳 اشتراك الكباتن (10 ريال/شهر)", callback_data='pay_subscription')],
            [InlineKeyboardButton("📊 حالة الدفعات والاشتراك", callback_data='my_payments')],
            [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data='main_menu')]
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
        # فحص الاشتراك قبل عرض الرحلات
        if not db.is_captain_subscribed(user_id):
            subscription_info = db.get_subscription_info(user_id)
            await query.edit_message_text(
                "❌ عذراً، يجب أن تكون مشتركاً لعرض الرحلات المتاحة\n\n"
                "💳 اشتراك الكباتن: 10 ريال شهرياً\n"
                "🎯 احصل على وصول كامل لجميع الرحلات المتاحة",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 دفع الاشتراك (10 ريال)", callback_data='pay_subscription')],
                    [InlineKeyboardButton("📞 تواصل مع الإدارة", url="https://t.me/novacompnay")],
                    [InlineKeyboardButton("العودة ↩️", callback_data='captain_button')]
                ])
            )
            return

        rides = db.get_pending_rides()
        if not rides:
            await query.edit_message_text("لا توجد رحلات متاحة حالياً 😔")
            return

        message = "الرحلات المتاحة 🚗:\n\n"
        keyboard = []

        for ride in rides[:5]:  # عرض أول 5 رحلات
            message += f"🆔 رحلة #{ride['ride_id']}\n"
            message += f"🔹 من: {ride['pickup_location']}\n"
            message += f"🏁 إلى: {ride['destination']}\n"

            # إضافة الإحداثيات إذا كانت متوفرة
            if ride.get('pickup_latitude') and ride.get('pickup_longitude'):
                pickup_maps = f"https://maps.google.com/?q={ride['pickup_latitude']},{ride['pickup_longitude']}"
                message += f"📍 [موقع الانطلاق]({pickup_maps})\n"

            if ride.get('destination_latitude') and ride.get('destination_longitude'):
                dest_maps = f"https://maps.google.com/?q={ride['destination_latitude']},{ride['destination_longitude']}"
                message += f"🏁 [موقع الوجهة]({dest_maps})\n"

                # حساب المسافة إذا كانت الإحداثيات متوفرة
                if ride.get('pickup_latitude') and ride.get('pickup_longitude'):
                    distance = calculate_distance(
                        ride['pickup_latitude'], ride['pickup_longitude'],
                        ride['destination_latitude'], ride['destination_longitude']
                    )
                    message += f"📏 المسافة: {distance:.1f} كم\n"

            if ride['price']:
                message += f"💰 السعر: {ride['price']} ريال\n"
            message += f"👤 العميل: {ride['first_name']}\n\n"

            keyboard.append([InlineKeyboardButton(
                f"✅ قبول الرحلة #{ride['ride_id']} 🚗",
                callback_data=f"accept_ride_{ride['ride_id']}"
            )])

        keyboard.append([InlineKeyboardButton("تحديث القائمة 🔄", callback_data='view_rides')])
        keyboard.append([InlineKeyboardButton("العودة ↩️", callback_data='captain_button')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)

    elif data.startswith('accept_ride_'):
        ride_id = int(data.split('_')[2])
        if db.accept_ride(ride_id, user_id):
            ride = db.get_ride_by_id(ride_id)
            await query.edit_message_text(
                f"تم قبول الرحلة #{ride_id} بنجاح! ✅\n\n"
                f"من: {ride['pickup_location']}\n"
                f"إلى: {ride['destination']}\n"
                f"العميل: {ride['client_name']}\n\n"
                f"يمكنك الآن بدء الرحلة عندما تكون جاهزاً.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"بدء الرحلة ▶️", callback_data=f"start_ride_{ride_id}")
                ], [
                    InlineKeyboardButton("رحلاتي النشطة 📋", callback_data='my_active_rides')
                ]])
            )

            # إشعار العميل
            try:
                await context.bot.send_message(
                    chat_id=ride['client_id'],
                    text=f"تم قبول رحلتك #{ride_id} ✅\n\n"
                    f"الكابتن: {query.from_user.first_name}\n"
                    f"سيبدأ الرحلة قريباً وسيتواصل معك."
                )
            except Exception as e:
                logger.error(f"Failed to notify client: {e}")
        else:
            await query.edit_message_text("عذراً، هذه الرحلة لم تعد متاحة 😔")

    elif data.startswith('publish_request_'):
        request_id = int(data.split('_')[2])
        
        # التأكد من أن المستخدم هو المدير
        if str(user_id) != ADMIN_CHAT_ID:
            await query.answer("هذا الإجراء مخصص للمدير فقط.", show_alert=True)
            return

        monthly_request = db.get_monthly_request(request_id)
        if not monthly_request:
            await query.edit_message_text("❌ لم يتم العثور على الطلب.")
            return

        if monthly_request['status'] == 'published':
            await query.answer("✅ تم نشر هذا الطلب مسبقاً.", show_alert=True)
            return
            
        # تجهيز الرسالة للنشر في مجموعة الكباتن
        captain_message = f"""📢 **طلب توصيل شهري جديد** 📢
        
{monthly_request['request_details']}
"""

        try:
            # نشر الرسالة في مجموعة الكباتن
            if not CAPTAIN_GROUP_ID:
                await query.edit_message_text("❌ لم يتم تعيين مجموعة الكباتن. يرجى تعيين CAPTAIN_GROUP_ID في ملف .env")
                return
                
            await context.bot.send_message(
                chat_id=CAPTAIN_GROUP_ID,
                text=captain_message,
                parse_mode='Markdown'
            )

            # تحديث حالة الطلب في قاعدة البيانات
            db.update_monthly_request_status(request_id, 'published')
            
            # تحديث رسالة المدير
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ تم النشر بنجاح", callback_data='dummy')],
                [InlineKeyboardButton("📝 إغلاق الطلب", callback_data=f'close_request_{request_id}')]
            ])
            await query.edit_message_text(
                text=query.message.text,
                reply_markup=keyboard
            )
            await query.answer("✅ تم نشر الطلب في مجموعة الكباتن بنجاح!", show_alert=True)

        except Exception as e:
            logger.error(f"Failed to publish request to captain's group: {e}")
            await query.answer(f"❌ حدث خطأ أثناء النشر: {e}", show_alert=True)

    elif data == 'my_active_rides':
        active_rides = db.get_captain_active_rides(user_id)
        if not active_rides:
            await query.edit_message_text(
                "لا توجد رحلات نشطة حالياً 😔\n\nيمكنك البحث عن رحلات جديدة من خلال 'عرض الرحلات المتاحة'",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("عرض الرحلات المتاحة 🚖", callback_data='view_rides')
                ], [
                    InlineKeyboardButton("العودة ↩️", callback_data='captain_button')
                ]])
            )
            return

        message = "رحلاتك النشطة 🚖:\n\n"
        keyboard = []

        for ride in active_rides:
            status_emoji = "🟡" if ride['status'] == 'accepted' else "🟢"
            status_text = "مقبولة" if ride['status'] == 'accepted' else "قيد التنفيذ"

            message += f"{status_emoji} رحلة #{ride['ride_id']}\n"
            message += f"   من: {ride['pickup_location']}\n"
            message += f"   إلى: {ride['destination']}\n"
            message += f"   العميل: {ride['first_name']}\n"
            message += f"   الحالة: {status_text}\n\n"

            if ride['status'] == 'accepted':
                keyboard.append([InlineKeyboardButton(
                    f"بدء الرحلة #{ride['ride_id']} ▶️",
                    callback_data=f"start_ride_{ride['ride_id']}"
                )])
            elif ride['status'] == 'in_progress':
                keyboard.append([InlineKeyboardButton(
                    f"🏁 إنهاء الرحلة #{ride['ride_id']} ✅",
                    callback_data=f"complete_ride_{ride['ride_id']}"
                )])

        keyboard.append([InlineKeyboardButton("تحديث القائمة 🔄", callback_data='my_active_rides')])
        keyboard.append([InlineKeyboardButton("العودة ↩️", callback_data='captain_button')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif data.startswith('start_ride_'):
        ride_id = int(data.split('_')[2])
        if db.start_ride(ride_id, user_id):
            ride = db.get_ride_by_id(ride_id)
            await query.edit_message_text(
                f"تم بدء الرحلة #{ride_id} بنجاح! 🚖\n\n"
                f"من: {ride['pickup_location']}\n"
                f"إلى: {ride['destination']}\n"
                f"العميل: {ride['client_name']}\n\n"
                f"اضغط 'إنهاء الرحلة' عند الوصول للوجهة.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"إنهاء الرحلة ✅", callback_data=f"complete_ride_{ride_id}")
                ], [
                    InlineKeyboardButton("رحلاتي النشطة 📋", callback_data='my_active_rides')
                ]])
            )

            # إشعار العميل
            try:
                await context.bot.send_message(
                    chat_id=ride['client_id'],
                    text=f"تم بدء رحلتك #{ride_id} 🚖\n\n"
                    f"الكابتن: {query.from_user.first_name}\n"
                    f"في الطريق إليك الآن!"
                )
            except Exception as e:
                logger.error(f"Failed to notify client: {e}")
        else:
            await query.edit_message_text("حدث خطأ في بدء الرحلة.")

    elif data.startswith('complete_ride_'):
        ride_id = int(data.split('_')[2])
        if db.complete_ride(ride_id, user_id):
            ride = db.get_ride_by_id(ride_id)
            await query.edit_message_text(
                f"تم إنهاء الرحلة #{ride_id} بنجاح! ✅\n\n"
                f"شكراً لك على الخدمة المميزة 🙏",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("رحلاتي النشطة 📋", callback_data='my_active_rides')
                ], [
                    InlineKeyboardButton("عرض رحلات جديدة 🚖", callback_data='view_rides')
                ]])
            )

            # إشعار العميل بإمكانية التقييم والدفع
            try:
                await context.bot.send_message(
                    chat_id=ride['client_id'],
                    text=f"تم إنهاء رحلتك #{ride_id} بنجاح! ✅\n\n"
                    f"نتمنى أن تكون قد استمتعت بالرحلة.\n"
                    f"يمكنك تقييم الكابتن ودفع قيمة الرحلة:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌟 قييم الكابتن 🌟", callback_data=f"rate_info_{ride_id}")],
                        [
                            InlineKeyboardButton("1⭐", callback_data=f"rate_1_{ride_id}_{user_id}"),
                            InlineKeyboardButton("2⭐⭐", callback_data=f"rate_2_{ride_id}_{user_id}"),
                            InlineKeyboardButton("3⭐⭐⭐", callback_data=f"rate_3_{ride_id}_{user_id}")
                        ],
                        [
                            InlineKeyboardButton("4⭐⭐⭐⭐", callback_data=f"rate_4_{ride_id}_{user_id}"),
                            InlineKeyboardButton("5⭐⭐⭐⭐⭐", callback_data=f"rate_5_{ride_id}_{user_id}")
                        ],
                        [InlineKeyboardButton("💰 ادفع للكابتن الآن", callback_data=f"pay_ride_{ride_id}")]
                    ])
                )
            except Exception as e:
                logger.error(f"Failed to notify client: {e}")
        else:
            await query.edit_message_text("حدث خطأ في إنهاء الرحلة.")

    elif data.startswith('rate_'):
        parts = data.split('_')
        rating = int(parts[1])
        ride_id = int(parts[2])
        captain_id = int(parts[3])

        if db.add_rating(ride_id, user_id, captain_id, rating):
            await query.edit_message_text(
                f"شكراً لك على التقييم! ⭐\n\n"
                f"تم إعطاء {rating} نجمة للكابتن.\n"
                f"تقييمك يساعدنا في تحسين الخدمة.\n\n"
                f"يمكنك الآن دفع قيمة الرحلة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 دفع قيمة الرحلة", callback_data=f"pay_ride_{ride_id}")]
                ])
            )
        else:
            await query.edit_message_text("حدث خطأ في حفظ التقييم.")

    elif data.startswith('pay_ride_'):
        ride_id = int(data.split('_')[2])
        ride = db.get_ride_by_id(ride_id)

        if not ride or ride['client_id'] != user_id:
            await query.edit_message_text("لا يمكن العثور على الرحلة أو ليست مخصصة لك.")
            return

        if ride['status'] != 'completed':
            await query.edit_message_text("يمكن دفع قيمة الرحلة فقط بعد إنهائها.")
            return

        # عرض خيارات الدفع للرحلة
        await query.edit_message_text(
            f"💳 دفع قيمة الرحلة #{ride_id}\n\n"
            f"🚗 من: {ride['pickup_location']}\n"
            f"🏁 إلى: {ride['destination']}\n"
            f"👤 الكابتن: {ride['captain_name'] or 'غير محدد'}\n\n"
            f"💰 يرجى إدخال قيمة الرحلة المتفق عليها مع الكابتن:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💰 10 ريال", callback_data=f'ride_amount_10_{ride_id}'),
                    InlineKeyboardButton("💰 15 ريال", callback_data=f'ride_amount_15_{ride_id}')
                ],
                [
                    InlineKeyboardButton("💰 20 ريال", callback_data=f'ride_amount_20_{ride_id}'),
                    InlineKeyboardButton("💰 25 ريال", callback_data=f'ride_amount_25_{ride_id}')
                ],
                [InlineKeyboardButton("💰 30 ريال", callback_data=f'ride_amount_30_{ride_id}')],
                [InlineKeyboardButton("العودة ↩️", callback_data='my_rides')]
            ])
        )

    elif data.startswith('ride_amount_'):
        parts = data.split('_')
        amount = float(parts[2])
        ride_id = int(parts[3])

        ride = db.get_ride_by_id(ride_id)
        if not ride or ride['client_id'] != user_id:
            await query.edit_message_text("خطأ في العثور على الرحلة.")
            return

        # إنشاء طلب دفع للرحلة
        request_id = db.create_payment_request(
            user_id=user_id,
            payment_type='ride_payment',
            amount=amount,
            description=f'دفع رحلة #{ride_id}',
            ride_id=ride_id
        )

        if request_id:
            await query.edit_message_text(
                f"💳 دفع قيمة الرحلة\n\n"
                f"💰 المبلغ: {amount} ريال سعودي\n"
                f"🚗 الرحلة: #{ride_id}\n\n"
                f"اختر طريقة الدفع:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💵 دفع نقدي للكابتن ⭐ (الأسرع والأفضل)", callback_data=f'payment_method_cash_{request_id}')],
                    [InlineKeyboardButton("📱 STC Pay", callback_data=f'payment_method_stc_{request_id}'), InlineKeyboardButton("🏦 الراجحي", callback_data=f'payment_method_bank_{request_id}')],
                    [InlineKeyboardButton("💰 urpay", callback_data=f'payment_method_urpay_{request_id}'), InlineKeyboardButton("💳 مدى MADA", callback_data=f'payment_method_mada_{request_id}')],
                    [InlineKeyboardButton("العودة ↩️", callback_data='my_rides')]
                ])
            )
        else:
            await query.edit_message_text("حدث خطأ في إنشاء طلب الدفع.")

    elif data == 'my_rides':
        user_rides = db.get_user_rides(user_id, 10)
        if not user_rides:
            await query.edit_message_text(
                "لا توجد رحلات سابقة 😔\n\nيمكنك طلب رحلة جديدة الآن:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("طلب رحلة فورية 🚗", callback_data='request_ride')
                ], [
                    InlineKeyboardButton("العودة ↩️", callback_data='client_button')
                ]])
            )
            return

        message = "رحلاتك 📋:\n\n"
        keyboard = []

        for ride in user_rides[:5]:  # عرض أول 5 رحلات
            status_emoji = {
                'pending': '🟡',
                'accepted': '🟢',
                'in_progress': '🔵',
                'completed': '✅',
                'cancelled': '❌'
            }.get(ride['status'], '❓')

            status_text = {
                'pending': 'في الانتظار',
                'accepted': 'مقبولة',
                'in_progress': 'قيد التنفيذ',
                'completed': 'مكتملة',
                'cancelled': 'ملغية'
            }.get(ride['status'], 'غير معروف')

            message += f"{status_emoji} رحلة #{ride['ride_id']}\n"
            message += f"   من: {ride['pickup_location']}\n"
            message += f"   إلى: {ride['destination']}\n"
            message += f"   الحالة: {status_text}\n"
            if ride['price']:
                message += f"   السعر: {ride['price']} ريال\n"
            message += "\n"

            # إضافة أزرار حسب حالة الرحلة
            if ride['status'] == 'pending':
                keyboard.append([InlineKeyboardButton(
                    f"إلغاء الرحلة #{ride['ride_id']} ❌",
                    callback_data=f"cancel_ride_{ride['ride_id']}"
                )])

        keyboard.append([InlineKeyboardButton("طلب رحلة جديدة 🚗", callback_data='request_ride')])
        keyboard.append([InlineKeyboardButton("العودة ↩️", callback_data='client_button')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    elif data.startswith('cancel_ride_'):
        ride_id = int(data.split('_')[2])
        if db.cancel_ride(ride_id, user_id):
            await query.edit_message_text(
                f"تم إلغاء الرحلة #{ride_id} بنجاح ❌\n\n"
                f"يمكنك طلب رحلة جديدة في أي وقت.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("طلب رحلة جديدة 🚗", callback_data='request_ride')
                ], [
                    InlineKeyboardButton("رحلاتي 📋", callback_data='my_rides')
                ]])
            )
        else:
            await query.edit_message_text("لا يمكن إلغاء هذه الرحلة.")

    elif data == 'pay_subscription':
        # إنشاء طلب دفع اشتراك
        request_id = db.create_payment_request(
            user_id=user_id,
            payment_type='subscription_payment',
            amount=10.0,
            description='اشتراك كابتن - شهر واحد',
            subscription_days=30
        )

        if request_id:
            await query.edit_message_text(
                "💳 دفع اشتراك الكباتن\n\n"
                "💰 المبلغ: 10 ريال سعودي\n"
                "⏰ المدة: شهر واحد (30 يوم)\n\n"
                "اختر طريقة الدفع المناسبة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 STC Pay", callback_data=f'payment_method_stc_{request_id}')],
                    [InlineKeyboardButton("🏦 حوالة بنكية", callback_data=f'payment_method_bank_{request_id}')],
                    [InlineKeyboardButton("💰 يور باي urpay", callback_data=f'payment_method_urpay_{request_id}')],
                    [InlineKeyboardButton("💳 مدى MADA", callback_data=f'payment_method_mada_{request_id}')],
                    [InlineKeyboardButton("❌ إلغاء", callback_data='captain_button')]
                ])
            )
        else:
            await query.edit_message_text("حدث خطأ في إنشاء طلب الدفع. يرجى المحاولة مرة أخرى.")

    elif data.startswith('payment_method_'):
        parts = data.split('_')
        payment_method = parts[2]
        request_id = int(parts[3])

        payment_request = db.get_payment_request(request_id)
        if not payment_request or payment_request['user_id'] != user_id:
            await query.edit_message_text("طلب الدفع غير صحيح أو منتهي الصلاحية.")
            return

        # معلومات الدفع حسب الطريقة
        payment_info = {
            'cash': {
                'name': 'الدفع النقدي',
                'details': '💵 ادفع نقداً للكابتن مباشرة\n✅ الطريقة الأسرع والأسهل',
                'instructions': 'قم بدفع المبلغ نقداً للكابتن في نهاية الرحلة ثم اضغط "تم الدفع"'
            },
            'stc': {
                'name': 'STC Pay',
                'details': '📱 رقم STC Pay: 0501234567\n👤 باسم: إدارة مشاوير مكة',
                'instructions': 'قم بتحويل المبلغ عبر STC Pay ثم أرسل لقطة شاشة للتحويل'
            },
            'bank': {
                'name': 'الحوالة البنكية',
                'details': '🏦 البنك: الراجحي\n💳 رقم الحساب: 123456789\n👤 باسم: إدارة مشاوير مكة',
                'instructions': 'قم بتحويل المبلغ ثم أرسل صورة إيصال التحويل'
            },
            'urpay': {
                'name': 'يور باي urpay',
                'details': '📱 رقم urpay: 0501234567\n👤 باسم: إدارة مشاوير مكة',
                'instructions': 'قم بتحويل المبلغ عبر urpay ثم أرسل لقطة شاشة للتحويل'
            },
            'mada': {
                'name': 'مدى MADA',
                'details': '💳 رقم البطاقة: 1234-5678-9012-3456\n👤 باسم: إدارة مشاوير مكة',
                'instructions': 'قم بتحويل المبلغ ثم أرسل إيصال التحويل'
            }
        }

        info = payment_info.get(payment_method, payment_info['stc'])

        # خاص للدفع النقدي - لا يحتاج إثبات دفع
        if payment_method == 'cash':
            await query.edit_message_text(
                f"💵 {info['name']}\n\n"
                f"💰 المبلغ المطلوب: {payment_request['amount']} ريال\n\n"
                f"{info['details']}\n\n"
                f"📋 التعليمات:\n"
                f"{info['instructions']}\n\n"
                f"✅ بعد دفع المبلغ للكابتن، اضغط 'تم الدفع' للتأكيد",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تم الدفع نقداً للكابتن 💵", callback_data=f'cash_paid_{request_id}')],
                    [InlineKeyboardButton("🔄 تغيير طريقة الدفع", callback_data=f'pay_ride_{payment_request.get("ride_id", "")}'  if payment_request.get('payment_type') == 'ride_payment' else 'pay_subscription')],
                    [InlineKeyboardButton("العودة ↩️", callback_data='my_rides' if payment_request.get('payment_type') == 'ride_payment' else 'captain_button')]
                ])
            )
        else:
            # الطرق الرقمية - تحتاج إثبات دفع
            await query.edit_message_text(
                f"💳 الدفع عبر {info['name']}\n\n"
                f"💰 المبلغ المطلوب: {payment_request['amount']} ريال\n\n"
                f"{info['details']}\n\n"
                f"📋 التعليمات:\n"
                f"{info['instructions']}\n\n"
                f"⚠️ ملاحظة: أرسل إثبات الدفع كصورة في هذه المحادثة",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ تم الدفع - إرسال الإثبات", callback_data=f'payment_proof_{request_id}_{payment_method}')],
                    [InlineKeyboardButton("🔄 تغيير طريقة الدفع", callback_data=f'pay_ride_{payment_request.get("ride_id", "")}' if payment_request.get('payment_type') == 'ride_payment' else 'pay_subscription')],
                    [InlineKeyboardButton("العودة ↩️", callback_data='my_rides' if payment_request.get('payment_type') == 'ride_payment' else 'captain_button')]
                ])
            )

    elif data.startswith('cash_paid_'):
        request_id = int(data.split('_')[2])
        payment_request = db.get_payment_request(request_id)

        if not payment_request or payment_request['user_id'] != user_id:
            await query.edit_message_text("طلب الدفع غير صحيح أو منتهي الصلاحية.")
            return

        # إنشاء دفعة نقدية مع تأكيد فوري
        try:
            payment_id = db.create_payment_record(
                user_id=user_id,
                payment_type=payment_request['payment_type'],
                amount=payment_request['amount'],
                payment_method='cash',
                ride_id=payment_request.get('ride_id'),
                payment_proof_url=None,  # لا يوجد إثبات للنقد
                notes=f"Cash payment for {payment_request['payment_type']} - Request ID: {request_id}"
            )
            logger.info(f"Created cash payment record with ID: {payment_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Error creating cash payment record: {e}")
            payment_id = None

        if payment_id:
            # تحديث حالة طلب الدفع
            db.update_payment_request_status(request_id, 'completed')

            await query.edit_message_text(
                "✅ تم تأكيد الدفع النقدي!\n\n"
                "💵 تم استلام الدفع نقداً من الكابتن\n"
                "🙏 شكراً لاستخدام خدماتنا"
            )

            # إشعار الإدارة بالدفع النقدي
            try:
                ride_info = ""
                if payment_request.get('ride_id'):
                    ride_info = f"🚗 رقم الرحلة: {payment_request['ride_id']}\n"

                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=f"💵 دفع نقدي جديد\n\n"
                    f"👤 العميل: {update.effective_user.first_name}\n"
                    f"🆔 معرف العميل: {user_id}\n"
                    f"💰 المبلغ: {payment_request['amount']} ريال\n"
                    f"📋 النوع: {payment_request['payment_type']}\n"
                    f"{ride_info}"
                    f"🆔 Payment ID: {payment_id}\n\n"
                    f"✅ تم التأكيد تلقائياً (دفع نقدي)"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin about cash payment: {e}")

            # تفعيل الاشتراك إذا كان الدفع للاشتراك
            if payment_request['payment_type'] == 'subscription':
                if db.add_subscription(user_id, 30, payment_request['amount']):
                    await update.effective_user.send_message(
                        "🎉 تم تفعيل اشتراكك بنجاح!\n\n"
                        "⏰ مدة الاشتراك: 30 يوم\n"
                        "✅ يمكنك الآن الوصول لجميع الرحلات المتاحة"
                    )
        else:
            logger.error(f"Failed to create cash payment record for request {request_id}")
            await query.edit_message_text("حدث خطأ في معالجة الدفع. يرجى المحاولة مرة أخرى.")

    elif data.startswith('payment_proof_'):
        parts = data.split('_')
        request_id = int(parts[2])
        payment_method = parts[3]

        payment_request = db.get_payment_request(request_id)
        if not payment_request or payment_request['user_id'] != user_id:
            await query.edit_message_text("طلب الدفع غير صحيح أو منتهي الصلاحية.")
            return

        # تحديث حالة طلب الدفع لانتظار الإثبات
        db.update_payment_request_status(request_id, 'awaiting_proof')

        # حفظ معلومات الدفع في بيانات المستخدم للمعالجة اللاحقة
        context.user_data['payment_request_id'] = request_id
        context.user_data['payment_method'] = payment_method
        context.user_data['awaiting_payment_proof'] = True

        await query.edit_message_text(
            "📷 يرجى إرسال صورة إثبات الدفع الآن\n\n"
            "✅ تأكد من وضوح المبلغ وتاريخ التحويل في الصورة\n"
            "⏰ سيتم مراجعة الدفع خلال 24 ساعة كحد أقصى\n\n"
            "💡 نصيحة: اضغط على الصورة ثم اختر 'إرسال كصورة' وليس كملف",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء", callback_data='captain_button')]
            ])
        )

    elif data == 'my_payments':
        user_payments = db.get_user_payments(user_id, 5)
        if not user_payments:
            await query.edit_message_text(
                "📊 لا توجد دفعات سابقة\n\n"
                "يمكنك دفع اشتراك الكباتن للحصول على وصول كامل للرحلات المتاحة",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 دفع الاشتراك", callback_data='pay_subscription')],
                    [InlineKeyboardButton("العودة ↩️", callback_data='captain_button')]
                ])
            )
            return

        message = "📊 حالة دفعاتك:\n\n"

        for payment in user_payments:
            status_emoji = {
                'pending': '⏳',
                'completed': '✅',
                'failed': '❌',
                'refunded': '↩️'
            }.get(payment['payment_status'], '❓')

            status_text = {
                'pending': 'قيد المراجعة',
                'completed': 'مكتملة',
                'failed': 'مرفوضة',
                'refunded': 'مردودة'
            }.get(payment['payment_status'], 'غير معروف')

            message += f"{status_emoji} {payment['amount']} ريال\n"
            message += f"📅 {payment['created_at'][:16]}\n"
            message += f"💳 {payment['payment_method']}\n"
            message += f"📊 {status_text}\n\n"

        keyboard = [
            [InlineKeyboardButton("💳 دفع اشتراك جديد", callback_data='pay_subscription')],
            [InlineKeyboardButton("🔄 تحديث", callback_data='my_payments')],
            [InlineKeyboardButton("العودة ↩️", callback_data='captain_button')]
        ]

        try:
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Payment list not modified, skipping update.")
                await query.answer("لا توجد تحديثات.")
            else:
                logger.error(f"Error updating payment list: {e}")
                raise

    elif data == 'subscribe_button':
        subscription_message = """لالشتراك في المجموعة، يرجى التواصل مع الإدارة عبر المعرف التالي:

@novacompnay"""

        keyboard = [
            [InlineKeyboardButton("التواصل مع الإدارة 📞", url="https://t.me/novacompnay")],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
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
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
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
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            ads_message,
            reply_markup=reply_markup
        )

    elif data == 'main_menu':
        keyboard = [
            [InlineKeyboardButton("🧑‍💼 أريد طلب رحلة (عميل)", callback_data='client_button')],
            [InlineKeyboardButton("🚗 أريد توصيل الناس (كابتن)", callback_data='captain_button')],
            [InlineKeyboardButton("💳 اشتراك الكباتن", callback_data='subscribe_button'), InlineKeyboardButton("⚠️ تنبيه مهم", callback_data='warning_button')],
            [InlineKeyboardButton("📞 التواصل مع الإدارة", url="https://t.me/novacompnay")],
            [InlineKeyboardButton("📢 الاستفسار عن باقات الإعلانات", callback_data='ads_button')]
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

        # إنشاء رابط خرائط Google
        maps_link = f"https://maps.google.com/?q={location.latitude},{location.longitude}"
        context.user_data['pickup_location'] = f"📍 الموقع المرسل"
        context.user_data['pickup_maps'] = maps_link
        context.user_data['step'] = 'waiting_destination'

        await update.message.reply_text(
            f"تم تسجيل موقع الانطلاق ✅\n\n"
            f"📍 خط العرض: {location.latitude:.6f}\n"
            f"📍 خط الطول: {location.longitude:.6f}\n\n"
            f"الآن أرسل موقع الوجهة 📍"
        )

    elif step == 'waiting_destination':
        destination_maps = f"https://maps.google.com/?q={location.latitude},{location.longitude}"
        destination_location = f"📍 الموقع المرسل"
        pickup_location = context.user_data.get('pickup_location')
        pickup_lat = context.user_data.get('pickup_lat')
        pickup_lon = context.user_data.get('pickup_lon')

        # حساب المسافة التقريبية (خط مستقيم)
        distance = calculate_distance(pickup_lat, pickup_lon, location.latitude, location.longitude)

        # إنشاء الرحلة مع الإحداثيات
        ride_id = db.create_ride(
            client_id=user_id,
            pickup_location=pickup_location,
            destination=destination_location
        )

        # تحديث الإحداثيات في قاعدة البيانات
        if ride_id:
            try:
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE rides SET
                        pickup_latitude = ?, pickup_longitude = ?,
                        destination_latitude = ?, destination_longitude = ?
                        WHERE ride_id = ?
                    """, (pickup_lat, pickup_lon, location.latitude, location.longitude, ride_id))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to update coordinates: {e}")

            pickup_maps = context.user_data.get('pickup_maps', '')
            await update.message.reply_text(
                f"تم إنشاء طلب الرحلة بنجاح! ✅\n\n"
                f"🆔 رقم الرحلة: {ride_id}\n"
                f"📏 المسافة التقريبية: {distance:.1f} كم\n\n"
                f"📍 نقطة الانطلاق: [عرض على الخريطة]({pickup_maps})\n"
                f"🏁 الوجهة: [عرض على الخريطة]({destination_maps})\n\n"
                f"سيتم إشعارك عند قبول أحد الكباتن للرحلة 🚖",
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            # مسح البيانات المؤقتة
            context.user_data.clear()
        else:
            await update.message.reply_text("حدث خطأ في إنشاء الرحلة. يرجى المحاولة مرة أخرى.")

# معالج الصور لإثباتات الدفع
async def photo_handler(update: Update, context):
    user_id = update.effective_user.id

    # فحص إذا كان المستخدم في انتظار إرسال إثبات دفع
    if context.user_data.get('awaiting_payment_proof'):
        request_id = context.user_data.get('payment_request_id')
        payment_method = context.user_data.get('payment_method')

        if not request_id:
            await update.message.reply_text("خطأ: لم يتم العثور على طلب الدفع.")
            return

        payment_request = db.get_payment_request(request_id)
        if not payment_request or payment_request['user_id'] != user_id:
            await update.message.reply_text("خطأ: طلب الدفع غير صحيح.")
            return

        # الحصول على أكبر حجم للصورة
        photo = update.message.photo[-1]
        file_id = photo.file_id

        # إنشاء سجل دفع
        try:
            payment_id = db.create_payment_record(
                user_id=user_id,
                payment_type=payment_request['payment_type'],
                amount=payment_request['amount'],
                payment_method=payment_method,
                ride_id=payment_request.get('ride_id'),
                payment_proof_url=file_id,
                notes=f"Payment proof for {payment_request['payment_type']} - Request ID: {request_id}"
            )
            logger.info(f"Created payment record with ID: {payment_id} for user {user_id}")
        except Exception as e:
            logger.error(f"Error creating payment record: {e}")
            payment_id = None

        if payment_id:
            # تحديث حالة طلب الدفع
            db.update_payment_request_status(request_id, 'completed')

            # مسح بيانات الدفع من الجلسة
            context.user_data.pop('awaiting_payment_proof', None)
            context.user_data.pop('payment_request_id', None)
            context.user_data.pop('payment_method', None)

            await update.message.reply_text(
                "✅ تم استلام إثبات الدفع بنجاح!\n\n"
                "⏰ سيتم مراجعة الدفع وتفعيل الاشتراك خلال 24 ساعة\n"
                "📩 سيتم إشعارك عند تفعيل الاشتراك\n\n"
                "🔔 يمكنك متابعة حالة الدفع مع الإدارة إذا لزم الأمر"
            )

            # إشعار الإدارة بالدفع الجديد
            try:
                if ADMIN_CHAT_ID:
                    caption_text = f"💳 إثبات دفع جديد\n\n"
                    caption_text += f"👤 المستخدم: {update.effective_user.first_name}\n"
                    caption_text += f"🆔 ID: {user_id}\n"
                    caption_text += f"💰 المبلغ: {payment_request['amount']} ريال\n"
                    caption_text += f"💳 الطريقة: {payment_method}\n"
                    caption_text += f"📋 النوع: {payment_request['payment_type']}\n"
                    caption_text += f"📝 الوصف: {payment_request['description']}\n"

                    if payment_request.get('ride_id'):
                        caption_text += f"🚗 رقم الرحلة: {payment_request['ride_id']}\n"

                    caption_text += f"🆔 Payment ID: {payment_id}\n\n"
                    caption_text += f"استخدم: /approve_payment {payment_id} لتأكيد الدفع"

                    await context.bot.send_photo(
                        chat_id=ADMIN_CHAT_ID,
                        photo=file_id,
                        caption=caption_text
                    )
            except Exception as e:
                logger.error(f"Failed to send payment notification to admin: {e}")

        else:
            await update.message.reply_text("حدث خطأ في حفظ إثبات الدفع. يرجى المحاولة مرة أخرى.")

    else:
        # رسالة عامة للصور العادية
        await update.message.reply_text(
            "تم استلام الصورة ✅\n\n"
            "إذا كانت هذه صورة إثبات دفع، يرجى أولاً اختيار 'تم الدفع - إرسال الإثبات' من القائمة."
        )

# معالج الرسائل النصية
async def text_handler(update: Update, context):
    user_id = update.effective_user.id
    text = update.message.text

    step = context.user_data.get('step', '')

    if step == 'waiting_form_response':
        # معالجة النموذج المعبأ من العميل
        await update.message.reply_text(
            "شكراً لك! تم استلام طلبك بنجاح ✅\n\n"
            "سيتم عرض طلبك على الكباتن المتاحين، وسنتواصل معك قريباً.\n\n"
            "يمكنك أيضاً نسخ ولصق النموذج في مجموعة مشاوير مكة لعرضه على جميع الكباتن."
        )

        # حفظ الطلب في قاعدة البيانات
        request_id = db.add_monthly_request(client_id=user_id, details=text)

        # إشعار المدير بالطلب الجديد
        if request_id and ADMIN_CHAT_ID:
            admin_notification = f"""🚗 **طلب سائق شهري جديد**

من: {update.effective_user.first_name} (@{update.effective_user.username or 'لا يوجد'})
معرف المستخدم: `{update.effective_user.id}`
---
**تفاصيل الطلب:**
{text}"""

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 نشر للكباتن", callback_data=f'publish_request_{request_id}')]
            ])

            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_notification,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification for new request: {e}")

        # مسح حالة المستخدم
        context.user_data.clear()

    elif step == 'waiting_pickup':
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

async def add_subscription_command(update: Update, context):
    """إضافة اشتراك لكابتن"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "استخدم: /add_subscription <معرف_المستخدم> <عدد_الأيام> [المبلغ]\n"
            "مثال: /add_subscription 123456789 30 10"
        )
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        amount = float(context.args[2]) if len(context.args) > 2 else 10.0

        # حساب تاريخ انتهاء الاشتراك
        from datetime import datetime, timedelta
        end_date = datetime.now() + timedelta(days=days)

        if db.add_subscription(
            user_id=user_id,
            subscription_type='captain_monthly',
            end_date=end_date.isoformat(),
            payment_amount=amount,
            payment_method='admin_manual',
            created_by=update.effective_user.id
        ):
            await update.message.reply_text(
                f"تم إضافة الاشتراك بنجاح!\n"
                f"👤 المستخدم: {user_id}\n"
                f"⏰ المدة: {days} يوم\n"
                f"💰 المبلغ: {amount} ريال\n"
                f"📅 ينتهي في: {end_date.strftime('%Y-%m-%d %H:%M')}"
            )

            # إشعار المستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 تم تفعيل اشتراكك بنجاح!\n\n"
                    f"⏰ مدة الاشتراك: {days} يوم\n"
                    f"📅 ينتهي في: {end_date.strftime('%Y-%m-%d')}\n\n"
                    f"يمكنك الآن الوصول لجميع ميزات الكباتن 🚖"
                )
            except Exception as e:
                await update.message.reply_text(f"تم إضافة الاشتراك لكن فشل إرسال الإشعار للمستخدم: {e}")
        else:
            await update.message.reply_text("حدث خطأ في إضافة الاشتراك.")

    except ValueError:
        await update.message.reply_text("يرجى إدخال أرقام صحيحة.")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def check_subscription_command(update: Update, context):
    """فحص اشتراك مستخدم"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("استخدم: /check_subscription <معرف_المستخدم>")
        return

    try:
        user_id = int(context.args[0])
        subscription = db.get_subscription_info(user_id)

        if subscription:
            from datetime import datetime
            end_date = datetime.fromisoformat(subscription['end_date'])
            status = "نشط ✅" if db.is_captain_subscribed(user_id) else "منتهي ❌"

            await update.message.reply_text(
                f"📋 معلومات الاشتراك:\n\n"
                f"👤 المستخدم: {user_id}\n"
                f"📊 الحالة: {status}\n"
                f"💳 النوع: {subscription['subscription_type']}\n"
                f"💰 المبلغ: {subscription['payment_amount']} ريال\n"
                f"📅 بداية الاشتراك: {subscription['start_date'][:10]}\n"
                f"📅 نهاية الاشتراك: {end_date.strftime('%Y-%m-%d')}\n"
                f"🔧 طريقة الدفع: {subscription['payment_method']}"
            )
        else:
            await update.message.reply_text(f"لا يوجد اشتراك نشط للمستخدم {user_id}")

    except ValueError:
        await update.message.reply_text("يرجى إدخال معرف مستخدم صحيح.")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def admin_stats_command(update: Update, context):
    """📊 لوحة التحكم الرئيسية - إحصائيات شاملة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # عدد المستخدمين
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'client'")
            clients = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'captain'")
            captains = cursor.fetchone()[0]

            # عدد الرحلات
            cursor.execute("SELECT COUNT(*) FROM rides")
            total_rides = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rides WHERE status = 'pending'")
            pending_rides = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rides WHERE status = 'in_progress'")
            active_rides = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rides WHERE status = 'completed'")
            completed_rides = cursor.fetchone()[0]

            # الاشتراكات
            cursor.execute("""
                SELECT COUNT(*) FROM subscriptions
                WHERE is_active = 1 AND datetime(end_date) > datetime('now')
            """)
            active_subscriptions = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*) FROM subscriptions
                WHERE is_active = 0 OR datetime(end_date) <= datetime('now')
            """)
            expired_subscriptions = cursor.fetchone()[0]

            # المدفوعات
            cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'pending'")
            pending_payments = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_status = 'completed'")
            completed_payments = cursor.fetchone()[0]

            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_status = 'completed'")
            total_revenue = cursor.fetchone()[0]

            # المدفوعات النقدية مقابل الرقمية
            cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_method = 'cash' AND payment_status = 'completed'")
            cash_payments = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_method != 'cash' AND payment_status = 'completed'")
            digital_payments = cursor.fetchone()[0]

            # الإحصائيات اليومية
            cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
            today_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rides WHERE DATE(created_at) = DATE('now')")
            today_rides = cursor.fetchone()[0]

            # رسالة الإحصائيات الشاملة
            stats_message = f"""📊 **لوحة التحكم الرئيسية**
━━━━━━━━━━━━━━━━━━━━━━

👥 **المستخدمون:**
   • الإجمالي: {total_users}
   • العملاء: {clients}
   • الكباتن: {captains}
   • انضموا اليوم: {today_users}

🚗 **الرحلات:**
   • الإجمالي: {total_rides}
   • معلقة: {pending_rides}
   • نشطة: {active_rides}
   • مكتملة: {completed_rides}
   • طلبات اليوم: {today_rides}

💳 **الاشتراكات:**
   • نشطة: {active_subscriptions}
   • منتهية: {expired_subscriptions}

💰 **المدفوعات:**
   • معلقة: {pending_payments}
   • مكتملة: {completed_payments}
   • إجمالي الإيرادات: {total_revenue:.2f} ريال

📊 **طرق الدفع:**
   • نقدية: {cash_payments}
   • رقمية: {digital_payments}

━━━━━━━━━━━━━━━━━━━━━━
⚡ أوامر لوحة التحكم:
• `/recent_rides` - آخر الرحلات
• `/recent_users` - آخر المستخدمين
• `/find_user [ID]` - البحث عن مستخدم
• `/live_activity` - النشاط المباشر
• `/revenue_report` - تقرير الإيرادات
• `/pending_payments` - المدفوعات المعلقة
• `/admin_help` - دليل جميع الأوامر 📚"""

            await update.message.reply_text(stats_message)

    except Exception as e:
        await update.message.reply_text(f"خطأ في جلب الإحصائيات: {e}")

# ============ أوامر لوحة التحكم المتقدمة ============

async def recent_rides_command(update: Update, context):
    """📋 عرض آخر الرحلات مع التفاصيل"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.ride_id, r.status, r.created_at,
                       client.first_name as client_name, client.user_id as client_id,
                       captain.first_name as captain_name, captain.user_id as captain_id,
                       r.pickup_location, r.destination
                FROM rides r
                JOIN users client ON r.client_id = client.user_id
                LEFT JOIN users captain ON r.captain_id = captain.user_id
                ORDER BY r.created_at DESC
                LIMIT 10
            """)
            rides = cursor.fetchall()

            if not rides:
                await update.message.reply_text("📭 لا توجد رحلات بعد")
                return

            message = "📋 **آخر 10 رحلات:**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

            for ride in rides:
                status_emoji = {"pending": "⏳", "in_progress": "🚗", "completed": "✅", "cancelled": "❌"}.get(ride[1], "❓")
                captain_info = f"👨‍✈️ {ride[5]} ({ride[6]})" if ride[5] else "👨‍✈️ لم يتم التعيين بعد"

                message += f"""🆔 **الرحلة #{ride[0]}** {status_emoji}
👤 العميل: {ride[3]} ({ride[4]})
{captain_info}
📍 من: {ride[7] or 'لم يحدد'}
🎯 إلى: {ride[8] or 'لم يحدد'}
⏰ {ride[2][:16]}

"""

            await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب الرحلات: {e}")

async def recent_users_command(update: Update, context):
    """👥 عرض آخر المستخدمين المنضمين"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, username, first_name, user_type, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 15
            """)
            users = cursor.fetchall()

            if not users:
                await update.message.reply_text("📭 لا يوجد مستخدمون بعد")
                return

            message = "👥 **آخر 15 مستخدم انضموا:**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

            for user in users:
                type_emoji = "👤" if user[3] == "client" else "👨‍✈️" if user[3] == "captain" else "❓"
                username = f"@{user[1]}" if user[1] else "بدون معرف"

                message += f"""{type_emoji} **{user[2]}** ({user[0]})
📱 {username}
📅 {user[4][:16]}

"""

            await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب المستخدمين: {e}")

async def find_user_command(update: Update, context):
    """🔍 البحث عن مستخدم بالمعرف وعرض تفاصيله"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("🔍 **البحث عن مستخدم**\n\nالاستخدام: `/find_user <معرف_المستخدم>`\nمثال: `/find_user 123456789`")
        return

    try:
        user_id = int(context.args[0])

        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # معلومات المستخدم الأساسية
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, user_type, created_at
                FROM users WHERE user_id = ?
            """, (user_id,))
            user = cursor.fetchone()

            if not user:
                await update.message.reply_text(f"❌ لم يتم العثور على مستخدم بالمعرف: {user_id}")
                return

            # إحصائيات الرحلات
            cursor.execute("SELECT COUNT(*) FROM rides WHERE client_id = ?", (user_id,))
            rides_as_client = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rides WHERE captain_id = ?", (user_id,))
            rides_as_captain = cursor.fetchone()[0]

            # الاشتراكات
            cursor.execute("""
                SELECT COUNT(*) FROM subscriptions
                WHERE user_id = ? AND is_active = 1 AND datetime(end_date) > datetime('now')
            """, (user_id,))
            active_subscription = cursor.fetchone()[0]

            # المدفوعات
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE user_id = ? AND payment_status = 'completed'", (user_id,))
            payment_stats = cursor.fetchone()

            # آخر نشاط
            cursor.execute("""
                SELECT created_at FROM rides
                WHERE client_id = ? OR captain_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (user_id, user_id))
            last_activity = cursor.fetchone()

            type_emoji = "👤" if user[4] == "client" else "👨‍✈️" if user[4] == "captain" else "❓"
            username = f"@{user[1]}" if user[1] else "بدون معرف"
            full_name = f"{user[2]} {user[3] or ''}".strip()

            message = f"""🔍 **تفاصيل المستخدم**
━━━━━━━━━━━━━━━━━━━━━━

{type_emoji} **{full_name}**
🆔 المعرف: `{user[0]}`
📱 اسم المستخدم: {username}
👥 النوع: {"عميل" if user[4] == "client" else "كابتن" if user[4] == "captain" else "غير محدد"}
📅 انضم في: {user[5][:16]}

📊 **الإحصائيات:**
🚗 رحلات كعميل: {rides_as_client}
👨‍✈️ رحلات ككابتن: {rides_as_captain}
💳 اشتراك نشط: {"✅ نعم" if active_subscription else "❌ لا"}
💰 إجمالي المدفوعات: {payment_stats[1]:.2f} ريال ({payment_stats[0]} دفعة)

⏰ **آخر نشاط:** {last_activity[0][:16] if last_activity else "لا يوجد نشاط"}"""

            await update.message.reply_text(message)

    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال معرف مستخدم صحيح (أرقام فقط)")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في البحث: {e}")

async def live_activity_command(update: Update, context):
    """⚡ النشاط المباشر - ما يحدث الآن"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # الرحلات النشطة
            cursor.execute("""
                SELECT r.ride_id, client.first_name as client_name,
                       captain.first_name as captain_name, r.created_at
                FROM rides r
                JOIN users client ON r.client_id = client.user_id
                LEFT JOIN users captain ON r.captain_id = captain.user_id
                WHERE r.status IN ('pending', 'in_progress')
                ORDER BY r.created_at DESC
            """)
            active_rides = cursor.fetchall()

            # المدفوعات المعلقة
            cursor.execute("""
                SELECT p.payment_id, u.first_name, p.amount, p.payment_type, p.created_at
                FROM payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.payment_status = 'pending'
                ORDER BY p.created_at DESC
                LIMIT 5
            """)
            pending_payments = cursor.fetchall()

            # المستخدمين الجدد اليوم
            cursor.execute("""
                SELECT first_name, user_type, created_at
                FROM users
                WHERE DATE(created_at) = DATE('now')
                ORDER BY created_at DESC
                LIMIT 5
            """)
            new_users_today = cursor.fetchall()

            message = "⚡ **النشاط المباشر**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # الرحلات النشطة
            if active_rides:
                message += "🚗 **الرحلات النشطة:**\n"
                for ride in active_rides[:5]:
                    captain_name = ride[2] if ride[2] else "لم يتم التعيين"
                    message += f"• #{ride[0]} - {ride[1]} ↔️ {captain_name}\n"
                message += "\n"
            else:
                message += "🚗 **لا توجد رحلات نشطة حالياً**\n\n"

            # المدفوعات المعلقة
            if pending_payments:
                message += "💰 **مدفوعات تحتاج موافقة:**\n"
                for payment in pending_payments:
                    message += f"• {payment[1]} - {payment[2]:.0f} ريال ({payment[3]})\n"
                message += "\n"
            else:
                message += "💰 **لا توجد مدفوعات معلقة**\n\n"

            # المستخدمين الجدد
            if new_users_today:
                message += "👥 **انضموا اليوم:**\n"
                for user in new_users_today:
                    type_emoji = "👤" if user[1] == "client" else "👨‍✈️"
                    message += f"• {type_emoji} {user[0]} - {user[2][:11]}\n"
            else:
                message += "👥 **لم ينضم أحد اليوم بعد**"

            await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب النشاط المباشر: {e}")

async def revenue_report_command(update: Update, context):
    """💰 تقرير الإيرادات التفصيلي"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # إجمالي الإيرادات
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_status = 'completed'")
            total_revenue = cursor.fetchone()[0]

            # الإيرادات حسب طريقة الدفع
            cursor.execute("""
                SELECT payment_method, COUNT(*), COALESCE(SUM(amount), 0)
                FROM payments
                WHERE payment_status = 'completed'
                GROUP BY payment_method
                ORDER BY SUM(amount) DESC
            """)
            payment_methods = cursor.fetchall()

            # الإيرادات حسب نوع الدفع
            cursor.execute("""
                SELECT payment_type, COUNT(*), COALESCE(SUM(amount), 0)
                FROM payments
                WHERE payment_status = 'completed'
                GROUP BY payment_type
                ORDER BY SUM(amount) DESC
            """)
            payment_types = cursor.fetchall()

            # إيرادات آخر 7 أيام
            cursor.execute("""
                SELECT DATE(created_at) as day, COALESCE(SUM(amount), 0)
                FROM payments
                WHERE payment_status = 'completed'
                AND DATE(created_at) >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY day DESC
            """)
            daily_revenue = cursor.fetchall()

            message = f"""💰 **تقرير الإيرادات التفصيلي**
━━━━━━━━━━━━━━━━━━━━━━

💵 **إجمالي الإيرادات:** {total_revenue:.2f} ريال

📊 **حسب طريقة الدفع:**"""

            for method in payment_methods:
                method_name = {"cash": "نقدي", "stc": "STC Pay", "bank": "حوالة بنكية", "urpay": "urpay", "mada": "مدى"}.get(method[0], method[0])
                percentage = (method[2] / total_revenue * 100) if total_revenue > 0 else 0
                message += f"\n• {method_name}: {method[2]:.2f} ريال ({method[1]} دفعة) - {percentage:.1f}%"

            message += "\n\n📈 **حسب نوع الدفع:**"
            for ptype in payment_types:
                type_name = {"subscription_payment": "اشتراكات", "ride_payment": "رحلات"}.get(ptype[0], ptype[0])
                percentage = (ptype[2] / total_revenue * 100) if total_revenue > 0 else 0
                message += f"\n• {type_name}: {ptype[2]:.2f} ريال ({ptype[1]} دفعة) - {percentage:.1f}%"

            message += "\n\n📅 **آخر 7 أيام:**"
            for day in daily_revenue:
                message += f"\n• {day[0]}: {day[1]:.2f} ريال"

            await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في جلب تقرير الإيرادات: {e}")

async def admin_help_command(update: Update, context):
    """📚 دليل أوامر الإدارة الشامل"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    help_message = """📚 **دليل أوامر الإدارة الشامل**
━━━━━━━━━━━━━━━━━━━━━━

📊 **لوحة التحكم الرئيسية:**
• `/stats` - إحصائيات شاملة ولوحة التحكم الرئيسية

🔍 **المراقبة والمتابعة:**
• `/live_activity` - النشاط المباشر (ما يحدث الآن)
• `/recent_rides` - آخر 10 رحلات مع التفاصيل
• `/recent_users` - آخر 15 مستخدم انضموا
• `/find_user <ID>` - البحث عن مستخدم بالمعرف

💰 **التقارير المالية:**
• `/revenue_report` - تقرير الإيرادات التفصيلي
• `/pending_payments` - المدفوعات المعلقة
• `/approve_payment <ID>` - تأكيد دفعة
• `/reject_payment <ID> <السبب>` - رفض دفعة

👥 **إدارة المستخدمين:**
• `/list_users [all|clients|captains]` - قائمة المستخدمين
• `/add_subscription <ID> <أيام> [المبلغ]` - إضافة اشتراك
• `/check_subscription <ID>` - فحص اشتراك مستخدم

🛡️ **الإشراف والمحتوى:**
• `/add_banned_word <كلمة>` - إضافة كلمة محظورة
• `/remove_banned_word <كلمة>` - إزالة كلمة محظورة
• `/list_banned_words` - عرض الكلمات المحظورة

📅 **الرسائل المجدولة:**
• `/schedule <ساعات> <أيام> <النص>` - جدولة رسالة

━━━━━━━━━━━━━━━━━━━━━━
💡 **نصائح:**
• ابدأ دائماً بـ `/stats` للحصول على نظرة شاملة
• استخدم `/live_activity` لمتابعة النشاط اللحظي
• `/find_user` مفيد جداً لحل مشاكل المستخدمين
• تحقق من `/pending_payments` بانتظام"""

    await update.message.reply_text(help_message)

# ============ نهاية أوامر لوحة التحكم ============

async def list_users_command(update: Update, context):
    """عرض قائمة المستخدمين"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        user_type = context.args[0] if context.args else 'all'

        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_type == 'clients':
                cursor.execute("""
                    SELECT user_id, username, first_name, created_at
                    FROM users WHERE user_type = 'client'
                    ORDER BY created_at DESC LIMIT 20
                """)
                title = "العملاء"
            elif user_type == 'captains':
                cursor.execute("""
                    SELECT user_id, username, first_name, created_at
                    FROM users WHERE user_type = 'captain'
                    ORDER BY created_at DESC LIMIT 20
                """)
                title = "الكباتن"
            else:
                cursor.execute("""
                    SELECT user_id, username, first_name, user_type, created_at
                    FROM users ORDER BY created_at DESC LIMIT 20
                """)
                title = "جميع المستخدمين"

            users = cursor.fetchall()

            if not users:
                await update.message.reply_text("لا توجد بيانات للمستخدمين")
                return

            message = f"📋 {title} (آخر 20):\n\n"

            for user in users:
                user_dict = dict(user)
                message += f"👤 {user_dict['first_name']}\n"
                message += f"   🆔 {user_dict['user_id']}\n"
                if user_dict.get('username'):
                    message += f"   📝 @{user_dict['username']}\n"
                if user_type == 'all':
                    message += f"   👥 {user_dict['user_type']}\n"
                message += f"   📅 {user_dict['created_at'][:10]}\n\n"

            # تقسيم الرسالة إذا كانت طويلة
            if len(message) > 4000:
                parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}\n\nاستخدم: /list_users [all|clients|captains]")

async def approve_payment_command(update: Update, context):
    """تأكيد دفعة وتفعيل الاشتراك"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if not context.args:
        await update.message.reply_text("استخدم: /approve_payment <payment_id>")
        return

    try:
        payment_id = int(context.args[0])

        # الحصول على معلومات الدفع
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.first_name, u.username
                FROM payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.payment_id = ?
            """, (payment_id,))
            payment = cursor.fetchone()

        if not payment:
            await update.message.reply_text("لم يتم العثور على الدفعة.")
            return

        if payment['payment_status'] != 'pending':
            await update.message.reply_text(f"هذه الدفعة تم معالجتها مسبقاً. الحالة الحالية: {payment['payment_status']}")
            return

        # تحديث حالة الدفع إلى مكتمل
        db.update_payment_status(payment_id, 'completed')

        # إذا كان دفع اشتراك، قم بإضافة الاشتراك
        if payment['payment_type'] == 'subscription_payment':
            from datetime import datetime, timedelta
            end_date = datetime.now() + timedelta(days=30)

            subscription_added = db.add_subscription(
                user_id=payment['user_id'],
                subscription_type='captain_monthly',
                end_date=end_date.isoformat(),
                payment_amount=payment['amount'],
                payment_method=payment['payment_method'],
                created_by=update.effective_user.id
            )

            if subscription_added:
                await update.message.reply_text(
                    f"✅ تم تأكيد الدفع وتفعيل الاشتراك!\n\n"
                    f"👤 المستخدم: {payment['first_name']}\n"
                    f"💰 المبلغ: {payment['amount']} ريال\n"
                    f"📅 مدة الاشتراك: 30 يوم\n"
                    f"📅 ينتهي في: {end_date.strftime('%Y-%m-%d')}"
                )

                # إشعار المستخدم
                try:
                    await context.bot.send_message(
                        chat_id=payment['user_id'],
                        text="🎉 تم تفعيل اشتراكك بنجاح!\n\n"
                        f"⏰ مدة الاشتراك: 30 يوم\n"
                        f"📅 ينتهي في: {end_date.strftime('%Y-%m-%d')}\n\n"
                        "يمكنك الآن الوصول لجميع ميزات الكباتن 🚖\n"
                        "استخدم /start لبدء استخدام البوت"
                    )
                except Exception as e:
                    await update.message.reply_text(f"تم تفعيل الاشتراك لكن فشل إرسال الإشعار: {e}")
            else:
                await update.message.reply_text("تم تأكيد الدفع لكن فشل في إضافة الاشتراك.")

        elif payment['payment_type'] == 'ride_payment':
            await update.message.reply_text(
                f"✅ تم تأكيد دفع الرحلة!\n\n"
                f"👤 المستخدم: {payment['first_name']}\n"
                f"💰 المبلغ: {payment['amount']} ريال\n"
                f"🚗 رقم الرحلة: {payment['ride_id']}"
            )

            # إشعار العميل
            try:
                await context.bot.send_message(
                    chat_id=payment['user_id'],
                    text=f"✅ تم تأكيد دفع رحلتك!\n\n"
                    f"💰 المبلغ: {payment['amount']} ريال\n"
                    f"🚗 رقم الرحلة: {payment['ride_id']}\n\n"
                    "شكراً لاستخدامك خدمة مشاوير مكة اليومية 🚖"
                )
            except Exception as e:
                await update.message.reply_text(f"تم تأكيد الدفع لكن فشل إرسال الإشعار: {e}")

        else:
            await update.message.reply_text(f"✅ تم تأكيد الدفع بنجاح!")

    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم دفع صحيح.")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def reject_payment_command(update: Update, context):
    """رفض دفعة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("استخدم: /reject_payment <payment_id> <سبب_الرفض>")
        return

    try:
        payment_id = int(context.args[0])
        reason = " ".join(context.args[1:])

        # الحصول على معلومات الدفع
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, u.first_name, u.username
                FROM payments p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.payment_id = ?
            """, (payment_id,))
            payment = cursor.fetchone()

        if not payment:
            await update.message.reply_text("لم يتم العثور على الدفعة.")
            return

        # تحديث حالة الدفع إلى مرفوض
        db.update_payment_status(payment_id, 'failed')

        await update.message.reply_text(
            f"❌ تم رفض الدفع\n\n"
            f"👤 المستخدم: {payment['first_name']}\n"
            f"💰 المبلغ: {payment['amount']} ريال\n"
            f"🔴 السبب: {reason}"
        )

        # إشعار المستخدم
        try:
            await context.bot.send_message(
                chat_id=payment['user_id'],
                text=f"❌ تم رفض دفعتك\n\n"
                f"💰 المبلغ: {payment['amount']} ريال\n"
                f"🔴 السبب: {reason}\n\n"
                "يرجى التواصل مع الإدارة لمزيد من التوضيح",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📞 تواصل مع الإدارة", url="https://t.me/novacompnay")
                ]])
            )
        except Exception as e:
            await update.message.reply_text(f"تم رفض الدفع لكن فشل إرسال الإشعار: {e}")

    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم دفع صحيح.")
    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

async def pending_payments_command(update: Update, context):
    """عرض الدفعات المعلقة"""
    if str(update.effective_user.id) != ADMIN_CHAT_ID:
        return

    try:
        pending_payments = db.get_pending_payments(10)

        if not pending_payments:
            await update.message.reply_text("لا توجد دفعات معلقة حالياً ✅")
            return

        message = "💳 الدفعات المعلقة:\n\n"

        for payment in pending_payments:
            message += f"🆔 Payment ID: {payment['payment_id']}\n"
            message += f"👤 {payment['first_name']}\n"
            message += f"💰 {payment['amount']} ريال - {payment['payment_method']}\n"
            message += f"📅 {payment['created_at'][:16]}\n"
            message += f"📋 {payment['payment_type']}\n\n"

        message += "استخدم الأوامر التالية:\n"
        message += "✅ /approve_payment <ID>\n"
        message += "❌ /reject_payment <ID> <السبب>"

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"خطأ: {e}")

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
        app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

        # أوامر الإدارة
        app.add_handler(CommandHandler("add_banned_word", add_banned_word_command))
        app.add_handler(CommandHandler("remove_banned_word", remove_banned_word_command))
        app.add_handler(CommandHandler("list_banned_words", list_banned_words_command))
        app.add_handler(CommandHandler("schedule", schedule_message_command))
        app.add_handler(CommandHandler("add_subscription", add_subscription_command))
        app.add_handler(CommandHandler("check_subscription", check_subscription_command))
        app.add_handler(CommandHandler("stats", admin_stats_command))
        app.add_handler(CommandHandler("list_users", list_users_command))
        app.add_handler(CommandHandler("approve_payment", approve_payment_command))
        app.add_handler(CommandHandler("reject_payment", reject_payment_command))
        app.add_handler(CommandHandler("pending_payments", pending_payments_command))

        # أوامر لوحة التحكم المتقدمة
        app.add_handler(CommandHandler("recent_rides", recent_rides_command))
        app.add_handler(CommandHandler("recent_users", recent_users_command))
        app.add_handler(CommandHandler("find_user", find_user_command))
        app.add_handler(CommandHandler("live_activity", live_activity_command))
        app.add_handler(CommandHandler("revenue_report", revenue_report_command))
        app.add_handler(CommandHandler("admin_help", admin_help_command))

        # معالج رسائل المجموعة (للإشراف)
        app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_message_handler))

        # معالج الرسائل الخاصة
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_handler))

        # إضافة معالج الأخطاء
        app.add_error_handler(error_handler)

        # بدء جدولة الرسائل والمهام الخلفية (سيتم تفعيلها لاحقاً)
        # Initialize and start scheduler
        scheduler = MessageScheduler(app)

        # Start scheduler as background task
        async def post_init(application):
            asyncio.create_task(scheduler.start_scheduler())

        app.post_init = post_init
        logger.info("Message scheduler enabled and will start after bot initialization")

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
