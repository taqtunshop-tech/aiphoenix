# APS Token Worker — Setup Guide

## 1. Регистрация Autodesk Developer Account
1. Перейти на https://aps.autodesk.com/
2. Click "Get Started" → Sign Up (бесплатно)
3. Создать приложение:
   - Name: `aiphx-viewer`
   - Callback URL: `https://taqtunshop-tech.github.io/aiphoenix/`
   - Принять Terms of Service
4. Скопировать **Client ID** и **Client Secret**

## 2. Установка Cloudflare Workers
```bash
npm install -g wrangler
wrangler login
```

## 3. Деплой Worker
```bash
cd worker/
wrangler secret put APS_CLIENT_ID     # вставить Client ID
wrangler secret put APS_CLIENT_SECRET  # вставить Client Secret
wrangler deploy
```

Worker будет доступен по URL вида:
`https://aps-token-worker.<ваш-аккаунт>.workers.dev/api/token`

## 4. Настройка calculator.html
В файле calculator.html найти `APS_CONFIG` и вставить:
- `clientId` — ваш Client ID
- `workerUrl` — URL задеплоенного Worker

## 5. Тест
Открыть calculator.html → выбрать модель → DWG загрузится через APS Viewer.

## Лимиты (Free Tier)
- APS: 300 000 API calls/мес
- Cloudflare Workers: 100 000 запросов/день
- Стоимость: $0
