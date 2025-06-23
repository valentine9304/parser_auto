"""Parse and process data from the server."""

import random
import re
import time
from typing import List, Optional

from bs4 import BeautifulSoup, Tag
from requests import Response, get
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from settings import app_settings
from src import strings
from src.schemas import Car


def get_pages_amount(content: bytes) -> int:
    """Calculate number of pages."""
    soup = BeautifulSoup(content, "html.parser")
    target_data = soup.find(strings.SPAN_TAG, class_=strings.TARGET_CLASS)

    if not target_data:
        return 0

    return len(target_data.contents)


def _extract_text(element: Optional[Tag], default: str = "", second_text: bool = False) -> str:
    """Extract text from a BeautifulSoup element, return default if not found.
    
    Args:
        element: BeautifulSoup Tag object or None.
        default: Default value to return if element is None (default is "").
        second_text: If True, return only the second text (e.g., "2024" from "Год выпуска2024").
    
    Returns:
        str: Full text of the element or second text if second_text=True, otherwise default.
    """
    # if not element:
    #     return default

    # if not element:
    #     return default

    # if second_text:
    #     # Извлекаем весь текст
    #     full_text = element.get_text().strip()
    #     # Список известных названий атрибутов
    #     attribute_prefixes = [
    #         "Год выпуска",
    #         "Двигатель",
    #         "Коробка",
    #         "Цвет",
    #         "Привод"
    #     ]
    #     # Проверяем, начинается ли текст с одного из известных префиксов
    #     for prefix in attribute_prefixes:
    #         if full_text.startswith(prefix):
    #             # Извлекаем значение, убирая префикс
    #             return full_text[len(prefix):].strip()
    #     # Если префикс не найден, возвращаем весь текст
    #     return full_text
    # else:
    #     # Возвращаем весь текст, как раньше
    return element.get_text().strip()


def clean_price(text):
    # Извлекаем все цифры, игнорируя пробелы и другие символы
    return text.replace('&nbsp;', ' ').replace('руб', '').strip()
    # return ''.join(filter(str.isdigit, text))

def _extract_attribute(
    container: Tag, 
    tag: str, 
    class_name: str, 
    default: str = "Не указано",
    second_text: bool = False
) -> str:
    """Extract attribute from a nested div structure."""
    if content := container.find(tag, class_name):
        if second_text:
            return _extract_text(content, default, second_text=True)
        else:
            inner_elements = content.find_all(strings.DIV_TAG, strings.ROW_CLASS)
            return _extract_text(inner_elements[1] if len(inner_elements) >= 2 else None, default)
    return default


def _parse_car_name(name_content: Optional[Tag], default: str = "") -> str:
    """Parse car name from text, removing year and comma.
    
    Args:
        name_content: BeautifulSoup Tag object containing the car name.
        default: Default value to return if name_content is None (default is "").
    
    Returns:
        str: Car name without year and comma, or default if not found.
    """
    if not name_content:
        return default

    raw_name = name_content.get_text().strip()
    # Удаляем запятую и всё, что после неё (например, ", 2024")
    name_parts = raw_name.split(",", 1)
    return name_parts[0].strip() if name_parts else default


def _parse_price(price_content: Optional[Tag]) -> int:
    """Parse price from text, handling NBSP and RUR symbols."""
    if not price_content:
        return 0

    raw_price = price_content.get_text().strip().split(strings.RUR)[0]

    try:
        return raw_price
    except ValueError:
        return 0


