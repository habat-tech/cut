import os
import uuid
import subprocess
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# تعريف حالات المحادثة
VIDEO = 0
CHOOSE_METHOD = 1
ENTER_PARTS = 2
OVERLAY_OPTION = 3
OVERLAY_TEXT = 4
OVERLAY_POSITION = 5
OVERLAY_TEXT_COLOR = 6
OVERLAY_BG_COLOR = 7
OVERLAY_BG_OPACITY = 8
OVERLAY_FONT_SIZE = 9
OVERLAY_BORDER = 10
PROCESSING = 11

# توكن البوت
TELEGRAM_API_TOKEN = "8134559871:AAGNoj-YNLpVkh6tiQrnmeJnZmcWkjih6ps"

def get_video_duration(filename: str) -> float:
    """
    إعادة مدة الفيديو بالثواني باستخدام ffprobe.
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filename
    ]
    output = subprocess.check_output(cmd).decode().strip()
    return float(output)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً! أرسل لي ملف الفيديو الذي تريد تقسيمه.")
    return VIDEO

# استقبال الفيديو
async def video_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video_file = update.message.video or update.message.document
    if not video_file:
        await update.message.reply_text("الرجاء إرسال فيديو صحيح.")
        return VIDEO

    file = await video_file.get_file()
    input_filename = f"input_{uuid.uuid4().hex}.mp4"
    await file.download_to_drive(custom_path=input_filename)
    context.user_data['input_video'] = input_filename

    # سؤال المستخدم عن طريقة التقسيم
    keyboard = [
        [InlineKeyboardButton("تقسيم كل دقيقة (تلقائي)", callback_data="method1")],
        [InlineKeyboardButton("تقسيم بناءً على عدد الأجزاء", callback_data="method2")]
    ]
    await update.message.reply_text(
        "اختر طريقة التقسيم:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSE_METHOD

# اختيار طريقة التقسيم
async def method_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data
    context.user_data['split_method'] = method

    if method == "method1":
        try:
            await query.edit_message_text("تم اختيار: تقسيم كل دقيقة.")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        return await ask_overlay_option(query.message, context)
    else:
        try:
            await query.edit_message_text("تم اختيار: تقسيم بناءً على عدد الأجزاء.\nكم عدد الأجزاء المطلوب؟")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        return ENTER_PARTS

# استقبال عدد الأجزاء للطريقة الثانية
async def enter_parts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        num_parts = int(text)
        if num_parts <= 0:
            raise ValueError("عدد الأجزاء يجب أن يكون أكبر من 0")
        context.user_data['num_parts'] = num_parts
    except ValueError:
        await update.message.reply_text("الرجاء إدخال رقم صحيح أكبر من 0.")
        return ENTER_PARTS

    return await ask_overlay_option(update.message, context)

async def ask_overlay_option(message, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("نعم", callback_data="overlay_yes")],
        [InlineKeyboardButton("لا", callback_data="overlay_no")]
    ]
    await message.reply_text(
        "هل تريد إضافة نص توضيحي مخصص على الفيديو؟\n"
        "إذا اخترت 'لا'، سيتم إضافة ترقيم تلقائي لكل جزء بالإعدادات الافتراضية:\n"
        "خلفية سوداء، نص أبيض، شفافية 100%، وحواف مستديرة.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return OVERLAY_OPTION

# خيار إضافة النص التوضيحي
async def overlay_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "overlay_yes":
        try:
            await query.edit_message_text("أدخل النص الذي تريد إضافته على الفيديو:")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        return OVERLAY_TEXT
    else:
        context.user_data['overlay'] = None
        try:
            await query.edit_message_text("سيتم إضافة ترقيم تلقائي على كل جزء بالإعدادات الافتراضية.\nجاري المعالجة...")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        await process_video(query.message, context)
        return ConversationHandler.END

# استقبال النص التوضيحي
async def overlay_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data['overlay'] = {}
    context.user_data['overlay']['text'] = text

    keyboard = [
        [InlineKeyboardButton("أعلى", callback_data="top")],
        [InlineKeyboardButton("وسط", callback_data="middle")],
        [InlineKeyboardButton("أسفل", callback_data="bottom")]
    ]
    await update.message.reply_text(
        "اختر مكان ظهور النص:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return OVERLAY_POSITION

# استقبال مكان النص
async def overlay_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pos = query.data
    if pos == "top":
        context.user_data['overlay']['position'] = "top"
    elif pos == "bottom":
        context.user_data['overlay']['position'] = "bottom"
    else:
        context.user_data['overlay']['position'] = "middle"
    try:
        await query.edit_message_text("اختر لون النص:")
    except Exception as e:
        if "Message is not modified" not in str(e):
            raise e
    return await ask_color(query.message, context, "text_color")

async def ask_color(message, context: ContextTypes.DEFAULT_TYPE, color_type: str):
    # لوحة ألوان بسيطة + خيار لون مخصص
    color_keyboard = [
        [
            InlineKeyboardButton("أبيض", callback_data="white"),
            InlineKeyboardButton("أسود", callback_data="black"),
            InlineKeyboardButton("أحمر", callback_data="red"),
        ],
        [
            InlineKeyboardButton("أخضر", callback_data="green"),
            InlineKeyboardButton("أزرق", callback_data="blue"),
            InlineKeyboardButton("لون مخصص", callback_data="custom"),
        ]
    ]
    context.user_data['color_type'] = color_type
    await message.reply_text(
        "اختر من الألوان التالية أو اختر (لون مخصص) لإدخال كود اللون:",
        reply_markup=InlineKeyboardMarkup(color_keyboard)
    )
    return OVERLAY_TEXT_COLOR if color_type == "text_color" else OVERLAY_BG_COLOR

# استقبال اختيار لون النص أو لون الخلفية
async def color_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen = query.data
    color_type = context.user_data['color_type']  # "text_color" أو "bg_color"

    if chosen == "custom":
        if color_type == "text_color":
            try:
                await query.edit_message_text("أدخل كود اللون النصي (مثال: #FF0000 أو red أو blue...):")
            except Exception as e:
                if "Message is not modified" not in str(e):
                    raise e
            return OVERLAY_TEXT_COLOR
        else:
            try:
                await query.edit_message_text("أدخل كود لون الخلفية (مثال: #FF0000 أو red أو blue...):")
            except Exception as e:
                if "Message is not modified" not in str(e):
                    raise e
            return OVERLAY_BG_COLOR
    else:
        context.user_data['overlay'][color_type] = chosen
        if color_type == "text_color":
            keyboard = [
                [
                    InlineKeyboardButton("بدون خلفية", callback_data="none"),
                    InlineKeyboardButton("اختيار لون خلفية", callback_data="color_bg"),
                ]
            ]
            try:
                await query.edit_message_text(
                    f"تم اختيار لون النص: {chosen}\nهل تريد إضافة خلفية للنص؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                if "Message is not modified" not in str(e):
                    raise e
            return OVERLAY_BG_COLOR
        else:
            return await ask_opacity(query.message, context)

# استقبال اللون المخصص (يدخله المستخدم يدويًا)
async def custom_color_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    color_type = context.user_data['color_type']
    context.user_data['overlay'][color_type] = text
    if color_type == "text_color":
        keyboard = [
            [
                InlineKeyboardButton("بدون خلفية", callback_data="none"),
                InlineKeyboardButton("اختيار لون خلفية", callback_data="color_bg"),
            ]
        ]
        await update.message.reply_text(
            f"تم اختيار لون النص: {text}\nهل تريد إضافة خلفية للنص؟",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return OVERLAY_BG_COLOR
    else:
        return await ask_opacity(update.message, context)

# دالة لمعالجة اختيار خلفية النص (عند الضغط على "none" أو "color_bg")
async def bg_color_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == "none":
        context.user_data['overlay']['bg_color'] = "none"
        context.user_data['overlay']['bg_opacity'] = "0.0"
        return await ask_font_size(query.message, context)
    elif choice == "color_bg":
        # عرض لوحة ألوان لاختيار لون الخلفية
        keyboard = [
            [
                InlineKeyboardButton("أبيض", callback_data="white"),
                InlineKeyboardButton("أسود", callback_data="black"),
                InlineKeyboardButton("أحمر", callback_data="red"),
            ],
            [
                InlineKeyboardButton("أخضر", callback_data="green"),
                InlineKeyboardButton("أزرق", callback_data="blue"),
                InlineKeyboardButton("لون مخصص", callback_data="custom"),
            ]
        ]
        context.user_data['color_type'] = "bg_color"
        try:
            await query.edit_message_text("اختر لون الخلفية:")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        await query.message.reply_text(
            "اختر من الألوان التالية أو اختر (لون مخصص) لإدخال كود اللون:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return OVERLAY_BG_COLOR

# اختيار شفافية الخلفية
async def ask_opacity(message, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("0.2", callback_data="0.2"),
         InlineKeyboardButton("0.4", callback_data="0.4"),
         InlineKeyboardButton("0.6", callback_data="0.6"),
         InlineKeyboardButton("0.8", callback_data="0.8"),
         InlineKeyboardButton("1.0", callback_data="1.0")]
    ]
    await message.reply_text("اختر شفافية الخلفية:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OVERLAY_BG_OPACITY

async def opacity_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen_opacity = query.data
    context.user_data['overlay']['bg_opacity'] = chosen_opacity
    try:
        await query.edit_message_text(f"تم اختيار الشفافية: {chosen_opacity}")
    except Exception as e:
        if "Message is not modified" not in str(e):
            raise e
    return await ask_font_size(query.message, context)

# اختيار حجم الخط
async def ask_font_size(message, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("16", callback_data="16"),
         InlineKeyboardButton("24", callback_data="24"),
         InlineKeyboardButton("32", callback_data="32"),
         InlineKeyboardButton("40", callback_data="40")],
        [InlineKeyboardButton("مخصص", callback_data="custom_font")]
    ]
    await message.reply_text("اختر حجم الخط:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OVERLAY_FONT_SIZE

async def font_size_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chosen_size = query.data
    if chosen_size == "custom_font":
        try:
            await query.edit_message_text("أدخل حجم الخط (رقم فقط):")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        return OVERLAY_FONT_SIZE
    else:
        context.user_data['overlay']['font_size'] = chosen_size
        try:
            await query.edit_message_text(f"تم اختيار حجم الخط: {chosen_size}\nالآن اختر شكل الحواف:")
        except Exception as e:
            if "Message is not modified" not in str(e):
                raise e
        return await ask_border_style(query.message, context)

async def custom_font_size_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("الرجاء إدخال رقم صحيح لحجم الخط:")
        return OVERLAY_FONT_SIZE
    context.user_data['overlay']['font_size'] = text
    await update.message.reply_text(f"تم اختيار حجم الخط: {text}\nالآن اختر شكل الحواف:")
    return await ask_border_style(update.message, context)

# خطوة اختيار شكل الحواف (البوردر)
async def ask_border_style(message, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("مستديرة", callback_data="rounded"),
            InlineKeyboardButton("مربعة", callback_data="square"),
            InlineKeyboardButton("بدون", callback_data="none_border"),
        ]
    ]
    await message.reply_text("اختر شكل الحواف:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OVERLAY_BORDER

async def border_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    style = query.data
    context.user_data['overlay']['border'] = style
    try:
        await query.edit_message_text(f"تم اختيار شكل الحواف: {style}\nجاري المعالجة...")
    except Exception as e:
        if "Message is not modified" not in str(e):
            raise e
    await process_video(query.message, context)
    return ConversationHandler.END

# الدالة الرئيسية لمعالجة الفيديو
async def process_video(message, context: ContextTypes.DEFAULT_TYPE):
    input_video = context.user_data.get('input_video')
    split_method = context.user_data.get('split_method')

    if split_method == "method1":
        segment_time = 60
    else:
        num_parts = context.user_data.get('num_parts')
        total_duration = get_video_duration(input_video)
        segment_time = total_duration / num_parts

    overlay = context.user_data.get('overlay')
    output_dir = f"output_{uuid.uuid4().hex}"
    os.makedirs(output_dir, exist_ok=True)

    # إذا كان هناك نص توضيحي مخصص، ندمجه مع الفيديو قبل التقسيم
    if overlay is not None:
        pos = overlay.get('position', 'middle')
        if pos == "top":
            y_pos = "20"
        elif pos == "bottom":
            y_pos = "h-text_h-20"
        else:
            y_pos = "(h-text_h)/2"

        text_color = overlay.get('text_color', 'white')
        bg_color = overlay.get('bg_color', 'black')
        bg_opacity = overlay.get('bg_opacity', '0.5')
        font_size = overlay.get('font_size', '24')
        text_val = overlay.get('text', 'Hello')
        border = overlay.get('border', 'rounded')  # افتراضي: مستديرة

        box = ""
        if bg_color != "none":
            box = f":box=1:boxcolor={bg_color}@{bg_opacity}"
            if border == "rounded":
                box += ":boxborderw=5"  # Changed from boxrounder
            elif border == "square":
                box += ":boxborderw=1"
            elif border == "none_border":
                box = ""
        drawtext_filter = (
            f"drawtext=text='{text_val}':"
            f"fontcolor={text_color}:"
            f"fontsize={font_size}:"
            f"x=(w-text_w)/2:y={y_pos}{box}"
        )
        video_with_text = os.path.join(output_dir, "video_text.mp4")
        cmd_text = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", drawtext_filter,
            "-codec:a", "copy",
            video_with_text
        ]
        subprocess.run(cmd_text, check=True)
        source_video = video_with_text
    else:
        source_video = input_video

    # تقسيم الفيديو
    if split_method == "method2":
        # Split video into equal parts using seeking
        for i in range(context.user_data.get('num_parts')):
            start_time = i * segment_time
            output_file = os.path.join(output_dir, f"part_{i:03d}.mp4")
            
            cmd_split = [
                "ffmpeg", "-y",
                "-ss", f"{start_time}",
                "-t", f"{segment_time}",
                "-i", source_video,
                "-c:v", "copy",
                "-c:a", "copy",
                output_file
            ]
            subprocess.run(cmd_split, check=True)
    else:
        # For method 1 (fixed duration), use the original segment approach
        cmd_split = [
            "ffmpeg", "-y", "-i", source_video,
            "-c", "copy",
            "-map", "0",
            "-segment_time", str(segment_time),
            "-f", "segment",
            output_pattern
        ]
        subprocess.run(cmd_split, check=True)

    # في حالة عدم وجود نص توضيحي (auto numbering) نستخدم الإعدادات الافتراضية
    if overlay is None:
        parts_list = sorted([f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".mp4")])
        for idx, part in enumerate(parts_list, start=1):
            part_path = os.path.join(output_dir, part)
            drawtext = ("drawtext=text='Part {}':fontcolor=white:fontsize=24:"
                        "x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@1.0:boxborderw=5").format(idx)
            output_with_part = os.path.join(output_dir, f"final_{part}")
            cmd_overlay_part = [
                "ffmpeg", "-y", "-i", part_path,
                "-vf", drawtext,
                "-codec:a", "copy",
                output_with_part
            ]
            subprocess.run(cmd_overlay_part, check=True)
            os.replace(output_with_part, part_path)

    # إرسال أجزاء الفيديو للمستخدم
    parts_list = sorted([f for f in os.listdir(output_dir) if f.startswith("part_") and f.endswith(".mp4")])
    if not parts_list:
        await message.reply_text("لم يتم إنتاج أي جزء. تأكد من أن الفيديو صالح أو الإعدادات صحيحة.")
        return

    for part in parts_list:
        part_path = os.path.join(output_dir, part)
        with open(part_path, "rb") as vf:
            await message.reply_video(video=vf)
    await message.reply_text("تمت معالجة الفيديو وإرسال الأجزاء بنجاح.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def main():
    application = ApplicationBuilder().token(TELEGRAM_API_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            VIDEO: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, video_received)],
            CHOOSE_METHOD: [CallbackQueryHandler(method_choice)],
            ENTER_PARTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_parts)],
            OVERLAY_OPTION: [CallbackQueryHandler(overlay_option)],
            OVERLAY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, overlay_text)],
            OVERLAY_POSITION: [CallbackQueryHandler(overlay_position)],
            OVERLAY_TEXT_COLOR: [
                CallbackQueryHandler(color_chosen, pattern="^(white|black|red|green|blue|custom)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_color_input)
            ],
            OVERLAY_BG_COLOR: [
                CallbackQueryHandler(bg_color_choice, pattern="^(none|color_bg)$"),
                CallbackQueryHandler(color_chosen, pattern="^(white|black|red|green|blue|custom)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_color_input)
            ],
            OVERLAY_BG_OPACITY: [CallbackQueryHandler(opacity_chosen)],
            OVERLAY_FONT_SIZE: [
                CallbackQueryHandler(font_size_chosen, pattern="^(16|24|32|40|custom_font)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_font_size_input)
            ],
            OVERLAY_BORDER: [CallbackQueryHandler(border_chosen, pattern="^(rounded|square|none_border)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
