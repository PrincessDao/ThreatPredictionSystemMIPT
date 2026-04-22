# app.py
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
import os
import sys
import json
import random
import base64
from io import BytesIO
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path

# === НАСТРОЙКА ПУТЕЙ ДЛЯ DJANGO ===

def get_project_root():
    """
    Находит корень Django-проекта с вложенной структурой:
    project_root/
    └── backend/              ← outer (добавляем в sys.path)
        ├── backend/         ← inner (Python-пакет с settings.py)
        │   └── settings.py
        ├── security_app/
        └── manage.py
    """
    current = Path(__file__).resolve()
    
    # Ищем папку, внутри которой есть backend/backend/settings.py
    for parent in [current.parent, current.parent.parent] + list(current.parents):
        # Проверяем вложенную структуру: outer/backend/inner/settings.py
        if (parent / 'backend' / 'backend' / 'settings.py').exists():
            return parent / 'backend'  # Возвращаем outer backend/
    
    # Fallback для Docker: проверяем /app/backend/backend/settings.py
    if Path('/app/backend/backend/settings.py').exists():
        return Path('/app/backend')
    
    # Если не нашли — выводим ошибку с подсказкой
    raise RuntimeError(
        "Не найдена вложенная структура backend/backend/settings.py!\n"
        f"Текущий файл: {current}\n"
        f"Проверьте структуру:\n"
        f"  project_root/\n"
        f"  └── backend/              ← outer (должен быть в sys.path)\n"
        f"      ├── backend/         ← inner (Python-пакет)\n"
        f"      │   └── settings.py\n"
        f"      ├── security_app/\n"
        f"      └── manage.py"
    )

# Применяем настройку
PROJECT_ROOT = get_project_root()
sys.path.insert(0, str(PROJECT_ROOT))  # Добавляем outer backend/

print(f"✅ PROJECT_ROOT (outer backend): {PROJECT_ROOT}")
print(f"✅ settings.py exists: {(PROJECT_ROOT / 'backend' / 'settings.py').exists()}")
print(f"✅ security_app/models.py exists: {(PROJECT_ROOT / 'security_app' / 'models.py').exists()}")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()
print("✅ Django успешно инициализирован")
# === КОНЕЦ НАСТРОЙКИ ===
    
from security_app.models import Incident, Threat

@st.cache_resource
def load_silero_tts():
    try:
        import torch
        import soundfile as sf
        torch.hub.set_dir("./.cache/torch")
        model, _ = torch.hub.load(
            repo_or_dir='snakers4/silero-models',
            model='silero_tts',
            language='ru',
            speaker='v4_ru'
        )
        model.to('cpu')
        return model
    except Exception as e:
        st.warning(f"Silero TTS не загружен: {e}")
        return None

tts_model = load_silero_tts()

def generate_tts_audio(text: str, speaker: str = "kseniya"):
    if tts_model is None:
        return None
    try:
        import torch
        import soundfile as sf
        audio_tensor = tts_model.apply_tts(
            text=text,
            speaker=speaker,
            sample_rate=48000,
            put_accent=True,
            put_yo=True
        )
        audio_np = audio_tensor.cpu().numpy().astype(np.float32)
        buffer = BytesIO()
        sf.write(buffer, audio_np, samplerate=48000, format='WAV')
        buffer.seek(0)
        audio_b64 = base64.b64encode(buffer.read()).decode('utf-8')
        return audio_b64
    except Exception as e:
        st.error(f"Ошибка генерации аудио: {e}")
        return None

