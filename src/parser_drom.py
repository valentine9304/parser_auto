"""Parse and process car data from the server."""

import random
import time
from typing import List, Optional, Dict
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
CAR_ATTRIBUTES = {
    "Двигатель": "engine",
    "Мощность": "engine_power",
    "Пробег": "mileage",
    "Цвет": "color",
    "Коробка передач": "transmission",
    "Привод": "drive",
}


class ParsingError(Exception):
    """Custom exception for parsing errors."""

    pass


def _extract_text(element: Optional[Tag], default: str = "") -> str:
    """Extract and clean text from BeautifulSoup element."""
    return element.get_text().strip() if element else default


def clean_price(text: str) -> str:
    """Clean price string by removing non-numeric characters."""
    return text.replace("&nbsp;", " ").replace("руб", "").strip()


def _parse_title(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Parse car title, year and price from meta tag or fallback to h1."""
    meta_tag = soup.find("meta", property="og:title")

    if meta_tag:
        title = meta_tag.get("content", "")
        parts = title.split(",")
        car_name = parts[0].replace("Продажа", "").strip().rsplit(" ", 1)[0]
        car_year = (
            parts[0].rsplit(" ", 1)[1] if len(parts[0].rsplit(" ", 1)) > 1 else ""
        )
        price = clean_price(parts[1].strip()) if len(parts) > 1 else ""
    else:
        car_name = _extract_text(soup.find(strings.H1_TAG))
        car_year = ""
        price = ""

    return car_name, car_year, price


def _parse_car_attributes(soup: BeautifulSoup) -> Dict[str, str]:
    """Parse car attributes from table."""
    table = soup.find("table")
    if not table:
        return {}

    car_data = {"engine": ""}
    for row in table.find_all("tr"):
        header = row.find("th")
        value = row.find("td")

        if header and value:
            key = _extract_text(header)
            val = (
                _extract_text(value)
                .replace(",\xa0налог", "")
                .replace("\xa0", " ")
                .strip()
            )

            if key in CAR_ATTRIBUTES:
                if key == "Мощность" and car_data["engine"]:
                    car_data["engine"] += f", {val}"
                elif key == "Двигатель":
                    car_data["engine"] = val
                else:
                    car_data[CAR_ATTRIBUTES[key]] = val

    return car_data


def _parse_images(soup: BeautifulSoup) -> List[str]:
    """Parse car images URLs."""
    image_divs = soup.find("div", {"data-ftid": "bull-page_bull-gallery_thumbnails"})
    if not image_divs:
        return []

    image_urls = []
    for link in image_divs.find_all("a", limit=3):
        href = link.get("href", "")
        if href:
            image_urls.append(f"https:{href}" if href.startswith("//") else href)

    return image_urls


def parse_content(url: str, content: bytes) -> Car:
    """Parse HTML content and create Car object."""
    soup = BeautifulSoup(content, "html.parser")
    car_name, car_year, car_price = _parse_title(soup)
    car_data = _parse_car_attributes(soup)
    image_urls = _parse_images(soup)

    return Car(
        name=car_name,
        price=car_price,
        year=car_year,
        mileage=car_data.get("mileage", ""),
        engine=car_data.get("engine", ""),
        transmission=car_data.get("transmission", ""),
        color=car_data.get("color", ""),
        drive=car_data.get("drive", ""),
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


def parse_response_drom(url: Optional[str] = None) -> Optional[Car]:
    """Parse car data from given URL."""
    url = url or app_settings.URL
    html_content = get_html_with_selenium(url)

    if not html_content:
        raise ParsingError("Не удалось получить содержимое страницы")

    return parse_content(url, html_content.encode("utf-8"))
