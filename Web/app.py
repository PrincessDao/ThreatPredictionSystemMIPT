import streamlit as st
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import os

st.set_page_config(page_title="Аналитическая платформа", layout="wide")
st.markdown("### Аналитическая платформа для отслеживания угроз ИБ")


@st.cache_data
def load_data():
    incidents = pd.read_excel("incidents_2000.xlsx")

    if os.path.exists("thrlist.xlsx"):
        threats = pd.read_excel("thrlist.xlsx")
    elif os.path.exists("Файл с сайта ФСТЭК.xlsx"):
        threats = pd.read_excel("Файл с сайта ФСТЭК.xlsx")
    else:
        threats = pd.DataFrame()

    return incidents, threats


incidents, threats = load_data()


if 'Дата инцидента' in incidents.columns:
    incidents['Дата инцидента'] = pd.to_datetime(incidents['Дата инцидента'], errors='coerce')
    incidents['hour'] = incidents['Дата инцидента'].dt.hour
    incidents['day_of_week'] = incidents['Дата инцидента'].dt.day_name(locale='ru_RU')
    incidents['month'] = incidents['Дата инцидента'].dt.month_name(locale='ru_RU')

    def get_season(month):
        if month in ['December', 'January', 'February']:
            return 'Зима'
        elif month in ['March', 'April', 'May']:
            return 'Весна'
        elif month in ['June', 'July', 'August']:
            return 'Лето'
        else:
            return 'Осень'

    incidents['season'] = incidents['month'].apply(get_season)


with st.sidebar:
    st.header("Фильтры")

    df = incidents.copy()

    if 'Тип предприятия' in df.columns:
        types = st.multiselect(
            "Тип предприятия",
            sorted(df['Тип предприятия'].dropna().unique())
        )
        if types:
            df = df[df['Тип предприятия'].isin(types)]

    if 'Регион размещения предприятия' in df.columns:
        regions = st.multiselect(
            "Регион",
            sorted(df['Регион размещения предприятия'].dropna().unique())
        )
        if regions:
            df = df[df['Регион размещения предприятия'].isin(regions)]


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Обзор",
    "Анализ инцидентов",
    "Паттерны по времени",
    "Прогноз атак",
    "Рекомендации"
])


with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего инцидентов", f"{len(df):,}")
    col2.metric("Угроз из ФСТЭК", len(threats))
    col3.metric(
        "Типов предприятий",
        df['Тип предприятия'].nunique() if 'Тип предприятия' in df.columns else 0
    )
    col4.metric(
        "Регионов",
        df['Регион размещения предприятия'].nunique()
        if 'Регион размещения предприятия' in df.columns else 0
    )

    st.subheader("Распределение инцидентов по типам предприятий")
    if 'Тип предприятия' in df.columns:
        type_counts = df['Тип предприятия'].value_counts().head(10).reset_index()
        type_counts.columns = ['Тип предприятия', 'Количество']

        fig = px.bar(
            type_counts,
            x='Тип предприятия',
            y='Количество',
            title="Топ-10 типов предприятий по количеству инцидентов"
        )
        st.plotly_chart(fig, use_container_width=True)


with tab2:
    st.subheader("Данные об инцидентах")
    st.dataframe(df.head(30), use_container_width=True)


with tab3:
    st.subheader("Паттерны атак по времени суток, дню недели и сезону")

    if 'hour' in df.columns and len(df) > 0:
        col_a, col_b = st.columns(2)

        with col_a:
            pivot = df.pivot_table(
                index='day_of_week',
                columns='hour',
                aggfunc='size',
                fill_value=0
            )
            fig, ax = plt.subplots(figsize=(12, 7))
            sns.heatmap(pivot, cmap="Reds", annot=False, ax=ax)
            plt.title("Частота инцидентов: День недели × Час суток")
            plt.xlabel("Час суток")
            plt.ylabel("День недели")
            st.pyplot(fig)

        with col_b:
            hourly = df.groupby('hour').size().reset_index(name='count')
            fig2 = px.bar(
                hourly,
                x='hour',
                y='count',
                title="Количество инцидентов по часам суток",
                labels={'hour': 'Час суток', 'count': 'Количество'}
            )
            st.plotly_chart(fig2, use_container_width=True)

        seasonal = df.groupby('season').size().reset_index(name='count')
        fig3 = px.bar(
            seasonal,
            x='season',
            y='count',
            title="Распределение инцидентов по сезонам"
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Не удалось извлечь временные данные из столбца 'Дата инцидента'.")


with tab4:
    st.subheader("Прогноз атак")
    st.info("Здесь будет прогноз с использованием Prophet.")


with tab5:
    st.subheader("Рекомендации по предотвращению")
    st.markdown("""
    Ключевые рекомендации на основе анализа:
    - Усилить мониторинг в вечерние и ночные часы (18:00 — 06:00)
    - Особое внимание предприятиям типов: химия, энергетика, отели
    - Разработать сезонные меры защиты, особенно в зимний и осенний период
    - Проводить целевые аудиты уязвимостей в регионах с высокой активностью
    """)