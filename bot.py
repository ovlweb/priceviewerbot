import logging
import random
from io import BytesIO
from urllib.parse import urlencode

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedPhoto, InlineQueryResultPhoto, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
)

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "TOKEN"  # <-- ТОКЕН ОТ @BotFather
# ID служебного канала/чата для кэширования картинок (например, -1001234567890)
STORAGE_CHAT_ID = -ID ПРИВАТНОГО ЧАТА  # <-- ЗАМЕНИ НА chat_id СВОЕГО ПРИВАТНОГО КАНАЛА/ГРУППЫ

API_BASE_URL = "https://imggen.send.tg/rates/image"

CRYPTO_LIST = {
    "USDT", "TON", "SOL", "TRX", "GRAM", "BTC", "ETH", "DOGE", "LTC", "NOT",
    "TRUMP", "MELANIA", "PEPE", "WIF", "BONK", "MAJOR", "MY", "DOGS", "MEMHASH",
    "BNB", "HMSTR", "CATI", "USDC"
}

FIAT_LIST = {
    "RUB", "USD", "EUR", "BYN", "UAH", "GBP", "CNY", "KZT", "UZS", "GEL",
    "TRY", "AMD", "THB", "INR", "BRL", "IDR", "AZN", "AED", "PLN", "ILS",
    "KGS", "TJS", "LKR"
}

TIMEFRAMES = {
    "day":   ["day", "d", "день", "д"],
    "week":  ["week", "w", "неделя", "нед", "н"],
    "month": ["month", "m", "месяц", "мес", "м"],
    "year":  ["year", "y", "год", "г"],
}


def normalize_timeframe(raw: str) -> str | None:
    raw = raw.lower()
    for key, aliases in TIMEFRAMES.items():
        if raw in aliases:
            return key
    return None


def timeframe_to_russian(timeframe: str) -> str:
    mapping = {
        "day": "день",
        "week": "неделю",
        "month": "месяц",
        "year": "год",
    }
    return mapping.get(timeframe, timeframe)


def generate_news_block(crypto: str, timeframe: str, percent: str) -> str:
    s = str(percent)
    sign = "+" if s.startswith("+") else "-" if s.startswith("-") else ""
    try:
        value = s.lstrip("+-")
    except Exception:  # noqa: BLE001
        value = s

    period_context = {
        "day": "сегодня",
        "week": "на этой неделе",
        "month": "в этом месяце",
        "year": "в этом году",
    }.get(timeframe, "за период")

    if sign == "+":
        templates = [
            f"{crypto}: цена уверенно растёт {period_context}, участники рынка наращивают позиции.",
            f"Интерес к {crypto} усиливается, инвесторы фиксируют рост около {value}% за период.",
            f"Аналитики отмечают положительный новостной фон и приток ликвидности в {crypto}.",
        ]
    elif sign == "-":
        templates = [
            f"{crypto}: наблюдается снижение {period_context}, часть трейдеров фиксирует убытки.",
            f"Продавцы доминируют, {crypto} теряет около {value}% за период.",
            f"Аналитики предупреждают о повышенной волатильности и возможном продолжении коррекции по {crypto}.",
        ]
    else:
        templates = [
            f"{crypto}: значимых движений {period_context} не зафиксировано, рынок остаётся в боковике.",
            f"Торги по {crypto} проходят спокойно, участники ждут новых драйверов.",
            f"Аналитики отмечают нейтральный баланс спроса и предложения по {crypto}.",
        ]

    news_count = 2 if len(templates) >= 2 else 1
    selected = random.sample(templates, k=news_count)
    joined = "\n".join(f"- {line}" for line in selected)
    return f"Новости:\n{joined}"


def build_caption(crypto: str, fiat: str, rate: str, timeframe: str, percent: str) -> str:
    period_ru = timeframe_to_russian(timeframe)
    s = str(percent)
    sign = "+" if s.startswith("+") else "-" if s.startswith("-") else ""
    try:
        value = s.lstrip("+-")
    except Exception:  # noqa: BLE001
        value = s

    if sign == "+":
        dynamics_line = f"Динамика за период: +{value}%"
    elif sign == "-":
        dynamics_line = f"Динамика за период: -{value}%"
    else:
        dynamics_line = f"Динамика за период: {s}%"

    news_block = generate_news_block(crypto, timeframe, percent)

    return (
        f"Пара: {crypto}/{fiat}\n"
        f"Текущая цена: {rate} {fiat}\n"
        f"Период: {period_ru}\n"
        f"{dynamics_line}\n\n"
        f"{news_block}"
    )