@st.cache_data(ttl=300)
def load_incidents_from_db():
    try:
        qs = Incident.objects.all().values(
            'enterprise_type',
            'enterprise_code',
            'host_count',
            'threat_code',
            'success',
            'region',
            'incident_date',
            'incident_time'
        )
        df = pd.DataFrame(list(qs))
        
        if df.empty:
            return pd.DataFrame()
        
        df = df.rename(columns={
            'enterprise_type': 'Тип_предприятия',
            'enterprise_code': 'Код_предприятия',
            'host_count': 'Количество_хостов',
            'threat_code': 'Код_реализованной_угрозы',
            'success': 'Успех',
            'region': 'Регион_размещения_предприятия',
            'incident_date': 'Дата_инцидента',
            'incident_time': 'Региональное_время'
        })
        
        df['Тип_предприятия'] = df['Тип_предприятия'].astype(str)
        df['Регион_размещения_предприятия'] = df['Регион_размещения_предприятия'].astype(str)
        df['Код_предприятия'] = pd.to_numeric(df['Код_предприятия'], errors='coerce').fillna(0).astype(int)
        df['Количество_хостов'] = pd.to_numeric(df['Количество_хостов'], errors='coerce').fillna(0).astype(int)
        df['Код_реализованной_угрозы'] = pd.to_numeric(df['Код_реализованной_угрозы'], errors='coerce').fillna(0).astype(int)
        df['Успех'] = pd.to_numeric(df['Успех'], errors='coerce').fillna(0).astype(int)
        
        df['Региональное_время'] = pd.to_datetime(df['Региональное_время'], errors='coerce')
        if df['Региональное_время'].dt.tz is not None:
            df['Региональное_время'] = df['Региональное_время'].dt.tz_localize(None)
        
        df['Дата_инцидента'] = pd.to_datetime(df['Дата_инцидента'], errors='coerce')
        if df['Дата_инцидента'].dt.tz is not None:
            df['Дата_инцидента'] = df['Дата_инцидента'].dt.tz_localize(None)
        
        df['час'] = df['Региональное_время'].dt.hour
        df['день_недели'] = df['Региональное_время'].dt.dayofweek
        df['месяц'] = df['Региональное_время'].dt.month
        
        def get_season(m):
            if m in [12, 1, 2]: return 'Зима'
            elif m in [3, 4, 5]: return 'Весна'
            elif m in [6, 7, 8]: return 'Лето'
            return 'Осень'
        
        df['сезон'] = df['месяц'].apply(get_season)
        
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки инцидентов: {e}")
        return pd.DataFrame()

def get_latest_attack_info(df):
    now = pd.Timestamp.now()
    
    if "alert_active_until" in st.session_state and "alert_text_cache" in st.session_state:
        if st.session_state.alert_active_until and now < st.session_state.alert_active_until:
            return {"attack": True, "text": st.session_state.alert_text_cache}
        else:
            st.session_state.alert_active_until = None
            st.session_state.alert_text_cache = None

    if df.empty or 'Региональное_время' not in df.columns:
        return {"attack": False, "text": "Нет данных"}
    
    # Убираем временную зону у 'now' для корректного сравнения
    now_naive = now.tz_localize(None) if now.tzinfo is not None else now
    
    last_5_sec = df[df['Региональное_время'] > now_naive - pd.Timedelta(seconds=5)]
    
    if len(last_5_sec) > 0:
        last = last_5_sec.iloc[-1]
        text = f"Прогнозируется атака! Тип: {last.get('Тип_предприятия', 'Неизвестно')}, Регион: {last.get('Регион_размещения_предприятия', 'Неизвестно')}"
        
        st.session_state.alert_active_until = now + pd.Timedelta(minutes=5)
        st.session_state.alert_text_cache = text
        return {"attack": True, "text": text}
    
    return {"attack": False, "text": "Событий не обнаружено"}

@st.cache_data(ttl=300)
def load_threats_from_db():
    try:
        qs = Threat.objects.all().values('threat_id', 'name')
        df = pd.DataFrame(list(qs))
        if df.empty:
            return pd.DataFrame(columns=['Код_угрозы', 'Название_угрозы'])
        
        df = df.rename(columns={
            'threat_id': 'Код_угрозы',
            'name': 'Название_угрозы'
        })
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки угроз: {e}")
        return pd.DataFrame(columns=['Код_угрозы', 'Название_угрозы'])
def get_latest_attack_info(df):
    now = pd.Timestamp.now()
    
    if "alert_active_until" in st.session_state and "alert_text_cache" in st.session_state:
        if st.session_state.alert_active_until and now < st.session_state.alert_active_until:
            return {"attack": True, "text": st.session_state.alert_text_cache}
        else:
            st.session_state.alert_active_until = None
            st.session_state.alert_text_cache = None

    if df.empty or 'Региональное_время' not in df.columns:
        return {"attack": False, "text": "Нет данных"}
    
    last_5_sec = df[df['Региональное_время'] > now - pd.Timedelta(seconds=5)]
    
    if len(last_5_sec) > 0:
        last = last_5_sec.iloc[-1]
        text = f"Прогнозируется атака! Тип: {last.get('Тип_предприятия', 'Неизвестно')}, Регион: {last.get('Регион_размещения_предприятия', 'Неизвестно')}"
        
        st.session_state.alert_active_until = now + pd.Timedelta(minutes=5)
        st.session_state.alert_text_cache = text
        return {"attack": True, "text": text}
    
    return {"attack": False, "text": "Событий не обнаружено"}

