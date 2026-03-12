# OpenClaw — Личный AI-ассистент на Beget VPS

## Обзор проекта

Разворачиваем OpenClaw (open-source AI-агент, MIT) на VPS Beget с подключением к Telegram.
Модель: DeepSeek V3.2 Exp через polza.ai (OpenAI-compatible endpoint, оплата в рублях).

**Цель:** персональный ассистент в Telegram, знающий профессию, проекты и цели владельца.

---

## Инфраструктура

| Компонент | Значение |
|---|---|
| Хостинг | Beget VPS |
| Локация | Москва |
| ОС | Ubuntu 24.04 LTS |
| RAM | 6 GB |
| vCPU | 1–2 |
| SSD | 10 GB |
| Ориентировочная стоимость | ~660 ₽/мес |

---

## LLM-провайдер

**Выбор: Qwen Flash через polza.ai** (переключили с DeepSeek V3.2 для экономии)

Причины отказа от локальных моделей:
- 2GB RAM не хватает для OpenClaw + Ollama одновременно
- Модели, влезающие в 2GB (1–2B параметров), дают 4k–8k контекст — ниже минимума OpenClaw (16k)
- Качество tool calls у малых моделей нестабильное

Причины использовать polza.ai вместо прямых API:
- Оплата рублями (российские карты)
- OpenAI-compatible API — никаких изменений кода
- Наценка ~5% к провайдерской стоимости

| Параметр | Значение |
|---|---|
| Провайдер | polza.ai |
| API Base URL | `https://polza.ai/api/v1` |
| Модель | `qwen/qwen3.5-flash-02-23` |
| Тип | OpenAI-compatible |
| contextWindow | 32768 токенов (уменьшили с 65536 для экономии) |
| Цена input | 8,6 ₽ / 1M токенов |
| Ориентировочные расходы | 10–30 ₽/мес |

---

## Каналы связи

- **Telegram** — основной канал управления ассистентом

---

## Стек

- **OpenClaw** — AI-агент (open-source, MIT)
- **Node.js 22** — runtime (обязательная версия)
- **nohup** — запуск gateway (systemd user services недоступны на этом сервере)
- **UFW** — firewall (порты: 22, 80, 443)

---

## Структура файлов на сервере

```
/home/openclaw/
├── .openclaw/
│   ├── openclaw.json        # конфигурация провайдера и каналов
│   ├── SOUL.md              # личность и знания ассистента
│   └── workspace/
│       └── MEMORY.md        # факты о пользователе (RAG-память)
└── .npm-global/bin/openclaw # бинарник
```

---

## Конфигурация (openclaw.json)

> Telegram НЕ настраивается через `openclaw onboard` — токен прописывается вручную в секции `channels`.

```json
{
  "models": {
    "mode": "merge",
    "providers": {
      "polza": {
        "type": "openai-compatible",
        "baseUrl": "https://polza.ai/api/v1",
        "apiKey": "ТВОЙ_КЛЮЧ_ОТ_POLZA.AI",
        "model": "qwen/qwen3.5-flash-02-23",
        "contextWindow": 32768
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "polza/qwen/qwen3.5-flash-02-23"
      }
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "ТВОЙ_TELEGRAM_BOT_TOKEN",
      "dmPolicy": "pairing",
      "allowFrom": ["tg:ТВОЙ_TELEGRAM_USER_ID"]
    }
  }
}
```

---

## SOUL.md — профиль ассистента

Файл `~/.openclaw/SOUL.md` определяет личность бота:

- Кто такой Женя (профессия, навыки, цели)
- Стиль общения
- Логика оценки идей
- Прайс на услуги
- Текущие цели (AI Engineer, клиентская база)

---

## План установки

### Блок 1 — Подготовка сервера (от root) ✅
- [x] Арендовать VPS на Beget (Москва, Ubuntu 24.04, 2GB)
- [x] Подключиться по SSH: `ssh root@<IP>`
- [x] `apt update && apt upgrade -y`
- [x] Установить Node.js 22:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt install -y nodejs
  node --version  # должно быть v22.x
  ```
- [x] Настроить UFW:
  ```bash
  ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
  ```
- [x] Создать пользователя: `adduser --disabled-password --gecos "" openclaw`

### Блок 2 — Установка OpenClaw (от пользователя openclaw) ✅
- [x] `su - openclaw`
- [x] `curl -fsSL https://openclaw.ai/install.sh | bash`
- [x] Добавить в PATH (npm-global):
  ```bash
  echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
  ```
- [x] Проверить: `openclaw --version`

### Блок 3 — Получение ключей ✅
- [x] Зарегистрироваться на polza.ai → создать API-ключ (оплата рублями)
- [x] Создать Telegram-бота через @BotFather → токен сохранён в openclaw.json
- [x] Узнать свой Telegram User ID через @userinfobot → сохранён (1039905495)

### Блок 4 — Онбординг и настройка конфига ✅
- [x] Запустить мастер (настраивает только LLM, не Telegram):
  ```bash
  openclaw onboard
  # Провайдер: OpenAI-compatible
  # URL: https://polza.ai/api/v1
  # Модель: qwen/qwen3.5-flash-02-23
  ```
- [x] Вручную прописать Telegram в конфиг:
  ```bash
  nano ~/.openclaw/openclaw.json
  ```
  Добавить секцию `channels` (см. раздел "Конфигурация" выше)
- [x] Gateway запущен через nohup:
  ```bash
  nohup su - openclaw -c "/home/openclaw/.npm-global/bin/openclaw gateway" > /tmp/openclaw.log 2>&1 &
  ```

