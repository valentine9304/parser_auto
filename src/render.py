import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from dataclasses import dataclass
import cairosvg
import base64
import re
from typing import Optional

from src.schemas import Car


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"


def generate_test_svg(choice_image, nds: bool = True, template_path: str = "static/template.svg", output_png: str = "test_input.png"):
    try:

        if not nds:
            template_path = "static/template_without_nds.svg"

        with open(template_path, 'r', encoding='utf-8') as file:
            svg_content = file.read()

        response = requests.get(choice_image)
        response.raise_for_status()
        image_data = response.content

        image_data_url = f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"

        matches = list(re.finditer(r'xlink:href="[^"]*"', svg_content))

        if len(matches) >= 2:
            second = matches[14]
            start, end = second.span()
            svg_content = svg_content[:start] + f'xlink:href="{image_data_url}"' + svg_content[end:]

        output_png = BytesIO()
        cairosvg.svg2png(bytestring=svg_content.encode('utf-8'), write_to=output_png)
        output_png.seek(0)  # Перемещаем указатель в начало потока
        print("PNG создан в памяти")

        return output_png

    except Exception as e:
        print(f"Ошибка при обработке SVG: {e}")
        return None, None


def draw_multiline_text(draw, text, position, font, fill, max_width, line_spacing=20):
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    x, y = position
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        line_height = draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1]
        y += line_height + line_spacing


def draw_car_info_on_image(car: Car, output_png: BytesIO):
    output_png.seek(0)  # Убедимся, что указатель в начале
    img = Image.open(output_png).convert("RGBA")
    draw = ImageDraw.Draw(img)

    draw_multiline_text(
        draw=draw,
        text=car.name,
        position=(205, 570),
        font=ImageFont.truetype("static/Montserrat-Bold.ttf", 50),
        fill="white",
        max_width=700  # например, ширина блока в пикселях
        )
    draw.text((500, 735), car.price + " P", font=ImageFont.truetype("static/horizon.otf", 40), fill="black")
    draw.text((730, 440), car.year, font=ImageFont.truetype("static/horizon.otf", 35), fill="black")
    draw.text((361, 905), car.engine, font=ImageFont.truetype("static/Montserrat-BoldItalic.ttf", 30), fill="white")
    draw.text((361, 980), car.mileage, font=ImageFont.truetype("static/Montserrat-BoldItalic.ttf", 30), fill="white")
    draw.text((361, 1065), car.drive, font=ImageFont.truetype("static/Montserrat-BoldItalic.ttf", 30), fill="white")
    draw.text((361, 1145), car.color, font=ImageFont.truetype("static/Montserrat-BoldItalic.ttf", 30), fill="white")

    output_modified = BytesIO()
    img.save(output_modified, format="PNG")
    output_modified.seek(0)  # Перемещаем указатель в начало
    return output_modified
