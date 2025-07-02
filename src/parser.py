"""Parser for Auto.ru car data."""

import re
from typing import Optional, List

from bs4 import BeautifulSoup, Tag
from settings import app_settings
from src import strings
from src.schemas import Car
from utils.parser_utils import (
    BaseParser,
    ParsingError,
    extract_text,
    get_html_with_selenium,
)

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


class AutoRuParser(BaseParser):
    """Parser implementation for Auto.ru."""

    def _extract_attribute(
        self,
        container: Tag,
        tag: str,
        class_name: str,
        default: str = "Не указано",
        second_text: bool = False,
    ) -> str:
        """Extract attribute from a nested div structure."""

        content = container.find(tag, class_name)
        print(content)
        if not content:
            return default

        if second_text:
            return extract_text(content, default, second_text=True)

        inner_elements = content.find_all(strings.DIV_TAG, strings.ROW_CLASS)
        return extract_text(
            inner_elements[1] if len(inner_elements) >= 2 else None, default
        )

    def _parse_car_name(self, name_content: Optional[Tag]) -> str:
        """Parse car name, removing year and comma."""
        raw_name = extract_text(name_content)
        return raw_name.split(",", 1)[0].strip() if "," in raw_name else raw_name

    def _parse_price(self, price_content: Optional[Tag]) -> str:
        """Parse price, handling NBSP and RUR symbols."""
        raw_price = extract_text(price_content).split(strings.RUR)[0]
        return raw_price.replace("\xa0", " ").strip()

    def _parse_images(self, soup: BeautifulSoup) -> List[str]:
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
                        f"https:{second_url}"
                        if second_url.startswith("//")
                        else second_url
                    )
                    continue

            span = div.find("span", class_="ImageGalleryDesktop__image_cover")
            if span and "background-image" in span.get("style", ""):
                match = re.search(r"url\((//[^)]+)\)", span["style"])
                if match:
                    image_urls.append(f"https:{match.group(1)}")

        return image_urls

    def parse_content(self, url: str, content: bytes) -> Car:
        """Parse HTML content and create Car object."""
        soup = BeautifulSoup(content, "html.parser")
        print(soup)
        # card_body = soup.find(strings.DIV_TAG, class_="CardOfferBody")
        card_body = soup

        if not card_body:
            with open("failed_auto_ru.html", "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))
            raise ParsingError("Card body not found")

        # Parse basic fields
        car_id = extract_text(card_body.find(strings.DIV_TAG, strings.ITEM_ID))
        car_name = self._parse_car_name(
            card_body.find(strings.H1_TAG, strings.ITEM_NAME)
        )

        # Determine if it's a new car
        is_new_car = "new" in url.lower()
        price_class = (
            strings.NEW_ITEM_PRICE_CONTENT if is_new_car else strings.ITEM_PRICE_CONTENT
        )
        price_tag = (
            strings.DIV_TAG if is_new_car else strings.SPAN_TAG
        )

        car_price = self._parse_price(card_body.find(price_tag, price_class))

        if is_new_car:
            car_price = self._parse_price(
                card_body.find(strings.DIV_TAG, strings.NEW_ITEM_PRICE_CONTENT)
            )
            if not car_price:
                car_price = self._parse_price(
                    card_body.find(strings.SPAN_TAG, strings.ITEM_PRICE_CONTENT)
                )
        else:
            car_price = self._parse_price(
                card_body.find(strings.SPAN_TAG, strings.ITEM_PRICE_CONTENT)
            )

        # # Define attribute mappings with custom defaults
        # attributes = {
        #     "year": (strings.ITEM_YEAR, "Новый год"),
        #     "mileage": (strings.ITEM_MILEAGE, "Новый автомобиль"),
        #     "engine": (strings.ITEM_ENGINE, "Новый двигатель"),
        #     "transmission": (strings.ITEM_TRANSMISSION, "Новая трансмиссия"),
        #     "color": (strings.ITEM_COLOR, "Новый цвет"),
        #     "drive": (strings.ITEM_DRIVE, "Новый привод"),
        # }

        # new_attributes = {
        #     "year": (strings.NEW_ITEM_YEAR, "Новый год"),
        #     "mileage": (strings.NEW_ITEM_MILEAGE, "Новый автомобиль"),
        #     "engine": (strings.NEW_ITEM_ENGINE, "Новый двигатель"),
        #     "transmission": (strings.NEW_ITEM_TRANSMISSION, "Новая трансмиссия"),
        #     "color": (strings.NEW_ITEM_COLOR, "Новый цвет"),
        #     "drive": (strings.NEW_ITEM_DRIVE, "Новый привод"),
        # }

        # # Проверяем новая машина или нет, разные страницы для парсинга
        # if "new" in url.lower():
        #     car_data = {
        #                 key: self._extract_attribute(card_body, strings.LI_TAG, attr, default, second_text=True)
        #                 for key, (attr, default) in new_attributes.items()
        #             }
        # else:
        #     car_data = {
        #         key: self._extract_attribute(card_body, strings.LI_TAG, attr, default)
        #         for key, (attr, default) in attributes.items()
        #     }

        #Parse attributes
        car_data = {
            key: self._extract_attribute(
                card_body,
                strings.LI_TAG,
                attrs["new" if is_new_car else "used"],
                attrs["default"],
                second_text=is_new_car,
            )
            for key, attrs in ATTRIBUTE_CLASSES.items()
        }

        image_urls = self._parse_images(soup)

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

    def parse(self, url: Optional[str] = None) -> Optional[Car]:
        """Parse car data from given URL."""
        url = url or app_settings.URL
        html_content = get_html_with_selenium(url, cookie_domain=".auto.ru")
        print(f"HTML content was recieved: {url}")

        if not html_content:
            raise ParsingError("Не удалось получить содержимое страницы")

        if "captcha" in html_content.lower():
            raise ParsingError("Обнаружена капча")

        return self.parse_content(url, html_content.encode("utf-8"))
