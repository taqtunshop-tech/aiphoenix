# -*- coding: utf-8 -*-
"""
AIPHX-OPERATOR: Text Parser
Извлечение тепловых параметров из русскоязычного текста.

Не hallucinирует: если параметр не найден — ставит None.
Приоритет: прямые числа > формул > приблизительные описания.
"""

import re
import math
from typing import Optional, Tuple, List
from .models import (
    ParsedParameters, MediaType, HeatExchangerType,
    MEDIA_KEYWORDS, UNIT_MULTIPLIERS
)


# ── Паттерны распознавания ───────────────────────────────────────────────────

# Температура: "t1 = 90°C", "температура входа 90 °C", "на входе 90 градусов"
TEMP_PATTERNS = [
    # t1 / t2 / tгоряч / tхолод + = + число
    (r"t\s*1\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"t\s*2\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    (r"t\s*3\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_in"),
    (r"t\s*4\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_out"),
    # горячая сторона: вход/выход
    (r"горяч\w*\s*(?:сторон\w*|поток\w*)?\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"горяч\w*\s*(?:сторон\w*|поток\w*)?\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    (r"高温侧\s* вход\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"高温侧\s* выход\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    (r"нагрев\w*\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"нагрев\w*\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    (r"греющ\w*\s*(?:сред\w*)?\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"греющ\w*\s*(?:сред\w*)?\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    # холодная сторона
    (r"холодн\w*\s*(?:сторон\w*|поток\w*)?\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_in"),
    (r"холодн\w*\s*(?:сторон\w*|поток\w*)?\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_out"),
    (r"охлажд\w*\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_in"),
    (r"охлажд\w*\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_out"),
    (r"охлаждающ\w*\s*(?:сред\w*)?\s*(?:на\s+)?вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_in"),
    (r"охлаждающ\w*\s*(?:сред\w*)?\s*(?:на\s+)?выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_out"),
    # generic: температура входа/выхода
    (r"температур\w*\s*вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"температур\w*\s*выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    # t1 на входе = 90
    (r"t\s*1\s+на\s+вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_in"),
    (r"t\s*2\s+на\s+выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_hot_out"),
    (r"t\s*3\s+на\s+вход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_in"),
    (r"t\s*4\s+на\s+выход\w*\s*[=:]\s*([\d]+[.,]?\d*)", "t_cold_out"),
    # 90°C -> 40°C (горячая -> холодная)
    (r"([\d]+[.,]?\d*)\s*°?\s*[сcC]\s*->\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "pair_hot"),
    # на входе 90°C, нужно охладить до 50°C (compound: hot_in + hot_out)
    (r"на\s+вход\w*\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]\s*,?\s*(?:нужно|надо|требуется)?\s*охлад\w*\s*до\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "pair_hot"),
    # на входе 90°C, нагреть до 120°C (compound: cold_in + cold_out)
    (r"на\s+вход\w*\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]\s*,?\s*(?:нужно|надо|требуется)?\s*нагр\w*\s*до\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "pair_cold"),
    # Медиум: температура (Пар: 120°C, Вода: 10°C)
    (r"пар\w*\s*[:=]\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "media_steam_temp"),
    (r"вода\w*\s*[:=]\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "media_water_temp"),
    (r"масл\w*\s*[:=]\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "media_oil_temp"),
    (r"гликол\w*\s*[:=]\s*([\d]+[.,]?\d*)\s*°?\s*[сcC]", "media_glycol_temp"),
]

# Мощность: "Q = 500 кВт", "мощность 500 кВт", "500квт"
POWER_PATTERNS = [
    (r"(?:Q|мощность|power)\s*[=:]\s*([\d]+[.,]?\d*)\s*(?:квт|kw|квтч)", "power"),
    (r"([\d]+[.,]?\d*)\s*(?:квт|квтч|kw)\b", "power"),
    (r"мощность\s*[=:]\s*([\d]+[.,]?\d*)", "power"),
    (r"([\d]+[.,]?\d*)\s*(?:гкал|гкал/ч)\b", "power_gkal"),
]

# Расход: "G = 15 кг/с", "расход 500 кг/ч", "5000 кг/ч горячей воды"
FLOW_PATTERNS = [
    (r"(?:G\s*1|расход\s*\d*\s*горяч\w*)\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_hot"),
    (r"(?:G\s*2|расход\s*\d*\s*холодн\w*)\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_cold"),
    (r"расход\s*нагрев\w*\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_hot"),
    (r"расход\s*охлажд\w*\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_cold"),
    (r"(?:G|расход)\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_generic"),
    # Производительность: "5000 кг/ч горячей воды", "10 м3/ч"
    (r"производительн\w*\s*[=:]\s*([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)", "flow_hot"),
    (r"([\d]+[.,]?\d*)\s*(кг/с|кг/ч|кг/мин|м3/ч|м3/с|л/ч|л/мин)\s*(?:горяч\w*\s*)?(?:вод\w*|жидк\w*)", "flow_hot"),
]

# Давление: "P = 1.6 МПа", "давление 6 бар"
PRESSURE_PATTERNS = [
    (r"(?:P\s*1|давление\s*\d*\s*горяч\w*)\s*[=:]\s*([\d]+[.,]?\d*)\s*(бар|мпа|атм)", "pressure_hot"),
    (r"(?:P\s*2|давление\s*\d*\s*холодн\w*)\s*[=:]\s*([\d]+[.,]?\d*)\s*(бар|мпа|атм)", "pressure_cold"),
    (r"(?:P|давлен\w*)\s*[=:]\s*([\d]+[.,]?\d*)\s*(бар|мпа|атм)", "pressure_generic"),
]

# Среда: "вода", "гликоль 30%", "масло"
MEDIA_PATTERNS = [
    # горячая
    (r"горяч\w*\s*(?:сторон\w*|поток\w*)?\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_hot_text"),
    (r"греющ\w*\s*(?:сред\w*)?\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_hot_text"),
    (r"нагрев\w*\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_hot_text"),
    # холодная
    (r"холодн\w*\s*(?:сторон\w*|поток\w*)?\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_cold_text"),
    (r"охлажд\w*\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_cold_text"),
    (r"охлаждающ\w*\s*(?:сред\w*)?\s*[:=]?\s*(\w[\w\s]*?)(?:[,;.\n]|на\s+)", "media_cold_text"),
    # generic
    (r"среда\s*[:=]\s*(\w[\w\s]*?)(?:[,;.\n])", "media_generic_text"),
]

# Тип теплообменника
HX_TYPE_PATTERNS = [
    (r"пластинч\w*\s*разборн\w*", HeatExchangerType.PLATE_DISMANTLED),
    (r"пластинч\w*\s*паян\w*", HeatExchangerType.PLATE_SOLDERED),
    (r"разборн\w*\s*пластинч\w*", HeatExchangerType.PLATE_DISMANTLED),
    (r"паян\w*\s*пластинч\w*", HeatExchangerType.PLATE_SOLDERED),
    (r"трубчат\w*", HeatExchangerType.SHELL_TUBE),
    (r"кожухотруб\w*", HeatExchangerType.SHELL_TUBE),
]

# Бренды для импортозамещения
BRAND_PATTERNS = [
    (r"(?:аналог|замена|вместо|заменить)\s+(alfa\s*laval|альфа\s*лаваль|alfalaval)", "Alfa Laval"),
    (r"(?:аналог|замена|вместо|заменить)\s+(ridan|ridan|ридан)", "Ридан"),
    (r"(?:аналог|замена|вместо|заменить)\s+(swep|свэп)", "SWEP"),
    (r"(?:аналог|замена|вместо|заменить)\s+(hisaka|хисака)", "Hisaka"),
    (r"(?:аналог|замена|вместо|заменить)\s+(funke|функе)", "Funke"),
    (r"(?:аналог|замена|вместо|заменить)\s+(apv|эйпиви)", "APV"),
    (r"(?:аналог|замена|вместо|заменить)\s+(nord|норд|whitenord)", "Норд"),
    (r"альфа\s*лаваль|alfa\s*laval", "Alfa Laval"),
]

# Модели пластин
PLATE_MODEL_PATTERNS = [
    (r"(APR-?\d+)", "APR"),
    (r"(ТП-?Б-?[\d.]+)", "ТП-Б"),
    (r"(ТП-?\d+)", "ТП"),
]

# Материал
MATERIAL_PATTERNS = [
    (r"(AISI\s*304|08Х18Н10)", "AISI 304"),
    (r"(AISI\s*316|08Х17Н12М2|316\s*[Лл])", "AISI 316"),
    (r"(титан)", "титан"),
]

# Уплотнения
SEAL_PATTERNS = [
    (r"(EPDM|эпдм)", "EPDM"),
    (r"(NBR|нбр|найрит)", "NBR"),
    (r"(Viton|витон|фторкаучук)", "Viton"),
]


# ── Класс-парсер ──────────────────────────────────────────────────────────────

class TextParser:
    """
    Парсер текста заявки на теплообменник.
    Извлекает параметры без hallucinations — только найденное.
    """

    def parse(self, text: str) -> ParsedParameters:
        """Разобрать текст и вернуть ParsedParameters."""
        params = ParsedParameters()
        text_lower = text.lower()

        # Температуры
        self._extract_temperatures(text, text_lower, params)

        # Мощность
        self._extract_power(text, text_lower, params)

        # Расходы
        self._extract_flows(text, text_lower, params)

        # Давление
        self._extract_pressure(text, text_lower, params)

        # Среды
        self._extract_media(text, text_lower, params)

        # Тип теплообменника
        self._extract_hx_type(text, text_lower, params)

        # Бренд-замена
        self._extract_brand_replace(text, text_lower, params)

        # Модели пластин
        self._extract_plate_models(text, params)

        # Материал и уплотнения
        self._extract_material_and_seal(text, text_lower, params)

        # Свободный текст
        params.free_text = text

        return params

    def _parse_number(self, s: str) -> Optional[float]:
        """Парсинг числа с запятой/точкой."""
        if not s:
            return None
        s = s.replace(",", ".").replace(" ", "").strip()
        try:
            return float(s)
        except ValueError:
            return None

    def _extract_temperatures(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение температур."""
        for pattern, field_name in TEMP_PATTERNS:
            if field_name in ("pair_hot", "pair_cold"):
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    v1 = self._parse_number(m.group(1))
                    v2 = self._parse_number(m.group(2))
                    if v1 and v2:
                        if field_name == "pair_hot":
                            params.t_hot_in = v1
                            params.t_hot_out = v2
                            params.notes.append(f"Температура парная: {v1}°C -> {v2}°C")
                        else:
                            params.t_cold_in = v1
                            params.t_cold_out = v2
                            params.notes.append(f"Температура парная: {v1}°C -> {v2}°C")
                continue

            if field_name.startswith("media_"):
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    val = self._parse_number(m.group(1))
                    if val is not None:
                        # Медиум: температура — определяем t_in для конкретного媒体
                        if field_name == "media_steam_temp":
                            params.t_hot_in = val
                            params.notes.append(f"Пар температура: {val}°C")
                        elif field_name == "media_water_temp":
                            # Если холодная среда не определена — это холодная вода
                            if params.t_cold_in is None:
                                params.t_cold_in = val
                                params.notes.append(f"Вода (холодная) температура: {val}°C")
                            else:
                                params.t_hot_in = val
                                params.notes.append(f"Вода (горячая) температура: {val}°C")
                        elif field_name == "media_oil_temp":
                            params.t_hot_in = val
                            params.notes.append(f"Масло температура: {val}°C")
                        elif field_name == "media_glycol_temp":
                            params.t_cold_in = val
                            params.notes.append(f"Гликоль температура: {val}°C")
                continue

            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = self._parse_number(m.group(1))
                if val is not None:
                    setattr(params, field_name, val)

    def _extract_power(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение мощности."""
        for pattern, ptype in POWER_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                if ptype == "power":
                    val = self._parse_number(m.group(1))
                    if val is not None:
                        params.power_kw = val
                        params.power_raw = m.group(0)
                elif ptype == "power_gkal":
                    val = self._parse_number(m.group(1))
                    if val is not None:
                        params.power_kw = round(val * 1.163, 2)
                        params.power_raw = m.group(0)
                break

    def _extract_flows(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение расходов."""
        for pattern, ftype in FLOW_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = self._parse_number(m.group(1))
                unit = m.group(2).lower()
                mult = UNIT_MULTIPLIERS.get(unit, 1.0)
                flow = val * mult if val else None

                if ftype == "flow_hot":
                    params.flow_hot = flow
                    params.flow_hot_raw = m.group(0)
                elif ftype == "flow_cold":
                    params.flow_cold = flow
                    params.flow_cold_raw = m.group(0)
                elif ftype == "flow_generic":
                    params.flow_hot = flow
                    params.flow_hot_raw = m.group(0)
                break

    def _extract_pressure(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение давления."""
        for pattern, ptype in PRESSURE_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = self._parse_number(m.group(1))
                unit = m.group(2).lower()
                mult = UNIT_MULTIPLIERS.get(unit, 1.0)
                pressure = val * mult if val else None

                if ptype == "pressure_hot":
                    params.pressure_hot = pressure
                elif ptype == "pressure_cold":
                    params.pressure_cold = pressure
                elif ptype == "pressure_generic":
                    params.pressure_hot = pressure
                    params.pressure_cold = pressure
                params.pressure_raw = m.group(0)
                break

    def _extract_media(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение рабочих сред."""
        for media_type, keywords in MEDIA_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    if params.media_hot == MediaType.UNKNOWN:
                        params.media_hot = media_type
                        params.media_hot_raw = kw
                    elif params.media_cold == MediaType.UNKNOWN:
                        params.media_cold = media_type
                        params.media_cold_raw = kw
                    break

    def _extract_hx_type(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение типа теплообменника."""
        for pattern, hx_type in HX_TYPE_PATTERNS:
            if re.search(pattern, text_lower):
                params.hx_type = hx_type
                break

    def _extract_brand_replace(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение бренда для импортозамещения."""
        for pattern, brand in BRAND_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                params.brand_replace = brand
                params.brand_replace_raw = m.group(0)
                break

    def _extract_plate_models(self, text: str, params: ParsedParameters):
        """Извлечение моделей пластин."""
        for pattern, prefix in PLATE_MODEL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                params.plate_models_mentioned.append(m.upper())

    def _extract_material_and_seal(self, text: str, text_lower: str, params: ParsedParameters):
        """Извлечение материала и типа уплотнений."""
        for pattern, material in MATERIAL_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                params.material = material
                break

        for pattern, seal in SEAL_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                params.seal_type = seal
                break
