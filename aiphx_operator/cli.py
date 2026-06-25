# -*- coding: utf-8 -*-
"""
AIPHX-OPERATOR: CLI Test Harness
Интерактивный тест парсера теплообменников.

Запуск:
  python -m aiphx_operator
  python -m aiphx_operator --file request.txt
  python -m aiphx_operator --demo
"""

import sys
import json
import os

from .core import OperatorAgent


# ── Тестовые данные ───────────────────────────────────────────────────────────

DEMO_REQUESTS = [
    {
        "name": "Заявка 1: Вода -> Вода (стандарт)",
        "text": """ООО "ТеплоПром"
Иванов Иван Иванович
г. Москва

Здравствуйте!
Нужен пластинчатый разборный теплообменник.
Греющая среда: вода, t1 = 90°C, t2 = 70°C.
Охлаждающая среда: вода, t3 = 20°C, t4 = 40°C.
Расход нагрева: G1 = 15 кг/с.
Давление: 1.6 МПа.
Нужен расчёт площади и подбор модели.

Контакты: ivanov@teploprom.ru, +7 (495) 123-45-67"""
    },
    {
        "name": "Заявка 2: Вода -> Гликоль + замена Alfa Laval",
        "text": """ЗАО "СтройМонтаж"
Петров Пётр
Екатеринбург

Требуется теплообменник для системы отопления.
Горячая сторона: вода, 85°C -> 65°C.
Холодная сторона: гликоль 30%, 10°C -> 45°C.
Расход: 8 кг/с (нагрев), мощность ≈ 670 кВт.

Нужен аналог Alfa Laval M15-BFG. Замена на наш завод Феникс.
AISI 316, уплотнения EPDM.

petrov@stroymontazh.ru"""
    },
    {
        "name": "Заявка 3: Масло (неполные данные)",
        "text": """ИП Сидоров
Ростов-на-Дону

Нужен теплообменник для охлаждения масла.
Масло техническое, на входе 90°C, нужно охладить до 50°C.
Давление: 6 бар.

Сколько стоит? Жду расчёта."""
    },
    {
        "name": "Заявка 4: Пар -> Вода",
        "text": """ООО "ПищеКомплект"
Казань

Для участка пастеризации нужен пластинчатый паяный теплообменник.
Пар (насыщенный) -> Вода.
Пар: 120°C, конденсация.
Вода: 10°C -> 80°C.
Производительность: 5000 кг/ч горячей воды.
Давление: 4 бар.

info@pishkomplekt.ru
ИНН: 1650000000"""
    },
]


