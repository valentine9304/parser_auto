"""Shared utilities for web parsing."""

import random
import time
from typing import Optional, Dict
from urllib.parse import urlencode
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from settings import app_settings
from src.schemas import Car


class ParsingError(Exception):
    """Custom exception for parsing errors."""

    pass


def extract_text(
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


def get_html_with_selenium(
    url: str, params: Optional[Dict] = None, cookie_domain: str = ".auto.ru"
) -> Optional[str]:
    """Get HTML content using Selenium."""
    try:
        with get_selenium_driver() as driver:
            full_url = url
            # if params:
            #     full_url += (
            #         f"?{urlencode(params)}"
            #         if "?" not in url
            #         else f"&{urlencode(params)}"
                # )

            full_url = url
            if params:
                full_url += "?" if "?" not in full_url else "&"
                full_url += "&".join([f"{k}={v}" for k, v in params.items()])

            if app_settings.COOKIE:
                for cookie_str in app_settings.COOKIE.split(";"):
                    if "=" in cookie_str:
                        name, value = cookie_str.strip().split("=", 1)
                        driver.add_cookie(
                            {"name": name, "value": value, "domain": cookie_domain}
                        )

            driver.get(full_url)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(random.uniform(1, 3))
            return driver.page_source

    except Exception as exc:
        print(f"Selenium error: {exc}")
        return None


class BaseParser(ABC):
    """Abstract base class for car parsers."""

    @abstractmethod
    def parse(self, url: Optional[str] = None) -> Optional[Car]:
        """Parse car data from the given URL."""
        pass

    @abstractmethod
    def parse_content(self, url: str, content: bytes) -> Car:
        """Parse HTML content and return a Car object."""
        pass
