# GitHub Actions: CI/CD, тесты и мониторинг

Этот проект использует GitHub Actions как CI/CD-контур: workflow запускает проверки Django-монолита, тесты FastAPI-микросервисов и проверяет, что Docker Compose конфигурация собирается. Внешнего деплоя на сервер пока нет: CD-часть здесь означает воспроизводимую сборку Docker-образов после успешных тестов.

## Что добавлено

- Workflow: `.github/workflows/ci-cd.yml`.
- Триггеры: `push`, `pull_request`, ручной запуск `workflow_dispatch`.
- Jobs:
  - `Django monolith checks` — ставит зависимости из `requirements.txt`, запускает `python manage.py check` и `python manage.py test`.
  - `Microservice tests` — матрицей запускает `pytest` для `auth_service`, `ticketing_service`, `payment_service`.
  - `Docker Compose validation` — выполняет `docker compose -f services/docker-compose.yml config` и `docker compose -f services/docker-compose.yml build`.
- Метрики Prometheus доступны на `/metrics` у Django, Auth, Ticketing и Payment.
- Prometheus доступен на `http://localhost:9090`, Grafana — на `http://localhost:3000`.

## Как загрузить проект на GitHub

1. Создайте пустой репозиторий на GitHub.
2. В локальном проекте проверьте текущую ветку:

```bash
git branch
```

3. Добавьте remote:

```bash
git remote add origin https://github.com/<owner>/<repo>.git
```

4. Отправьте код:

```bash
git push -u origin main
```

Если основная ветка называется иначе, например `mik/main`, отправьте её:

```bash
git push -u origin mik/main
```

## Как включить GitHub Actions

1. Откройте репозиторий на GitHub.
2. Перейдите во вкладку `Actions`.
3. Если GitHub попросит подтвердить запуск workflow из репозитория, нажмите `I understand my workflows, go ahead and enable them`.
4. После первого push workflow `CI/CD` появится в списке автоматически.

## Когда запускается CI/CD

Workflow запускается автоматически:

- при `push` в ветки `main`, `master`, `mik/main`;
- при создании или обновлении Pull Request;
- вручную через кнопку `Run workflow`.

Ручной запуск:

1. GitHub → `Actions`.
2. Выберите workflow `CI/CD`.
3. Нажмите `Run workflow`.
4. Выберите ветку.
5. Подтвердите запуск.

## Secrets

Сейчас secrets не обязательны, потому что workflow не публикует Docker-образы и не деплоит проект на сервер.

Для будущей публикации образов в GitHub Container Registry можно будет добавить:

- `GHCR_USERNAME` — имя пользователя или организации.
- `GHCR_TOKEN` — token с правами `write:packages`.

Для будущего деплоя по SSH можно будет добавить:

- `DEPLOY_HOST` — адрес сервера.
- `DEPLOY_USER` — пользователь сервера.
- `DEPLOY_SSH_KEY` — приватный SSH-ключ.
- `DEPLOY_PATH` — директория проекта на сервере.

## Как читать результаты workflow

Откройте `Actions` → `CI/CD` → конкретный запуск.

- Если `Django monolith checks` красный, смотрите шаги `Django system check` и `Django tests`.
- Если `Microservice tests` красный, откройте упавший matrix-job: `auth`, `ticketing` или `payment`.
- Если `Docker Compose validation` красный, чаще всего проблема в `services/docker-compose.yml`, Dockerfile или зависимостях в `requirements.txt`.

Успешный запуск должен показать зелёные jobs:

- `Django monolith checks`;
- `Microservice tests`;
- `Docker Compose validation`.

## Как повторить CI локально

Из корня проекта:

```bash
python3 -m venv .ci/venv
source .ci/venv/bin/activate
pip install -r requirements.txt
SKIP_FOOTBALL_IMPORT=1 python manage.py check
SKIP_FOOTBALL_IMPORT=1 python manage.py test --verbosity 2
```

Auth Service:

```bash
cd services/auth_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Ticketing Service:

```bash
cd services/ticketing_service/ticketing_fastapi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Payment Service:

```bash
cd services/payment_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Docker Compose:

```bash
docker compose -f services/docker-compose.yml config
docker compose -f services/docker-compose.yml build
```

Если локально доступен только legacy Compose:

```bash
docker-compose -f services/docker-compose.yml config
docker-compose -f services/docker-compose.yml build
```

Compose файл использует `network_mode: host`, поэтому при локальном запуске
проверьте, что свободны порты `3000`, `5435`, `5672`, `8000`, `8001`,
`8002`, `8003`, `9090`, `15672`.

## Как запустить весь стек локально

Из корня проекта:

```bash
docker compose -f services/docker-compose.yml up --build
```

Fallback для legacy Compose:

```bash
docker-compose -f services/docker-compose.yml up --build
```

После запуска проверьте URL:

| Компонент | URL |
| --- | --- |
| Django monolith | http://localhost:8000 |
| Auth Swagger | http://localhost:8003/docs |
| Ticketing Swagger | http://localhost:8001/docs |
| Payment Swagger | http://localhost:8002/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| RabbitMQ Management | http://localhost:15672 |

Grafana credentials по умолчанию:

- login: `admin`;
- password: `admin`.

В Grafana должен появиться datasource `Prometheus` и dashboard `GoroXcore Overview`.

## Как проверить метрики

Откройте:

- http://localhost:8000/metrics — Django monolith;
- http://localhost:8003/metrics — Auth;
- http://localhost:8001/metrics — Ticketing;
- http://localhost:8002/metrics — Payment.

Минимальные метрики:

- `gx_http_requests_total`;
- `gx_http_request_duration_seconds`;
- `gx_http_requests_in_progress`.

Бизнес-метрики:

- `gx_auth_registrations_total`;
- `gx_ticketing_booking_events_total`;
- `gx_payment_status_changes_total`.

В Prometheus откройте `Status` → `Targets`. Targets `goroxcore-monolith`, `goroxcore-auth`, `goroxcore-ticketing`, `goroxcore-payment` должны быть `UP`.

## Как расширить CI до публикации Docker images в GHCR

Добавьте permissions в workflow:

```yaml
permissions:
  contents: read
  packages: write
```

Затем добавьте job после тестов:

```yaml
- name: Log in to GHCR
  run: echo "${{ secrets.GHCR_TOKEN }}" | docker login ghcr.io -u "${{ secrets.GHCR_USERNAME }}" --password-stdin

- name: Build and push image
  run: |
    docker build -t ghcr.io/<owner>/<repo>/monolith:${{ github.sha }} .
    docker push ghcr.io/<owner>/<repo>/monolith:${{ github.sha }}
```

Для каждого микросервиса используйте свой build context:

- `services/auth_service`;
- `services/ticketing_service/ticketing_fastapi`;
- `services/payment_service`.

После этого CD можно расширить деплоем на сервер: скачать свежие images, обновить `.env`, выполнить `docker compose pull` и `docker compose up -d`.
