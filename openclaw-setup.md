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
| Локация | Москва (Рига распродана) |
| ОС | Ubuntu 22.04 LTS |
| RAM | 2 GB |
| vCPU | 1–2 |
| SSD | 20 GB |
| Ориентировочная стоимость | ~660 ₽/мес |

---

## LLM-провайдер

**Выбор: DeepSeek V3.2 Exp через polza.ai**

Причины отказа от локальных моделей:
- 2GB RAM не хватает для OpenClaw + Ollama одновременно
- Модели, влезающие в 2GB (1–2B параметров), дают 4k–8k контекст — ниже минимума OpenClaw (16k)
- Качество tool calls у малых моделей нестабильное

Причины использовать polza.ai вместо прямого DeepSeek API:
- Оплата рублями (российские карты) — прямой DeepSeek API оплатить из РФ проблематично
- OpenAI-compatible API — никаких изменений кода
- Наценка ~5% к провайдерской стоимости

| Параметр | Значение |
|---|---|
| Провайдер | polza.ai |
| API Base URL | `https://polza.ai/api/v1` |
| Модель | `deepseek/deepseek-v3.2-exp` |
| Тип | OpenAI-compatible |
| Контекст | 64k токенов |
| Цена input | 23,32 ₽ / 1M токенов |
| Цена output | 35,42 ₽ / 1M токенов |
| Ориентировочные расходы | 30–100 ₽/мес |

---

## Каналы связи

- **Telegram** — основной канал управления ассистентом

---

## Стек

- **OpenClaw** — AI-агент (open-source, MIT)
- **Node.js 22** — runtime (обязательная версия)
- **systemd** — автозапуск службы
- **UFW** — firewall (порты: 22, 80, 443)

---

## Структура файлов на сервере

```
/home/openclaw/
├── .openclaw/
│   ├── openclaw.json     # конфигурация провайдера и каналов
│   └── SOUL.md           # личность и знания ассистента
└── .local/bin/openclaw   # бинарник
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
        "model": "deepseek/deepseek-v3.2-exp",
        "contextWindow": 65536
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "polza/deepseek/deepseek-v3.2-exp"
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

### Блок 1 — Подготовка сервера (от root)
- [ ] Арендовать VPS на Beget (Рига, Ubuntu 22.04, 2GB)
- [ ] Подключиться по SSH: `ssh root@<IP>`
- [ ] `apt update && apt upgrade -y`
- [ ] Установить Node.js 22:
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt install -y nodejs
  node --version  # должно быть v22.x
  ```
- [ ] Настроить UFW:
  ```bash
  ufw allow 22 && ufw allow 80 && ufw allow 443 && ufw enable
  ```
- [ ] Создать пользователя: `adduser --disabled-password --gecos "" openclaw`

### Блок 2 — Установка OpenClaw (от пользователя openclaw)
- [ ] `su - openclaw`
- [ ] `curl -fsSL https://openclaw.ai/install.sh | bash`
- [ ] Добавить в PATH:
  ```bash
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
  ```
- [ ] Проверить: `openclaw --version`

### Блок 3 — Получение ключей
- [ ] Зарегистрироваться на polza.ai → создать API-ключ (оплата рублями)
- [ ] Создать Telegram-бота через @BotFather → сохранить токен вида `123456789:ABC...`
- [ ] Узнать свой Telegram User ID через @userinfobot → сохранить число

### Блок 4 — Онбординг и настройка конфига
- [ ] Запустить мастер (настраивает только LLM и daemon, не Telegram):
  ```bash
  openclaw onboard --install-daemon
  # Провайдер: OpenAI-compatible
  # URL: https://polza.ai/api/v1
  # Модель: deepseek/deepseek-v3.2-exp
  # Daemon: yes
  ```
- [ ] Вручную прописать Telegram в конфиг:
  ```bash
  nano ~/.openclaw/openclaw.json
  ```
  Добавить секцию `channels` (см. раздел "Конфигурация" выше)
- [ ] Перезапустить gateway: `openclaw gateway restart`

### Блок 5 — Проверка
- [ ] `openclaw doctor`
- [ ] `openclaw gateway status`
- [ ] Написать боту в Telegram — он попросит подтвердить pairing (ввести код)
- [ ] Подтвердить pairing → бот готов
- [ ] При проблемах: `openclaw logs`

### Блок 6 — Персонализация ✅
- [x] Настроить `~/.openclaw/SOUL.md` (личность, профессия, стиль общения)
- [x] Создать `MEMORY.md` с фактами о пользователе (цели, проекты, предпочтения)
- [x] contextWindow увеличен до 65536
- [x] `openclaw gateway restart`
- [x] Финальный тест диалога — Боб читает MEMORY.md, отвечает профессионально

### Блок 7 — Инструменты и расширение
- [ ] Переключить tool profile с `coding` на `full` в openclaw.json
- [ ] Включить browser-инструмент (Playwright) — проверить доступность и RAM
- [ ] Подключить n8n на Railway: добавить API URL и токен в конфиг Боба
- [ ] Создать субагента "n8n-оператор":
  - [ ] Отдельный Telegram-бот через @BotFather
  - [ ] Настроить как второй агент в OpenClaw (`openclaw agents add n8n-operator`)
  - [ ] Написать SOUL.md для субагента (роль: управление n8n, триггеры, логика)
  - [ ] Связать основного Боба с субагентом
- [ ] Финальный тест: Боб → субагент → n8n
- [ ] **GitHub доступ для Боба**:
  - Создать GitHub Personal Access Token (repo + contents права)
  - Установить `gh` CLI на сервер (`apt install gh`)
  - Авторизовать через токен: `gh auth login`
  - Прописать токен в SOUL.md или AGENTS.md чтобы Боб знал как использовать gh
  - Тест: попросить Боба показать список репозиториев

### Блок 8 — ClawHub: выбор и установка скиллов
- [ ] Установить ClawHub CLI: `npm i -g clawhub`
- [ ] Изучить каталог: `clawhub search ""` (все скиллы)
- [ ] Категории для оценки:
  - Memory / RAG
  - Web search / Browser
  - Telegram / Social media
  - Productivity / Tasks
  - Code / Dev tools
- [ ] Выбрать нужные, установить: `clawhub install <skill-slug>`
- [ ] Проверить каждый скилл в диалоге с Бобом

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
| Beget VPS 2GB, Москва | ~660 ₽/мес |
| polza.ai (DeepSeek V3.2 Exp) | ~30–100 ₽/мес |
| **Итого** | **~690–760 ₽/мес** |

---

## Статус

- [x] VPS арендован
- [x] OpenClaw установлен
- [x] DeepSeek подключён
- [x] Telegram-бот работает
- [x] SOUL.md настроен
- [x] MEMORY.md создан, RAG-память работает
- [ ] Tool profile = full, browser включён
- [ ] n8n (Railway) подключён
- [ ] Субагент n8n-оператор создан
- [ ] ClawHub скиллы выбраны и установлены