def safe_get(series, default=0):
    return series.iloc[0] if len(series) > 0 else default
def plot_industry_distribution(df):
    if 'Тип_предприятия' not in df.columns or df.empty:
        return None
    top = df['Тип_предприятия'].value_counts().head(10).reset_index()
    top.columns = ['Отрасль', 'Количество']
    fig = px.bar(top, x='Количество', y='Отрасль', orientation='h',
                 title='Топ-10 отраслей по числу инцидентов',
                 color='Количество', color_continuous_scale='Blues')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=400)
    return fig

def plot_region_distribution(df):
    if 'Регион_размещения_предприятия' not in df.columns or df.empty:
        return None
    top = df['Регион_размещения_предприятия'].value_counts().head(10).reset_index()
    top.columns = ['Регион', 'Количество']
    fig = px.bar(top, x='Количество', y='Регион', orientation='h',
                 title='Топ-10 регионов по числу инцидентов',
                 color='Количество', color_continuous_scale='Greens')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=400)
    return fig

def plot_success_rate_by_industry(df):
    if 'Тип_предприятия' not in df.columns or 'Успех' not in df.columns or df.empty:
        return None
    stats = df.groupby('Тип_предприятия')['Успех'].agg(['mean', 'count']).reset_index()
    stats = stats[stats['count'] >= 5]
    stats.columns = ['Отрасль', 'Успешность', 'Количество']
    stats['Успешность'] = stats['Успешность'] * 100
    
    fig = px.bar(stats, x='Отрасль', y='Успешность',
                 title='Доля успешных атак по отраслям (%)',
                 color='Успешность', color_continuous_scale='RdYlGn_r')
    fig.update_layout(xaxis_tickangle=-45, height=400)
    fig.update_yaxes(range=[0, 100], title='Успешность, %')
    return fig

def plot_threat_distribution(df, threats_df):
    if 'Код_реализованной_угрозы' not in df.columns or df.empty:
        return None
    
    df_merged = df.merge(
        threats_df[['Код_угрозы', 'Название_угрозы']],
        left_on='Код_реализованной_угрозы',
        right_on='Код_угрозы',
        how='left'
    )
    
    top = df_merged['Название_угрозы'].value_counts().head(10).reset_index()
    top.columns = ['Угроза', 'Количество']
    top['Угроза'] = top['Угроза'].fillna('Неизвестно')
    
    fig = px.bar(top, x='Количество', y='Угроза', orientation='h',
                 title='Топ-10 типов угроз',
                 color='Количество', color_continuous_scale='OrRd')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=400)
    return fig

def plot_attacks_by_hour(df):
    if 'час' not in df.columns or df.empty:
        return None
    hourly = df.groupby('час').size().reset_index(name='count')
    fig = px.line(hourly, x='час', y='count', markers=True,
                  title='Динамика атак по часам суток',
                  labels={'час': 'Час', 'count': 'Количество инцидентов'})
    fig.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=2), height=350)
    return fig

def plot_attacks_by_day(df):
    if 'день_недели' not in df.columns or df.empty:
        return None
    days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    daily = df.groupby('день_недели').size().reset_index(name='count')
    daily['День'] = daily['день_недели'].map(lambda x: days_ru[x])
    
    fig = px.bar(daily, x='День', y='count',
                 title='Распределение атак по дням недели',
                 color='count', color_continuous_scale='Purples')
    fig.update_layout(height=350)
    return fig

def plot_attacks_by_season(df):
    if 'сезон' not in df.columns or df.empty:
        return None
    seasonal = df.groupby('сезон').size().reset_index(name='count')
    season_order = ['Зима', 'Весна', 'Лето', 'Осень']
    seasonal = seasonal[seasonal['сезон'].isin(season_order)]
    
    fig = px.pie(seasonal, values='count', names='сезон',
                 title='Распределение атак по сезонам',
                 color='сезон', color_discrete_sequence=px.colors.sequential.RdBu)
    fig.update_layout(height=350)
    return fig

def plot_heatmap_hour_day(df):
    if 'час' not in df.columns or 'день_недели' not in df.columns or df.empty:
        return None
    
    days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    pivot = df.pivot_table(index='день_недели', columns='час', aggfunc='size', fill_value=0)
    pivot.index = pivot.index.map(lambda x: days_ru[x] if x in range(7) else x)
    
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot, cmap='YlOrRd', annot=False, ax=ax, cbar_kws={'label': 'Количество'})
    ax.set_title('Частота инцидентов: День недели × Час суток')
    ax.set_xlabel('Час суток')
    ax.set_ylabel('День недели')
    plt.tight_layout()
    return fig
