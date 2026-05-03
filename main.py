import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import WebAppInfo
from supabase import create_client

# 1. Твій ID (Адмін)
ADMIN_ID = 733972417 

# Налаштування
TOKEN = os.environ['TELEGRAM_TOKEN']
supabase = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_KEY'])

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Survey(StatesGroup):
    company_id = State()
    role = State()
    first_name = State()
    last_name = State()
    experience = State()
    danger = State()
    phone = State()

# --- ФОНОВЕ ЗАВДАННЯ: КУР'ЄР ПОВІДОМЛЕНЬ ВІД ІНЖЕНЕРА ОП ---
async def check_notifications():
    print("🚀 Система сповіщень активована...")
    while True:
        try:
            # Шукаємо в базі нові повідомлення для відправки
            res = supabase.table("bot_notifications").select("*").eq("is_sent", False).execute()
            for note in res.data:
                try:
                    # Створюємо кнопку для переходу в навчання
                    lms_url = f"https://hse-vision.lovable.app/?tg_id={note['telegram_id']}"
                    builder = InlineKeyboardBuilder()
                    builder.row(types.InlineKeyboardButton(
                        text="🚀 Відкрити навчання", 
                        web_app=WebAppInfo(url=lms_url)
                    ))

                    # Надсилаємо повідомлення робітнику з кнопкою
                    await bot.send_message(
                        note['telegram_id'], 
                        f"🔔 <b>Повідомлення Інженера з ОП:</b>\n\n{note['message']}", 
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )

                    # Позначаємо як відправлене
                    supabase.table("bot_notifications").update({"is_sent": True}).eq("id", note['id']).execute()
                    print(f"✅ Сповіщення відправлено до {note['telegram_id']}")
                except Exception as e:
                    print(f"Помилка відправки повідомлення: {e}")
        except Exception as e:
            print(f"Помилка зв'язку з базою: {e}")
        await asyncio.sleep(10) # Перевірка кожні 10 секунд

