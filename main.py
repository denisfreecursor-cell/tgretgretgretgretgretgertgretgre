import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота (замени на свой)
BOT_TOKEN = "8332841587:AAFVWfnwTJbYqf-rWXTsaFgfBSxlvSx4R8c"

# ID администратора (замени на свой Telegram ID)
ADMIN_ID = 6763279788  # Узнать свой ID можно у @userinfobot

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class Form(StatesGroup):
    waiting_for_payment_method = State()
    waiting_for_requisites = State()
    waiting_for_withdraw_amount = State()
    waiting_for_report_photos = State()
    waiting_for_payment_amount = State()

# База данных пользователей (в реальном проекте используй БД)
users_db = {}
pending_reports = {}  # Отчеты ожидающие проверки
pending_withdrawals = {}  # Заявки на вывод

def get_user_data(user_id):
    """Получить данные пользователя"""
    if user_id not in users_db:
        users_db[user_id] = {
            'balance': 0,
            'payment_method': None,
            'requisites': None,
            'total_reports': 0,
            'completed_reports': 0
        }
    return users_db[user_id]

# Клавиатуры
def main_menu_keyboard():
    """Главное меню - красивая раскладка 2x2"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Сдать отчет", callback_data="report"),
            InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ]
    ])
    return keyboard

def services_keyboard():
    """Меню выбора сервиса для отчета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 TikTok Комментарии", callback_data="service_tiktok_comments"),
            InlineKeyboardButton(text="🎬 TikTok Видео", callback_data="service_tiktok_video")
        ],
        [
            InlineKeyboardButton(text="💬 Threads Комментарии", callback_data="service_threads_comments"),
            InlineKeyboardButton(text="🧵 Threads Ветки", callback_data="service_threads_threads")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard

def instruction_keyboard():
    """Меню инструкций - красивая раскладка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 TikTok Комментарии", callback_data="inst_tiktok_comments"),
            InlineKeyboardButton(text="🎬 TikTok Видео", callback_data="inst_tiktok_video")
        ],
        [
            InlineKeyboardButton(text="💬 Threads Комментарии", callback_data="inst_threads_comments"),
            InlineKeyboardButton(text="🧵 Threads Ветки", callback_data="inst_threads_threads")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard

def profile_keyboard():
    """Меню профиля"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Добавить реквизиты", callback_data="add_requisites")],
        [InlineKeyboardButton(text="💰 Вывод баланса", callback_data="withdraw")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard

def back_to_profile_keyboard():
    """Кнопка назад в профиль"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])
    return keyboard

def back_to_main_keyboard():
    """Кнопка назад в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    return keyboard

def finish_report_keyboard(photos_count):
    """Кнопка завершения отчета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Завершить работу ({photos_count} фото)", callback_data="finish_report")],
        [InlineKeyboardButton(text="🔙 Отменить", callback_data="cancel_report")]
    ])
    return keyboard

def admin_review_keyboard(user_id, report_id):
    """Кнопки для администратора при проверке отчета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{user_id}_{report_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user_id}_{report_id}")
        ]
    ])
    return keyboard

