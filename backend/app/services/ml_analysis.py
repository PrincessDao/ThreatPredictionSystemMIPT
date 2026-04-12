import pandas as pd
import numpy as np
import io
import base64
import logging
import joblib
import os
from datetime import datetime
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import xgboost as xgb
import shap
import matplotlib.pyplot as plt
from app.db.database import get_sync_client

logger = logging.getLogger(__name__)

class MLReportGenerator:
    def __init__(self, models_dir="models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self.df = None
        self.model_success_baseline = None
        self.model_success_improved = None
        self.model_threat_improved = None
        self.scaler = None
        self.scaler_cluster = None
        self.kmeans = None
        self.label_encoders = {}
        self.le_threat = None
        self.feature_cols_base = []
        self.feature_cols_ext = []
        self.num_cols = ['hosts_count', 'hour', 'day_of_week', 'month']
        self.cat_cols = ['industry', 'region', 'season']
        self.top_threats_limit = 10
        self.best_k = None
        self.acc_baseline = None
        self.acc_improved = None

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
        return True

    def encode_categorical(self, df, fit=True):
        for col in self.cat_cols:
            if fit:
                le = LabelEncoder()
                df[col + '_enc'] = le.fit_transform(df[col].astype(str))
                self.label_encoders[col] = le
            else:
                df[col + '_enc'] = self.label_encoders[col].transform(df[col].astype(str))
        return df

    def prepare_cluster_features(self, df, fit_scaler=True):
        cluster_features = self.num_cols + [col + '_enc' for col in self.cat_cols]
        X = df[cluster_features].copy()
        if fit_scaler:
            self.scaler_cluster = StandardScaler()
            X_scaled = self.scaler_cluster.fit_transform(X)
        else:
            X_scaled = self.scaler_cluster.transform(X)
        return X_scaled, cluster_features

    def perform_clustering(self, X_scaled):
        inertias = []
        silhouettes = []
        K_range = range(2, 11)
        for k in K_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(X_scaled)
            inertias.append(kmeans.inertia_)
            silhouettes.append(silhouette_score(X_scaled, kmeans.labels_))
        self.best_k = K_range[np.argmax(silhouettes)]
        self.kmeans = KMeans(n_clusters=self.best_k, random_state=42, n_init=10)
        clusters = self.kmeans.fit_predict(X_scaled)
        return clusters

    def prepare_features_with_clusters(self, df, clusters, fit_scaler=True):
        df = df.copy()
        df['cluster'] = clusters
        for col in self.cat_cols:
            if col + '_enc' not in df.columns:
                df = self.encode_categorical(df, fit=True)
        base_features = self.num_cols + [col + '_enc' for col in self.cat_cols]
        ext_features = base_features + ['cluster']
        X_base = df[base_features].copy()
        X_ext = df[ext_features].copy()
        if fit_scaler:
            self.scaler = StandardScaler()
            X_base[self.num_cols] = self.scaler.fit_transform(X_base[self.num_cols])
        else:
            X_base[self.num_cols] = self.scaler.transform(X_base[self.num_cols])
        X_ext[self.num_cols] = X_base[self.num_cols]
        return X_base, X_ext, base_features, ext_features

    def train_success_models(self, X_base, X_ext, y):
        X_train_b, X_test_b, y_train, y_test = train_test_split(
            X_base, y, test_size=0.2, random_state=42, stratify=y
        )
        X_train_e, X_test_e, _, _ = train_test_split(
            X_ext, y, test_size=0.2, random_state=42, stratify=y
        )
        model_b = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            random_state=42, use_label_encoder=False, eval_metric='logloss'
        )
        model_b.fit(X_train_b, y_train)
        y_pred_b = model_b.predict(X_test_b)
        acc_b = accuracy_score(y_test, y_pred_b)
        model_e = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1,
            random_state=42, use_label_encoder=False, eval_metric='logloss'
        )
        model_e.fit(X_train_e, y_train)
        y_pred_e = model_e.predict(X_test_e)
        acc_e = accuracy_score(y_test, y_pred_e)
        self.model_success_baseline = model_b
        self.model_success_improved = model_e
        self.acc_baseline = acc_b
        self.acc_improved = acc_e
        return model_b, model_e, acc_b, acc_e

    def train_threat_model(self, X_ext, y_threat_codes):
        top_threats = self.df['Код_реализованной_угрозы'].value_counts().head(self.top_threats_limit).index
        mask = self.df['Код_реализованной_угрозы'].isin(top_threats)
        X_threat = X_ext[mask]
        y_threat = self.df.loc[mask, 'Код_реализованной_угрозы']
        self.le_threat = LabelEncoder()
        y_enc = self.le_threat.fit_transform(y_threat)
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
        self.model_threat_improved = model
        return model, acc

    def save_artifacts(self):
        joblib.dump(self.model_success_baseline, os.path.join(self.models_dir, 'model_success_baseline.pkl'))
        joblib.dump(self.model_success_improved, os.path.join(self.models_dir, 'model_success_improved.pkl'))
        joblib.dump(self.model_threat_improved, os.path.join(self.models_dir, 'model_threat_improved.pkl'))
        joblib.dump(self.scaler, os.path.join(self.models_dir, 'scaler.pkl'))
        joblib.dump(self.scaler_cluster, os.path.join(self.models_dir, 'scaler_cluster.pkl'))
        joblib.dump(self.kmeans, os.path.join(self.models_dir, 'kmeans_model.pkl'))
        joblib.dump(self.label_encoders, os.path.join(self.models_dir, 'label_encoders.pkl'))
        joblib.dump(self.le_threat, os.path.join(self.models_dir, 'label_encoder_threat.pkl'))
        joblib.dump(self.feature_cols_ext, os.path.join(self.models_dir, 'feature_columns.pkl'))
        joblib.dump(self.best_k, os.path.join(self.models_dir, 'best_k.pkl'))
        logger.info("Artifacts saved to %s", self.models_dir)

    def load_artifacts(self):
        try:
            self.model_success_baseline = joblib.load(os.path.join(self.models_dir, 'model_success_baseline.pkl'))
            self.model_success_improved = joblib.load(os.path.join(self.models_dir, 'model_success_improved.pkl'))
            self.model_threat_improved = joblib.load(os.path.join(self.models_dir, 'model_threat_improved.pkl'))
            self.scaler = joblib.load(os.path.join(self.models_dir, 'scaler.pkl'))
            self.scaler_cluster = joblib.load(os.path.join(self.models_dir, 'scaler_cluster.pkl'))
            self.kmeans = joblib.load(os.path.join(self.models_dir, 'kmeans_model.pkl'))
            self.label_encoders = joblib.load(os.path.join(self.models_dir, 'label_encoders.pkl'))
            self.le_threat = joblib.load(os.path.join(self.models_dir, 'label_encoder_threat.pkl'))
            self.feature_cols_ext = joblib.load(os.path.join(self.models_dir, 'feature_columns.pkl'))
            self.best_k = joblib.load(os.path.join(self.models_dir, 'best_k.pkl'))
            return True
        except Exception as e:
            logger.warning("Could not load artifacts: %s", e)
            return False

    def generate_cluster_analysis(self):
        df = self.df
        cluster_risk = df.groupby('cluster')['Успех'].mean().sort_values(ascending=False)
        cluster_profile = df.groupby('cluster')[self.num_cols + ['Успех']].mean()
        cluster_profile['count'] = df['cluster'].value_counts()
        X_cluster_scaled = self.scaler_cluster.transform(df[self.feature_cols_ext[:-1]].values)
        pca = PCA(n_components=2)
        pca_result = pca.fit_transform(X_cluster_scaled)
        return {
            "optimal_clusters": int(self.best_k),
            "cluster_risk": cluster_risk.to_dict(),
            "cluster_profile": cluster_profile.to_dict(),
            "pca_coordinates": pca_result.tolist()
        }

    def generate_recommendations_with_clusters(self):
        df = self.df
        hour_success = df.groupby('час')['Успех'].mean()
        dow_success = df.groupby('день_недели')['Успех'].mean()
        month_success = df.groupby('месяц')['Успех'].mean()
        industry_success = df.groupby('Тип_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
        region_success = df.groupby('Регион_размещения_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
        threat_success = df.groupby('Название_угрозы')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
        threat_success_filtered = threat_success[threat_success['count'] >= 10].head(10)
        cluster_risk = df.groupby('cluster')['Успех'].mean().sort_values(ascending=False)
        importances = pd.Series(self.model_success_improved.feature_importances_, index=self.feature_cols_ext).sort_values(ascending=False)
        recommendations = {
            "temporal": {
                "hour": int(hour_success.idxmax()),
                "day_of_week": int(dow_success.idxmax()),
                "month": int(month_success.idxmax())
            },
            "top_industries": industry_success.head(3).index.tolist(),
            "top_regions": region_success.head(3).index.tolist(),
            "top_threats_by_success": threat_success_filtered.head(5).index.tolist(),
            "high_risk_clusters": cluster_risk.head(2).index.tolist(),
            "feature_importance": importances.head(3).to_dict()
        }
        text_lines = [
            "=== Рекомендации по усилению защиты (с учётом кластеров) ===",
            f"1. Временная защита: усилить мониторинг в {recommendations['temporal']['hour']}:00, по {recommendations['temporal']['day_of_week']}-му дню недели и в {recommendations['temporal']['month']}-м месяце.",
            f"2. Отраслевая защита: особое внимание уделить отраслям {recommendations['top_industries']}.",
            f"3. Региональная защита: повышенный контроль в регионах {recommendations['top_regions']}.",
            f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {recommendations['top_threats_by_success']}.",
            f"5. Кластеры высокого риска: {recommendations['high_risk_clusters']} требуют немедленного внимания.",
            f"6. Ключевые факторы успешной атаки (важность): {recommendations['feature_importance']}",
            "7. Архитектура безопасности: внедрить систему раннего предупреждения на основе улучшенной модели с кластеризацией."
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
        if self.model_success_improved is not None:
            explainer = shap.TreeExplainer(self.model_success_improved)
            X_sample = self.X_test_e.sample(min(500, len(self.X_test_e)), random_state=42)
            shap_values = explainer.shap_values(X_sample)
            plt.figure(figsize=(10,6))
            shap.summary_plot(shap_values, X_sample, feature_names=self.feature_cols_ext, show=False)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            figures['shap_summary'] = base64.b64encode(buf.read()).decode()
            plt.close()
            plt.figure(figsize=(10,6))
            xgb.plot_importance(self.model_success_improved, importance_type='weight', ax=plt.gca())
            plt.title('Важность признаков (XGBoost с кластером)')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            figures['feature_importance'] = base64.b64encode(buf.read()).decode()
            plt.close()
        if self.kmeans is not None:
            pca = PCA(n_components=2)
            X_cluster_scaled = self.scaler_cluster.transform(self.df[self.feature_cols_ext[:-1]].values)
            X_pca = pca.fit_transform(X_cluster_scaled)
            plt.figure(figsize=(10,8))
            scatter = plt.scatter(X_pca[:,0], X_pca[:,1], c=self.df['cluster'], cmap='tab10', alpha=0.6)
            plt.colorbar(scatter, label='Кластер')
            plt.title('Визуализация кластеров инцидентов (PCA)')
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            figures['cluster_pca'] = base64.b64encode(buf.read()).decode()
            plt.close()
        return figures

    def generate_full_report(self, force_retrain=False):
        if not force_retrain and self.load_artifacts() and self.df is not None:
            logger.info("Using pre-trained models")
        else:
            if not self.load_data_from_clickhouse():
                return {"error": "No data in ClickHouse"}
            df_encoded = self.encode_categorical(self.df, fit=True)
            X_cluster_scaled, _ = self.prepare_cluster_features(df_encoded, fit_scaler=True)
            clusters = self.perform_clustering(X_cluster_scaled)
            self.df['cluster'] = clusters
            X_base, X_ext, base_features, ext_features = self.prepare_features_with_clusters(self.df, clusters, fit_scaler=True)
            self.feature_cols_base = base_features
            self.feature_cols_ext = ext_features
            y_success = self.df['Успех'].values
            self.train_success_models(X_base, X_ext, y_success)
            self.train_threat_model(X_ext, self.df['Код_реализованной_угрозы'].values)
            self.save_artifacts()
            self.X_test_e = X_ext
        total_incidents = len(self.df)
        successful = self.df['Успех'].sum()
        recommendations_text, recommendations_struct = self.generate_recommendations_with_clusters()
        cluster_analysis = self.generate_cluster_analysis()
        figures = self.generate_figures_base64()
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_incidents": total_incidents,
            "successful_incidents": int(successful),
            "success_rate": float(successful / total_incidents * 100),
            "baseline_accuracy": self.acc_baseline,
            "improved_accuracy": self.acc_improved,
            "accuracy_improvement": self.acc_improved - self.acc_baseline if self.acc_baseline else None,
            "cluster_analysis": cluster_analysis,
            "recommendations_text": recommendations_text,
            "recommendations_structured": recommendations_struct,
            "figures_base64": figures
        }
        return report

ml_generator = MLReportGenerator()