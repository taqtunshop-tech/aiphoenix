# -*- coding: utf-8 -*-
"""
AIPHX-OPERATOR: Core Agent
Оператор-парсер: чтение писем, парсинг текста, распознавание сканов.

Вход:  email (IMAP) / текст / файл
Выход: IncomingRequest (JSON) -> AIPHX-ORCHESTRATOR

Запуск:
  python -m aiphx_operator                  # CLI интерактивный режим
  python -m aiphx_operator --file письмо.txt  # из файла
  python -m aiphx_operator --email user@host  # IMAP подключение (TODO)
"""

import json
import sys
import os
import hashlib
from datetime import datetime
from typing import Optional

from .models import IncomingRequest, RequestStatus, ClientInfo, ParsedParameters
from .parser import TextParser


# ── Валидация параметров ─────────────────────────────────────────────────────

def validate_request(req: IncomingRequest) -> IncomingRequest:
    """
    Валидация извлечённых параметров.
    Если не хватает данных — статус INCOMPLETE.
    Если данные некорректны — REJECTED.
    """
    issues = []
    p = req.params

    # Проверка среды
    from .models import MediaType
    if p.media_hot == MediaType.UNKNOWN and p.media_cold == MediaType.UNKNOWN:
        issues.append("Не указана рабочая среда (нужно: вода/гликоль/масло/пар)")

    # Проверка температур / мощности
    temps = [p.t_hot_in, p.t_hot_out, p.t_cold_in, p.t_cold_out]
    has_all_temps = all(t is not None for t in temps)
    has_power = p.power_kw is not None

    if not has_all_temps and not has_power:
        issues.append("Нужны либо 4 температуры (t1-t4), либо мощность (Q) + температуры")

    # Проверка направления потока
    if p.t_hot_in is not None and p.t_hot_out is not None:
        if p.t_hot_in <= p.t_hot_out:
            issues.append(f"t_горячей_вход ({p.t_hot_in}°C) должно быть > t_горячей_выход ({p.t_hot_out}°C)")
    if p.t_cold_in is not None and p.t_cold_out is not None:
        if p.t_cold_in >= p.t_cold_out:
            issues.append(f"t_холодной_вход ({p.t_cold_in}°C) должно быть < t_холодной_выход ({p.t_cold_out}°C)")

    # Проверка лимитов
    if p.pressure_hot and p.pressure_hot > 2.5:
        issues.append(f"Давление {p.pressure_hot} МПа > лимит 2.5 МПа")
    for label, val in [("t_hot_in", p.t_hot_in), ("t_cold_in", p.t_cold_in)]:
        if val and val > 200:
            issues.append(f"{label}={val}°C > лимит 200°C")

    if issues:
        req.status = RequestStatus.INCOMPLETE
        req.status_notes = issues
    else:
        req.status = RequestStatus.VALIDATED

    return req


# ── Клиентский парсер ────────────────────────────────────────────────────────

def extract_client_info(text: str) -> ClientInfo:
    """Извлечение контактных данных клиента из текста."""
    import re
    client = ClientInfo()

    # Email
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    if m:
        client.email = m.group(0)

    # Телефон
    m = re.search(r"[\+]?[\d\s\-\(\)]{10,}", text)
    if m:
        client.phone = m.group(0).strip()

    # ИНН
    m = re.search(r"(?:ИНН|inn)\s*[=:]\s*(\d{10,12})", text, re.IGNORECASE)
    if m:
        client.inn = m.group(1)

    # Город
    cities = ["москва", "санкт-петербург", "ростов", "екатеринбург", "новосибирск",
              "краснодар", "самара", "казань", "нижний новгород", "челябинск",
              "уфа", "омск", "волгоград", "красноярск", "саратов"]
    text_lower = text.lower()
    for city in cities:
        if city in text_lower:
            client.city = city.title()
            break

    # Компания (обычно первая строка или после "от кого")
    lines = text.strip().split("\n")
    if lines:
        first = lines[0].strip()
        if len(first) > 3 and len(first) < 100 and not first.startswith("Re:"):
            client.company = first

    return client


# ── Основной оператор ────────────────────────────────────────────────────────

class OperatorAgent:
    """
    AIPHX-OPERATOR: Оператор-Парсер.

    Роль:
      - Читает входящие письма и мессенджеры
      - Извлекает параметры (температуры, среды, давления, мощность)
      - Передаёт структурированные данные в AIPHX-ORCHESTRATOR

    НЕ считает! Только парсит.
    """

    def __init__(self):
        self.parser = TextParser()
        self.processed = []

    def process_text(self, text: str, source: str = "text",
                     subject: str = None, from_addr: str = None) -> IncomingRequest:
        """
        Обработать текстовое сообщение/письмо.
        Возвращает IncomingRequest с извлечёнными параметрами.
        """
        req = IncomingRequest(
            source=source,
            source_subject=subject,
            source_from=from_addr,
            raw_text=text,
        )

        # 1. Извлечение контактных данных
        req.client = extract_client_info(text)

        # 2. Парсинг параметров теплообменника
        req.params = self.parser.parse(text)

        # 3. Валидация
        req = validate_request(req)

        # 4. Сохранение в историю
        self.processed.append(req)

        return req

    def process_file(self, filepath: str) -> IncomingRequest:
        """Обработать текстовый файл."""
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        return self.process_text(text, source="file",
                                 subject=os.path.basename(filepath))

    def process_email(self, email_data: dict) -> IncomingRequest:
        """
        Обработать данные письма (из IMAP).
        email_data = {
            "subject": str,
            "from": str,
            "body": str,
            "attachments": [filepath, ...]
        }
        """
        req = self.process_text(
            text=email_data.get("body", ""),
            source="email",
            subject=email_data.get("subject"),
            from_addr=email_data.get("from"),
        )
        req.attachments = email_data.get("attachments", [])
        return req

    def process_batch(self, texts: list) -> list:
        """Обработать несколько сообщений."""
        results = []
        for text_data in texts:
            if isinstance(text_data, str):
                results.append(self.process_text(text_data))
            elif isinstance(text_data, dict):
                results.append(self.process_email(text_data))
        return results

    def get_stats(self) -> dict:
        """Статистика обработанных заявок."""
        total = len(self.processed)
        validated = sum(1 for r in self.processed if r.status == RequestStatus.VALIDATED)
        incomplete = sum(1 for r in self.processed if r.status == RequestStatus.INCOMPLETE)
        rejected = sum(1 for r in self.processed if r.status == RequestStatus.REJECTED)
        return {
            "total": total,
            "validated": validated,
            "incomplete": incomplete,
            "rejected": rejected,
            "success_rate": f"{validated/total*100:.1f}%" if total else "0%",
        }

    def export_results(self, filepath: str = "operator_output.json"):
        """Экспорт результатов в JSON."""
        data = {
            "agent": "AIPHX-OPERATOR",
            "exported_at": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "requests": [r.to_dict() for r in self.processed],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Экспорт: {filepath} ({len(self.processed)} заявок)")
        return filepath