def admin_withdrawal_keyboard(user_id, withdrawal_id):
    """Кнопки для администратора при проверке вывода"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выплачено", callback_data=f"paid_{user_id}_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_withdrawal_{user_id}_{withdrawal_id}")
        ]
    ])
    return keyboard

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user_data = get_user_data(message.from_user.id)

    await message.answer(
        text="🎉 <b>Добро пожаловать в главное меню!</b>\n\n"
             "👋 Выберите нужный раздел из меню ниже:\n\n"
             "📊 <b>Сдать отчет</b> - загрузите скриншоты вашей работы\n"
             "📖 <b>Инструкция</b> - подробные гайды по сервисам\n"
             "ℹ️ <b>Информация</b> - общая информация\n"
             "👤 <b>Профиль</b> - ваш баланс и реквизиты",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

# ============= РАЗДЕЛ: СДАТЬ ОТЧЕТ =============

@dp.callback_query(F.data == "report")
async def show_report_menu(callback: CallbackQuery):
    """Показать меню выбора сервиса для отчета"""
    await callback.message.edit_text(
        text="📊 <b>Сдать отчет</b>\n\n"
             "🎯 Выберите сервис, по которому хотите сдать отчет:\n\n"
             "💡 <i>После выбора сервиса вам нужно будет отправить скриншоты выполненной работы</i>",
        reply_markup=services_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def start_report(callback: CallbackQuery, state: FSMContext):
    """Начать процесс сдачи отчета"""
    service = callback.data.replace("service_", "")

    service_names = {
        "tiktok_comments": "📱 TikTok Комментарии",
        "tiktok_video": "🎬 TikTok Видео",
        "threads_comments": "💬 Threads Комментарии",
        "threads_threads": "🧵 Threads Ветки"
    }

    service_name = service_names.get(service, "Неизвестный сервис")

    await state.update_data(
        service=service,
        service_name=service_name,
        photos=[],
        message_id=callback.message.message_id
    )

    await callback.message.edit_text(
        text=f"📸 <b>Загрузка отчета</b>\n\n"
             f"🎯 <b>Сервис:</b> {service_name}\n\n"
             f"📤 Отправьте скриншоты выполненной работы (фото)\n"
             f"📊 <b>Загружено:</b> 0 фото\n\n"
             f"💡 <i>Когда загрузите все скриншоты, нажмите кнопку 'Завершить работу'</i>",
        reply_markup=finish_report_keyboard(0),
        parse_mode="HTML"
    )

    await state.set_state(Form.waiting_for_report_photos)
    await callback.answer("📸 Ожидаю скриншоты...")

@dp.message(Form.waiting_for_report_photos, F.photo)
async def receive_report_photo(message: Message, state: FSMContext):
    """Получение фото для отчета"""
    data = await state.get_data()
    photos = data.get('photos', [])

    # Сохраняем file_id самого большого фото
    photo = message.photo[-1]
    photos.append(photo.file_id)

    await state.update_data(photos=photos)

    service_name = data.get('service_name', 'Неизвестный сервис')

    # Отправляем обновленное сообщение
    await message.answer(
        text=f"📸 <b>Загрузка отчета</b>\n\n"
             f"🎯 <b>Сервис:</b> {service_name}\n\n"
             f"✅ <b>Фото успешно добавлено!</b>\n"
             f"📊 <b>Загружено:</b> {len(photos)} фото\n\n"
             f"💡 <i>Загружайте ещё скриншоты или нажмите 'Завершить работу'</i>",
        reply_markup=finish_report_keyboard(len(photos)),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "finish_report")
async def finish_report(callback: CallbackQuery, state: FSMContext):
    """Завершить отчет и отправить на проверку"""
    data = await state.get_data()
    photos = data.get('photos', [])
    service_name = data.get('service_name', 'Неизвестный сервис')

    if not photos:
        await callback.answer("❌ Вы не загрузили ни одного фото!", show_alert=True)
        return

    user_id = callback.from_user.id
    report_id = f"{user_id}_{int(datetime.now().timestamp())}"

    # Сохраняем отчет
    pending_reports[report_id] = {
        'user_id': user_id,
        'username': callback.from_user.username or callback.from_user.first_name,
        'service_name': service_name,
        'photos': photos,
        'timestamp': datetime.now().strftime("%d.%m.%Y %H:%M")
    }

    user_data = get_user_data(user_id)
    user_data['total_reports'] += 1

    await state.clear()

    # Уведомление пользователю
    await callback.message.edit_text(
        text=f"✅ <b>Отчет успешно отправлен на проверку!</b> 🎉\n\n"
             f"🎯 <b>Сервис:</b> {service_name}\n"
             f"📊 <b>Загружено фото:</b> {len(photos)} шт.\n"
             f"⏰ <b>Время:</b> {pending_reports[report_id]['timestamp']}\n\n"
             f"⏳ <b>Ожидайте проверки администратора...</b>\n"
             f"📧 Вы получите уведомление о результате проверки!",
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )

    # Отправка отчета администратору
    try:
        await bot.send_message(
            ADMIN_ID,
            text=f"🆕 <b>НОВЫЙ ОТЧЕТ!</b>\n\n"
                 f"👤 <b>Работник:</b> @{pending_reports[report_id]['username']}\n"
                 f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                 f"🎯 <b>Сервис:</b> {service_name}\n"
                 f"📊 <b>Количество фото:</b> {len(photos)} шт.\n"
                 f"⏰ <b>Время:</b> {pending_reports[report_id]['timestamp']}\n\n"
                 f"📸 <b>Скриншоты работы:</b>",
            parse_mode="HTML"
        )

        # Отправляем все фото администратору
        for photo_id in photos:
            await bot.send_photo(ADMIN_ID, photo=photo_id)

        # Отправляем кнопки для проверки
        await bot.send_message(
            ADMIN_ID,
            text=f"⚡️ <b>Проверьте отчет и примите решение:</b>",
            reply_markup=admin_review_keyboard(user_id, report_id),
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Ошибка отправки администратору: {e}")

    await callback.answer("✅ Отчет отправлен!")

@dp.callback_query(F.data == "cancel_report")
async def cancel_report(callback: CallbackQuery, state: FSMContext):
    """Отменить создание отчета"""
    await state.clear()
    await callback.message.edit_text(
        text="❌ <b>Создание отчета отменено</b>\n\n"
             "🔙 Вы вернулись в главное меню",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ============= АДМИН: ПРОВЕРКА ОТЧЕТОВ =============

@dp.callback_query(F.data.startswith("accept_"))
async def admin_accept_report(callback: CallbackQuery, state: FSMContext):
    """Администратор принимает отчет"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = int(parts[1])
    report_id = '_'.join(parts[2:])

    if report_id not in pending_reports:
        await callback.answer("❌ Отчет не найден!", show_alert=True)
        return

    await state.update_data(
        pending_report_id=report_id,
        pending_user_id=user_id
    )

    await callback.message.edit_text(
        text=f"💰 <b>Отчет принят!</b>\n\n"
             f"💵 Введите сумму для начисления работнику (в рублях):\n\n"
             f"💡 <i>Например: 500</i>",
        parse_mode="HTML"
    )

    await state.set_state(Form.waiting_for_payment_amount)
    await callback.answer("✅ Отчет принят! Введите сумму")

