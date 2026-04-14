"""Project schemas."""

from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Car:
    id: int = None
    name: str = ""
    price: Optional[str] = 0
    year: str = "Новый год"
    mileage: str = "Новый автомобиль"
    engine: str = "Новый двигатель"
    transmission: str = "Новая трансмиссия"
    color: str = "Новый цвет"
    drive: str = "Новый привод"
    images: List[str] = field(default_factory=list)
    url: str = " Нет адресса"

    def __post_init__(self):
        """Автоматически устанавливает 'Новый автомобиль', если пробег меньше 500."""
        try:
            # Пробуем преобразовать mileage в число, убирая возможные пробелы и нечисловые символы
            mileage_value = int(self.mileage.replace('\xa0', '').replace(' ', '').replace('км', ''))
            if mileage_value < 500:
                self.mileage = "Новый автомобиль"
        except (ValueError, AttributeError):
            # Если mileage не удалось преобразовать в число, оставляем как есть
            pass

    def __str__(self) -> str:
        """Возвращает красиво отформатированное строковое представление автомобиля."""
        clean = lambda s: str(s).replace('\xa0', ' ').strip() if s else 'Не указано'
        return (
            # "🚗 Информация об автомобиле 🚗\n"
            # f"ID: {clean(self.id) if self.id is not None else 'Не указан'}\n"
            f"{clean(self.name) or 'Не указано'}\n"
            f"Цена: {clean(self.price) + ' P' if self.price else 'Не указана'}\n"
            f"Год: {clean(self.year)}\n"
            f"Пробег: {clean(self.mileage)}\n"
            f"Двигатель: {clean(self.engine)}\n"
            f"Трансмиссия: {clean(self.transmission)}\n"
            f"Цвет: {clean(self.color)}\n"
            f"Привод: {clean(self.drive)}\n"
            # f"URL: {clean(self.url)}\n\n"
        )

    def __repr__(self) -> str:
        """Возвращает техническое, но читаемое представление автомобиля для списков и отладки."""
        return self.__str__()
