import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def run_full_eda(df, ARTIFACTS_DIR):
    plt.style.use('ggplot')

    # Отрасли
    plt.figure(figsize=(12,6))
    top_industries = df['Тип_предприятия'].value_counts().head(10)
    top_industries.plot(kind='bar')
    plt.title('Топ-10 отраслей по числу инцидентов')
    plt.xlabel('Отрасль')
    plt.ylabel('Количество инцидентов')
    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / 'fig_industries.png')
    plt.close()

    # Регионы
    plt.figure(figsize=(12,6))
    top_regions = df['Регион_размещения_предприятия'].value_counts().head(10)
    top_regions.plot(kind='bar')
    plt.title('Топ-10 регионов по числу инцидентов')
    plt.xlabel('Регион')
    plt.ylabel('Количество инцидентов')
    plt.tight_layout()
    plt.savefig(ARTIFACTS_DIR / 'fig_regions.png')
    plt.close()

    # Временные паттерны
    fig, axes = plt.subplots(2,2, figsize=(14,10))

    hour_success = df.groupby('час')['Успех'].mean()
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
    plt.savefig(ARTIFACTS_DIR / 'fig_temporal_patterns.png')
    plt.close()

    
    
    return hour_success, dow_success, month_success, season_success