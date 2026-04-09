import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import os
import json
import random
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Аналитическая платформа", layout="wide")
st.markdown("### Аналитическая платформа для отслеживания угроз ИБ")
st_autorefresh(interval=5000, key="refresh")

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

def get_latest_attack_info(df):
    now = pd.Timestamp.now()
    
    if "alert_active_until" in st.session_state and "alert_text_cache" in st.session_state:
        if st.session_state.alert_active_until and now < st.session_state.alert_active_until:
            return {"attack": True, "text": st.session_state.alert_text_cache}
        else:
            st.session_state.alert_active_until = None
            st.session_state.alert_text_cache = None

    if 'Дата инцидента' not in df.columns or len(df) == 0:
        return {"attack": False, "text": "Нет данных"}
    
    last_5_sec = df[df['Дата инцидента'] > now - pd.Timedelta(seconds=5)]
    
    if len(last_5_sec) > 0:
        last = last_5_sec.iloc[-1]
        text = f"Прогнозируется атака! Тип угрозы: {last.get('Тип предприятия', 'Неизвестно')}, Регион: {last.get('Регион размещения предприятия', 'Неизвестно')}"
        
        st.session_state.alert_active_until = now + pd.Timedelta(minutes=5)
        st.session_state.alert_text_cache = text
        
        return {"attack": True, "text": text}
        
    return {"attack": False, "text": "Событий не обнаружено"}

incidents, threats = load_data()

if 'Дата инцидента' in incidents.columns:
    incidents['Дата инцидента'] = pd.to_datetime(incidents['Дата инцидента'], errors='coerce')
    incidents['hour'] = incidents['Дата инцидента'].dt.hour
    incidents['day_of_week'] = incidents['Дата инцидента'].dt.day_name(locale='ru_RU')
    incidents['month'] = incidents['Дата инцидента'].dt.month_name(locale='ru_RU')

def get_season(month):
    if month in ['December', 'January', 'February']: return 'Зима'
    elif month in ['March', 'April', 'May']: return 'Весна'
    elif month in ['June', 'July', 'August']: return 'Лето'
    else: return 'Осень'

incidents['season'] = incidents['month'].apply(get_season)

with st.sidebar:
    st.header("Фильтры")
    df = incidents.copy()
    if 'Тип предприятия' in df.columns:
        types = st.multiselect("Тип предприятия", sorted(df['Тип предприятия'].dropna().unique()))
        if types: df = df[df['Тип предприятия'].isin(types)]
    if 'Регион размещения предприятия' in df.columns:
        regions = st.multiselect("Регион", sorted(df['Регион размещения предприятия'].dropna().unique()))
        if regions: df = df[df['Регион размещения предприятия'].isin(regions)]

tab1, tab2, tab3 = st.tabs(["Обзор", "Анализ инцидентов", "Паттерны по времени"])