logging.basicConfig(level=logging.INFO)


async def download_image(url: str) -> BytesIO | None:
    """Скачать картинку по URL и вернуть BytesIO или None при ошибке."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        bio = BytesIO(resp.content)
        bio.name = "rate.png"
        return bio
    except Exception as e:  # noqa: BLE001
        logging.exception("Failed to download image: %s", e)
        return None


# ==== ХЕНДЛЕРЫ КОМАНД ====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Привет! Я генерирую картинки с курсом криптовалют на основе API из одного криптокошелька.\n\n"
        "Вот мои типичные команды:\n"
        "/gen <стоимость> <валюта страны> <крипта> <период> <процент> — сгенерировать конкретный курс.\n"
        "/random — случайный курс и новости.\n\n"
        "Примеры:\n"
        "/gen 65000 USD BTC month +12.5\n"
        "/gen 1000 RUB TON day -5\n\n"
        "Доступные криптовалюты: "
        + ", ".join(sorted(CRYPTO_LIST))
        + "\nДоступные фиатные валюты: "
        + ", ".join(sorted(FIAT_LIST))
        + "\nПериоды: day/week/month/year (можно писать по-русски)."
    )
    if update.message:
        await update.message.reply_text(text)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Случайный курс и псевдо-новости."""
    if not update.message:
        return

    crypto = random.choice(sorted(CRYPTO_LIST))
    fiat = random.choice(sorted(FIAT_LIST))
    timeframe = random.choice(["day", "week", "month", "year"])

    # Простейшая генерация цены в зависимости от типа актива
    if crypto in {"BTC", "ETH", "BNB", "TON", "SOL", "LTC"}:
        rate = random.uniform(10, 100_000)
    else:
        rate = random.uniform(0.0001, 500)
    rate_str = f"{rate:.4f}".rstrip("0").rstrip(".")

    delta = random.uniform(-30, 30)
    sign = "+" if delta >= 0 else ""
    percent_str = f"{sign}{delta:.2f}".rstrip("0").rstrip(".")

    params = {
        "base": crypto,
        "quote": fiat,
        "rate": rate_str,
        "percent": percent_str,
        "timeframe": timeframe,
    }
    url = f"{API_BASE_URL}?{urlencode(params)}"

    caption = build_caption(crypto, fiat, rate_str, timeframe, percent_str)

    img = await download_image(url)
    if img is not None:
        await update.message.reply_photo(photo=img, caption=caption)
    else:
        await update.message.reply_photo(photo=url, caption=caption)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик inline-кнопки.

    Формат callback_data: gen|rate|FIAT|CRYPTO|timeframe|percent
    """
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    try:
        parts = data.split("|")
        if len(parts) != 6 or parts[0] != "gen":
            await query.answer("Некорректные данные кнопки", show_alert=True)
            return

        _, rate, fiat, crypto, timeframe, percent = parts

        if crypto not in CRYPTO_LIST or fiat not in FIAT_LIST:
            await query.answer("Валюта не поддерживается", show_alert=True)
            return

        params = {
            "base": crypto,
            "quote": fiat,
            "rate": rate,
            "percent": percent,
            "timeframe": timeframe,
        }
        url = f"{API_BASE_URL}?{urlencode(params)}"

        caption = build_caption(crypto, fiat, rate, timeframe, percent)

        if query.message:
            img = await download_image(url)
            if img is not None:
                await query.message.reply_photo(photo=img, caption=caption)
            else:
                await query.message.reply_photo(photo=url, caption=caption)
        await query.answer()
    except Exception as e:  # noqa: BLE001
        logging.exception("Error in callback handler: %s", e)
        await query.answer("Ошибка при обработке кнопки", show_alert=True)


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка inline-запросов.

    Поддерживаются два режима:
    1) Конкретный курс: "9181 RUB NOT year +1881"
    2) Случайный курс: "random" (или "rand")
    """
    inline_query = update.inline_query
    if not inline_query:
        return

    query_text = (inline_query.query or "").strip()

    # Пустой запрос — ничего не показываем, чтобы не спамить
    if not query_text:
        await inline_query.answer([], cache_time=0, is_personal=True)
        return

    # Если не настроен STORAGE_CHAT_ID, inline-генерация недоступна
    if not STORAGE_CHAT_ID:
        await inline_query.answer([], cache_time=0, is_personal=True)
        return

    # Режим случайного курса через inline: "@бот random"
    lowered = query_text.lower()
    if lowered.startswith("random") or lowered.startswith("rand"):
        try:
            crypto = random.choice(sorted(CRYPTO_LIST))
            fiat = random.choice(sorted(FIAT_LIST))
            timeframe = random.choice(["day", "week", "month", "year"])

            if crypto in {"BTC", "ETH", "BNB", "TON", "SOL", "LTC"}:
                rate = random.uniform(10, 100_000)
            else:
                rate = random.uniform(0.0001, 500)
            rate_str = f"{rate:.4f}".rstrip("0").rstrip(".")

            delta = random.uniform(-30, 30)
            sign = "+" if delta >= 0 else ""
            percent_str = f"{sign}{delta:.2f}".rstrip("0").rstrip(".")

            params = {
                "base": crypto,
                "quote": fiat,
                "rate": rate_str,
                "percent": percent_str,
                "timeframe": timeframe,
            }
            url = f"{API_BASE_URL}?{urlencode(params)}"

            caption = build_caption(crypto, fiat, rate_str, timeframe, percent_str)

            # Скачиваем картинку и загружаем в ЛС, чтобы получить file_id
            img = await download_image(url)
            if img is None:
                await inline_query.answer([], cache_time=0, is_personal=True)
                return

            upload_msg = await context.bot.send_photo(
                chat_id=STORAGE_CHAT_ID,
                photo=img,
                caption=caption,
            )
            if not upload_msg.photo:
                await inline_query.answer([], cache_time=0, is_personal=True)
                return

            file_id = upload_msg.photo[-1].file_id

            # Пытаемся сразу удалить временное сообщение из ЛС
            try:
                await context.bot.delete_message(
                    chat_id=upload_msg.chat_id,
                    message_id=upload_msg.message_id,
                )
            except Exception:  # noqa: BLE001
                pass

            results = [
                InlineQueryResultCachedPhoto(
                    id="rand-1",
                    photo_file_id=file_id,
                    caption=caption,
                )
            ]
            await inline_query.answer(results, cache_time=0, is_personal=True)
        except Exception as e:  # noqa: BLE001
            logging.exception("Error in inline_query_handler random: %s", e)
            await inline_query.answer([], cache_time=0, is_personal=True)
        return

    # Режим конкретного курса: "9181 RUB NOT year +1881"
    parts = query_text.split()
    # Поддержка варианта с префиксом /gen или gen
    if parts and (parts[0].lower().startswith("/gen") or parts[0].lower() == "gen"):
        parts = parts[1:]
    if len(parts) < 5:
        await inline_query.answer([], cache_time=0, is_personal=True)
        return

    try:
        rate_str, fiat_raw, crypto_raw, timeframe_raw, percent_raw = parts[:5]

        # Валидация стоимости
        try:
            float(rate_str)
        except ValueError:
            await inline_query.answer([], cache_time=0, is_personal=True)
            return

        fiat = fiat_raw.upper()
        crypto = crypto_raw.upper()
        if crypto not in CRYPTO_LIST or fiat not in FIAT_LIST:
            await inline_query.answer([], cache_time=0, is_personal=True)
            return

        timeframe = normalize_timeframe(timeframe_raw) or "day"

        percent = percent_raw.replace(",", ".")
        if not (percent.startswith("+") or percent.startswith("-")):
            percent = "+" + percent
        try:
            float(percent)
        except ValueError:
            await inline_query.answer([], cache_time=0, is_personal=True)
            return

        params = {
            "base": crypto,
            "quote": fiat,
            "rate": rate_str,
            "percent": percent,
            "timeframe": timeframe,
        }
        url = f"{API_BASE_URL}?{urlencode(params)}"

        caption = build_caption(crypto, fiat, rate_str, timeframe, percent)

        img = await download_image(url)
        if img is None:
            await inline_query.answer([], cache_time=0, is_personal=True)
            return

        upload_msg = await context.bot.send_photo(
            chat_id=STORAGE_CHAT_ID,
            photo=img,
            caption=caption,
        )
        if not upload_msg.photo:
            await inline_query.answer([], cache_time=0, is_personal=True)
            return

        file_id = upload_msg.photo[-1].file_id

        try:
            await context.bot.delete_message(
                chat_id=upload_msg.chat_id,
                message_id=upload_msg.message_id,
            )
        except Exception:  # noqa: BLE001
            pass

        results = [
            InlineQueryResultCachedPhoto(
                id="rate-1",
                photo_file_id=file_id,
                caption=caption,
            )
        ]

        await inline_query.answer(results, cache_time=0, is_personal=True)
    except Exception as e:  # noqa: BLE001
        logging.exception("Error in inline_query_handler: %s", e)
        await inline_query.answer([], cache_time=0, is_personal=True)


