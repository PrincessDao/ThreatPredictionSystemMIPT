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
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, top_k_accuracy_score
import joblib
from pathlib import Path
import os

# Модули
import data_loader
import features
import clustering
import models
import reporting

os.environ["LOKY_MAX_CPU_COUNT"] = "4"
ARTIFACTS_DIR = Path("../artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)

# 1. Загрузка
incidents_df = data_loader.load_incidents()
threats_df = data_loader.load_threats()
df = data_loader.merge_data(incidents_df, threats_df)

df['is_weekend'] = df['день_недели'].isin([5, 6]).astype(int)
df['night_attack'] = ((df['час'] >= 22) | (df['час'] <= 5)).astype(int)
df['working_hours'] = df['час'].between(9, 18).astype(int)
df['region_freq'] = df.groupby('Регион_размещения_предприятия')['Регион_размещения_предприятия'].transform('count')
df['industry_freq'] = df.groupby('Тип_предприятия')['Тип_предприятия'].transform('count')
df['threat_freq'] = df.groupby('Код_реализованной_угрозы')['Код_реализованной_угрозы'].transform('count')
df['region_industry'] = df['Регион_размещения_предприятия'].astype(str) + "_" + df['Тип_предприятия'].astype(str)
df['industry_threat'] = df['Тип_предприятия'].astype(str) + "_" + df['Код_реализованной_угрозы'].astype(str)
df['hour_sin'] = np.sin(2 * np.pi * df['час'] / 24.0)
df['hour_cos'] = np.cos(2 * np.pi * df['час'] / 24.0)
df['dow_sin'] = np.sin(2 * np.pi * df['день_недели'] / 7.0)
df['dow_cos'] = np.cos(2 * np.pi * df['день_недели'] / 7.0)
df['month_sin'] = np.sin(2 * np.pi * df['месяц'] / 12.0)
df['month_cos'] = np.cos(2 * np.pi * df['месяц'] / 12.0)

print("=== Общая статистика ===")
print(f"Всего инцидентов: {len(df)}")
print(f"Успешных атак: {df['Успех'].sum()}")
print(f"Процент успешных: {df['Успех'].mean()*100:.2f}%")

# 2. EDA
hour_success, dow_success, month_success, season_success = features.run_full_eda(df, ARTIFACTS_DIR)

print("\n=== Временные паттерны ===")
print(f"Пиковые часы успешности: {hour_success.idxmax()}:00 с долей {hour_success.max():.2f}")
print(f"Наиболее опасный день недели (0=пн): {dow_success.idxmax()}")
print(f"Наиболее опасный месяц: {month_success.idxmax()}")
print(f"Наиболее опасный сезон: {season_success.idxmax()}")

# Тепловая карта: успешность по часам и дням недели
hour_dow_success = df.groupby(['день_недели', 'час'])['Успех'].mean().unstack()

plt.figure(figsize=(12, 8))
sns.heatmap(hour_dow_success, cmap='YlOrRd', annot=True, fmt='.2f', 
            linewidths=.5, cbar_kws={'label': 'Доля успешных атак'})
plt.title('Успешность атак по дням недели и часам')
plt.xlabel('Час суток')
plt.ylabel('День недели (0=пн, 6=вс)')
plt.tight_layout()
plt.savefig(ARTIFACTS_DIR / 'fig_heatmap_hour_dow.png', dpi=300)
plt.close()

# Тепловая карта: успешность по месяцам и сезонам
month_season_success = df.groupby(['сезон', 'месяц'])['Успех'].mean().unstack()
month_order = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
month_season_success = month_season_success[month_order]

plt.figure(figsize=(10, 6))
sns.heatmap(month_season_success, cmap='YlOrRd', annot=True, fmt='.2f',
            linewidths=.5, cbar_kws={'label': 'Доля успешных атак'})
plt.title('Успешность атак по месяцам и сезонам')
plt.xlabel('Месяц')
plt.ylabel('Сезон')
plt.tight_layout()
plt.savefig(ARTIFACTS_DIR / 'fig_heatmap_month_season.png', dpi=300)
plt.close()

top_10_threats = df['Код_реализованной_угрозы'].value_counts().head(10).index
top_10_industries = df['Тип_предприятия'].value_counts().head(10).index

df_subset = df[(df['Код_реализованной_угрозы'].isin(top_10_threats)) & 
               (df['Тип_предприятия'].isin(top_10_industries))]

threat_industry_matrix = pd.crosstab(df_subset['Тип_предприятия'], 
                                      df_subset['Код_реализованной_угрозы'])

plt.figure(figsize=(14, 10))
sns.heatmap(threat_industry_matrix, cmap='YlGnBu', annot=True, fmt='d',
            linewidths=.5, cbar_kws={'label': 'Количество инцидентов'})
plt.title('Распределение угроз по отраслям (Топ-10)')
plt.xlabel('Код угрозы')
plt.ylabel('Отрасль')
plt.tight_layout()
plt.savefig(ARTIFACTS_DIR / 'fig_heatmap_threats_industries.png', dpi=300)
plt.close()

# 3. Кластеризация
cat_cols = ['Тип_предприятия', 'Регион_размещения_предприятия', 'сезон', 'region_industry', 'industry_threat']
num_cols = ['Количество_хостов', 'час', 'день_недели', 'месяц']
label_encoders = {}
for col in cat_cols:
    le = LabelEncoder()
    df[col + '_enc'] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = le

cluster_features = num_cols + [col + '_enc' for col in cat_cols]
df, kmeans, scaler_cluster, best_k, cluster_profile = clustering.run_clustering_process(df, cluster_features, num_cols, ARTIFACTS_DIR)

print(f"\nОптимальное число кластеров по силуэту: {best_k}")
print("\nПрофили кластеров (средние значения):")
print(cluster_profile)

# 4. Модели
df_model = df.copy()
cat_features_ohe = ['Тип_предприятия', 'Регион_размещения_предприятия', 'сезон']
df_model = pd.get_dummies(df_model, columns=cat_features_ohe, drop_first=True)
exclude_cols = ['Дата_инцидента', 'Региональное_время', 'Код_реализованной_угрозы', 'Название_угрозы', 'Код_угрозы', 'Идентификатор УБИ', 'Наименование УБИ', 'region_industry', 'industry_threat', 'pca1', 'pca2'] + [col + '_enc' for col in cat_cols]
feature_cols_base = [c for c in df_model.columns if c not in exclude_cols and c != 'Успех' and df_model[c].dtype in ['int64', 'float64', 'bool', 'uint8']]

# Успешность
model_final, acc_b, acc_final, selected_features, y_test, y_pred_final, imp_final = models.train_success_models(df_model, df_model[feature_cols_base], df_model['Успех'].values, feature_cols_base, ARTIFACTS_DIR)

print("\n=== Сравнение моделей предсказания успешности атаки ===")
print(f"Точность baseline (все признаки): {acc_b:.4f}")
print(f"Точность final (баланс + отбор признаков): {acc_final:.4f}")
print("Улучшение на {:.4f}".format(acc_final - acc_b))
print("\nClassification report (final model):")
print(classification_report(y_test, y_pred_final))

# Тип угрозы
model_threat_e, acc_threat_b, acc_threat_e, top3_acc, le_threat, X_test_tb, y_test_t = models.train_threat_models(df_model, feature_cols_base)

print("\n=== Сравнение моделей предсказания типа угрозы (топ-10) ===")
print(f"Точность baseline (базовая): {acc_threat_b:.4f}")
print(f"Точность improved (баланс + регуляризация): {acc_threat_e:.4f}")
print("Улучшение на {:.4f}".format(acc_threat_e - acc_threat_b))
print(f"Top-3 точность: {top3_acc:.4f}")
print("\nClassification report (improved threat model):")
print(classification_report(y_test_t, model_threat_e.predict(X_test_tb), target_names=le_threat.classes_.astype(str)))

# 5. Анализ и отчет
industry_success, region_success, threat_success_filtered = reporting.run_vulnerability_analysis(df, imp_final, None)
cluster_risk = df.groupby('cluster')['Успех'].mean().sort_values(ascending=False)

print("\n=== Анализ уязвимых мест ===")
print("\nТоп-5 отраслей с наибольшей долей успешных атак:\n", industry_success.head(5))
print("\nТоп-5 регионов с наибольшей долей успешных атак:\n", region_success.head(5))
print("\nУгрозы с наибольшей долей успеха (min 10 инцидентов):\n", threat_success_filtered)
print("\nРиск по кластерам (доля успешных атак):\n", cluster_risk)

print("\n=== Рекомендации по усилению защиты ===")
print(f"1. Временная защита: усилить мониторинг в {hour_success.idxmax()}:00, по {dow_success.idxmax()}-му дню недели и в {month_success.idxmax()}-м месяце.")
print(f"2. Отраслевая защита: особое внимание уделить отраслям {industry_success.head(3).index.tolist()}.")
print(f"3. Региональная защита: повышенный контроль в регионах {region_success.head(3).index.tolist()}.")
print(f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {threat_success_filtered.head(5).index.tolist()}.")
print(f"5. Кластеры высокого риска: кластеры {cluster_risk.head(2).index.tolist()} требуют немедленного внимания.")
print(f"\n6. Ключевые факторы успешной атаки (важность): {imp_final.head(3).to_dict()}")
print("7. Архитектура безопасности: внедрить систему раннего предупреждения.")

reporting.write_final_report(df, best_k, acc_b, acc_final, acc_threat_b, acc_threat_e, top3_acc, hour_success, dow_success, month_success, industry_success, region_success, threat_success_filtered, cluster_risk, imp_final, ARTIFACTS_DIR)

joblib.dump(model_final, ARTIFACTS_DIR / 'model_success_improved.pkl')
joblib.dump(selected_features, ARTIFACTS_DIR / 'feature_columns.pkl')
joblib.dump(model_threat_e, ARTIFACTS_DIR / 'model_threat_improved.pkl')
joblib.dump(scaler_cluster, ARTIFACTS_DIR / 'scaler_cluster.pkl')
joblib.dump(kmeans, ARTIFACTS_DIR / 'kmeans_model.pkl')
joblib.dump(label_encoders, ARTIFACTS_DIR / 'label_encoders.pkl')
joblib.dump(le_threat, ARTIFACTS_DIR / 'label_encoder_threat.pkl')

print("\nАнализ завершен. Результаты сохранены.")