def main():
    st.set_page_config(
        page_title="Аналитическая платформа ИБ",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("### Аналитическая платформа для отслеживания угроз информационной безопасности")
    
    incidents_df = load_incidents_from_db()
    threats_df = load_threats_from_db()
    
    with st.sidebar:
        st.header("Фильтры")
        
        df_filtered = incidents_df.copy()
        
        if not df_filtered.empty and 'Тип_предприятия' in df_filtered.columns:
            types = st.multiselect(
                "Тип предприятия",
                sorted(df_filtered['Тип_предприятия'].dropna().unique()),
                default=[]
            )
            if types:
                df_filtered = df_filtered[df_filtered['Тип_предприятия'].isin(types)]
        
        if not df_filtered.empty and 'Регион_размещения_предприятия' in df_filtered.columns:
            regions = st.multiselect(
                "Регион",
                sorted(df_filtered['Регион_размещения_предприятия'].dropna().unique()),
                default=[]
            )
            if regions:
                df_filtered = df_filtered[df_filtered['Регион_размещения_предприятия'].isin(regions)]
        
        if not df_filtered.empty and 'Успех' in df_filtered.columns:
            success_filter = st.radio(
                "Фильтр по успешности",
                ["Все", "Только успешные", "Только неудачные"],
                index=0
            )
            if success_filter == "Только успешные":
                df_filtered = df_filtered[df_filtered['Успех'] == 1]
            elif success_filter == "Только неудачные":
                df_filtered = df_filtered[df_filtered['Успех'] == 0]
    
    if "fake_alert_text" not in st.session_state:
        st.session_state.fake_alert_text = None
        
    attack_info = get_latest_attack_info(df_filtered)
    
    if st.session_state.fake_alert_text:
        attack_info = {"attack": True, "text": st.session_state.fake_alert_text}
        st.session_state.alert_active_until = datetime.now() + timedelta(minutes=5)
        st.session_state.alert_text_cache = st.session_state.fake_alert_text
        st.session_state.fake_alert_text = None

    audio_b64 = None
    if attack_info.get("attack") and tts_model:
        audio_b64 = generate_tts_audio(attack_info["text"], speaker="kseniya")

    attack_json = json.dumps(attack_info, ensure_ascii=False)

    components.html(f"""
    <!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ margin:0; background: linear-gradient(135deg, #0b0f1a 0%, #1a1f3a 100%); color: white; font-family: system-ui, sans-serif; overflow: hidden; }}
#waveContainer {{ position: relative; width: 100%; height: 180px; display: flex; align-items: center; justify-content: center; }}
canvas {{ width: 100%; height: 100%; display: block; }}
#text {{ position: absolute; bottom: 12px; left: 0; right: 0; text-align: center; font-size: 15px; color: #e5e7eb; text-shadow: 0 0 15px rgba(0,0,0,0.95); pointer-events: none; padding: 0 20px; }}
#text.active {{ color: #00f5ff; font-weight: 600; text-shadow: 0 0 20px rgba(0,245,255,0.8); }}
</style>
</head>
<body>
<div id="waveContainer">
<canvas id="waveCanvas"></canvas>
<div id="text">Ожидание данных...</div>
</div>
<audio id="alertAudio" autoplay></audio>

<script>
const canvas = document.getElementById('waveCanvas');
const ctx = canvas.getContext('2d');

let width, height, phase = 0;
let isSpeaking = false;
let currentAmp = 6;
let targetAmp = 6;

const attackData = {attack_json};
const audioB64 = "{audio_b64 or ''}";

function resize() {{
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  width = rect.width; height = rect.height;
}}
window.addEventListener('resize', resize);
resize();

function triggerAlert(text) {{
  const txtEl = document.getElementById("text");
  txtEl.innerText = text;
  txtEl.classList.add("active");

  if (audioB64) {{
    const audio = document.getElementById("alertAudio");
    audio.src = "data:audio/wav;base64," + audioB64;
    audio.onplay = () => {{ isSpeaking = true; targetAmp = 35; }};
    audio.onended = () => {{ isSpeaking = false; targetAmp = 6; }};
    audio.play().catch(() => {{}});
  }}
}}

function draw() {{
  ctx.clearRect(0, 0, width, height);
  currentAmp += (targetAmp - currentAmp) * 0.06;
  const amp = currentAmp;
  const w = width, h = height, points = 200;
  const step = w / points;
  const centerY = h / 2;

  const freq = isSpeaking ? 0.07 : 0.018;
  const speed = isSpeaking ? 0.35 : 0.05;
  const glow = isSpeaking ? 35 : 10;

  ctx.beginPath();
  for (let i = 0; i <= points; i++) {{
    const x = i * step;
    const y = centerY + amp * Math.sin(i * freq + phase);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }}
  ctx.strokeStyle = '#4b5563';
  ctx.lineWidth = isSpeaking ? 4 : 2.5;
  ctx.shadowBlur = glow;
  ctx.shadowColor = '#4b5563';
  ctx.stroke();
  ctx.shadowBlur = 0;

  ctx.beginPath();
  ctx.globalAlpha = 0.6;
  for (let i = 0; i <= points; i++) {{
    const x = i * step;
    const y = centerY + (amp * 0.8) * Math.sin(i * freq * 1.3 + phase * 1.3);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }}
  ctx.strokeStyle = '#ff2f92';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.globalAlpha = 1;

  phase += speed;
  requestAnimationFrame(draw);
}}

draw();
if (attackData && attackData.attack) {{ triggerAlert(attackData.text); }}
</script>
</body>
</html>
    """, height=200)

    tab1, tab2, tab3 = st.tabs(["Обзор", "Анализ инцидентов", "Временные паттерны"])

    with tab1:
        st.subheader("Сводная статистика")
        
        if df_filtered.empty:
            st.warning("Нет данных для отображения. Проверьте подключение к базе данных.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Всего инцидентов", f"{len(df_filtered):,}")
            with col2:
                st.metric("Угроз в базе", f"{len(threats_df):,}")
            with col3:
                n_types = df_filtered['Тип_предприятия'].nunique() if 'Тип_предприятия' in df_filtered.columns else 0
                st.metric("Типов предприятий", f"{n_types:,}")
            with col4:
                n_regions = df_filtered['Регион_размещения_предприятия'].nunique() if 'Регион_размещения_предприятия' in df_filtered.columns else 0
                st.metric("Регионов", f"{n_regions:,}")
            
            st.markdown("---")
            
            col5, col6, col7 = st.columns(3)
            with col5:
                if 'Успех' in df_filtered.columns:
                    success_rate = df_filtered['Успех'].mean() * 100
                    st.metric("Процент успешных атак", f"{success_rate:.1f}%")
            with col6:
                if 'Количество_хостов' in df_filtered.columns:
                    avg_hosts = df_filtered['Количество_хостов'].mean()
                    st.metric("Среднее количество хостов", f"{avg_hosts:,.0f}")
            with col7:
                if 'Код_реализованной_угрозы' in df_filtered.columns:
                    unique_threats = df_filtered['Код_реализованной_угрозы'].nunique()
                    st.metric("Уникальных угроз", f"{unique_threats:,}")
            
            st.markdown("---")
            with st.expander("Тест голосового оповещения"):
                fake_type = st.text_input("Введите тип угрозы для симуляции", "")
                if st.button("Отправить тестовое оповещение", type="primary"):
                    if fake_type.strip():
                        fake_text = f"Прогнозируется атака! Тип угрозы: {fake_type}, Регион: Тестовый"
                        st.session_state.fake_alert_text = fake_text
                        st.rerun()
                    else:
                        st.warning("Введите тип угрозы")

    with tab2:
        st.subheader("Детальный анализ инцидентов")
        
        if df_filtered.empty:
            st.info("Нет данных для анализа")
        else:
            col1, col2 = st.columns(2)
            with col1:
                fig = plot_industry_distribution(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = plot_region_distribution(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            col3, col4 = st.columns(2)
            with col3:
                fig = plot_success_rate_by_industry(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col4:
                fig = plot_threat_distribution(df_filtered, threats_df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Временные паттерны атак")
        
        if df_filtered.empty:
            st.info("Нет данных для анализа")
        else:
            col1, col2 = st.columns(2)
            with col1:
                fig = plot_attacks_by_hour(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = plot_attacks_by_day(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            
            col3, col4 = st.columns(2)
            with col3:
                fig = plot_attacks_by_season(df_filtered)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            with col4:
                fig = plot_heatmap_hour_day(df_filtered)
                if fig:
                    st.pyplot(fig, use_container_width=True)

if __name__ == "__main__":
    main()