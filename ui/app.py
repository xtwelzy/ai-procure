import os
import streamlit as st
import pandas as pd
import requests
import streamlit.components.v1 as components

# Базовый URL бэкенда FastAPI
FASTAPI_URL = "http://127.0.0.1:8000"

# ----------------------------------------------------------------------
# НАСТРОЙКА СТРАНИЦЫ
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="AI-Procure — Аналитика тендеров и подбор поставщиков",
    layout="wide",
)

# ----------------------------------------------------------------------
# САЙДБАР: НАВИГАЦИЯ + AI-АНАЛИЗ
# ----------------------------------------------------------------------
st.sidebar.title("Навигация")
menu = st.sidebar.radio(
    "",
    ["Загрузка данных", "Список тендеров", "Карточка тендера"],
)

st.sidebar.markdown("### 🤖 AI-инструменты")
ai_tender_id = st.sidebar.number_input(
    "ID тендера (для AI анализа)", min_value=1, value=1
)

if st.sidebar.button("Запустить AI-анализ"):
    try:
        resp = requests.get(f"{FASTAPI_URL}/ai/analyze_tender/{ai_tender_id}")
        if resp.status_code == 200:
            st.sidebar.success("Готово! Проверьте вывод ниже.")
            # Выводим результат анализа в основной области
            st.json(resp.json())
        else:
            st.sidebar.error(f"Ошибка анализа: {resp.status_code}")
    except Exception as e:
        st.sidebar.error(f"Ошибка запроса: {e}")

# ----------------------------------------------------------------------
# ЭКРАН 1. ЗАГРУЗКА ДАННЫХ
# ----------------------------------------------------------------------
if menu == "Загрузка данных":
    st.title("Загрузка данных")

    # ---- Тендеры ----
    st.subheader("Загрузка тендеров из CSV")
    file_t = st.file_uploader("CSV файл тендеров", type=["csv"], key="tenders_csv")

    if st.button("Загрузить тендеры") and file_t:
        try:
            resp = requests.post(
                f"{FASTAPI_URL}/tenders/ingest_csv",
                files={"file": (file_t.name, file_t.getvalue(), "text/csv")},
            )
            st.json(resp.json())
        except Exception as e:
            st.error(f"Ошибка загрузки тендеров: {e}")

    st.markdown("---")

    # ---- Поставщики ----
    st.subheader("Загрузка поставщиков из CSV")
    file_s = st.file_uploader("CSV файл поставщиков", type=["csv"], key="suppliers_csv")

    if st.button("Загрузить поставщиков") and file_s:
        try:
            resp = requests.post(
                f"{FASTAPI_URL}/suppliers/ingest_csv",
                files={"file": (file_s.name, file_s.getvalue(), "text/csv")},
            )
            st.json(resp.json())
        except Exception as e:
            st.error(f"Ошибка загрузки поставщиков: {e}")

# ----------------------------------------------------------------------
# ЭКРАН 2. СПИСОК ТЕНДЕРОВ
# ----------------------------------------------------------------------
elif menu == "Список тендеров":
    st.title("Список тендеров")

    try:
        resp = requests.get(f"{FASTAPI_URL}/tenders")
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json())
            st.dataframe(df, use_container_width=True)
        else:
            st.error(f"Ошибка получения тендеров: {resp.status_code}")
    except Exception as e:
        st.error(f"Ошибка запроса: {e}")

# ----------------------------------------------------------------------
# ЭКРАН 3. КАРТОЧКА ТЕНДЕРА
# ----------------------------------------------------------------------
elif menu == "Карточка тендера":
    st.title("Карточка тендера и отчёт")

    tid = st.number_input("ID тендера", min_value=1, value=1)

    if st.button("Показать отчёт"):
        try:
            resp = requests.get(f"{FASTAPI_URL}/tenders/{tid}/report")
            if resp.status_code == 200:
                st.json(resp.json())
            else:
                st.error(f"Ошибка получения отчёта: {resp.status_code}")
        except Exception as e:
            st.error(f"Ошибка запроса: {e}")

# ----------------------------------------------------------------------
# ПЛАВАЮЩИЙ AI-ЧАТ (ОДИН КОМПОНЕНТ НА ВСЮ СТРАНИЦУ)
# ----------------------------------------------------------------------
chat_path = os.path.join(os.path.dirname(__file__), "components", "chat_component.html")

try:
    if os.path.exists(chat_path):
        with open(chat_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=600, scrolling=False)
    else:
        st.error(f"Файл чата не найден: {chat_path}")
except Exception as e:
    st.error(f"Ошибка инициализации чата: {e}")
