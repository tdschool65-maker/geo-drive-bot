import math


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Вычисляет ортодромическое расстояние (расстояние по дуге большого круга)
    между двумя географическими точками на Земле с использованием формулы Хаверсина.

    Параметры:
        lat1 (float): Широта первой точки в градусах (например, 55.7558).
        lon1 (float): Долгота первой точки в градусах (например, 37.6173).
        lat2 (float): Широта второй точки в градусах.
        lon2 (float): Долгота второй точки в градусах.

    Возвращает:
        float: Расстояние между точками в метрах.
    """
    # Средний радиус Земли в метрах (согласно Международному геодезическому союзу)
    EARTH_RADIUS_METERS: float = 6371000.0

    # Перевод градусов в радианы
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Применение формулы Хаверсина:
    # a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )

    # Защита от погрешностей вычислений с плавающей точкой (значение 'a' не должно превышать 1.0)
    a = min(1.0, max(0.0, a))

    # Вычисление углового расстояния в радианах:
    # c = 2 * atan2(√a, √(1−a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    # Итоговое линейное расстояние: длина дуги = R * c
    distance_meters = EARTH_RADIUS_METERS * c

    return distance_meters


def format_distance(distance_meters: float) -> str:
    """
    Форматирует расстояние в метрах в удобную для чтения строку (метры или километры).
    Например: 350 м или 2.4 км.
    """
    if distance_meters < 1000:
        return f"{int(round(distance_meters))} м"
    return f"{distance_meters / 1000.0:.1f} км"
