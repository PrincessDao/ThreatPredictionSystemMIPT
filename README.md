# Аналитическая система прогнозирования угроз

## Описание

Демонстрация веб интерфейса для аналитического приложения

## Установка и запуск

- Необходимо Python 3.11.9

```
docker compose build --no-cache
docker compose up -d
```
```
docker run -d --name kafka -p 9092:9092 apache/kafka
```
- Убедиться что для postgreSql есть доступ по md5 для всех пользователей

# 1. Создаём файл миграции на основе ваших моделей
 python manage.py makemigrations

# 2. Применяем миграцию (создаём таблицы в БД)
 python manage.py migrate

# 3. Запускаем загрузку данных
 python manage.py load_data --threats ../data/thrlist.xlsx --incidents ../data/incidents_2000.xlsx

# 4. Запускаем сервер
 python manage.py runserver

1. **Развертывание аналитического приложения**

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 src/main.py
```

2. **Запуск экземпляра нового инцидента и прогнозирования атаки**

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 example/example.py
```

3. **Развертывание прототипа веб-интерфейса**

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

```
Streamlit (Web) http://localhost:8501/
Django (Backend) http://localhost:8000/
Postgres http://localhost:5432/
Kafka http://localhost:9092/
```
