"""Parser for Drom.ru car data."""

from typing import Optional, Dict, List

from bs4 import BeautifulSoup, Tag
from settings import app_settings
from src.schemas import Car
from utils.parser_utils import (
    BaseParser,
    ParsingError,
    extract_text,
    get_html_with_selenium,
)

# Константы для парсинга
CAR_ATTRIBUTES = {
    "Двигатель": "engine",
    "Мощность": "engine_power",
    "Пробег": "mileage",
    "Цвет": "color",
    "Коробка передач": "transmission",
    "Привод": "drive",
}


class DromParser(BaseParser):
    """Parser implementation for Drom.ru."""

    def clean_price(self, text: str) -> str:
        """Clean price string by removing non-numeric characters."""
        return text.replace("&nbsp;", " ").replace("руб", "").strip()

    def _parse_title(self, soup: BeautifulSoup) -> tuple[str, str, str]:
        """Parse car title, year and price from meta tag or fallback to h1."""
        meta_tag = soup.find("meta", property="og:title")

        if meta_tag:
            title = meta_tag.get("content", "")
            parts = title.split(",")
            # car_name = parts[0].replace("Продажа", "").strip().rsplit(" ", 1)[0]
            car_name = extract_text(soup.find("h1")).split(",")[0].replace("Продажа", "").strip()
            car_year = (
                parts[0].rsplit(" ", 1)[1] if len(parts[0].rsplit(" ", 1)) > 1 else ""
            )
            price = self.clean_price(parts[1].strip()) if len(parts) > 1 else ""
        else:
            car_name = extract_text(soup.find("h1"))
            car_year = ""
            price = ""

        return car_name, car_year, price

    def _parse_car_attributes(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Parse car attributes from table."""
        table = soup.find("table")
        if not table:
            return {}

        car_data = {"engine": ""}
        for row in table.find_all("tr"):
            header = row.find("th")
            value = row.find("td")

            if header and value:
                key = extract_text(header)
                val = (
                    extract_text(value)
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

    def _parse_images(self, soup: BeautifulSoup) -> List[str]:
        """Parse car image URLs."""
        image_divs = soup.find(
            "div", {"data-ftid": "bull-page_bull-gallery_thumbnails"}
        )
        if not image_divs:
            return []

        image_urls = []
        for link in image_divs.find_all("a", limit=3):
            href = link.get("href", "")
            if href:
                image_urls.append(f"https:{href}" if href.startswith("//") else href)

        return image_urls

    def parse_content(self, url: str, content: bytes) -> Car:
        """Parse HTML content and create Car object."""
        soup = BeautifulSoup(content, "html.parser")

        car_name, car_year, car_price = self._parse_title(soup)
        car_data = self._parse_car_attributes(soup)
        image_urls = self._parse_images(soup)

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

    def parse(self, url: Optional[str] = None) -> Optional[Car]:
        """Parse car data from given URL."""
        url = url or app_settings.URL
        html_content = get_html_with_selenium(url, cookie_domain=".drom.ru")

        if not html_content:
            raise ParsingError("Не удалось получить содержимое страницы")

        if "С вашего IP-адреса" in html_content.lower():
            raise ParsingError("С IP много запросов")

        return self.parse_content(url, html_content.encode("utf-8"))