def parse_content(url, content: bytes) -> List[Car]:
    car_url = url
    soup = BeautifulSoup(content, "html.parser")
    meta_tag = soup.find('meta', property='og:title')

    if meta_tag:
        title = meta_tag.get('content')
        parts = title.split(',')
        car_name = parts[0].replace('Продажа', '').strip().rsplit(' ', 1)[0]
        car_year = parts[0].replace('Продажа', '').strip().rsplit(' ', 1)[1]
        price_str = parts[1].strip()
        car_price = clean_price(price_str)
    else:
        car_name = _extract_text(
            soup.find(strings.H1_TAG)
        )
        car_price = ''

    table = soup.find('table')
    car_data = {}

    # Проходим по строкам таблицы
    for row in table.find_all('tr'):
        # Находим заголовок (th) и значение (td)
        header = row.find('th')
        value = row.find('td')

        if header and value:
            # Извлекаем текст из заголовка и значения
            key = _extract_text(header)
            val = _extract_text(value)

            if key in ['Мощность', 'Пробег']:
                val = val.replace(',\xa0налог', '').replace('\xa0', ' ').strip()

            if key == "Двигатель":
                car_data["engine"] = val
            elif key == "Мощность":
                car_data["engine"] += ", " + val
            elif key == "Пробег":
                car_data["mileage"] = val
            elif key == "Цвет":
                car_data["color"] = val
            elif key == "Коробка передач":
                car_data["transmission"] = val
            elif key == "Привод":
                car_data["drive"] = val

    image_divs = soup.find('div', {'data-ftid': 'bull-page_bull-gallery_thumbnails'})
    image_urls = []

    if image_divs:
        links = image_divs.find_all('a', limit=3)
        for link in links:
            href = link.get('href')
            if href:
                # Если href начинается с "//", добавляем "https:"
                if href.startswith('//'):
                    href = 'https:' + href
                image_urls.append(href)

    car = Car(
        # id=car_id,
        name=car_name,
        price=car_price,
        year=car_year,
        mileage=car_data["mileage"],
        engine=car_data["engine"],
        transmission=car_data["transmission"],
        color=car_data["color"],
        drive=car_data["drive"],
        images=image_urls,
        url=car_url,
    )

    return car


def get_html(url: str, headers: dict, params: dict | None = None) -> Response:
    """Get the response from the server."""
    try:
        return get(url, headers=headers, params=params)
    except Exception as error:
        raise ConnectionError(f"При выполнении запроса произошла ошибка: {error}")


def get_html_with_selenium(url: str, params: dict | None = None) -> str | None:
    """Get HTML content using Selenium for better anti-bot protection bypass."""
    service = Service()
    options = Options()

    if app_settings.USE_SELENIUM_IN_BACKGROUND:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={app_settings.HEADERS['user-agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1920, 1080)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    try:
        full_url = url
        if params:
            full_url += "?" if "?" not in full_url else "&"
            full_url += "&".join([f"{k}={v}" for k, v in params.items()])

        driver.get(full_url)

        if app_settings.COOKIE:
            for cookie_str in app_settings.COOKIE.split(";"):
                if "=" in cookie_str:
                    name, value = cookie_str.strip().split("=", 1)
                    driver.add_cookie(
                        {"name": name, "value": value, "domain": ".auto.ru"}
                    )

        # time.sleep(TIME_TO_ENTER_CAPCHA)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")

        time.sleep(random.uniform(1, 3))

        return driver.page_source

    except Exception as exc:
        print(f"Ошибка при использовании Selenium: {exc}")
        return None

    finally:
        driver.quit()


def parse_response_drom(url: str) -> list[Car] | None:
    """Parse the request."""
    url = url or app_settings.URL

    if app_settings.USE_SELENIUM:
        car = parse_response_with_selenium(url)
    else:
        car = simple_parse_response(url)

    if not car:
        return None

    return car


def simple_parse_response(url: str) -> list[Car] | None:
    html = get_html(url, app_settings.HEADERS)
    if html.status_code != 200:
        print(f"Сайт вернул статус-код {html.status_code}")
        return None

    if "captcha" in html.text.lower():
        print(
            "Обнаружена капча! 🤬 \n"
            "Попробуйте обойти капчу и получить данные при помощи Selenium, "
            "для этого нужно запустить парсер с переменной 'USE_SELENIUM=True'. "
        )
        return None

    cars: list[Car] = []
    pages_amount = get_pages_amount(html.content)
    for page in range(1, pages_amount + 1):
        print(f"Парсим {page} страницу из {pages_amount}...")

        html = get_html(url, app_settings.HEADERS, params={"page": page})
        cars.extend(parse_content(content=html.content))

    return cars


def parse_response_with_selenium(url: str) -> Car | None:
    html_content = get_html_with_selenium(url)

    if not html_content:
        print("Не удалось получить содержимое страницы.")
        return None

    # if "captcha" in html_content.lower():
    #     print("Снова капча! 🤬")
    #     return None

    html_bytes = html_content.encode("utf-8")

    car = parse_content(url, content=html_bytes)

    return car