def print_result(req, verbose=True):
    """Красивый вывод результата."""
    status_colors = {
        "validated": "\033[92m",   # зелёный
        "incomplete": "\033[93m",  # жёлтый
        "rejected": "\033[91m",    # красный
        "parsed": "\033[94m",      # синий
    }
    reset = "\033[0m"
    color = status_colors.get(req.status.value, "")

    print(f"\n{'='*70}")
    print(f"  Заявка: {req.request_id}")
    print(f"  Статус: {color}{req.status.value.upper()}{reset}")
    print(f"  Источник: {req.source}")
    if req.source_subject:
        print(f"  Тема: {req.source_subject}")
    print(f"{'='*70}")

    # Клиент
    c = req.client
    if any([c.company, c.contact_name, c.email, c.phone, c.city]):
        print(f"\n  КЛИЕНТ:")
        if c.company: print(f"    Компания: {c.company}")
        if c.contact_name: print(f"    Контакт:  {c.contact_name}")
        if c.email: print(f"    Email:     {c.email}")
        if c.phone: print(f"    Телефон:   {c.phone}")
        if c.city: print(f"    Город:     {c.city}")
        if c.inn: print(f"    ИНН:       {c.inn}")

    # Параметры
    p = req.params
    print(f"\n  ПАРАМЕТРЫ ТЕПЛООБМЕННИКА:")

    # Среды
    if p.media_hot.value != "unknown":
        print(f"    Горячая среда:    {p.media_hot.value}" + (f" (raw: {p.media_hot_raw})" if p.media_hot_raw else ""))
    if p.media_cold.value != "unknown":
        print(f"    Холодная среда:   {p.media_cold.value}" + (f" (raw: {p.media_cold_raw})" if p.media_cold_raw else ""))

    # Температуры
    temps = []
    if p.t_hot_in is not None: temps.append(f"t1={p.t_hot_in}°C")
    if p.t_hot_out is not None: temps.append(f"t2={p.t_hot_out}°C")
    if p.t_cold_in is not None: temps.append(f"t3={p.t_cold_in}°C")
    if p.t_cold_out is not None: temps.append(f"t4={p.t_cold_out}°C")
    if temps:
        print(f"    Температуры:      {', '.join(temps)}")

    # Мощность
    if p.power_kw:
        print(f"    Мощность:        {p.power_kw} кВт" + (f" (raw: {p.power_raw})" if p.power_raw else ""))

    # Расход
    if p.flow_hot:
        print(f"    Расход нагрева:  {p.flow_hot:.4f} кг/с" + (f" (raw: {p.flow_hot_raw})" if p.flow_hot_raw else ""))
    if p.flow_cold:
        print(f"    Расход охлажд.:  {p.flow_cold:.4f} кг/с" + (f" (raw: {p.flow_cold_raw})" if p.flow_cold_raw else ""))

    # Давление
    if p.pressure_hot:
        print(f"    Давление нагрева: {p.pressure_hot} МПа")
    if p.pressure_cold:
        print(f"    Давление охлажд.: {p.pressure_cold} МПа")

    # Тип
    if p.hx_type.value != "unknown":
        print(f"    Тип ТО:          {p.hx_type.value}")

    # Бренд-замена
    if p.brand_replace:
        print(f"    Аналог:          {p.brand_replace}" + (f" (raw: {p.brand_replace_raw})" if p.brand_replace_raw else ""))

    # Модели
    if p.plate_models_mentioned:
        print(f"    Модели пластин:  {', '.join(set(p.plate_models_mentioned))}")

    # Материал/уплотнения
    if p.material:
        print(f"    Материал:        {p.material}")
    if p.seal_type:
        print(f"    Уплотнения:      {p.seal_type}")

    # Примечания
    if p.notes:
        print(f"\n  ПРИМЕЧАНИЯ:")
        for note in p.notes:
            print(f"    • {note}")

    # Проблемы
    if req.status_notes:
        print(f"\n  ПРОБЛЕМЫ:")
        for issue in req.status_notes:
            print(f"    ⚠ {issue}")

    if verbose and req.raw_text:
        print(f"\n  ИСХОДНЫЙ ТЕКСТ (первые 300 символов):")
        print(f"    {req.raw_text[:300]}...")

    print()


def main():
    agent = OperatorAgent()

    # Проверка аргументов
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            print("AIPHX-OPERATOR: Демонстрация на тестовых данных\n")
            for demo in DEMO_REQUESTS:
                print(f"\n--- {demo['name']} ---")
                req = agent.process_text(demo["text"], source="demo")
                print_result(req)
        elif sys.argv[1] == "--file":
            if len(sys.argv) < 3:
                print("Использование: python -m operator --file <путь_к_файлу>")
                sys.exit(1)
            filepath = sys.argv[2]
            print(f"AIPHX-OPERATOR: Обработка файла {filepath}\n")
            req = agent.process_file(filepath)
            print_result(req)
        else:
            print("Неизвестный аргумент. Доступно: --demo, --file <path>")
            sys.exit(1)
    else:
        # Интерактивный режим
        print("AIPHX-OPERATOR: Интерактивный режим")
        print("Введите текст заявки на теплообменник (или 'выход' для завершения):\n")
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text or text.lower() in ("выход", "exit", "quit"):
                break
            req = agent.process_text(text, source="interactive")
            print_result(req)

    # Статистика
    stats = agent.get_stats()
    print(f"\n{'='*70}")
    print(f"  СТАТИСТИКА:")
    print(f"    Всего заявок:    {stats['total']}")
    print(f"    Валидных:        {stats['validated']}")
    print(f"    Неполных:        {stats['incomplete']}")
    print(f"    Отклонённых:     {stats['rejected']}")
    print(f"    Успешность:      {stats['success_rate']}")
    print(f"{'='*70}")

    # Экспорт
    if stats['total'] > 0:
        agent.export_results("operator_output.json")


if __name__ == "__main__":
    main()
