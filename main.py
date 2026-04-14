"""Main Telegram bot logic for parsing car data and generating offers."""

from typing import List, Dict

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    InputFile,
)


from settings import app_settings
from src.parser import AutoRuParser
from src.parser_drom import DromParser
from utils.parser_utils import ParsingError
from src.render import generate_test_svg, draw_car_info_on_image
from src.schemas import Car


bot = Bot(
    token=app_settings.TELEGRAM_TOKEN,
    proxy=app_settings.PROXY_URL
)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_cars: Dict[int, Car] = {}
user_media_messages: Dict[int, List[int]] = {}


def create_photo_keyboard(image_count: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with photo selection buttons."""
    keyboard = InlineKeyboardMarkup(row_width=3)
    for i in range(min(3, image_count)):
        keyboard.insert(
            InlineKeyboardButton(text=f"Фото {i+1}", callback_data=f"photo_{i}")
        )
    return keyboard


def create_vat_keyboard(index: int) -> InlineKeyboardMarkup:
    """Create inline keyboard for VAT selection."""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="с НДС", callback_data=f"vat_yes_{index}"),
        InlineKeyboardButton(text="без НДС", callback_data=f"vat_no_{index}"),
        InlineKeyboardButton(text="Назад к фото", callback_data="back_to_photos"),
    )
    return keyboard


async def check_user_access(user_id: int, message: types.Message) -> bool:
    """Check if user is allowed to use the bot."""
    try:
        if user_id not in app_settings.ALLOWED_USER_IDS:
            await message.reply("Извините, доступ к боту ограничен.")
            return False
    except TypeError as e:
        print(
            f"Error checking user ID: {e}, ALLOWED_USER_IDS: {app_settings.ALLOWED_USER_IDS}"
        )
        await message.reply("Ошибка конфигурации бота. Обратитесь к администратору.")
        return False
    return True


async def send_car_media(car: Car, chat_id: int) -> List[int]:
    """Send car images as a media group."""
    media = [types.InputMediaPhoto(media=img_url) for img_url in car.images[:3]]
    sent_messages = await bot.send_media_group(chat_id=chat_id, media=media)
    return [msg.message_id for msg in sent_messages]


async def format_car_info(
    car: Car, additional_text: str = "", max_length: int = 4096
) -> str:
    """Format car information with additional text, respecting max length."""
    car_info = str(car)
    full_text = f"{car_info}{additional_text}"
    if len(full_text) > max_length:
        return f"{car_info[:max_length - len(additional_text) - 3]}...{additional_text}"
    return full_text


async def delete_user_messages(
    chat_id: int, message_id: int, media_message_ids: List[int]
) -> None:
    """Delete user message and media messages."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"Failed to delete user message {message_id}: {e}")

    for msg_id in media_message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            print(f"Failed to delete media message {msg_id}: {e}")


async def process_car_url(message: types.Message, url: str, parse_func) -> None:
    """Process car URL and send car details with photos."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await check_user_access(user_id, message):
        return

    print(f"Processing URL by USER: {user_id} : {url}")

    try:
        car = parse_func(url)
        if not car or not car.images:
            await message.reply(
                "Не удалось извлечь данные. Проверьте ссылку или попробуйте позже."
            )
            return
        print(f"HTML content was parsed: {url}")
        user_cars[user_id] = car
        media_message_ids = await send_car_media(car, chat_id)
        user_media_messages[user_id] = media_message_ids

        additional_text = (
            "\n📸 Выберите фото для коммерческого предложения и укажите, нужен ли НДС.\n"
            "На основе выбранного изображения будет сформировано персонализированное предложение."
        )
        full_car_info = await format_car_info(car, additional_text)

        await delete_user_messages(chat_id, message.message_id, [])
        await message.answer(
            full_car_info, reply_markup=create_photo_keyboard(len(car.images))
        )
        print(f"Answer message was Sent to USER: {user_id}")

    except ParsingError as e:
        print(f"Parsing error for URL {url}: {e}")
        await message.reply(f"Ошибка парсинга: {str(e)}")
    except Exception as e:
        print(f"Unexpected error processing URL {url}: {e}")
        await message.reply("Произошла ошибка. Попробуйте позже.")


@dp.message_handler(commands=["start"])
async def start(message: types.Message) -> None:
    """Handle /start command."""
    await message.reply(
        "Привет! Отправь ссылку на объявление с Auto.ru или Drom.ru, чтобы получить информацию об автомобиле."
    )


def setup_handlers(dp: Dispatcher) -> None:
    """Register message handlers for the bot."""
    # Словарь для маппинга доменов на парсеры
    PARSERS = {
        "https://auto.ru": AutoRuParser,
        "https://auto.drom.ru": DromParser,
    }

    @dp.message_handler(
        lambda message: any(
            message.text.startswith(domain) for domain in PARSERS.keys()
        )
    )
    async def handle_car_url(message: types.Message) -> None:
        """Handle car URLs for supported websites (Auto.ru, Drom.ru)."""
        url = message.text.strip()

        # Находим подходящий парсер
        for domain, parser_class in PARSERS.items():
            if url.startswith(domain):
                parser = parser_class()
                await process_car_url(message, url, parser.parse)
                return

        # Если домен не поддерживается
        await message.answer(
            "Ошибка: неподдерживаемый сайт. Используйте ссылки на auto.ru или auto.drom.ru."
        )


@dp.callback_query_handler(lambda call: call.data.startswith("photo_"))
async def handle_photo_click(call: CallbackQuery) -> None:
    """Handle photo selection callback."""
    user_id = call.from_user.id
    index = int(call.data.split("_")[1])
    car = user_cars.get(user_id)

    if not car or index >= len(car.images):
        await call.answer("Фотография недоступна", show_alert=True)
        return

    await call.message.edit_reply_markup(reply_markup=create_vat_keyboard(index))
    await call.answer(f"Выбрано Фото {index+1}")


@dp.callback_query_handler(lambda call: call.data == "back_to_photos")
async def handle_back_to_photos(call: CallbackQuery) -> None:
    """Handle back to photos callback."""
    user_id = call.from_user.id
    car = user_cars.get(user_id)

    if not car:
        await call.answer("Данные об автомобиле недоступны", show_alert=True)
        return

    await call.message.edit_reply_markup(
        reply_markup=create_photo_keyboard(len(car.images))
    )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith("vat_"))
async def handle_vat_click(call: CallbackQuery) -> None:
    """Handle VAT selection callback."""
    user_id = call.from_user.id
    vat_choice, index = call.data.split("_")[1], int(call.data.split("_")[2])
    car = user_cars.get(user_id)

    if not car:
        await call.answer("Данные об автомобиле недоступны", show_alert=True)
        return

    nds = vat_choice == "yes"

    if nds:
        try:
            cleaned_price = "".join(c for c in car.price if c.isdigit())
            new_price_int = int(cleaned_price) * 1.22
            car.price = "{:,.0f}".format(new_price_int).replace(",", " ")
        except (ValueError, TypeError) as e:
            print(f"Error calculating VAT for price {car.price}: {e}")
            await call.answer("Ошибка: Неверный формат цены", show_alert=True)
            return

    chat_id = call.message.chat.id
    message_id = call.message.message_id
    media_message_ids = user_media_messages.get(user_id, [])

    # Format car info with VAT
    price_text = f"{car.price} ₽ {'с НДС' if nds else 'без НДС'}"
    caption = str(car)
    caption_lines = caption.split("\n")
    for i, line in enumerate(caption_lines):
        if line.startswith("Цена:"):
            caption_lines[i] = f"Цена: {price_text}"
            break
    caption = "\n".join(caption_lines)
    if len(caption) > 1000:
        caption = caption[:950] + "..."

    # Generate offer image
    try:
        choice_image = car.images[index]
        output_png = generate_test_svg(choice_image, nds)
        output_modified = draw_car_info_on_image(car, output_png)

        await delete_user_messages(chat_id, message_id, media_message_ids)
        user_media_messages.pop(user_id, None)

        await call.answer()

        await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(output_modified, filename="car_offer.png"),
            caption=caption,
        )

        await bot.send_message(
            chat_id=chat_id,
            text=f"URL: {car.url}"
        )

    except Exception as e:
        print(f"Error generating offer for user {user_id}: {e}")
        await call.answer(
            "Ошибка при создании предложения. Попробуйте снова.", show_alert=True
        )


if __name__ == "__main__":
    if not app_settings.TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN not found in .env file!")

    print("Bot is starting...", flush=True)
    setup_handlers(dp)  # Регистрируем обработчики
    executor.start_polling(dp, skip_updates=True)