async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/gen <rate> <фиат> <крипта> <period> <percent>

    Пример:
    /gen 65000 USD BTC month +12.5
    """
    args = context.args

    if len(args) != 5:
        text = (
            "Неверный формат.\n"
            "Использование:\n"
            "/gen <стоимость> <фиат> <крипта> <период> <процент>\n"
            "Например:\n"
            "/gen 65000 USD BTC month +12.5"
        )
        if update.message:
            await update.message.reply_text(text)
        return

    rate_str, fiat_raw, crypto_raw, timeframe_raw, percent_raw = args

    # Валидация стоимости
    try:
        float(rate_str)
    except ValueError:
        if update.message:
            await update.message.reply_text(
                "Стоимость должна быть числом (например, 65000 или 0.1234)."
            )
        return

    # Нормализация валют
    fiat = fiat_raw.upper()
    crypto = crypto_raw.upper()
    if crypto not in CRYPTO_LIST:
        if update.message:
            await update.message.reply_text(
                "Неподдерживаемая криптовалюта.\n"
                "Доступные: " + ", ".join(sorted(CRYPTO_LIST))
            )
        return

    if fiat not in FIAT_LIST:
        if update.message:
            await update.message.reply_text(
                "Неподдерживаемая фиатная валюта.\n"
                "Доступные: " + ", ".join(sorted(FIAT_LIST))
            )
        return

    # Нормализация периода
    timeframe = normalize_timeframe(timeframe_raw)
    if timeframe is None:
        if update.message:
            await update.message.reply_text(
                "Неверный период. Используй: day, week, month, year "
                "или их русские аналоги (день, неделя, месяц, год)."
            )
        return

    # Валидация процента
    percent = percent_raw.replace(",", ".")
    if not (percent.startswith("+") or percent.startswith("-")):
        if update.message:
            await update.message.reply_text(
                "Процент должен начинаться с '+' или '-', "
                "например: +12.5 или -3.2"
            )
        return
    try:
        float(percent)
    except ValueError:
        if update.message:
            await update.message.reply_text(
                "Некорректный процент. Пример: +12.5 или -3.2"
            )
        return

    # Формируем URL для API
    params = {
        "base": crypto,
        "quote": fiat,
        "rate": rate_str,
        "percent": percent,
        "timeframe": timeframe,
    }
    url = f"{API_BASE_URL}?{urlencode(params)}"

    caption = build_caption(crypto, fiat, rate_str, timeframe, percent)

    if update.message:
        img = await download_image(url)
        if img is not None:
            await update.message.reply_photo(photo=img, caption=caption)
        else:
            await update.message.reply_photo(photo=url, caption=caption)


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("random", cmd_menu))
    application.add_handler(CommandHandler("gen", cmd_gen))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(InlineQueryHandler(inline_query_handler))

    # Явно указываем все типы апдейтов, чтобы точно получать inline_query
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
