from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile

from settings import app_settings
from src.parser import parse_response
from src.parser_drom import parse_response_drom
from src.render import generate_test_svg, draw_car_info_on_image

bot = Bot(token=app_settings.TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_cars = {}
user_media_messages = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message) -> None:
    await message.reply(
        "Привет! Пришли ссылку на auto.ru, и я покажу подробности и фото автомобиля."
    )


@dp.message_handler(lambda message: message.text.startswith('https://auto.ru'))
async def handle_message(message: types.Message) -> None:
    try:
        if message.from_user.id not in app_settings.ALLOWED_USER_IDS:
            await message.reply("Извините, доступ к боту ограничен.")
            return
    except TypeError as e:
        print(app_settings.ALLOWED_USER_IDS)
        print(type(app_settings.ALLOWED_USER_IDS))
        print(f"Ошибка проверки ID: {e}")
        await message.reply("Ошибка конфигурации бота. Обратитесь к администратору.")
        return

    url = message.text.strip()
    print(f"Начинаем извлекать данные {url}")

    car = parse_response(url)
    if not car or not car.images:
        await message.reply("Не удалось извлечь данные. Возможно, ссылка неверная или на странице есть капча.")
        return
    user_cars[message.from_user.id] = car

    media = [
        types.InputMediaPhoto(media=img_url)
        for img_url in car.images[:3]
    ]

    sent_messages = await message.answer_media_group(media)
    user_media_messages[message.from_user.id] = [msg.message_id for msg in sent_messages]

    keyboard = InlineKeyboardMarkup(row_width=3)
    for i in range(min(3, len(car.images))):
        keyboard.insert(
            InlineKeyboardButton(text=f"Фото {i+1}", callback_data=f"photo_{i}")
        )

    additional_text = (
        "📸 Пожалуйста, выберите одну из фотографий выше, которая будет использована в коммерческом предложении"
        ",а также укажите, требуется ли включение НДС.\n"
        "На основе выбранного изображения и представленных данных будет сформировано персонализированное предложение по автомобилю."
    )


    car_info = str(car)
    if len(car_info) + len(additional_text) > 4096:
        car_info = car_info[:4096 - len(additional_text) - 3] + "..."

    full_car_info = f"{car_info}{additional_text}"

    try:
        await message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения пользователя: {e}")

    await message.answer(full_car_info, reply_markup=keyboard)

@dp.message_handler(lambda message: message.text.startswith('https://auto.drom.ru'))
async def handle_message(message: types.Message) -> None:
    try:
        if message.from_user.id not in app_settings.ALLOWED_USER_IDS:
            await message.reply("Извините, доступ к боту ограничен.")
            return
    except TypeError as e:
        print(app_settings.ALLOWED_USER_IDS)
        print(type(app_settings.ALLOWED_USER_IDS))
        print(f"Ошибка проверки ID: {e}")
        await message.reply("Ошибка конфигурации бота. Обратитесь к администратору.")
        return

    url = message.text.strip()
    print(f"Начинаем извлекать данные {url}")

    car = parse_response_drom(url)
    if not car or not car.images:
        await message.reply("Не удалось извлечь данные. Возможно, ссылка неверная или на странице есть капча.")
        return
    user_cars[message.from_user.id] = car

    media = [
        types.InputMediaPhoto(media=img_url)
        for img_url in car.images[:3]
    ]

    sent_messages = await message.answer_media_group(media)
    user_media_messages[message.from_user.id] = [msg.message_id for msg in sent_messages]

    keyboard = InlineKeyboardMarkup(row_width=3)
    for i in range(min(3, len(car.images))):
        keyboard.insert(
            InlineKeyboardButton(text=f"Фото {i+1}", callback_data=f"photo_{i}")
        )

    additional_text = (
        "📸 Пожалуйста, выберите одну из фотографий выше, которая будет использована в коммерческом предложении"
        ",а также укажите, требуется ли включение НДС.\n"
        "На основе выбранного изображения и представленных данных будет сформировано персонализированное предложение по автомобилю."
    )


    car_info = str(car)
    if len(car_info) + len(additional_text) > 4096:
        car_info = car_info[:4096 - len(additional_text) - 3] + "..."

    full_car_info = f"{car_info}{additional_text}"

    try:
        await message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения пользователя: {e}")

    await message.answer(full_car_info, reply_markup=keyboard)


