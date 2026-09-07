# Task Tracker API

[![CI/CD](https://github.com/exlip-creator/Task-tracker-api/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/exlip-creator/Task-tracker-api/actions/workflows/ci-cd.yml)
![Python](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-1.15-7B42BC?logo=terraform&logoColor=white)
![Ansible](https://img.shields.io/badge/Ansible-14-EE0000?logo=ansible&logoColor=white)

Pet-проект, в котором основное внимание уделено инфраструктуре и полному циклу
выкатки кода, а не бизнес-логике. Приложение — намеренно минимальный REST API
для задач; оно играет роль полезной нагрузки, вокруг которой построено всё
остальное: контейнеризация, тесты, сборка образа, поднятие облачной
инфраструктуры, конфигурация сервера, деплой и мониторинг.

Один `git push` в `main` приводит к тому, что в Yandex Cloud появляется
настроенная виртуальная машина с работающим приложением, базой данных,
Prometheus и Grafana. Ручных шагов на сервере нет ни одного.

## Стек

| Слой | Технологии |
|---|---|
| Приложение | Python 3.13, FastAPI, Pydantic, asyncpg, Uvicorn |
| База данных | PostgreSQL 16 (alpine) |
| Контейнеризация | Docker (multi-stage), Docker Compose |
| CI/CD | GitHub Actions, Docker Hub |
| Инфраструктура | Terraform 1.15, Yandex Cloud, S3-backend для state |
| Конфигурация серверов | Ansible 14.3.1 |
| Мониторинг | Prometheus, Grafana, prometheus-fastapi-instrumentator |
| Качество кода | flake8, pytest, httpx |

## Приложение

REST API на FastAPI с четырьмя эндпоинтами. Работа с БД идёт напрямую через
`asyncpg` без ORM: запросы параметризованные, схема простая, а слой абстракции
над SQL в проекте такого размера дал бы больше кода, чем пользы.

Пул соединений создаётся один раз в `lifespan` (`min_size=3`, `max_size=5`) и
закрывается при остановке приложения. Соединение выдаётся хендлерам через
зависимость `get_db` — это же место в тестах подменяется на тестовый пул.

| Метод | Эндпоинт | Описание | Коды ответа |
|---|---|---|---|
| `GET` | `/tasks` | Список задач, отсортированный по `id` по убыванию | `200` |
| `POST` | `/tasks` | Создать задачу (`title`, опционально `description`) | `201` |
| `PATCH` | `/tasks/{task_id}/complete` | Пометить задачу выполненной | `200`, `404` |
| `DELETE` | `/tasks/{task_id}` | Удалить задачу | `204`, `404` |
| `GET` | `/metrics` | Метрики в формате Prometheus | `200` |

Валидация входа и сериализация ответа описаны двумя схемами Pydantic:
`TaskCreate` (то, что принимается) и `Task` (то, что отдаётся). Разделение
намеренное — клиент не может задать `id` или `completed` при создании.

```json
{
  "id": 1,
  "title": "Написать README",
  "description": "Описать инфраструктурную часть проекта",
  "completed": false
}
```

Интерактивная документация доступна на `/docs` (Swagger UI) и `/redoc` —
генерируется из тех же схем, отдельно поддерживать её не нужно.

### База данных

Схема состоит из одной таблицы и создаётся скриптом `data_base/init_db.sql`.
Он монтируется в `/docker-entrypoint-initdb.d/`, поэтому применяется
автоматически при первой инициализации тома PostgreSQL.

| Поле | Тип | Ограничения |
|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` |
| `title` | `VARCHAR(255)` | `NOT NULL` |
| `description` | `TEXT` | — |
| `completed` | `BOOLEAN` | `DEFAULT FALSE` |

Данные лежат в именованном volume `postgres_data`, так что `docker compose down`
их не удаляет.

## Контейнеризация

Образ собирается в два этапа. На стадии `builder` зависимости компилируются в
wheel-пакеты, на стадии `runtime` они ставятся из готовых колёс с
`--no-index` — в финальный образ не попадают ни компиляторы, ни кеш pip.

| Стадия | Что делает | Что остаётся в образе |
|---|---|---|
| `builder` | `pip wheel` для всех зависимостей в `/wheels` | ничего, стадия отбрасывается |
| `runtime` | установка из `/wheels`, копирование кода | Python 3.13-slim, зависимости, `app/` |

Приложение запускается не от root: в образе создаются системная группа
`workgroup` и пользователь `workuser`, код копируется с `--chown`, и последней
инструкцией перед `CMD` идёт `USER workuser`. Если контейнер скомпрометируют,
права внутри него будут минимальными.

### Compose-стек

Один и тот же `compose.yml` используется и локально, и на сервере — разница
только в содержимом `.env`.

| Сервис | Образ | Порт | Назначение |
|---|---|---|---|
| `web` | `${DOCKERHUB_USERNAME}/task-tracker-api:latest` | `8000` | API |
| `db` | `postgres:16-alpine` | `5433 → 5432` | база данных |
| `prometheus` | `prom/prometheus:v3.14.0` | `9090` | сбор метрик |
| `grafana` | `grafana/grafana:13.2.1` | `3000` | визуализация |

У базы настроен healthcheck на `pg_isready`, а `web` объявляет зависимость
`condition: service_healthy`. Без этого приложение стартовало бы раньше, чем
PostgreSQL готов принимать соединения, и падало на создании пула. Версии
образов зафиксированы явно — чтобы окружение не менялось само по себе между
запусками пайплайна.

## Тестирование

Тесты интеграционные: приложение поднимается целиком через
`httpx.AsyncClient` с `ASGITransport` и ходит в настоящий PostgreSQL. Моков
базы нет — проверяется в том числе корректность SQL.

| Фикстура | Скоуп | Что делает |
|---|---|---|
| `db_pool` | `session` | создаёт пул к тестовой БД из `TEST_DATABASE_URL` |
| `set_up_db` | функция, `autouse` | `TRUNCATE ... RESTART IDENTITY` перед каждым тестом |
| `client` | функция | подменяет зависимость `get_db` и отдаёт HTTP-клиент |

Очистка таблицы с `RESTART IDENTITY` перед каждым тестом означает, что тесты
не зависят от порядка запуска и от данных, оставшихся от предыдущего прогона.
Подмена делается через `app.dependency_overrides` и снимается после теста, так
что продовый код ничего не знает о тестовом окружении.

```bash
pip install -r requirements-dev.txt
export TEST_DATABASE_URL="postgresql://user:password@127.0.0.1:5433/test_db"
pytest
```

## CI/CD

Пайплайн описан в `.github/workflows/ci-cd.yml` и состоит из четырёх job'ов,
связанных через `needs` — каждый следующий запускается только после успеха
предыдущего.

| Job | Что делает | Когда выполняется |
|---|---|---|
| `lint-and-test` | flake8 + pytest на сервисном контейнере PostgreSQL | всегда |
| `build-and-push-docker` | multi-stage сборка и публикация в Docker Hub | только `main` |
| `terraform-provision` | `fmt` → `validate` → `plan` → `apply` | только `main` |
| `ansible-configure-deploy` | установка Docker и деплой стека на ВМ | только `main` |

| Триггер | Что запускается |
|---|---|
| push в `main` | весь пайплайн целиком |
| push в `feature/*` | только линт и тесты |
| pull request в `main` | только линт и тесты |
| `workflow_dispatch` | весь пайплайн вручную |

Разделение сделано осознанно: проверки идут на каждую ветку и каждый PR, но
образ собирается и деплоится только из `main`. Код не может попасть в прод,
не пройдя тесты, и при этом ветки не тратят время на выкатку.

Линтер запускается в строгом наборе `--select=E9,F63,F7,F82` — это ошибки
парсинга, некорректные сравнения и обращения к неопределённым именам, то есть
то, что действительно ломает выполнение, а не стилистические замечания.

Тесты в CI ходят в сервисный контейнер `postgres:16-alpine` с healthcheck'ом.
Схема в него накатывается отдельным шагом: `init_db.sql` монтируется в
одноразовый контейнер `psql`, запущенный с `--net=host`.

Каждый образ публикуется сразу с двумя тегами:

| Тег | Зачем |
|---|---|
| `:latest` | его подтягивает `compose.yml` на сервере |
| `:${{ github.sha }}` | позволяет вернуться к образу конкретного коммита |

## Инфраструктура (Terraform)

```mermaid
flowchart LR
    dev[Developer] -->|git push| gh[GitHub Actions]

    subgraph CI["CI"]
        lint[flake8] --> test[pytest + PostgreSQL service]
        test --> build[Docker build & push]
    end

    subgraph CD["CD"]
        tf[Terraform apply] --> ans[Ansible playbooks]
    end

    gh --> CI
    build --> hub[(Docker Hub)]
    CI --> CD

    subgraph YC["Yandex Cloud VM"]
        api[FastAPI :8000]
        db[(PostgreSQL :5432)]
        prom[Prometheus :9090]
        graf[Grafana :3000]

        api --> db
        prom -->|scrape /metrics| api
        graf --> prom
    end

    hub -.->|docker compose pull| api
    ans --> YC
```

Конфигурация в `terraform/` описывает всё, что нужно приложению в Yandex
Cloud. Ресурсы разнесены по файлам по назначению, чтобы конфигурация читалась
без поиска по одному длинному файлу.

| Файл | Ресурсы |
|---|---|
| `network.tf` | `yandex_vpc_network`, `yandex_vpc_subnet` |
| `security.tf` | `yandex_vpc_security_group` |
| `compute.tf` | `yandex_compute_instance` + data-source образа Ubuntu 22.04 LTS |
| `provider.tf` | конфигурация провайдера |
| `variables.tf` | входные переменные с дефолтами |
| `outputs.tf` | имя ВМ, приватный и публичный IP |
| `versions.tf` | пины версий и S3-backend |

Виртуальная машина берётся не по фиксированному ID образа, а через
`data "yandex_compute_image"` с `family = "ubuntu-2204-lts"` — так при
пересоздании подтягивается актуальный образ семейства, а не устаревший
снапшот. Публичный ключ SSH прокидывается через `metadata.ssh-keys`, поэтому
Ansible получает доступ сразу после создания ВМ, без ручной настройки.

Правила security group:

| Порт | Назначение |
|---|---|
| 22 | SSH для Ansible |
| 80, 443 | зарезервированы под reverse proxy |
| 8000 | приложение |
| 3000 | Grafana |

Egress открыт полностью — серверу нужно ходить в Docker Hub и apt-репозитории.

### Состояние

State хранится удалённо, в S3-совместимом Object Storage Yandex Cloud
(`versions.tf`, backend `s3`, ключ `prod/terraform.tfstate`). Это принципиально
для пайплайна: раннер GitHub Actions каждый раз новый, и с локальным state
второй запуск попытался бы создать всю инфраструктуру заново. С удалённым
state `terraform apply` видит уже созданные ресурсы и остаётся идемпотентным.

Перед `apply` в пайплайне выполняются `terraform fmt -check` и
`terraform validate` — форматирование и синтаксис проверяются до того, как
что-либо будет создано в облаке.

### Удаление инфраструктуры

Отдельный workflow `destroy-infr.yml` запускается только вручную и требует
ввести строку `destroy` в поле подтверждения — при любом другом значении job
падает на первом шаге. Выполняется он в окружении `production`, к которому
можно привязать required reviewers. Последним шагом с `if: always()` печатается
`terraform state list`, чтобы было видно, не осталось ли ресурсов.

Ключи сервисного аккаунта и SSH записываются на раннер во временные файлы и
удаляются шагами с `if: always()` — даже если пайплайн упадёт посередине,
файлы с секретами не останутся в рабочей директории.

## Конфигурация сервера (Ansible)

Инвентарь не хранится в репозитории как статический файл: публичный IP
берётся из output'а Terraform и передаётся в `ansible-playbook` строкой прямо
из пайплайна. Перед запуском плейбуков CI ждёт, пока ВМ начнёт принимать
SSH-соединения — до 30 попыток `ssh-keyscan` с паузой в 10 секунд, потому что
после `terraform apply` машина ещё несколько десятков секунд загружается.

| Плейбук | Что делает |
|---|---|
| `install_docker.yml` | ставит Docker CE и `docker-compose-plugin` из официального репозитория |
| `deploy.yml` | раскладывает конфиги, генерирует `.env`, поднимает стек |

`install_docker.yml` не использует пакет из репозитория Ubuntu, а добавляет
официальный репозиторий Docker: скачивает GPG-ключ, переводит его в бинарный
формат, подключает источник и ставит `docker-ce`, `docker-ce-cli`,
`containerd.io`, `docker-compose-plugin`. Затем включает автозапуск сервиса и
добавляет пользователя в группу `docker`.

`deploy.yml` создаёт `/opt/task-tracker` со структурой подкаталогов,
копирует `compose.yml`, конфигурацию Prometheus, provisioning Grafana и
init-скрипт БД, после чего выполняет `docker compose pull` и
`docker compose up -d --remove-orphans`. Флаг `--remove-orphans` убирает
контейнеры от сервисов, которых больше нет в compose-файле.

Файл `.env` на сервере не копируется из репозитория, а генерируется из шаблона
`templates/env.j2` по переменным окружения. Задача помечена `no_log: true`,
чтобы значения не попали в лог пайплайна, и файл создаётся с правами `0600`.

## Секреты

В репозитории нет ни одного секрета — только `.env.example` и
`terraform.tfvars.example` с плейсхолдерами. Всё остальное живёт в GitHub
Secrets и попадает в пайплайн через переменные окружения.

| Секрет | Назначение |
|---|---|
| `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` | публикация образа |
| `YC_CLOUD_ID`, `YC_FOLDER_ID`, `YC_KEY_FILE` | доступ к Yandex Cloud |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | доступ к S3-backend для state |
| `SSH_PUBLIC_KEY`, `SSH_PRIVATE_KEY`, `SERVER_SSH_USER` | доступ Ansible к ВМ |
| `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | подключение к БД |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | учётная запись Grafana |

Terraform-переменные передаются через префикс `TF_VAR_`, поэтому в
`.tfvars`-файлах на раннере нужды нет.

## Мониторинг

Метрики собираются библиотекой `prometheus-fastapi-instrumentator`, которая
публикует их на эндпоинте `/metrics` в формате Prometheus. Инструментатор
настроен с `should_group_status_codes=False` — коды ответов не схлопываются в
группы `2xx` / `5xx`, поэтому в метриках виден каждый конкретный статус.

Prometheus снимает метрики с таргета `web:8000` (job `task-tracker-api`).
Grafana подключается к Prometheus через provisioning: датасорс и дашборд
поднимаются автоматически при старте контейнера, ручная настройка через UI
не требуется.

### Дашборд «FastAPI Observability»

Находится в папке `Task Tracker API`, окно по умолчанию — последний час,
автообновление раз в 5 секунд. Переменная `$app_name` подставляется из
`label_values(http_requests_total, job)` и позволяет переключаться между
инстансами приложения, если их станет несколько.

Служебный эндпоинт `/metrics` исключён из большинства панелей фильтром
`handler!="/metrics"`, чтобы собственные обращения Prometheus не искажали
статистику по бизнес-эндпоинтам.

**Трафик**

| Панель | Метрика | Что показывает |
|---|---|---|
| Total Requests | `sum(http_requests_total)` | Суммарное число запросов за всё время работы инстанса |
| Requests Count | `http_requests_total` | Разбивка счётчика по методу и хендлеру |
| Request Per Sec | `rate(http_requests_total[1m])` | Текущий RPS по каждому хендлеру |

**Латентность**

| Панель | Метрика | Что показывает |
|---|---|---|
| Requests Average Duration | `http_request_duration_seconds_sum / _count` | Средняя длительность запроса по эндпоинтам |
| PR 99 Requests Duration | `histogram_quantile(0.99, rate(..._bucket[1m]))` | 99-й перцентиль — хвост распределения, который средняя скрывает |

Перцентиль считается из гистограммы `http_request_duration_seconds_bucket`.
Средняя длительность и p99 намеренно выведены рядом: расхождение между ними
показывает, есть ли у сервиса «медленный хвост» запросов.

**Надёжность**

| Панель | Метрика | Что показывает |
|---|---|---|
| Percent of 2xx Requests | доля `status=~"2.*"` от всех запросов | Доля успешных ответов, порог тревоги ниже 80% |
| Percent of 5xx Requests | доля `status=~"5.*"` от всех запросов | Доля серверных ошибок, порог тревоги выше 10% |

Пороги заданы в `thresholds` панелей: график 2xx краснеет при падении ниже
0.8, график 5xx — при росте выше 0.1.

**Ресурсы процесса**

| Панель | Метрика | Что показывает |
|---|---|---|
| Python Process Resident Memory Use | `process_resident_memory_bytes` | Потребление RSS процессом Uvicorn |
| Python Process CPU Use | `irate(process_cpu_seconds_total[5m])` | Загрузка CPU процессом |

Эти метрики отдаёт стандартный `prometheus_client` без дополнительной
настройки. Они полезны, чтобы отличить деградацию из-за нехватки ресурсов
на VM от проблем в самом коде: если латентность растёт вместе с RSS, дело,
скорее всего, в утечке памяти, а не в запросах к БД.

### Как посмотреть

```bash
docker compose up -d
```

Grafana доступна на `http://localhost:3000`, логин и пароль берутся из
`GRAFANA_ADMIN_USER` и `GRAFANA_ADMIN_PASSWORD`. Дашборд появится сам —
провижининг настроен с `updateIntervalSeconds: 30`, поэтому правки в JSON
подхватываются без перезапуска контейнера.

Чтобы на графиках появились данные, сделайте несколько запросов к API:

```bash
for i in $(seq 1 50); do
  curl -s -X POST http://localhost:8000/tasks \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"Task $i\"}" > /dev/null
  curl -s http://localhost:8000/tasks > /dev/null
done
```

## Запуск локально

```bash
git clone https://github.com/exlip-creator/Task-tracker-api.git
cd Task-tracker-api

cp .env.example .env
# заполнить переменные в .env

docker compose up -d --build
```

| Сервис | Адрес |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| Метрики | http://localhost:8000/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| PostgreSQL | `localhost:5433` |

Порт PostgreSQL наружу проброшен как `5433`, чтобы не конфликтовать с локально
установленной базой на `5432`.

## Развёртывание в облаке

Подготовка выполняется один раз:

1. Создать сервисный аккаунт в Yandex Cloud с правами на вычислительные и
   сетевые ресурсы, выгрузить authorized key в JSON.
2. Создать бакет в Object Storage под state Terraform — имя должно совпадать
   с указанным в `terraform/versions.tf` — и статический ключ доступа к нему.
3. Заполнить секреты из таблицы выше в настройках репозитория.

Дальше выкатка идёт сама: push в `main` или ручной запуск workflow. Чтобы
удалить созданные ресурсы, нужно запустить workflow **Destroy infrastructure**
и ввести `destroy` в поле подтверждения.

## Структура репозитория

```
.
├── app/                  # FastAPI-приложение, схемы, тесты
├── data_base/            # init-скрипт схемы PostgreSQL
├── terraform/            # IaC: сеть, ВМ, security group, outputs, S3-backend
├── ansible/              # установка Docker и деплой приложения
├── prometheus/           # конфигурация сбора метрик
├── grafana/provisioning/ # автоподключение datasource и дашборда
├── .github/workflows/    # CI/CD и workflow удаления инфраструктуры
├── Dockerfile            # multi-stage сборка образа
└── compose.yml           # локальный и продовый стек сервисов
```

## Почему web-часть такая простая

Это сознательное решение. Цель проекта — не написать очередной таск-трекер, а
пройти весь путь кода от коммита до работающего в облаке сервиса под
мониторингом: спроектировать инфраструктуру как код, собрать пайплайн,
разобраться с секретами, удалённым состоянием Terraform, идемпотентностью
Ansible и наблюдаемостью.

Простое приложение здесь скорее преимущество: четыре CRUD-эндпоинта дают ровно
столько поведения, сколько нужно, чтобы пайплайну было что тестировать,
Prometheus — что измерять, а Grafana — что показывать, и при этом не отвлекают
внимание от инфраструктурной части. Усложнить бизнес-логику при готовой
инфраструктуре — вопрос нескольких файлов в `app/`; всё остальное менять не
придётся.

## Направления развития

| Что | Зачем |
|---|---|
| Reverse proxy (nginx / Traefik) с TLS | убрать прямой проброс порта `8000`, задействовать 80 и 443 |
| Сузить security group | SSH и Grafana сейчас открыты в `0.0.0.0/0` |
| Alertmanager | алерты поверх уже собираемых метрик и заданных порогов |
