import joblib
import pandas as pd

# Загрузка артефактов
model = joblib.load('model_success_improved.pkl')
scaler = joblib.load('scaler.pkl')
label_encoders = joblib.load('label_encoders.pkl')
kmeans = joblib.load('kmeans_model.pkl')
scaler_cluster = joblib.load('scaler_cluster.pkl')
feature_cols_ext = joblib.load('feature_columns.pkl')

# Новый инцидент
new_incident = {
    'Количество_хостов': 1000000,
    'час': 17,
    'день_недели': 1,
    'месяц': 7,
    'Тип_предприятия': 'Финансовый сектор',
    'Регион_размещения_предприятия': 'Москва',
    'сезон': 'лето'
}
new_df = pd.DataFrame([new_incident])

# Безопасное кодирование категорий
def safe_label_transform(le, value):
    if value in le.classes_:
        return le.transform([value])[0]
    else:
        # В реальном проекте лучше использовать значение по умолчанию (например, 0)
        # или специальный обработчик неизвестных категорий
        return 0

for col, le in label_encoders.items():
    new_df[col + '_enc'] = safe_label_transform(le, new_df[col].iloc[0])

# Масштабирование числовых признаков
num_cols = ['Количество_хостов', 'час', 'день_недели', 'месяц']
new_df[num_cols] = scaler.transform(new_df[num_cols])

# Кластеризация нового объекта
cluster_features = num_cols + [col + '_enc' for col in label_encoders.keys()]
X_cluster_new = new_df[cluster_features]
X_cluster_new_scaled = scaler_cluster.transform(X_cluster_new)
new_df['cluster'] = kmeans.predict(X_cluster_new_scaled)

# Предсказание
X_new = new_df[feature_cols_ext]
prob_success = model.predict_proba(X_new)[0, 1]
print(f"Вероятность успешной атаки: {prob_success:.2%}")