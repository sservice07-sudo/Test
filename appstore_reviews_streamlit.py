import streamlit as st
import requests
import pandas as pd
import time
import re


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def extract_app_id(app_store_url: str) -> str:
    """
    Извлекает numeric App ID из ссылки App Store
    """
    match = re.search(r"/id(\d+)", app_store_url)
    if not match:
        raise ValueError("Не удалось извлечь app_id из ссылки App Store")
    return match.group(1)


def fetch_all_reviews(app_id: str, sleep_sec: float = 1.0):
    """
    Загружает все доступные отзывы через публичный RSS App Store
    """
    all_reviews = []
    page = 1

    while True:
        url = (
            f"https://itunes.apple.com/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json?cc=ru"
        )

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
            break

        entries = data.get("feed", {}).get("entry", [])

        # первая запись — metadata приложения
        if page == 1 and entries:
            entries = entries[1:]

        if not entries:
            break

        for entry in entries:
            all_reviews.append({
                "review_id": entry.get("id", {}).get("label"),
                "review_date": entry.get("updated", {}).get("label"),
                "rating": int(entry.get("im:rating", {}).get("label", 0)),
                "username": entry.get("author", {}).get("name", {}).get("label"),
                "app_version": entry.get("im:version", {}).get("label"),
                "original_text": entry.get("content", {}).get("label")
            })

        st.write(f"Загружена страница {page}, всего отзывов: {len(all_reviews)}")
        page += 1
        time.sleep(sleep_sec)

    return all_reviews


def translate_to_ru(text: str) -> str:
    """
    Переводит EN → RU через бесплатный Google Translate endpoint.
    Если текст уже на русском — возвращает как есть.
    """
    if not text or re.search(r"[А-Яа-я]", text):
        return text

    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "ru",
        "dt": "t",
        "q": text
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return "".join([item[0] for item in r.json()[0]])
    except Exception:
        return text


# =========================
# STREAMLIT UI
# =========================

st.set_page_config(page_title="App Store Reviews Parser", layout="centered")

st.title("📱 Парсер отзывов App Store (Россия)")
st.write("Работает только с публичными данными, без авторизации.")

app_url = st.text_input(
    "Вставьте ссылку на приложение в App Store (RU):",
    value="https://apps.apple.com/ru/app/duolingo/id570060128"
)

start_button = st.button("🚀 Собрать отзывы")

if start_button:
    try:
        app_id = extract_app_id(app_url)
        st.success(f"App ID найден: {app_id}")
    except Exception as e:
        st.error(str(e))
        st.stop()

    with st.spinner("Загрузка отзывов..."):
        reviews = fetch_all_reviews(app_id)

    if not reviews:
        st.warning("Отзывы не найдены.")
        st.stop()

    df = pd.DataFrame(reviews)
    st.success(f"Всего отзывов загружено: {len(df)}")

    st.write("🔄 Перевод английских отзывов на русский...")
    translated = []

    progress = st.progress(0)
    for i, text in enumerate(df["original_text"]):
        translated.append(translate_to_ru(text))
        progress.progress((i + 1) / len(df))
        if i % 20 == 0:
            time.sleep(0.5)

    df["translated_text_ru"] = translated

    df_final = df[
        [
            "review_id",
            "review_date",
            "rating",
            "username",
            "app_version",
            "original_text",
            "translated_text_ru"
        ]
    ]

    output_file = "appstore_reviews_ru.csv"
    df_final.to_csv(output_file, index=False, encoding="utf-8")

    st.success("✅ Готово!")
    st.write(f"📁 Файл сохранён: `{output_file}`")

    st.write("📊 Первые 5 строк:")
    st.dataframe(df_final.head(5))

    with open(output_file, "rb") as f:
        st.download_button(
            label="⬇️ Скачать CSV",
            data=f,
            file_name=output_file,
            mime="text/csv"
        )