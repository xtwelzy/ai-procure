import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os

# ============================
#   ПАРСИНГ ТЕНДЕРОВ ГОСЗАКУП
# ============================


def get_tenders_last_days(days=1):
    """
    Парсит тендеры с ows.goszakup.gov.kz
    без API-ключа (через публичный endpoint).
    """

    print(f"▶ Парсим тендеры за последние {days} дней...")

    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")

    url = f"https://ows.goszakup.gov.kz/v3/tender?filter[announce_date][gte]={date_from}&filter[announce_date][lte]={date_to}&per-page=500"

    response = requests.get(url)
    if response.status_code != 200:
        print("❌ Ошибка запроса:", response.status_code)
        return

    data = response.json()
    tenders = data.get("data", [])

    if not tenders:
        print("⚠ Нет тендеров за выбранный период.")
        return

    print(f"✔ Найдено тендеров: {len(tenders)}")

    # Выбираем поля, подходящие для твоего проекта
    rows = []
    for t in tenders:
        rows.append(
            {
                "external_id": t.get("id"),
                "platform": "goszakup",
                "customer_name": t.get("customer", {}).get("name_ru"),
                "subject": t.get("name_ru"),
                "description_raw": t.get("description_ru"),
                "price_amount": t.get("amount"),
                "price_currency": t.get("currency"),
                "announce_date": t.get("announce_date"),
            }
        )

    df = pd.DataFrame(rows)

    # сохраняем результат
    filename = "tenders_latest.csv"
    df.to_csv(filename, index=False, encoding="utf-8-sig")

    print(f"📁 Файл сохранён: {filename}")
    print("✔ Готово!")


# ============================
#        ОСНОВНОЕ МЕНЮ
# ============================


def main():
    os.system("cls")
    print("===================================")
    print("  АВТО-ПАРСЕР ТЕНДЕРОВ КАЗАХСТАНА  ")
    print("===================================\n")

    print("1. Парсить тендеры за сегодня")
    print("2. Парсить за вчера")
    print("3. Парсить за последние 7 дней")
    print("4. Ввести своё количество дней")
    print("0. Выйти\n")

    choice = input("Выберите пункт: ").strip()

    if choice == "1":
        get_tenders_last_days(1)
    elif choice == "2":
        get_tenders_last_days(2)
    elif choice == "3":
        get_tenders_last_days(7)
    elif choice == "4":
        d = int(input("Введите количество дней: "))
        get_tenders_last_days(d)
    else:
        print("Выход...")


if __name__ == "__main__":
    main()
