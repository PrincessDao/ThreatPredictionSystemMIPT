import pandas as pd

def run_vulnerability_analysis(df, imp_final, cluster_risk):
    industry_success = df.groupby('Тип_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    region_success = df.groupby('Регион_размещения_предприятия')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    threat_success = df.groupby('Название_угрозы')['Успех'].agg(['mean', 'count']).sort_values('mean', ascending=False)
    threat_success_filtered = threat_success[threat_success['count'] >= 10].head(10)
    
    return industry_success, region_success, threat_success_filtered

def write_final_report(df, best_k, acc_b, acc_final, acc_threat_b, acc_threat_e, top3_acc, hour_success, dow_success, month_success, industry_success, region_success, threat_success_filtered, cluster_risk, imp_final, ARTIFACTS_DIR):
    with open(ARTIFACTS_DIR / 'report.txt', 'w', encoding='utf-8') as f:
        f.write("=== Отчет по анализу угроз информационной безопасности ===\n\n")
        f.write(f"Всего инцидентов: {len(df)}\n")
        f.write(f"Успешных атак: {df['Успех'].sum()}\n")
        f.write(f"Оптимальное число кластеров: {best_k}\n\n")
        f.write("=== Сравнение моделей успешности ===\n")
        f.write(f"Baseline accuracy: {acc_b:.4f}\n")
        f.write(f"Final accuracy (баланс + отбор признаков): {acc_final:.4f}\n")
        f.write(f"Улучшение: {acc_final - acc_b:.4f}\n\n")
        f.write("=== Сравнение моделей угроз ===\n")
        f.write(f"Baseline threat accuracy: {acc_threat_b:.4f}\n")
        f.write(f"Improved threat accuracy: {acc_threat_e:.4f}\n")
        f.write(f"Top-3 Threat Accuracy: {top3_acc:.4f}\n\n")
        f.write("=== Рекомендации ===\n")
        f.write(f"1. Временная защита: усилить мониторинг в {hour_success.idxmax()}:00, по {dow_success.idxmax()}-му дню недели и в {month_success.idxmax()}-м месяце.\n")
        f.write(f"2. Отраслевая защита: особое внимание уделить отраслям {industry_success.head(3).index.tolist()}.\n")
        f.write(f"3. Региональная защита: повышенный контроль в регионах {region_success.head(3).index.tolist()}.\n")
        f.write(f"4. По угрозам: сконцентрироваться на предотвращении следующих типов атак: {threat_success_filtered.head(5).index.tolist()}.\n")
        f.write(f"5. Кластеры высокого риска: {cluster_risk.head(2).index.tolist()}\n")
        f.write(f"6. Ключевые факторы успешной атаки: {imp_final.head(3).to_dict()}\n")
        f.write("7. Архитектура безопасности: внедрить систему раннего предупреждения на основе улучшенной модели.\n")