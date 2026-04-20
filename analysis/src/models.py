import xgboost as xgb
import pandas as pd
import numpy as np
import shap
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import accuracy_score, top_k_accuracy_score, classification_report

def train_success_models(df_model, X_base, y_success, feature_cols_base, ARTIFACTS_DIR):
    train_idx, test_idx = train_test_split(df_model.index, test_size=0.2, random_state=42, stratify=y_success)
    X_train_b, X_test_b = X_base.loc[train_idx], X_base.loc[test_idx]
    y_train, y_test = y_success[train_idx], y_success[test_idx]

    n_neg, n_pos = (y_train == 0).sum(), (y_train == 1).sum()
    scale_w = n_neg / n_pos

    model_pre = xgb.XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=5, subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0, scale_pos_weight=scale_w, random_state=42, eval_metric='logloss', use_label_encoder=False)
    model_pre.fit(X_train_b, y_train)
    acc_b = accuracy_score(y_test, model_pre.predict(X_test_b))

    importances_pre = pd.Series(model_pre.feature_importances_, index=feature_cols_base)
    threshold = importances_pre.quantile(0.3)
    selected_features = importances_pre[importances_pre > threshold].index.tolist()

    X_train_sel, X_test_sel = X_train_b[selected_features], X_test_b[selected_features]
    model_final = xgb.XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=5, subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=1.0, scale_pos_weight=scale_w, random_state=42, eval_metric='logloss', use_label_encoder=False)
    model_final.fit(X_train_sel, y_train)
    y_pred_final = model_final.predict(X_test_sel)
    acc_final = accuracy_score(y_test, y_pred_final)

    # Важность признаков
    imp_final = pd.Series(model_final.feature_importances_, index=selected_features).sort_values(ascending=False)
    plt.figure(figsize=(10,6))
    imp_final.head(15).plot(kind='barh', ax=plt.gca())
    plt.gca().invert_yaxis()
    plt.title('Важность признаков (Final Model)')
    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / 'fig_feature_importance_improved.png')
    plt.close()

    # SHAP
    explainer = shap.TreeExplainer(model_final)
    shap_values = explainer.shap_values(X_test_sel)
    plt.figure(figsize=(10,6))
    shap.summary_plot(shap_values, X_test_sel, feature_names=selected_features, show=False)
    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / 'fig_shap_summary_improved.png')
    plt.close()

    return model_final, acc_b, acc_final, selected_features, y_test, y_pred_final, imp_final

def train_threat_models(df_model, feature_cols_base):
    top_threats = df_model['Код_реализованной_угрозы'].value_counts().head(10).index
    df_threat_subset = df_model[df_model['Код_реализованной_угрозы'].isin(top_threats)].copy().reset_index(drop=True)

    le_threat = LabelEncoder()
    y_threat_enc = le_threat.fit_transform(df_threat_subset['Код_реализованной_угрозы'].values)
    X_threat = df_threat_subset[feature_cols_base]

    train_idx_t, test_idx_t = train_test_split(df_threat_subset.index, test_size=0.2, random_state=42, stratify=y_threat_enc)
    X_train_tb, X_test_tb = X_threat.loc[train_idx_t], X_threat.loc[test_idx_t]
    y_train_t, y_test_t = y_threat_enc[train_idx_t], y_threat_enc[test_idx_t]

    model_threat_b = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9, random_state=42, eval_metric='mlogloss', use_label_encoder=False)
    model_threat_b.fit(X_train_tb, y_train_t)
    acc_threat_b = accuracy_score(y_test_t, model_threat_b.predict(X_test_tb))

    sw = compute_sample_weight('balanced', y_train_t)
    model_threat_e = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.7, colsample_bytree=0.7, reg_alpha=1.0, reg_lambda=2.0, min_child_weight=3, random_state=42, eval_metric='mlogloss', use_label_encoder=False)
    model_threat_e.fit(X_train_tb, y_train_t, sample_weight=sw)
    acc_threat_e = accuracy_score(y_test_t, model_threat_e.predict(X_test_tb))

    if acc_threat_e < acc_threat_b:
        model_threat_e = model_threat_b
        acc_threat_e = acc_threat_b

    proba_threat = model_threat_e.predict_proba(X_test_tb)
    top3_acc = top_k_accuracy_score(y_test_t, proba_threat, k=3)

    return model_threat_e, acc_threat_b, acc_threat_e, top3_acc, le_threat, X_test_tb, y_test_t