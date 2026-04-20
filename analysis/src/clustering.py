import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def run_clustering_process(df, cluster_features, num_cols, ARTIFACTS_DIR):
    X_cluster = df[cluster_features].copy()
    scaler_cluster = StandardScaler()
    X_cluster_scaled = scaler_cluster.fit_transform(X_cluster)

    inertias = []
    silhouettes = []
    K_range = range(2, 11)
    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_cluster_scaled)
        iner = kmeans.inertia_
        iner = float(iner) if iner is not None else 0.0
        inertias.append(iner)
        labels = kmeans.labels_
        sil = silhouette_score(X_cluster_scaled, labels)
        silhouettes.append(sil)

    fig, ax1 = plt.subplots(figsize=(10,5))
    ax1.plot(K_range, inertias, 'bo-', label='Инерция')
    ax1.set_xlabel('Число кластеров')
    ax1.set_ylabel('Инерция', color='b')
    ax2 = ax1.twinx()
    ax2.plot(K_range, silhouettes, 'rs-', label='Silhouette Score')
    ax2.set_ylabel('Silhouette Score', color='r')
    plt.title('Выбор числа кластеров для KMeans')
    fig.legend(loc='upper right')
    plt.savefig(ARTIFACTS_DIR / 'fig_cluster_elbow.png')
    plt.close()

    best_k = K_range[np.argmax(silhouettes)]
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(X_cluster_scaled)

    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_cluster_scaled)
    df['pca1'] = X_pca[:,0]
    df['pca2'] = X_pca[:,1]

    plt.figure(figsize=(10,8))
    scatter = plt.scatter(df['pca1'], df['pca2'], c=df['cluster'], cmap='tab10', alpha=0.6)
    plt.colorbar(scatter, label='Кластер')
    plt.title('Визуализация кластеров инцидентов (PCA)')
    plt.xlabel('Главная компонента 1')
    plt.ylabel('Главная компонента 2')
    plt.savefig(ARTIFACTS_DIR / 'fig_clusters_pca.png')
    plt.close()

    cluster_profile = df.groupby('cluster')[num_cols + ['Успех']].mean()
    cluster_profile['count'] = df['cluster'].value_counts()
    
    return df, kmeans, scaler_cluster, best_k, cluster_profile