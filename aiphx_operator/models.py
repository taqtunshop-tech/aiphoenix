# -*- coding: utf-8 -*-
"""
AIPHX-OPERATOR: Data Models
Структуры данных для входящих заявок на теплообменники.

Статусы обработки:
  PARSED      — текст распарсен, извлечены параметры
  VALIDATED   — параметры прошли валидацию (все поля на месте)
  INCOMPLETE  — не хватает данных, нужен запрос клиенту
  REJECTED    — некорректные данные / не теплообменник
  ESCALATED   — передано инженеру на ручную обработку
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from datetime import datetime


class RequestStatus(Enum):
    PARSED = "parsed"
    VALIDATED = "validated"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class MediaType(Enum):
    WATER = "water"
    GLYCOL30 = "glycol30"
    GLYCOL50 = "glycol50"
    OIL = "oil"
    STEAM = "steam"
    AIR = "air"
    UNKNOWN = "unknown"


class HeatExchangerType(Enum):
    PLATE_DISMANTLED = "plate_dismantled"
    PLATE_SOLDERED = "plate_soldered"
    SHELL_TUBE = "shell_tube"
    UNKNOWN = "unknown"


# Маппинг русских терминов на MediaType
MEDIA_KEYWORDS = {
    MediaType.WATER: ["вода", "водой", "воде", "воду", "водяная", "водяной",
                      "горячая вода", "холодная вода", "гвс", "хвс",
                      "тёплая вода", "теплая вода", "技术服务 вода"],
    MediaType.GLYCOL30: ["гликоль", "гликолевый", "гликолевая", "антифриз",
                         "этиленгликоль", "пропиленгликоль", "30% гликоль",
                         "гликоль 30", "незамерзающая"],
    MediaType.GLYCOL50: ["гликоль 50", "50% гликоль", "концентрат гликолевый"],
    MediaType.OIL: ["масло", "масла", "масле", "маслённое", "масляное",
                    "масляный", "техническое масло", "масляная",
                    "трансмиссионное", "гидравлическое масло"],
    MediaType.STEAM: ["пар", "пара", "паре", "паровая", "паровой",
                      "конденсат", "перегретый пар", "насыщенный пар"],
    MediaType.AIR: ["воздух", "воздуха", "воздухе", "воздушная", "воздушный",
                    "нагрев воздуха", "охлаждение воздуха"],
}

# Русские единицы измерения
UNIT_MULTIPLIERS = {
    "квт": 1.0, "квтч": 1.0, "kw": 1.0,
    "мвт": 1000.0, "mwt": 1000.0,
    "гц": 1.0, "гкал": 1.163, "гкал/ч": 1.163,
    "кг/с": 1.0, "кг/ч": 1.0 / 3600.0, "кг/мин": 1.0 / 60.0,
    "м3/ч": 0.2778, "м3/с": 1.0, "л/ч": 0.0002778, "л/мин": 0.00001667,
    "бар": 0.1, "мпа": 1.0, "атм": 0.101325,
    "°c": 1.0, "с": 1.0,
}


class RequestStatus(Enum):
    PARSED = "parsed"
    VALIDATED = "validated"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class ParsedParameters:
    """Извлечённые тепловые параметры из заявки."""
    # Температуры, °C
    t_hot_in: Optional[float] = None
    t_hot_out: Optional[float] = None
    t_cold_in: Optional[float] = None
    t_cold_out: Optional[float] = None

    # Расходы
    flow_hot: Optional[float] = None       # кг/с
    flow_cold: Optional[float] = None      # кг/с
    flow_hot_raw: Optional[str] = None     # исходная строка
    flow_cold_raw: Optional[str] = None

    # Мощность
    power_kw: Optional[float] = None
    power_raw: Optional[str] = None

    # Среды
    media_hot: MediaType = MediaType.UNKNOWN
    media_cold: MediaType = MediaType.UNKNOWN
    media_hot_raw: Optional[str] = None
    media_cold_raw: Optional[str] = None

    # Давление
    pressure_hot: Optional[float] = None   # МПа
    pressure_cold: Optional[float] = None
    pressure_raw: Optional[str] = None

    # Тип теплообменника
    hx_type: HeatExchangerType = HeatExchangerType.UNKNOWN

    # Бренд-замена (для импортозамещения)
    brand_replace: Optional[str] = None    # "Alfa Laval M15" -> ищем аналог Феникс
    brand_replace_raw: Optional[str] = None

    # Дополнительно
    material: Optional[str] = None         # "AISI 316", "титан"
    seal_type: Optional[str] = None        # "EPDM", "NBR"
    frame_size: Optional[str] = None       # "А-25", "М-15"

    # Известные модели пластин
    plate_models_mentioned: List[str] = field(default_factory=list)

    # Свободный текст для инженера
    free_text: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class ClientInfo:
    """Информация о клиенте из письма/заявки."""
    company: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    inn: Optional[str] = None


@dataclass
class IncomingRequest:
    """
    Полная структура входящей заявки.
    Формируется AIPHX-OPERATOR, передаётся в AIPHX-ORCHESTRATOR.
    """
    request_id: str = ""
    timestamp: str = ""

    # Источник
    source: str = "email"             # email / telegram / whatsapp / web
    source_id: Optional[str] = None   # Message-ID или уникальный ID
    source_subject: Optional[str] = None
    source_from: Optional[str] = None

    # Клиент
    client: ClientInfo = field(default_factory=ClientInfo)

    # Параметры
    params: ParsedParameters = field(default_factory=ParsedParameters)

    # Статус
    status: RequestStatus = RequestStatus.PARSED
    status_notes: List[str] = field(default_factory=list)

    # Текст (для передачи дальше)
    raw_text: Optional[str] = None
    attachments: List[str] = field(default_factory=list)  # paths к файлам

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"REQ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def validate(self) -> bool:
        """Валидация извлечённых параметров. Возвращает True если OK."""
        p = self.params
        issues = []

        # Должна быть хотя бы одна среда
        if p.media_hot == MediaType.UNKNOWN and p.media_cold == MediaType.UNKNOWN:
            issues.append("Не указана рабочая среда (горячая/холодная)")

        # Температуры: либо все 4, либо мощность + 2 температуры
        temps = [p.t_hot_in, p.t_hot_out, p.t_cold_in, p.t_cold_out]
        has_all_temps = all(t is not None for t in temps)
        has_power = p.power_kw is not None

        if not has_all_temps and not has_power:
            issues.append("Нужны либо 4 температуры, либо мощность + температуры")

        if has_all_temps:
            if p.t_hot_in <= p.t_hot_out:
                issues.append("t_горячей_вход > t_горячей_выход (нарушение направления потока)")
            if p.t_cold_in >= p.t_cold_out:
                issues.append("t_холодной_вход < t_холодной_выход (нарушение направления потока)")

        # Давление не более 2.5 МПа
        if p.pressure_hot and p.pressure_hot > 2.5:
            issues.append(f"Давление {p.pressure_hot} МПа превышает лимит 2.5 МПа")
        if p.pressure_cold and p.pressure_cold > 2.5:
            issues.append(f"Давление {p.pressure_cold} МПа превышает лимит 2.5 МПа")

        # Температура не более 200°C
        for label, val in [("t_hot_in", p.t_hot_in), ("t_hot_out", p.t_hot_out),
                           ("t_cold_in", p.t_cold_in), ("t_cold_out", p.t_cold_out)]:
            if val and val > 200:
                issues.append(f"{label}={val}°C превышает лимит 200°C")

        if issues:
            self.status = RequestStatus.INCOMPLETE
            self.status_notes = issues
            return False

        self.status = RequestStatus.VALIDATED
        return True

    def to_dict(self) -> dict:
        """Сериализация в dict для JSON."""
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "source_id": self.source_id,
            "source_subject": self.source_subject,
            "source_from": self.source_from,
            "client": {
                "company": self.client.company,
                "contact_name": self.client.contact_name,
                "email": self.client.email,
                "phone": self.client.phone,
                "city": self.client.city,
                "inn": self.client.inn,
            },
            "params": {
                "t_hot_in": self.params.t_hot_in,
                "t_hot_out": self.params.t_hot_out,
                "t_cold_in": self.params.t_cold_in,
                "t_cold_out": self.params.t_cold_out,
                "flow_hot": self.params.flow_hot,
                "flow_cold": self.params.flow_cold,
                "flow_hot_raw": self.params.flow_hot_raw,
                "flow_cold_raw": self.params.flow_cold_raw,
                "power_kw": self.params.power_kw,
                "power_raw": self.params.power_raw,
                "media_hot": self.params.media_hot.value,
                "media_cold": self.params.media_cold.value,
                "media_hot_raw": self.params.media_hot_raw,
                "media_cold_raw": self.params.media_cold_raw,
                "pressure_hot": self.params.pressure_hot,
                "pressure_cold": self.params.pressure_cold,
                "pressure_raw": self.params.pressure_raw,
                "hx_type": self.params.hx_type.value,
                "brand_replace": self.params.brand_replace,
                "brand_replace_raw": self.params.brand_replace_raw,
                "material": self.params.material,
                "seal_type": self.params.seal_type,
                "frame_size": self.params.frame_size,
                "plate_models_mentioned": self.params.plate_models_mentioned,
                "free_text": self.params.free_text,
                "notes": self.params.notes,
            },
            "status": self.status.value,
            "status_notes": self.status_notes,
            "raw_text": self.raw_text[:500] if self.raw_text else None,
            "attachments": self.attachments,
        }
