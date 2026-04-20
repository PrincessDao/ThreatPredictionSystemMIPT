import joblib
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

ARTIFACTS_DIR = Path("../artifacts")

# ------------------------------------------------------------
# 1. Загрузка моделей и артефактов
# ------------------------------------------------------------
model_success = joblib.load(ARTIFACTS_DIR / 'model_success_improved.pkl')
model_threat  = joblib.load(ARTIFACTS_DIR / 'model_threat_improved.pkl')
le_threat     = joblib.load(ARTIFACTS_DIR / 'label_encoder_threat.pkl')
kmeans        = joblib.load(ARTIFACTS_DIR / 'kmeans_model.pkl')
scaler_cluster= joblib.load(ARTIFACTS_DIR / 'scaler_cluster.pkl')
label_encoders= joblib.load(ARTIFACTS_DIR / 'label_encoders.pkl')

# ------------------------------------------------------------
# 2. Загрузка данных из таблицы
# ------------------------------------------------------------
DATA_PATH = Path("../../data/incidents_2000.xlsx")
df = pd.read_excel(DATA_PATH)
df.columns = df.columns.str.strip().str.replace(' ', '_')

if 'Региональное_время' in df.columns:
    df['Региональное_время'] = pd.to_datetime(df['Региональное_время'], dayfirst=True, errors='coerce')
else:
    df['Региональное_время'] = pd.to_datetime("2024-08-12 11:00:00")

df['час'] = df['Региональное_время'].dt.hour
df['день_недели'] = df['Региональное_время'].dt.dayofweek
df['месяц'] = df['Региональное_время'].dt.month

df['час'] = df['час'].fillna(0).astype(int)
df['день_недели'] = df['день_недели'].fillna(0).astype(int)
df['месяц'] = df['месяц'].fillna(1).astype(int)

def get_season(m):
    if m in [12,1,2]: return 'зима'
    if m in [3,4,5]: return 'весна'
    if m in [6,7,8]: return 'лето'
    return 'осень'
df['сезон'] = df['месяц'].apply(get_season)

df['_orig_region'] = df['Регион_размещения_предприятия'].copy()
df['_orig_industry'] = df['Тип_предприятия'].copy()
df['_orig_hour'] = df['час'].copy()
df['_orig_day'] = df['день_недели'].copy()

# ------------------------------------------------------------
# 3. Feature engineering
# ------------------------------------------------------------
df['is_weekend'] = df['день_недели'].isin([5, 6]).astype(int)
df['night_attack'] = ((df['час'] >= 22) | (df['час'] <= 5)).astype(int)
df['working_hours'] = df['час'].between(9, 18).astype(int)

df['region_freq'] = df.groupby('Регион_размещения_предприятия')['Регион_размещения_предприятия'].transform('count')
df['industry_freq'] = df.groupby('Тип_предприятия')['Тип_предприятия'].transform('count')
df['threat_freq'] = 0

df['region_industry'] = df['Регион_размещения_предприятия'].astype(str) + "_" + df['Тип_предприятия'].astype(str)
df['industry_threat'] = df['Тип_предприятия'].astype(str) + "_0"

df['hour_sin']  = np.sin(2 * np.pi * df['час'] / 24.0)
df['hour_cos']  = np.cos(2 * np.pi * df['час'] / 24.0)
df['dow_sin']   = np.sin(2 * np.pi * df['день_недели'] / 7.0)
df['dow_cos']   = np.cos(2 * np.pi * df['день_недели'] / 7.0)
df['month_sin'] = np.sin(2 * np.pi * df['месяц'] / 12.0)
df['month_cos'] = np.cos(2 * np.pi * df['месяц'] / 12.0)

# ------------------------------------------------------------
# 4. Label Encoding
# ------------------------------------------------------------
def safe_le_transform(le, series):
    def transform_val(x):
        if pd.isna(x): return 0
        return le.transform([str(x)])[0] if str(x) in le.classes_ else 0
    return series.apply(transform_val)

cat_cols = list(label_encoders.keys())
for col in cat_cols:
    if col in df.columns:
        df[col + '_enc'] = safe_le_transform(label_encoders[col], df[col])
    else:
        df[col + '_enc'] = 0

cat_features_ohe = ['Тип_предприятия', 'Регион_размещения_предприятия', 'сезон']
df = pd.get_dummies(df, columns=cat_features_ohe, drop_first=True)

# ------------------------------------------------------------
# 5. Кластеризация
# ------------------------------------------------------------
num_cols = ['Количество_хостов', 'час', 'день_недели', 'месяц']
cluster_features = num_cols + [col + '_enc' for col in cat_cols]

for c in cluster_features:
    if c not in df.columns: df[c] = 0

X_cluster = df[cluster_features].fillna(0).replace([np.inf, -np.inf], 0)
X_cluster_scaled = scaler_cluster.transform(X_cluster)
df['cluster'] = kmeans.predict(X_cluster_scaled)

# ------------------------------------------------------------
# 6. Выравнивание признаков и предсказания
# ------------------------------------------------------------
success_features = list(model_success.feature_names_in_)
threat_features  = list(model_threat.feature_names_in_)

X_new_success = df.reindex(columns=success_features, fill_value=0).fillna(0).replace([np.inf, -np.inf], 0)
X_new_threat  = df.reindex(columns=threat_features, fill_value=0).fillna(0).replace([np.inf, -np.inf], 0)

prob_success_arr = model_success.predict_proba(X_new_success)[:, 1]

row_idx = np.random.randint(0, len(df))
row = df.iloc[row_idx]

region = str(row.get('_orig_region', 'Неизвестно'))
industry = str(row.get('_orig_industry', 'Неизвестно'))
hour = int(row.get('_orig_hour', 0)) if pd.notna(row.get('_orig_hour')) else 0
day = int(row.get('_orig_day', 0)) if pd.notna(row.get('_orig_day')) else 0

prob = prob_success_arr[row_idx]

print("\n" + "="*50)
print("Прогнозируется атака")
print(f"   Регион:          {region.title()}")
print(f"   Отрасль:         {industry.title()}")
print(f"   Время атаки:     {hour:02d}:00 (День {day})")
print(f"   Вероятность успеха: {prob:.2%}")
print("="*50)