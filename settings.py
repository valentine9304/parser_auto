import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    CSV_FOLDER_NAME: str = "csv_files"
    URL: str = os.getenv("URL")
    ALLOWED_USER_IDS: set = set(int(id) for id in os.getenv("ALLOWED_USER_IDS", "").split(",") if id)
    COOKIE: str = os.getenv("COOKIE")
    HEADERS: dict[str, str] = {
        "user-agent": os.getenv("USER_AGENT"),
        "accept": os.getenv("ACCEPT"),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "accept-encoding": "gzip, deflate, br, zstd",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="101", "Opera";v="87"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "ec-fetch-mode": "no-cors",
        "Cookie": COOKIE,
    }
    USE_SELENIUM: bool = os.getenv("USE_SELENIUM")
    USE_SELENIUM_IN_BACKGROUND: bool = os.getenv("USE_SELENIUM_IN_BACKGROUND")
    TELEGRAM_TOKEN: bool = os.getenv("TELEGRAM_TOKEN")


app_settings = Settings()
