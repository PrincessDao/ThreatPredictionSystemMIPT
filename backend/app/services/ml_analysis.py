import pandas as pd
import numpy as np
import io
import base64
import logging
from datetime import datetime
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from app.db.database import get_sync_client

logger = logging.getLogger(__name__)

class MLReportGenerator:
    def __init__(self):
        self.df = None
        self.threats_df = None
        self.model_success = None
        self.model_threat = None
        self.scaler = None
        self.label_encoders = {}
        self.feature_cols = []
        self.num_cols = ['hosts_count', 'hour', 'day_of_week', 'month']
        self.cat_cols = ['industry', 'region', 'season']
        self.top_threats_limit = 10
        self.last_train_time = None

    def load_data_from_clickhouse(self):
        client = get_sync_client()
        incidents_query = "SELECT * FROM incidents"
        incidents_df = client.query_df(incidents_query)
        threats_query = "SELECT code, name FROM threats"
        threats_df = client.query_df(threats_query)
        client.close()

        if incidents_df.empty:
            logger.warning("No incidents data in ClickHouse")
            return False

        incidents_df.rename(columns={
            'industry': 'Тип_предприятия',
            'region': 'Регион_размещения_предприятия',
            'hosts_count': 'Количество_хостов',
            'threat_code': 'Код_реализованной_угрозы',
            'success': 'Успех',
            'hour': 'час',
            'day_of_week': 'день_недели',
            'month': 'месяц',
            'season': 'сезон'
        }, inplace=True)
        threats_df.rename(columns={'code': 'Код_угрозы', 'name': 'Название_угрозы'}, inplace=True)

        self.df = incidents_df.merge(threats_df, left_on='Код_реализованной_угрозы', right_on='Код_угрозы', how='left')
        self.threats_df = threats_df
        return True

    def prepare_features(self):
        for col in self.cat_cols:
            le = LabelEncoder()
            self.df[col + '_enc'] = le.fit_transform(self.df[col].astype(str))
            self.label_encoders[col] = le

        self.feature_cols = self.num_cols + [col + '_enc' for col in self.cat_cols]
        X = self.df[self.feature_cols].copy()

        self.scaler = StandardScaler()
        X[self.num_cols] = self.scaler.fit_transform(X[self.num_cols])
        return X

    def train_success_model(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        model = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            random_state=42, use_label_encoder=False, eval_metric='logloss'
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        logger.info(f"Success model accuracy: {acc:.4f}")
        return model, acc, report

    def train_threat_model(self, X, y_threat_codes):
        top_threats = self.df['Код_реализованной_угрозы'].value_counts().head(self.top_threats_limit).index
        mask = self.df['Код_реализованной_угрозы'].isin(top_threats)
        X_threat = X[mask]
        y_threat = self.df.loc[mask, 'Код_реализованной_угрозы']

        le_threat = LabelEncoder()
        y_enc = le_threat.fit_transform(y_threat)

        X_train, X_test, y_train, y_test = train_test_split(
            X_threat, y_enc, test_size=0.2, random_state=42, stratify=y_enc
        )
        model = xgb.XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.1,
            random_state=42, use_label_encoder=False, eval_metric='mlogloss'
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)
        logger.info(f"Threat model accuracy: {acc:.4f}")
        return model, le_threat, acc, report

    def compute_shap(self, model, X_sample):
        explainer = shap.TreeExplainer(model)
        X_sample_small = X_sample.sample(min(500, len(X_sample)), random_state=42)
        shap_values = explainer.shap_values(X_sample_small)
        return shap_values, explainer, X_sample_small

    def generate_recommendations(self):
        df = self.df
        hour_success = df.groupby('час')['Успех'].mean()
        dow_success = df.groupby('день_недели')['Успех'].mean()
        month_success = df.groupby('месяц')['Успех'].mean()
        season_success = df.groupby('сезон')['Успех'].mean()

        industry_success = df.groupby('Тип_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
        region_success = df.groupby('Регион_размещения_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)

        threat_success = df.groupby('Название_угрозы')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
        threat_success_filtered = threat_success[threat_success['count'] >= 10].head(10)

        importance = pd.Series(self.model_success.feature_importances_, index=self.feature_cols).sort_values(ascending=False)

        recommendations = {
            "temporal": {
                "hour": int(hour_success.idxmax()) if not pd.isna(hour_success.idxmax()) else None,
                "day_of_week": int(dow_success.idxmax()) if not pd.isna(dow_success.idxmax()) else None,
                "month": int(month_success.idxmax()) if not pd.isna(month_success.idxmax()) else None,
                "season": season_success.idxmax() if not pd.isna(season_success.idxmax()) else None
            },
            "top_industries": industry_success.head(3).index.tolist(),
            "top_regions": region_success.head(3).index.tolist(),
            "top_threats_by_success": threat_success_filtered.head(5).index.tolist(),
            "feature_importance": importance.head(3).to_dict()
        }

        text_lines = [
            "=== Рекомендации по усилению защиты ===",
            f"1. Временная защита: усилить мониторинг в {recommendations['temporal']['hour']}:00, по {recommendations['temporal']['day_of_week']}-му дню недели и в {recommendations['temporal']['month']}-м месяце.",
            f"2. Отраслевая защита: особое внимание уделить отраслям {recommendations['top_industries']}.",
            f"3. Региональная защита: повышенный контроль в регионах {recommendations['top_regions']}.",
            f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {recommendations['top_threats_by_success']}.",
            f"5. Ключевые факторы успешной атаки (важность): {recommendations['feature_importance']}",
            "6. Архитектура безопасности: использовать ML-модели и SHAP-анализ для динамической корректировки политик."
        ]
        return "\n".join(text_lines), recommendations

    def generate_figures_base64(self):
        df = self.df
        figures = {}

        plt.figure(figsize=(12,6))
        top_industries = df['Тип_предприятия'].value_counts().head(10)
        top_industries.plot(kind='bar')
        plt.title('Топ-10 отраслей по числу инцидентов')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        figures['industries'] = base64.b64encode(buf.read()).decode()
        plt.close()

        plt.figure(figsize=(12,6))
        top_regions = df['Регион_размещения_предприятия'].value_counts().head(10)
        top_regions.plot(kind='bar')
        plt.title('Топ-10 регионов по числу инцидентов')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        figures['regions'] = base64.b64encode(buf.read()).decode()
        plt.close()

        fig, axes = plt.subplots(2,2, figsize=(14,10))
        hour_success = df.groupby('час')['Успех'].mean()
        axes[0,0].bar(hour_success.index, hour_success.values)
        axes[0,0].set_title('Успешность по часам')
        dow_success = df.groupby('день_недели')['Успех'].mean()
        axes[0,1].bar(dow_success.index, dow_success.values)
        axes[0,1].set_title('Успешность по дням недели')
        month_success = df.groupby('месяц')['Успех'].mean()
        axes[1,0].bar(month_success.index, month_success.values)
        axes[1,0].set_title('Успешность по месяцам')
        season_success = df.groupby('сезон')['Успех'].mean()
        axes[1,1].bar(season_success.index, season_success.values)
        axes[1,1].set_title('Успешность по сезонам')
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        figures['temporal'] = base64.b64encode(buf.read()).decode()
        plt.close()

        if self.model_success is not None:
            shap_values, _, X_sample = self.compute_shap(self.model_success, X=self.X_encoded)
            plt.figure(figsize=(10,6))
            shap.summary_plot(shap_values, X_sample, feature_names=self.feature_cols, show=False)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            figures['shap_summary'] = base64.b64encode(buf.read()).decode()
            plt.close()

        if self.model_success is not None:
            plt.figure(figsize=(10,6))
            xgb.plot_importance(self.model_success, importance_type='weight', ax=plt.gca())
            plt.title('Важность признаков (XGBoost)')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            figures['feature_importance'] = base64.b64encode(buf.read()).decode()
            plt.close()

        return figures

    def generate_full_report(self):
        if not self.load_data_from_clickhouse():
            return {"error": "No data in ClickHouse"}

        X = self.prepare_features()
        self.X_encoded = X
        y_success = self.df['Успех'].values

        self.model_success, acc_success, report_success = self.train_success_model(X, y_success)

        self.model_threat, self.le_threat, acc_threat, report_threat = self.train_threat_model(X, self.df['Код_реализованной_угрозы'].values)

        self.compute_shap(self.model_success, X)

        recommendations_text, recommendations_struct = self.generate_recommendations()

        figures = self.generate_figures_base64()

        total_incidents = len(self.df)
        successful = self.df['Успех'].sum()

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_incidents": total_incidents,
            "successful_incidents": int(successful),
            "success_rate": float(successful / total_incidents * 100),
            "success_model_accuracy": acc_success,
            "threat_model_accuracy": acc_threat,
            "classification_report_success": report_success,
            "recommendations_text": recommendations_text,
            "recommendations_structured": recommendations_struct,
            "figures_base64": figures
        }
        self.last_train_time = datetime.utcnow()
        return report

ml_generator = MLReportGenerator()