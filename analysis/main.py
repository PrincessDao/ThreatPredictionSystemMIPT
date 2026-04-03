import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import xgboost as xgb
import shap

def load_incidents(file_path):
    df = pd.read_excel(file_path, sheet_name='Sheet1')
    df.columns = df.columns.str.strip().str.replace(' ', '_')
    df['Дата_инцидента'] = pd.to_datetime(df['Дата_инцидента'], dayfirst=True)
    df['Региональное_время'] = pd.to_datetime(df['Региональное_время'], dayfirst=True)
    df['час'] = df['Региональное_время'].dt.hour
    df['день_недели'] = df['Региональное_время'].dt.dayofweek
    df['месяц'] = df['Региональное_время'].dt.month
    
    def get_season(month):
        if month in [12, 1, 2]:
            return 'зима'
        elif month in [3, 4, 5]:
            return 'весна'
        elif month in [6, 7, 8]:
            return 'лето'
        else:
            return 'осень'
    df['сезон'] = df['месяц'].apply(get_season)
    return df

def load_threats(file_path):
    df = pd.read_excel(file_path, sheet_name='Sheet', header=1)
    df = df[['Идентификатор УБИ', 'Наименование УБИ']].copy()
    df['Идентификатор_целое'] = df['Идентификатор УБИ'].astype(str).str.split('.').str[0].astype(int)
    df = df.rename(columns={'Идентификатор_целое': 'Код_угрозы', 'Наименование УБИ': 'Название_угрозы'})
    return df

def merge_data(incidents, threats):
    df = incidents.merge(threats, left_on='Код_реализованной_угрозы', right_on='Код_угрозы', how='left')
    return df

incidents_df = load_incidents('incidents_2000.xlsx')
threats_df = load_threats('Файл с сайта ФСТЭК.xlsx')
df = merge_data(incidents_df, threats_df)

print("=== Общая статистика ===")
print(f"Всего инцидентов: {len(df)}")
print(f"Успешных атак: {df['Успех'].sum()}")
print(f"Процент успешных: {df['Успех'].mean()*100:.2f}%")

plt.style.use('ggplot')

plt.figure(figsize=(12,6))
top_industries = df['Тип_предприятия'].value_counts().head(10)
top_industries.plot(kind='bar')
plt.title('Топ-10 отраслей по числу инцидентов')
plt.xlabel('Отрасль')
plt.ylabel('Количество инцидентов')
plt.tight_layout()
plt.savefig('fig_industries.png')
plt.close()

plt.figure(figsize=(12,6))
top_regions = df['Регион_размещения_предприятия'].value_counts().head(10)
top_regions.plot(kind='bar')
plt.title('Топ-10 регионов по числу инцидентов')
plt.xlabel('Регион')
plt.ylabel('Количество инцидентов')
plt.tight_layout()
plt.savefig('fig_regions.png')
plt.close()

fig, axes = plt.subplots(2,2, figsize=(14,10))

hour_success = df.groupby('час')['Успех'].mean()
hour_counts = df['час'].value_counts().sort_index()
axes[0,0].bar(hour_success.index, hour_success.values)
axes[0,0].set_title('Успешность атак по часам суток')
axes[0,0].set_xlabel('Час')
axes[0,0].set_ylabel('Доля успешных')

dow_success = df.groupby('день_недели')['Успех'].mean()
axes[0,1].bar(dow_success.index, dow_success.values)
axes[0,1].set_title('Успешность атак по дням недели')
axes[0,1].set_xlabel('День недели (0=пн)')
axes[0,1].set_ylabel('Доля успешных')

month_success = df.groupby('месяц')['Успех'].mean()
axes[1,0].bar(month_success.index, month_success.values)
axes[1,0].set_title('Успешность атак по месяцам')
axes[1,0].set_xlabel('Месяц')
axes[1,0].set_ylabel('Доля успешных')

season_success = df.groupby('сезон')['Успех'].mean()
axes[1,1].bar(season_success.index, season_success.values)
axes[1,1].set_title('Успешность атак по сезонам')
axes[1,1].set_xlabel('Сезон')
axes[1,1].set_ylabel('Доля успешных')

plt.tight_layout()
plt.savefig('fig_temporal_patterns.png')
plt.close()

print("\n=== Временные паттерны ===")
print("Пиковые часы успешности:", hour_success.idxmax(), "с долей", hour_success.max())
print("Наиболее опасный день недели (0=пн):", dow_success.idxmax())
print("Наиболее опасный месяц:", month_success.idxmax())
print("Наиболее опасный сезон:", season_success.idxmax())

cat_cols = ['Тип_предприятия', 'Регион_размещения_предприятия', 'сезон']
num_cols = ['Количество_хостов', 'час', 'день_недели', 'месяц']

label_encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col + '_enc'] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

feature_cols = num_cols + [col + '_enc' for col in cat_cols]
X = df[feature_cols].copy()
y_success = df['Успех'].values
y_threat = df['Код_реализованной_угрозы'].values

scaler = StandardScaler()
X[num_cols] = scaler.fit_transform(X[num_cols])

X_train, X_test, y_train, y_test = train_test_split(X, y_success, test_size=0.2, random_state=42, stratify=y_success)