# --- ДОПОМІЖНА ФУНКЦІЯ (Початок анкети) ---
async def start_survey_flow(message: types.Message, state: FSMContext, command: CommandObject = None):
    await state.clear()

    # Визначаємо компанію з аргументів посилання
    args = command.args if command else None
    company = args if args else "no_name"
    await state.update_data(company_id=company)

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Я — Зварювальник", callback_data="role_worker"))
    builder.row(types.InlineKeyboardButton(text="Я — Інженер з Охорони праці (ОП)", callback_data="role_engineer"))

    await message.answer(
        "Привіт! Я — твій <b>цифровий напарник</b>. Допоможу з безпекою праці та навчанням, щоб робота йшла як по маслу.\n\n"
        "Давай за 30 секунд налаштуємо твій профіль.\n\n"
        "<b>Хто ти сьогодні?</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(Survey.role)

# --- 1. ГОЛОВНИЙ СТАРТ ---
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext, command: CommandObject):
    user_id = message.from_user.id
    await state.clear()

    # Шукаємо конкретного користувача в базі
    user_query = supabase.table("profiles").select("*").eq("telegram_id", user_id).execute()
    existing_user = user_query.data[0] if user_query.data else None

    # ЛОГІКА ДЛЯ АДМІНА (Тебе)
    if user_id == ADMIN_ID:
        count_query = supabase.table("profiles").select("*", count="exact").limit(1).execute()
        total_users = count_query.count if count_query.count is not None else 0

        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🧪 Тестувати анкету", callback_data="start_survey"))
        builder.row(types.InlineKeyboardButton(text="🚀 Перейти до навчання", web_app=WebAppInfo(url=f"https://hse-vision.lovable.app/?tg_id={user_id}")))

        await message.answer(
            f"🛠 <b>ПАНЕЛЬ АДМІНІСТРАТОРА</b>\n\n"
            f"Зараз у базі користувачів: <b>{total_users}</b>\n\n"
            f"Оберіть дію або просто пишіть повідомлення:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    # ЛОГІКА ДЛЯ ІСНУЮЧОГО ЮЗЕРА
    if existing_user:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔄 Оновити анкету", callback_data="start_survey"))

        lms_url = f"https://hse-vision.lovable.app/?tg_id={user_id}"
        builder.row(types.InlineKeyboardButton(text="🚀 Розпочати Навчання", web_app=WebAppInfo(url=lms_url)))

        first_name = existing_user.get('first_name', 'напарнику')

        await message.answer(
            f"Привіт, <b>{first_name}</b>! Радий тебе бачити знову.\n\n"
            f"Ти вже зареєстрований у системі. Бажаєш <b>оновити свої дані</b> чи <b>перейти до навчання</b>?\n\n"
            "Також ти можеш просто написати мені будь-яке питання нижче.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    # ЛОГІКА ДЛЯ НОВОГО ЮЗЕРА
    await start_survey_flow(message, state, command)

# Обробник кнопки "Оновити анкету"
@dp.callback_query(F.data == "start_survey")
async def handle_update_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_survey_flow(callback.message, state)

# --- КРОКИ АНКЕТИ ---

@dp.callback_query(F.data.startswith("role_"))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(role=callback.data)
    await callback.message.answer(
        "Напиши, будь ласка, тільки своє <b>Ім’я</b>.\n"
        "<i>(Це потрібно для твоїх дипломів)</i>",
        parse_mode="HTML"
    )
    await state.set_state(Survey.first_name)

@dp.message(Survey.first_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Добре! А тепер напиши <b>Прізвище</b>:", parse_mode="HTML")
    await state.set_state(Survey.last_name)

@dp.message(Survey.last_name)
async def process_surname(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="До 1 року (тільки починаю)", callback_data="exp_1"))
    builder.row(types.InlineKeyboardButton(text="1–5 років (уже дещо бачив)", callback_data="exp_1_5"))
    builder.row(types.InlineKeyboardButton(text="Понад 5 років (мене не чим не здивуєш)", callback_data="exp_5plus"))
    await message.answer("Чудово! А який у тебе вже <b>досвід</b> у професії?", reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(Survey.experience)

@dp.callback_query(Survey.experience)
async def process_exp(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(experience=callback.data)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Щодня (гаряча ділянка)", callback_data="danger_daily"))
    builder.row(types.InlineKeyboardButton(text="Раз на тиждень (буває всяке)", callback_data="danger_weekly"))
    builder.row(types.InlineKeyboardButton(text="Майже ніколи (у нас все чітко)", callback_data="danger_never"))
    await callback.message.answer(
        "Круто! Будемо чесними: <b>як часто</b> на зміні стаються якісь <b>\"нежданчики\"</b> або <b>небезпечні моменти</b>?", 
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(Survey.danger)

@dp.callback_query(Survey.danger)
async def process_danger(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(danger=callback.data)
    kb = ReplyKeyboardBuilder()
    kb.row(types.KeyboardButton(text="🚀 Отримати доступ до навчання", request_contact=True))
    await callback.message.answer(
        "Ще трошки! Поділись номером телефону, щоб ми <b>зберегли твій прогрес</b> і ти не загубив <b>доступ до кабінету</b>",
        reply_markup=kb.as_markup(resize_keyboard=True, one_time_keyboard=True),
        parse_mode="HTML"
    )
    await state.set_state(Survey.phone)

@dp.message(Survey.phone, F.contact | F.text)
async def finish(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    data = await state.get_data()
    supabase.table("profiles").upsert({
        "telegram_id": message.from_user.id,
        "role": data['role'],
        "first_name": data['first_name'],
        "last_name": data['last_name'],
        "experience": data['experience'],
        "danger_frequency": data['danger'],
        "phone": phone,
        "company_id": data['company_id']
    }, on_conflict="telegram_id").execute()
    await state.clear()
    lms_url = f"https://hse-vision.lovable.app/?tg_id={message.from_user.id}"
    builder_reply = ReplyKeyboardBuilder()
    builder_reply.row(types.KeyboardButton(text="🚀 Розпочати Навчання", web_app=WebAppInfo(url=lms_url)))
    builder_inline = InlineKeyboardBuilder()
    builder_inline.row(types.InlineKeyboardButton(text="🚀 Розпочати Навчання", web_app=WebAppInfo(url=lms_url)))
    await message.answer(
        "✅ <b>Готово!</b> Тепер задавай мені будь-яке питання з безпеки праці тут або проходь <b>Навчання з Охорони Праці — кнопка знизу екрану</b>",
        reply_markup=builder_reply.as_markup(resize_keyboard=True),
        parse_mode="HTML"
    )
    await message.answer("<b>Скористайся кнопкою для входу:</b>", reply_markup=builder_inline.as_markup(), parse_mode="HTML")

async def main():
    # Запускаємо фонову перевірку сповіщень
    asyncio.create_task(check_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())