@dp.message(Form.waiting_for_payment_amount)
async def admin_set_payment(message: Message, state: FSMContext):
    """Администратор вводит сумму оплаты"""
    if message.from_user.id != ADMIN_ID:
        return

    try:
        amount = float(message.text)

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!")
            return

        data = await state.get_data()
        report_id = data.get('pending_report_id')
        user_id = data.get('pending_user_id')

        if report_id not in pending_reports:
            await message.answer("❌ Отчет не найден!")
            await state.clear()
            return

        report = pending_reports[report_id]
        user_data = get_user_data(user_id)

        # Начисляем деньги
        user_data['balance'] += amount
        user_data['completed_reports'] += 1

        # Удаляем отчет из ожидающих
        del pending_reports[report_id]

        await state.clear()

        # Уведомление администратору
        await message.answer(
            text=f"✅ <b>Оплата начислена!</b>\n\n"
                 f"💰 <b>Сумма:</b> {amount} ₽\n"
                 f"👤 <b>Работник:</b> @{report['username']}\n"
                 f"🎯 <b>Сервис:</b> {report['service_name']}\n\n"
                 f"📧 Работник получил уведомление!",
            parse_mode="HTML"
        )

        # Уведомление работнику
        try:
            await bot.send_message(
                user_id,
                text=f"🎉 <b>ОТЧЕТ ПРИНЯТ!</b> 🎉\n\n"
                     f"✅ Ваш отчет успешно проверен и одобрен!\n\n"
                     f"🎯 <b>Сервис:</b> {report['service_name']}\n"
                     f"💰 <b>Начислено:</b> +{amount} ₽\n"
                     f"💵 <b>Текущий баланс:</b> {user_data['balance']} ₽\n\n"
                     f"🎊 Отличная работа! Так держать!",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю: {e}")

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (число)!")

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject_report(callback: CallbackQuery):
    """Администратор отклоняет отчет"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return

    parts = callback.data.split("_")

    # Проверяем - это отклонение отчета или вывода
    if parts[0] == "reject" and parts[1] == "withdrawal":
        # Это отклонение вывода
        user_id = int(parts[2])
        withdrawal_id = '_'.join(parts[3:])

        if withdrawal_id not in pending_withdrawals:
            await callback.answer("❌ Заявка не найдена!", show_alert=True)
            return

        withdrawal = pending_withdrawals[withdrawal_id]

        # Возвращаем деньги
        user_data = get_user_data(user_id)
        user_data['balance'] += withdrawal['amount']

        del pending_withdrawals[withdrawal_id]

        await callback.message.edit_text(
            text=f"❌ <b>Заявка на вывод отклонена</b>\n\n"
                 f"👤 <b>Работник:</b> @{withdrawal['username']}\n"
                 f"💰 <b>Сумма:</b> {withdrawal['amount']} ₽\n\n"
                 f"📧 Работник получил уведомление",
            parse_mode="HTML"
        )

        # Уведомление работнику
        try:
            await bot.send_message(
                user_id,
                text=f"❌ <b>ЗАЯВКА НА ВЫВОД ОТКЛОНЕНА</b>\n\n"
                     f"💰 <b>Сумма:</b> {withdrawal['amount']} ₽\n"
                     f"💵 <b>Средства возвращены на баланс</b>\n"
                     f"📊 <b>Текущий баланс:</b> {user_data['balance']} ₽\n\n"
                     f"💡 Свяжитесь с администратором для уточнения причины",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю: {e}")

        await callback.answer("❌ Заявка отклонена")
        return

    # Это отклонение отчета
    user_id = int(parts[1])
    report_id = '_'.join(parts[2:])

    if report_id not in pending_reports:
        await callback.answer("❌ Отчет не найден!", show_alert=True)
        return

    report = pending_reports[report_id]
    del pending_reports[report_id]

    await callback.message.edit_text(
        text=f"❌ <b>Отчет отклонен</b>\n\n"
             f"👤 <b>Работник:</b> @{report['username']}\n"
             f"🎯 <b>Сервис:</b> {report['service_name']}\n\n"
             f"📧 Работник получил уведомление",
        parse_mode="HTML"
    )

    # Уведомление работнику
    try:
        await bot.send_message(
            user_id,
            text=f"❌ <b>ОТЧЕТ ОТКЛОНЕН</b>\n\n"
                 f"😔 К сожалению, ваш отчет не прошел проверку\n\n"
                 f"🎯 <b>Сервис:</b> {report['service_name']}\n"
                 f"📊 <b>Фото:</b> {len(report['photos'])} шт.\n\n"
                 f"💡 Пожалуйста, убедитесь что:\n"
                 f"   • Скриншоты четкие и читаемые\n"
                 f"   • Выполнена вся необходимая работа\n"
                 f"   • Соблюдены все требования\n\n"
                 f"🔄 Попробуйте сдать отчет еще раз!",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки пользователю: {e}")

    await callback.answer("❌ Отчет отклонен")

# ============= РАЗДЕЛ: ИНСТРУКЦИИ =============

@dp.callback_query(F.data == "instruction")
async def show_instructions(callback: CallbackQuery):
    """Показать меню инструкций"""
    await callback.message.edit_text(
        text="📚 <b>Выберите сервис для просмотра инструкции:</b>\n\n"
             "📱 <b>TikTok</b> - инструкции по работе с комментариями и видео\n"
             "🧵 <b>Threads</b> - гайды по комментариям и веткам\n\n"
             "💡 <i>Нажмите на нужный раздел для получения подробной информации</i>",
        reply_markup=instruction_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("inst_"))
async def show_instruction_detail(callback: CallbackQuery):
    """Показать конкретную инструкцию"""
    instruction_type = callback.data.replace("inst_", "")
    instructions = {
"tiktok_comments": (
    "📱 <b>Инструкция: TikTok Комментарии</b>\n\n"
    "Ваша задача — оставлять комментарии под <b>видео, связанными с Казахстаном и темой вейпов</b> 💨\n"
    "Так как заказчик работает только на территории Казахстана, фокус именно на этом регионе 🇰🇿\n\n"
    "🔍 <b>Что искать:</b>\n"
    "• В TikTok используйте ключевые слова: «вейп», «одноразка», «Казахстан», «VAKA» и т.д.\n"
    "• Видео из России, где основная аудитория — российская, не считаются.\n"
    "• Нам нужны именно казахстанские видео!\n\n"
    "💬 <b>Как комментировать:</b>\n"
    "• В каждом комментарии обязательно указывайте @LuxtoreVape (Telegram)\n"
    "• Можно писать под чужими комментариями — например, если кто-то спрашивает, где купить одноразку.\n"
    "• Комментарии должны быть нейтральными, естественными и без грубости.\n"
    "• Не используйте прямые призывы «покупай» или «переходи», чтобы TikTok не блокировал.\n\n"
    "🖼️ <b>Дополнительно:</b>\n"
    "• Можно создать в Photoshop изображение с надписью @LuxtoreVape (Telegram) и лёгким призывом.\n"
    "• Такое изображение можно прикреплять под подходящие видео — это тоже засчитывается.\n\n"
    "📋 <b>Отчёт:</b>\n"
    "• Укажите ссылку на видео, где оставлен комментарий.\n"
    "• Приложите скриншот вашего комментария под видео.\n\n"
    "⚠️ <b>Важно:</b>\n"
    "• Комментарий должен быть хорошо виден на скриншоте.\n"
    "• Скриншот должен быть чётким.\n"
    "• Не используйте запрещённые слова или грубые выражения."
),

        "tiktok_video": (
            "🎬 <b>Инструкция: TikTok Видео</b>\n\n"
            "1️⃣ Создайте видео согласно требованиям\n"
            "2️⃣ Загрузите видео в TikTok\n"
            "3️⃣ Добавьте хештеги из задания\n"
            "4️⃣ Опубликуйте видео\n"
            "5️⃣ Сделайте скриншот статистики\n\n"
            "⚠️ <b>Важно:</b>\n"
            "• Видео должно соответствовать заданию\n"
            "• Все хештеги должны быть добавлены"
        ),
        "threads_comments": (
            "💬 <b>Инструкция: Threads Комментарии</b>\n\n"
            "1️⃣ Откройте приложение Threads\n"
            "2️⃣ Найдите нужный пост\n"
            "3️⃣ Напишите комментарий\n"
            "4️⃣ Сделайте скриншот\n\n"
            "⚠️ <b>Важно:</b>\n"
            "• Комментарий должен быть содержательным\n"
            "• Без спама и рекламы"
        ),
        "threads_threads": (
            "🧵 <b>Инструкция: Threads Ветки</b>\n\n"
            "1️⃣ Создайте новый тред\n"
            "2️⃣ Добавьте требуемый контент\n"
            "3️⃣ Опубликуйте\n"
            "4️⃣ Сделайте скриншоты\n\n"
            "⚠️ <b>Важно:</b>\n"
            "• Контент должен быть уникальным\n"
            "• Следуйте всем требованиям задания"
        )
    }

    text = instructions.get(instruction_type, "Инструкция не найдена")
    await callback.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К списку инструкций", callback_data="instruction")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

# ============= РАЗДЕЛ: ПРОФИЛЬ =============

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    """Показать профиль пользователя"""
    await state.clear()
    user_data = get_user_data(callback.from_user.id)

    requisites_text = "❌ Не указаны"
    if user_data['payment_method'] and user_data['requisites']:
        requisites_text = f"✅ {user_data['payment_method']}\n🔢 <code>{user_data['requisites']}</code>"

    await callback.message.edit_text(
        text=f"👤 <b>Ваш профиль</b>\n\n"
             f"💰 <b>Баланс:</b> {user_data['balance']} ₽\n\n"
             f"💳 <b>Реквизиты:</b>\n{requisites_text}\n\n"
             f"📊 <b>Статистика:</b>\n"
             f"   • Всего отчетов: {user_data['total_reports']}\n"
             f"   • Принято: {user_data['completed_reports']}\n\n"
             f"💡 <i>Управляйте реквизитами и выводите заработанные средства</i>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ============= ДОБАВЛЕНИЕ РЕКВИЗИТОВ =============

@dp.callback_query(F.data == "add_requisites")
async def add_requisites_step1(callback: CallbackQuery, state: FSMContext):
    """Первый шаг добавления реквизитов - выбор способа оплаты"""
    await callback.message.edit_text(
        text="💳 <b>Добавление реквизитов</b>\n\n"
             f"📝 <b>Шаг 1/2:</b> Укажите способ оплаты\n\n"
             f"💡 Например:\n"
             f"   • Банковская карта\n"
             f"   • Qiwi\n"
             f"   • ЮMoney\n"
             f"   • Криптокошелек\n\n"
             f"✏️ Напишите способ оплаты:",
        reply_markup=back_to_profile_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_payment_method)
    await callback.answer()

@dp.message(Form.waiting_for_payment_method)
async def add_requisites_step2(message: Message, state: FSMContext):
    """Второй шаг - запрос реквизитов"""
    await state.update_data(payment_method=message.text)

    await message.answer(
        text=f"🔢 <b>Добавление реквизитов</b>\n\n"
             f"📝 <b>Шаг 2/2:</b> Укажите реквизиты\n\n"
             f"💳 <b>Способ оплаты:</b> {message.text}\n\n"
             f"✏️ Напишите номер карты, кошелька или другие данные:",
        reply_markup=back_to_profile_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_requisites)

@dp.message(Form.waiting_for_requisites)
async def save_requisites(message: Message, state: FSMContext):
    """Сохранение реквизитов"""
    data = await state.get_data()
    payment_method = data.get('payment_method')

    user_data = get_user_data(message.from_user.id)
    user_data['payment_method'] = payment_method
    user_data['requisites'] = message.text

    await state.clear()

    await message.answer(
        text=f"✅ <b>Реквизиты успешно сохранены!</b> 🎉\n\n"
             f"💳 <b>Способ оплаты:</b> {payment_method}\n"
             f"🔢 <b>Реквизиты:</b> <code>{message.text}</code>\n\n"
             f"💰 Теперь вы можете выводить заработанные средства!",
        parse_mode="HTML"
    )

    # Показываем обновленный профиль
    requisites_text = f"✅ {payment_method}\n🔢 <code>{message.text}</code>"

    await message.answer(
        text=f"👤 <b>Ваш профиль</b>\n\n"
             f"💰 <b>Баланс:</b> {user_data['balance']} ₽\n\n"
             f"💳 <b>Реквизиты:</b>\n{requisites_text}\n\n"
             f"📊 <b>Статистика:</b>\n"
             f"   • Всего отчетов: {user_data['total_reports']}\n"
             f"   • Принято: {user_data['completed_reports']}\n\n"
             f"💡 <i>Управляйте реквизитами и выводите заработанные средства</i>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )

# ============= ВЫВОД СРЕДСТВ =============

@dp.callback_query(F.data == "withdraw")
async def withdraw_balance(callback: CallbackQuery, state: FSMContext):
    """Начать процесс вывода баланса"""
    user_data = get_user_data(callback.from_user.id)

    if user_data['balance'] <= 0:
        await callback.answer(
            "❌ У вас недостаточно средств для вывода!\n\n"
            "💡 Сдавайте отчеты для пополнения баланса",
            show_alert=True
        )
        return

    if not user_data['requisites']:
        await callback.answer(
            "❌ Сначала добавьте реквизиты!\n\n"
            "💡 Нажмите 'Добавить реквизиты'",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        text=f"💰 <b>Вывод средств</b>\n\n"
             f"💵 <b>Доступно для вывода:</b> {user_data['balance']} ₽\n"
             f"💳 <b>Реквизиты:</b> {user_data['payment_method']}\n"
             f"🔢 <code>{user_data['requisites']}</code>\n\n"
             f"✏️ Введите сумму которую хотите вывести:\n\n"
             f"💡 <i>Минимальная сумма вывода: 100 ₽</i>",
        reply_markup=back_to_profile_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_withdraw_amount)
    await callback.answer()

@dp.message(Form.waiting_for_withdraw_amount)
async def process_withdraw(message: Message, state: FSMContext):
    """Обработка запроса на вывод"""
    try:
        amount = float(message.text)
        user_data = get_user_data(message.from_user.id)

        if amount < 100:
            await message.answer(
                "❌ <b>Минимальная сумма вывода: 100 ₽</b>\n\n"
                "💡 Укажите сумму не менее 100 рублей",
                parse_mode="HTML"
            )
            return

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!")
            return

        if amount > user_data['balance']:
            await message.answer(
                f"❌ <b>Недостаточно средств!</b>\n\n"
                f"💰 Ваш баланс: {user_data['balance']} ₽\n"
                f"💵 Вы пытаетесь вывести: {amount} ₽\n\n"
                f"💡 Укажите сумму не больше вашего баланса",
                parse_mode="HTML"
            )
            return

        # Создаем заявку на вывод
        withdrawal_id = f"{message.from_user.id}_{int(datetime.now().timestamp())}"
        pending_withdrawals[withdrawal_id] = {
            'user_id': message.from_user.id,
            'username': message.from_user.username or message.from_user.first_name,
            'amount': amount,
            'payment_method': user_data['payment_method'],
            'requisites': user_data['requisites'],
            'timestamp': datetime.now().strftime("%d.%m.%Y %H:%M")
        }

        # Снимаем деньги с баланса
        user_data['balance'] -= amount

        await state.clear()

        # Уведомление пользователю
        await message.answer(
            text=f"✅ <b>Заявка на вывод создана!</b> 🎉\n\n"
                 f"💰 <b>Сумма вывода:</b> {amount} ₽\n"
                 f"💳 <b>Способ:</b> {user_data['payment_method']}\n"
                 f"🔢 <b>Реквизиты:</b> <code>{user_data['requisites']}</code>\n"
                 f"⏰ <b>Время:</b> {pending_withdrawals[withdrawal_id]['timestamp']}\n\n"
                 f"⏳ <b>Ожидайте рассмотрения вашей заявки...</b>\n"
                 f"📧 Вы получите уведомление о результате!\n\n"
                 f"💵 <b>Новый баланс:</b> {user_data['balance']} ₽",
            parse_mode="HTML"
        )

        # Возврат в главное меню
        await message.answer(
            text="🎉 <b>Добро пожаловать в главное меню!</b>\n\n"
                 "👋 Выберите нужный раздел из меню ниже:\n\n"
                 "📊 <b>Сдать отчет</b> - загрузите скриншоты вашей работы\n"
                 "📖 <b>Инструкция</b> - подробные гайды по сервисам\n"
                 "ℹ️ <b>Информация</b> - общая информация\n"
                 "👤 <b>Профиль</b> - ваш баланс и реквизиты",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

        # Отправка заявки администратору
        try:
            await bot.send_message(
                ADMIN_ID,
                text=f"💰 <b>НОВАЯ ЗАЯВКА НА ВЫВОД!</b>\n\n"
                     f"👤 <b>Работник:</b> @{pending_withdrawals[withdrawal_id]['username']}\n"
                     f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n\n"
                     f"💵 <b>Сумма:</b> {amount} ₽\n"
                     f"💳 <b>Способ оплаты:</b> {user_data['payment_method']}\n"
                     f"🔢 <b>Реквизиты:</b> <code>{user_data['requisites']}</code>\n\n"
                     f"⏰ <b>Время:</b> {pending_withdrawals[withdrawal_id]['timestamp']}\n\n"
                     f"⚡️ <b>Примите решение:</b>",
                reply_markup=admin_withdrawal_keyboard(message.from_user.id, withdrawal_id),
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки администратору: {e}")

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (число)!")

# ============= АДМИН: ПРОВЕРКА ВЫВОДА =============

@dp.callback_query(F.data.startswith("paid_"))
async def admin_confirm_payment(callback: CallbackQuery):
    """Администратор подтверждает выплату"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав!", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = int(parts[1])
    withdrawal_id = '_'.join(parts[2:])

    if withdrawal_id not in pending_withdrawals:
        await callback.answer("❌ Заявка не найдена!", show_alert=True)
        return

    withdrawal = pending_withdrawals[withdrawal_id]
    del pending_withdrawals[withdrawal_id]

    await callback.message.edit_text(
        text=f"✅ <b>Выплата подтверждена!</b>\n\n"
             f"👤 <b>Работник:</b> @{withdrawal['username']}\n"
             f"💰 <b>Сумма:</b> {withdrawal['amount']} ₽\n"
             f"💳 <b>Способ:</b> {withdrawal['payment_method']}\n\n"
             f"📧 Работник получил уведомление",
        parse_mode="HTML"
    )

    # Уведомление работнику
    try:
        user_data = get_user_data(user_id)
        await bot.send_message(
            user_id,
            text=f"✅ <b>ВЫПЛАТА ВЫПОЛНЕНА!</b> 🎉\n\n"
                 f"💰 <b>Сумма:</b> {withdrawal['amount']} ₽\n"
                 f"💳 <b>Способ:</b> {withdrawal['payment_method']}\n"
                 f"🔢 <b>Реквизиты:</b> <code>{withdrawal['requisites']}</code>\n\n"
                 f"🎊 Средства успешно переведены на ваши реквизиты!\n"
                 f"💵 <b>Текущий баланс:</b> {user_data['balance']} ₽\n\n"
                 f"💼 Спасибо за работу! Продолжайте в том же духе!",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки пользователю: {e}")

    await callback.answer("✅ Выплата подтверждена!")

# ============= РАЗДЕЛ: ИНФОРМАЦИЯ =============

@dp.callback_query(F.data == "info")
async def show_info(callback: CallbackQuery):
    """Показать информацию"""
    await callback.message.edit_text(
        text="ℹ️ <b>Информация о боте</b>\n\n"
             "🤖 <b>Что это за бот?</b>\n"
             "Этот бот создан для удобного взаимодействия работников с администрацией. "
             "Здесь вы можете сдавать отчеты о выполненной работе и получать за это вознаграждение.\n\n"
             "💼 <b>Как работать?</b>\n"
             "1️⃣ Выберите сервис для работы в разделе 'Инструкция'\n"
             "2️⃣ Изучите требования к выполнению задания\n"
             "3️⃣ Выполните работу и сделайте скриншоты\n"
             "4️⃣ Сдайте отчет через раздел 'Сдать отчет'\n"
             "5️⃣ Дождитесь проверки администратором\n"
             "6️⃣ Получите оплату на баланс\n"
             "7️⃣ Выведите средства на свои реквизиты\n\n"
             "💰 <b>Оплата:</b>\n"
             "Стоимость работы зависит от сервиса и сложности задания. "
             "Оплата начисляется после проверки и одобрения отчета администратором.\n\n"
             "📞 <b>Поддержка:</b>\n"
             "Если у вас возникли вопросы, обратитесь к администратору.\n\n"
             "🎯 <b>Удачной работы!</b>",
        reply_markup=back_to_main_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# ============= КНОПКА НАЗАД =============

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        text="🎉 <b>Добро пожаловать в главное меню!</b>\n\n"
             "👋 Выберите нужный раздел из меню ниже:\n\n"
             "📊 <b>Сдать отчет</b> - загрузите скриншоты вашей работы\n"
             "📖 <b>Инструкция</b> - подробные гайды по сервисам\n"
             "ℹ️ <b>Информация</b> - общая информация\n"
             "👤 <b>Профиль</b> - ваш баланс и реквизиты",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

# Запуск бота
async def main():
    """Главная функция запуска бота"""
    print("🤖 Бот запущен и готов к работе!")
    print(f"📝 ID администратора: {ADMIN_ID}")
    print("⚠️  Не забудьте заменить BOT_TOKEN и ADMIN_ID!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