with tab1:
    if "fake_alert_text" not in st.session_state:
        st.session_state.fake_alert_text = None
        
    attack_info = get_latest_attack_info(df)
    
    if st.session_state.fake_alert_text:
        attack_info = {"attack": True, "text": st.session_state.fake_alert_text}
        st.session_state.alert_active_until = pd.Timestamp.now() + pd.Timedelta(minutes=5)
        st.session_state.alert_text_cache = st.session_state.fake_alert_text
        st.session_state.fake_alert_text = None

    attack_json = json.dumps(attack_info, ensure_ascii=False)
    
    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ margin:0; background: #0b0f1a; color: white; font-family: system-ui, sans-serif; overflow: hidden; }}
        #waveContainer {{ position: relative; width: 100%; height: 160px; display: flex; align-items: center; justify-content: center; }}
        canvas {{ width: 100%; height: 100%; display: block; }}
        #text {{ position: absolute; bottom: 12px; left: 0; right: 0; text-align: center; font-size: 15px; color: #e5e7eb; text-shadow: 0 0 12px rgba(0,0,0,0.9); pointer-events: none; letter-spacing: 0.5px; padding: 0 20px; box-sizing: border-box; transition: color 0.3s, opacity 0.3s; }}
        #text.active {{ color: #00e5ff; font-weight: 500; }}
      </style>
    </head>
    <body>
      <div id="waveContainer">
        <canvas id="waveCanvas"></canvas>
        <div id="text">Ожидание данных...</div>
      </div>
      <script>
        const canvas = document.getElementById('waveCanvas');
        const ctx = canvas.getContext('2d');
        let width, height, phase = 0;
        
        let alertEndTime = 0;
        let isAlertActive = false;
        let isSpeaking = false;
        const attackData = {attack_json};

        function resize() {{
          const dpr = window.devicePixelRatio || 1;
          const rect = canvas.getBoundingClientRect();
          canvas.width = rect.width * dpr;
          canvas.height = rect.height * dpr;
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          width = rect.width;
          height = rect.height;
        }}
        window.addEventListener('resize', resize);
        resize();

        function triggerAlert(text) {{
          if (!text || text === "Ожидание данных...") return;
          
          const txtEl = document.getElementById("text");
          txtEl.innerText = text;
          txtEl.classList.add("active");

          alertEndTime = Date.now() + 300000;
          isAlertActive = true;
          isSpeaking = true;

          const msg = new SpeechSynthesisUtterance(text);
          msg.lang = 'ru-RU';
          msg.rate = 1.05;
          
          msg.onend = () => {{ 
            isSpeaking = false;
          }};
          msg.onerror = () => {{ 
            isSpeaking = false; 
          }};
          speechSynthesis.speak(msg);
        }}

        function checkAlertStatus() {{
            const now = Date.now();
            if (isAlertActive && now >= alertEndTime) {{
                isAlertActive = false;
                isSpeaking = false;
                const txtEl = document.getElementById("text");
                txtEl.classList.remove("active");
                txtEl.innerText = "Ожидание данных...";
            }}
        }}

        function draw() {{
          checkAlertStatus();

          ctx.clearRect(0, 0, width, height);
          const w = width;
          const h = height;
          const points = 200;
          const step = w / points;
          const centerY = h / 2;

          const baseColor = '#4b5563';
          const secondaryColor = '#ff2f92';
          
          const baseAmp = 5;
          const speakingAmp = 30;
          
          let currentAmp = isSpeaking ? speakingAmp : baseAmp;
          
          if (isSpeaking) {{
             currentAmp *= (0.5 + 0.5 * Math.sin(phase * 2.2)); 
          }}
          
          const frequency = isSpeaking ? 0.05 : 0.015;
          const speed = isSpeaking ? 0.25 : 0.04;
          const glowSize = isSpeaking ? 25 : 8;

          ctx.beginPath();
          for (let i = 0; i <= points; i++) {{
            const x = i * step;
            const y = centerY + currentAmp * Math.sin(i * frequency + phase);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          }}
          ctx.strokeStyle = baseColor;
          ctx.lineWidth = isSpeaking ? 3 : 2;
          ctx.shadowBlur = glowSize;
          ctx.shadowColor = baseColor;
          ctx.stroke();
          ctx.shadowBlur = 0;

          ctx.beginPath();
          ctx.globalAlpha = 0.4;
          for (let i = 0; i <= points; i++) {{
            const x = i * step;
            const y = centerY + (currentAmp * 0.7) * Math.sin(i * frequency * 1.4 + phase * 1.3);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          }}
          ctx.strokeStyle = secondaryColor;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.globalAlpha = 1;

          phase += speed;
          requestAnimationFrame(draw);
        }}
        
        draw();

        if (attackData && attackData.attack) {{
            triggerAlert(attackData.text);
        }}
      </script>
    </body>
    </html>
    """, height=200)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего инцидентов", f"{len(df):,}")
    col2.metric("Угроз из ФСТЭК", len(threats))
    col3.metric("Типов предприятий", df['Тип предприятия'].nunique() if 'Тип предприятия' in df.columns else 0)
    col4.metric("Регионов", df['Регион размещения предприятия'].nunique() if 'Регион размещения предприятия' in df.columns else 0)
    
    st.subheader("Распределение инцидентов по типам предприятий")
    if 'Тип предприятия' in df.columns:
        type_counts = df['Тип предприятия'].value_counts().head(10).reset_index()
        type_counts.columns = ['Тип предприятия', 'Количество']
        fig = px.bar(type_counts, x='Тип предприятия', y='Количество', title="Топ-10 типов предприятий по количеству инцидентов")
        st.plotly_chart(fig, use_container_width=True)
        
    st.subheader("Фейковое оповещение")
    fake_type = st.text_input("Введите тип угрозы для оповещения", "")
    if st.button("Отправить оповещение", type="primary"):
        if fake_type.strip():
            fake_text = f"Прогнозируется атака! Тип угрозы: {fake_type}, Регион: Симулированный"
            st.session_state.fake_alert_text = fake_text
            st.session_state.alert_active_until = pd.Timestamp.now() + pd.Timedelta(minutes=5)
            st.session_state.alert_text_cache = fake_text
            st.rerun()
        else:
            st.warning("Введите тип угрозы")

with tab2:
    st.subheader("Данные об инцидентах")
    st.dataframe(df.head(30), use_container_width=True)

with tab3:
    st.subheader("Паттерны атак по времени суток, дню недели и сезону")
    if 'hour' in df.columns and len(df) > 0:
        col_a, col_b = st.columns(2)
        with col_a:
            pivot = df.pivot_table(index='day_of_week', columns='hour', aggfunc='size', fill_value=0)
            fig, ax = plt.subplots(figsize=(12, 7))
            sns.heatmap(pivot, cmap="Reds", annot=False, ax=ax)
            plt.title("Частота инцидентов: День недели × Час суток")
            plt.xlabel("Час суток")
            plt.ylabel("День недели")
            st.pyplot(fig)
        with col_b:
            hourly = df.groupby('hour').size().reset_index(name='count')
            fig2 = px.bar(hourly, x='hour', y='count', title="Количество инцидентов по часам суток", labels={'hour': 'Час суток', 'count': 'Количество'})
            st.plotly_chart(fig2, use_container_width=True)
        seasonal = df.groupby('season').size().reset_index(name='count')
        fig3 = px.bar(seasonal, x='season', y='count', title="Распределение инцидентов по сезонам", labels={'season': 'Сезон', 'count': 'Количество'})
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.warning("Не удалось извлечь временные данные из столбца 'Дата инцидента'.")

if "live_incidents" not in st.session_state:
    st.session_state.live_incidents = incidents.copy()
if "live_threats" not in st.session_state:
    st.session_state.live_threats = threats.copy()
if "bottom_active_tab" not in st.session_state:
    st.session_state.bottom_active_tab = -1

def add_random_rows(df, template_df, max_rows=2):
    if template_df.empty: return df
    n_add = random.randint(0, max_rows)
    if n_add == 0: return df
    
    new_rows = []
    cols = template_df.columns
    for _ in range(n_add):
        row = {}
        for c in cols:
            if c == 'Дата инцидента':
                row[c] = pd.Timestamp.now()
            elif template_df[c].dtype in ['object', 'category', 'string']:
                vals = template_df[c].dropna().unique()
                row[c] = random.choice(vals) if len(vals) > 0 else "Неизвестно"
            elif pd.api.types.is_numeric_dtype(template_df[c]):
                vals = template_df[c].dropna()
                row[c] = float(random.choice(vals)) if len(vals) > 0 else 0.0
            else:
                row[c] = None
        new_rows.append(row)
    return pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

if random.random() < 0.45:
    st.session_state.live_incidents = add_random_rows(st.session_state.live_incidents, incidents, 1)
if not threats.empty and random.random() < 0.35:
    st.session_state.live_threats = add_random_rows(st.session_state.live_threats, threats, 1)

payload = {
    "incidents": st.session_state.live_incidents.tail(100).to_dict(orient='records'),
    "threats": st.session_state.live_threats.tail(100).to_dict(orient='records'),
    "active_tab": st.session_state.bottom_active_tab
}
payload_str = json.dumps(payload, default=str, ensure_ascii=False)

components.html(f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; font-family: system-ui, -apple-system, sans-serif; background: transparent; }}
  .tabs-wrapper {{ display: flex; background: #0b0f1a; border-top: 2px solid #374151; }}
  .tab-btn {{ flex: 1; padding: 14px; background: #111827; color: #9ca3af; border: none; border-top: 2px solid #374151; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; }}
  .tab-btn:hover {{ background: #1f2937; color: #e5e7eb; }}
  .tab-btn.active {{ background: #0f172a; color: #38bdf8; border-top-color: #38bdf8; }}
  .slide-panel {{ display: none; background: #0b0f1a; border-top: 1px solid #374151; max-height: 340px; overflow: hidden; }}
  .slide-panel.open {{ display: block; }}
  .panel-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: #111827; color: #f3f4f6; border-bottom: 1px solid #1f2937; flex-shrink: 0; }}
  .close-btn {{ background: #ef4444; border: none; color: white; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; }}
  .table-container {{ max-height: 280px; overflow: auto; padding: 0; }}
  table {{ width: 100%; border-collapse: collapse; color: #d1d5db; font-size: 12px; }}
  th, td {{ padding: 9px 12px; border-bottom: 1px solid #1f2937; text-align: left; white-space: nowrap; }}
  th {{ background: #0f172a; color: #38bdf8; position: sticky; top: 0; font-weight: 600; z-index: 1; }}
  tr:hover {{ background: #1e293b; }}
  .empty-msg {{ padding: 40px; text-align: center; color: #6b7280; }}
</style>
</head>
<body>
<div class="tabs-wrapper">
  <button class="tab-btn active" id="t0" onclick="setTab(0)">📊 Инциденты (Live)</button>
  <button class="tab-btn" id="t1" onclick="setTab(1)">⚠️ Угрозы (Live)</button>
</div>
<div class="slide-panel" id="panel">
  <div class="panel-header">
    <span id="pTitle">Живая таблица</span>
    <button class="close-btn" onclick="setTab(-1)">✕</button>
  </div>
  <div class="table-container" id="tCont">
    <table id="tData"></table>
  </div>
</div>
<script>
(function() {{
  const DATA = {payload_str};
  let curTab = -1;
  function setTab(idx) {{
    curTab = idx;
    const t0 = document.getElementById('t0');
    const t1 = document.getElementById('t1');
    const panel = document.getElementById('panel');
    t0.classList.toggle('active', idx === 0);
    t1.classList.toggle('active', idx === 1);
    if (idx === -1) {{
      panel.classList.remove('open');
      return;
    }}
    document.getElementById('pTitle').innerText = idx === 0 ? 'Живая таблица инцидентов' : 'Живая таблица угроз ФСТЭК';
    render(idx === 0 ? DATA.incidents : DATA.threats);
    panel.classList.add('open');
  }}
  function render(data) {{
    const table = document.getElementById('tData');
    if (!data || data.length === 0) {{
      table.innerHTML = '<div class="empty-msg">Нет данных</div>';
      return;
    }}
    const headers = Object.keys(data[0]);
    let html = '<thead><tr>' + headers.map(h => `<th>${{h}}</th>`).join('') + '</tr></thead>';
    html += '<tbody>' + data.map(row => '<tr>' + headers.map(h => `<td>${{row[h] !== null && row[h] !== undefined ? row[h] : ''}}</td>`).join('') + '</tr>').join('') + '</tbody>';
    table.innerHTML = html;
    const container = document.getElementById('tCont');
    container.scrollTop = container.scrollHeight;
  }}
  window.setTab = setTab;
}})();
</script>
</body>
</html>
""", height=400)

st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)