@dp.callback_query_handler(lambda call: call.data.startswith("photo_"))
async def handle_photo_click(call: CallbackQuery):
    index = int(call.data.split("_")[1])
    car = user_cars.get(call.from_user.id)

    if not car or index >= len(car.images):
        await call.answer("Фотография недоступна", show_alert=True)
        return

    vat_keyboard = InlineKeyboardMarkup(row_width=2)
    vat_keyboard.add(
        InlineKeyboardButton(text="с НДС", callback_data=f"vat_yes_{index}"),
        InlineKeyboardButton(text="без НДС", callback_data=f"vat_no_{index}"),
        InlineKeyboardButton(text="Назад к фото", callback_data="back_to_photos")
    )

    await call.message.edit_reply_markup(reply_markup=vat_keyboard)
    await call.answer(f"Выбрано Фото {index+1}")

@dp.callback_query_handler(lambda call: call.data.startswith("vat_"))
async def handle_vat_click(call: CallbackQuery):
    vat_choice, index = call.data.split("_")[1], int(call.data.split("_")[2])
    car = user_cars.get(call.from_user.id)

    if not car:
        await call.answer("Данные об автомобиле недоступны", show_alert=True)
        return

    nds = True if vat_choice == "yes" else False

    if nds:
        try:
            cleaned_price = car.price.replace("\xa0", "").replace(" ", "")
            new_price_int = int(cleaned_price) * 1.2
            new_price_str = "{:,.0f}".format(new_price_int).replace(",", " ")
            car.price = new_price_str
        except (ValueError, TypeError):
            await call.answer("Ошибка: Неверный формат цены", show_alert=True)

    car_info = str(car)
    if len(car_info) > 4000:
        car_info = car_info[:3950] + "..."
    updated_car_info = f"{car_info} ⏳ Загрузка..."

    try:
        await call.message.edit_text(updated_car_info, reply_markup=None)

    except Exception as e:
        await call.answer("Не удалось обновить сообщение. Попробуйте снова.", show_alert=True)
        print(f"Ошибка при редактировании сообщения: {e}")

    choice_image = car.images[index]

    output_png = generate_test_svg(choice_image, nds)
    output_modified = draw_car_info_on_image(car, output_png)

    media_message_ids = user_media_messages.get(call.from_user.id, [])

    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении: {e}")

    for msg_id in media_message_ids:
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=msg_id)
        except Exception as e:
            print(f"Не удалось удалить сообщение {msg_id}: {e}")

    user_media_messages.pop(call.from_user.id, None)

    # Отправка финального фото
    caption = str(car)

    # Извлекаем цену и добавляем текст НДС
    price_text = car.price if car.price else "Не указана"
    price_with_vat = f"{price_text} P {'с НДС' if nds else 'без НДС'}"
    # Заменяем строку с ценой в caption
    caption_lines = caption.split('\n')
    for i, line in enumerate(caption_lines):
        if line.startswith("Цена:"):
            caption_lines[i] = f"Цена: {price_with_vat}"
            break
    caption = '\n'.join(caption_lines)

    # Обрезаем, если превышает 1000 символов
    if len(caption) > 1000:
        caption = caption[:950] + "..."

    # Отправляем фото
    await call.message.answer_photo(
        photo=InputFile(output_modified, filename="car_info.png"),
        caption=caption
    )

if __name__ == "__main__":
    if not app_settings.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN not found in .env file!")

    print("Bot is running...")
    executor.start_polling(dp, skip_updates=True)