### Блок 5 — Проверка ✅
- [x] `openclaw doctor`
- [x] `openclaw gateway status`
- [x] Написать боту в Telegram — он попросит подтвердить pairing (ввести код)
- [x] Подтвердить pairing → бот готов
- [x] При проблемах: `openclaw logs`

### Блок 6 — Персонализация ✅
- [x] Настроить `~/.openclaw/SOUL.md` (личность, профессия, стиль общения)
- [x] Создать `MEMORY.md` с фактами о пользователе (цели, проекты, предпочтения)
- [x] contextWindow установлен в 32768 (уменьшили с 65536 для экономии)
- [x] `openclaw gateway restart`
- [x] Финальный тест диалога — Боб читает MEMORY.md, отвечает профессионально

### Блок 7 — Инструменты и расширение
- [x] Переключить tool profile с `coding` на `full` в openclaw.json
- [x] Включить browser-инструмент (Playwright) — установлен для root и openclaw
- [ ] **Подключить n8n через MCP** (не REST API — более надёжная архитектура):
  - Установить `n8n-mcp` пакет на сервер: `npm i -g n8n-mcp`
  - Получить n8n API Key: Railway n8n → Settings → n8n API → Create API key
  - Прописать MCP сервер в конфиг OpenClaw
  - n8n воркфлоу становятся нативными инструментами Боба
  - Тест: Боб видит и запускает воркфлоу напрямую
  - Ссылки: https://github.com/czlonkowski/n8n-mcp, https://github.com/leonardsellem/n8n-mcp-server
- [ ] Создать субагента "n8n-оператор":
  - [ ] Отдельный Telegram-бот через @BotFather
  - [ ] Настроить как второй агент в OpenClaw (`openclaw agents add n8n-operator`)
  - [ ] Написать SOUL.md для субагента (роль: управление n8n, триггеры, логика)
  - [ ] Связать основного Боба с субагентом
- [ ] Финальный тест: Боб → субагент → n8n
- [x] **GitHub доступ для Боба**:
  - [x] Создать GitHub Personal Access Token (repo + admin:org права)
  - [x] Установить `gh` CLI на сервер
  - [x] Авторизовать: `gh auth login --with-token` (аккаунт: Kowkapro)
  - [x] Токен прописан в MEMORY.md на сервере — Боб знает как использовать gh
  - [x] Тест пройден: Боб видит репозитории

### Блок 8 — ClawHub: выбор и установка скиллов
- [x] Установить ClawHub CLI: `npm i -g clawhub`
- [x] Приоритетные скиллы установлены:
  - [x] **Summarize** — установлен в workspace/skills/summarize
  - [x] **GitHub** — установлен в workspace/skills/github
  - [x] **DuckDuckGo Search** — установлен в workspace/skills/duckduckgo-search (замена Tavily)
  - [x] **Self-Improving Agent** — установлен в workspace/skills/self-improving-agent (замена Capability Evolver)
  - ❌ Capability Evolver — заблокирован clawhub как malware
  - ❌ Tavily — заблокирован VirusTotal, Brave API платный
- [ ] Проверить каждый скилл в диалоге с Бобом (clawhub-скиллы не видны Бобу — возможно несовместимы с v2026.3.11)
- [ ] При необходимости — доустановить по категориям: `clawhub search ""`

### Блок 9 — Мультимодальность
- [ ] **Голосовые сообщения (STT)**: подключить Whisper через polza.ai API
  - Проверить наличие Whisper-модели на polza.ai
  - Прописать транскрипцию в openclaw.json (`transcription` секция)
- [ ] **Распознавание картинок (Vision)**: проверить поддержку в DeepSeek V3.2
  - Если нет — добавить отдельную vision-модель через polza.ai
  - Бот должен читать текст с картинок и описывать изображения
- [ ] **Саммари видео**:
  - YouTube URL → yt-dlp → аудио → Whisper → саммари
  - Локальный файл → ffmpeg → аудио → Whisper → саммари
  - Оформить как скилл OpenClaw

---

## Systemd-служба (ручная установка если мастер не создал)

```ini
[Unit]
Description=OpenClaw AI Agent
After=network.target

[Service]
Type=simple
User=openclaw
ExecStart=/home/openclaw/.local/bin/openclaw gateway start
Restart=always
RestartSec=10
# OPENCLAW_TELEGRAM_DISABLE_AUTO_SELECT_FAMILY — обходит IPv6-проблемы при подключении к Telegram API
# на серверах где IPv6 активен но нестабилен (Beget Рига). Убрать если проблем нет.
Environment=OPENCLAW_TELEGRAM_DISABLE_AUTO_SELECT_FAMILY=true

[Install]
WantedBy=multi-user.target
```

Активация службы (от root):

```bash
# Создать файл службы
nano /etc/systemd/system/openclaw.service
# (вставить содержимое выше)

# Зарегистрировать и запустить
systemctl daemon-reload
systemctl enable openclaw
systemctl start openclaw

# Проверить статус
systemctl status openclaw
```

---

## Расходы

| Статья | Цена |
|---|---|
| Beget VPS 6GB, Москва | ~990 ₽/мес |
| polza.ai (Qwen Flash) | ~10–30 ₽/мес |
| **Итого** | **~670–690 ₽/мес** |

---

## Статус

- [x] VPS арендован
- [x] OpenClaw установлен
- [x] Qwen Flash подключён через polza.ai
- [x] Telegram-бот работает
- [x] SOUL.md настроен
- [x] MEMORY.md создан, RAG-память работает
- [x] Tool profile = full
- [x] GitHub доступ (gh CLI, Kowkapro)
- [x] Browser-инструмент (Playwright)
- [ ] n8n через MCP подключён
- [ ] Субагент n8n-оператор создан
- [~] ClawHub скиллы установлены (но не подхватываются ботом — нужно разобраться)