model_success = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1,
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss'
)
model_success.fit(X_train, y_train)

y_pred = model_success.predict(X_test)
print("\n=== Модель предсказания успешности атаки ===")
print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
print(classification_report(y_test, y_pred))

explainer = shap.TreeExplainer(model_success)
shap_values = explainer.shap_values(X_test)

plt.figure(figsize=(10,6))
shap.summary_plot(shap_values, X_test, feature_names=feature_cols, show=False)
plt.tight_layout()
plt.savefig('fig_shap_summary.png')
plt.close()

plt.figure(figsize=(10,6))
xgb.plot_importance(model_success, importance_type='weight', ax=plt.gca())
plt.title('Важность признаков (XGBoost)')
plt.tight_layout()
plt.savefig('fig_feature_importance.png')
plt.close()

top_threats = df['Код_реализованной_угрозы'].value_counts().head(10).index
df_threat_subset = df[df['Код_реализованной_угрозы'].isin(top_threats)].copy()
X_threat = df_threat_subset[feature_cols].copy()
X_threat[num_cols] = scaler.transform(X_threat[num_cols])  # используем тот же scaler
y_threat_subset = df_threat_subset['Код_реализованной_угрозы'].values

X_train_t, X_test_t, y_train_t, y_test_t = train_test_split(
    X_threat, y_threat_subset, test_size=0.2, random_state=42, stratify=y_threat_subset
)

from sklearn.preprocessing import LabelEncoder
le_threat = LabelEncoder()
y_train_t_enc = le_threat.fit_transform(y_train_t)
y_test_t_enc = le_threat.transform(y_test_t)

model_threat = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    random_state=42,
    use_label_encoder=False,
    eval_metric='mlogloss'
)
model_threat.fit(X_train_t, y_train_t_enc)

y_pred_enc = model_threat.predict(X_test_t)
y_pred = le_threat.inverse_transform(y_pred_enc)
print("\n=== Модель предсказания типа угрозы (топ-10) ===")
print(f"Accuracy: {accuracy_score(y_test_t, y_pred):.4f}")
print(classification_report(y_test_t, y_pred))

print("\n=== Анализ уязвимых мест ===")

industry_success = df.groupby('Тип_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
print("\nТоп-5 отраслей с наибольшей долей успешных атак:")
print(industry_success.head(5))

region_success = df.groupby('Регион_размещения_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
print("\nТоп-5 регионов с наибольшей долей успешных атак:")
print(region_success.head(5))

top_threat_names = df['Название_угрозы'].value_counts().head(10)
print("\nТоп-10 наиболее часто реализуемых угроз:")
print(top_threat_names)

threat_success = df.groupby('Название_угрозы')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
print("\nУгрозы с наибольшей долей успеха (min 10 инцидентов):")
threat_success_filtered = threat_success[threat_success['count'] >= 10].head(10)
print(threat_success_filtered)

print("\n=== Рекомендации по усилению защиты ===")

print(f"1. Временная защита: усилить мониторинг в {hour_success.idxmax()}:00, по {dow_success.idxmax()}-му дню недели и в {month_success.idxmax()}-м месяце.")
print(f"2. Отраслевая защита: особое внимание уделить отраслям {industry_success.head(3).index.tolist()}.")
print(f"3. Региональная защита: повышенный контроль в регионах {region_success.head(3).index.tolist()}.")
print(f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {threat_success_filtered.head(5).index.tolist()}.")

top_features = pd.Series(model_success.feature_importances_, index=feature_cols).sort_values(ascending=False)
print(f"\n5. Ключевые факторы успешной атаки (важность): {top_features.head(3).to_dict()}")
print("   Рекомендуется усилить контроль по этим направлениям (например, для отрасли – провести аудит, для региона – установить дополнительные средства защиты).")

print("\n6. Архитектура безопасности: внедрить систему раннего предупреждения на основе предложенных моделей. Использовать SHAP-анализ для динамической корректировки политик безопасности.")

with open('report.txt', 'w', encoding='utf-8') as f:
    f.write("=== Отчет по анализу угроз информационной безопасности ===\n\n")
    f.write(f"Всего инцидентов: {len(df)}\n")
    f.write(f"Успешных атак: {df['Успех'].sum()}\n\n")
    f.write("=== Рекомендации ===\n")
    f.write(f"1. Временная защита: усилить мониторинг в {hour_success.idxmax()}:00, по {dow_success.idxmax()}-му дню недели и в {month_success.idxmax()}-м месяце.\n")
    f.write(f"2. Отраслевая защита: особое внимание уделить отраслям {industry_success.head(3).index.tolist()}.\n")
    f.write(f"3. Региональная защита: повышенный контроль в регионах {region_success.head(3).index.tolist()}.\n")
    f.write(f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {threat_success_filtered.head(5).index.tolist()}.\n")
    f.write(f"5. Ключевые факторы успешной атаки: {top_features.head(3).to_dict()}\n")
    f.write("6. Архитектура безопасности: внедрить систему раннего предупреждения на основе предложенных моделей.\n")

print("\nАнализ завершен. Результаты сохранены в файлы: report.txt, а также изображения в текущей папке.")
