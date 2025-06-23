"""Parse and process car data from Auto.ru."""

import random
import re
import time
from typing import Optional, Dict, List
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from settings import app_settings
from src import strings
from src.schemas import Car

# Константы для парсинга
ATTRIBUTE_CLASSES = {
    "year": {
        "used": strings.ITEM_YEAR,
        "new": strings.NEW_ITEM_YEAR,
        "default": "Новый год",
    },
    "mileage": {
        "used": strings.ITEM_MILEAGE,
        "new": strings.NEW_ITEM_MILEAGE,
        "default": "Новый автомобиль",
    },
    "engine": {
        "used": strings.ITEM_ENGINE,
        "new": strings.NEW_ITEM_ENGINE,
        "default": "Новый двигатель",
    },
    "transmission": {
        "used": strings.ITEM_TRANSMISSION,
        "new": strings.NEW_ITEM_TRANSMISSION,
        "default": "Новая трансмиссия",
    },
    "color": {
        "used": strings.ITEM_COLOR,
        "new": strings.NEW_ITEM_COLOR,
        "default": "Новый цвет",
    },
    "drive": {
        "used": strings.ITEM_DRIVE,
        "new": strings.NEW_ITEM_DRIVE,
        "default": "Новый привод",
    },
}


class ParsingError(Exception):
    """Custom exception for parsing errors."""

    pass


def _extract_text(
    element: Optional[Tag], default: str = "", second_text: bool = False
) -> str:
    """Extract and clean text from BeautifulSoup element."""
    if not element:
        return default

    full_text = element.get_text().strip()
    if not second_text:
        return full_text

    attribute_prefixes = ["Год выпуска", "Двигатель", "Коробка", "Цвет", "Привод"]
    for prefix in attribute_prefixes:
        if full_text.startswith(prefix):
            return full_text[len(prefix) :].strip()
    return full_text


def _extract_attribute(
    container: Tag,
    tag: str,
    class_name: str,
    default: str = "Не указано",
    second_text: bool = False,
) -> str:
    """Extract attribute from a nested div structure."""
    content = container.find(tag, class_name)
    if not content:
        return default

    if second_text:
        return _extract_text(content, default, second_text=True)

    inner_elements = content.find_all(strings.DIV_TAG, strings.ROW_CLASS)
    return _extract_text(
        inner_elements[1] if len(inner_elements) >= 2 else None, default
    )


def _parse_car_name(name_content: Optional[Tag]) -> str:
    """Parse car name, removing year and comma."""
    if not name_content:
        return ""

    raw_name = name_content.get_text().strip()
    return raw_name.split(",", 1)[0].strip() if "," in raw_name else raw_name


def _parse_price(price_content: Optional[Tag]) -> str:
    """Parse price, handling NBSP and RUR symbols."""
    if not price_content:
        return ""

    raw_price = price_content.get_text().strip().split(strings.RUR)[0]
    return raw_price.replace("\xa0", " ").strip()


def _parse_images(soup: BeautifulSoup) -> List[str]:
    """Parse car image URLs."""
    image_divs = soup.find_all("div", class_="ImageGalleryDesktop__itemContainer")
    image_urls = []

    for div in image_divs[:3]:
        img = div.find("img", class_="ImageGalleryDesktop__image")
        if img and img.get("srcset"):
            urls = img["srcset"].split(",")
            if len(urls) >= 2:
                second_url = urls[1].strip().split(" ")[0]
                image_urls.append(
                    f"https:{second_url}" if second_url.startswith("//") else second_url
                )
                continue

        span = div.find("span", class_="ImageGalleryDesktop__image_cover")
        if span and "background-image" in span.get("style", ""):
            match = re.search(r"url\((//[^)]+)\)", span["style"])
            if match:
                image_urls.append(f"https:{match.group(1)}")

    return image_urls


def parse_content(url: str, content: bytes) -> Car:
    """Parse HTML content and create Car object."""
    soup = BeautifulSoup(content, "html.parser")
    card_body = soup.find(strings.DIV_TAG, class_="CardOfferBody")
    if not card_body:
        raise ParsingError("Card body not found")

    # Parse basic fields
    car_id = _extract_text(card_body.find(strings.DIV_TAG, strings.ITEM_ID))
    car_name = _parse_car_name(card_body.find(strings.H1_TAG, strings.ITEM_NAME))

    # Determine if it's a new car
    is_new_car = "new" in url.lower()
    price_class = (
        strings.NEW_ITEM_PRICE_CONTENT if is_new_car else strings.ITEM_PRICE_CONTENT
    )
    car_price = _parse_price(card_body.find(strings.SPAN_TAG, price_class))
    if is_new_car and not car_price:
        car_price = _parse_price(
            card_body.find(strings.SPAN_TAG, strings.ITEM_PRICE_CONTENT)
        )

    # Parse attributes
    car_data = {
        key: _extract_attribute(
            card_body,
            strings.LI_TAG,
            attrs["new" if is_new_car else "used"],
            attrs["default"],
            second_text=is_new_car,
        )
        for key, attrs in ATTRIBUTE_CLASSES.items()
    }

    image_urls = _parse_images(soup)

    return Car(
        id=car_id,
        name=car_name,
        price=car_price,
        year=car_data["year"],
        mileage=car_data["mileage"],
        engine=car_data["engine"],
        transmission=car_data["transmission"],
        color=car_data["color"],
        drive=car_data["drive"],
        images=image_urls,
        url=url,
    )


def get_selenium_driver() -> webdriver.Chrome:
    """Initialize and configure Selenium WebDriver."""
    options = Options()
    if app_settings.USE_SELENIUM_IN_BACKGROUND:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={app_settings.HEADERS['user-agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=Service(), options=options)
    driver.set_window_size(1920, 1080)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


def get_html_with_selenium(url: str, params: Optional[Dict] = None) -> Optional[str]:
    """Get HTML content using Selenium."""
    try:
        with get_selenium_driver() as driver:
            full_url = url
            if params:
                full_url += (
                    f"?{urlencode(params)}"
                    if "?" not in url
                    else f"&{urlencode(params)}"
                )

            driver.get(full_url)

            if app_settings.COOKIE:
                for cookie_str in app_settings.COOKIE.split(";"):
                    if "=" in cookie_str:
                        name, value = cookie_str.strip().split("=", 1)
                        driver.add_cookie(
                            {"name": name, "value": value, "domain": ".auto.ru"}
                        )

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(random.uniform(1, 3))

            return driver.page_source

    except Exception as exc:
        print(f"Ошибка при использовании Selenium: {exc}")
        return None


def parse_response(url: Optional[str] = None) -> Optional[Car]:
    """Parse car data from given URL."""
    url = url or app_settings.URL
    html_content = get_html_with_selenium(url)

    if not html_content:
        raise ParsingError("Не удалось получить содержимое страницы")

    if "captcha" in html_content.lower():
        raise ParsingError("Обнаружена капча")

    return parse_content(url, html_content.encode("utf-8"))
