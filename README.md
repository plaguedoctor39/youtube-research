# YouTube Research MCP Server

MCP сервер для работы с YouTube из Claude Code — поиск видео, получение метаданных и субтитров.

## Инструменты

| Инструмент | Описание |
|---|---|
| `youtube_search(query, max_results)` | Поиск видео по запросу |
| `youtube_video_info(video_url_or_id)` | Метаданные видео по ссылке/ID |
| `youtube_transcript(video_url_or_id, lang)` | Субтитры видео с таймкодами |

## Установка

### 1. Получение YouTube API ключа

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект (или выберите существующий)
3. Перейдите в **APIs & Services → Library**
4. Найдите и включите **YouTube Data API v3**
5. Перейдите в **APIs & Services → Credentials**
6. Нажмите **Create Credentials → API Key**
7. Скопируйте ключ

### 2. Установка зависимостей

```bash
cd /path/to/youtube_research
uv sync
```

### 3. Конфигурация Claude Code

Добавьте в `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "youtube-research": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/youtube_research", "server.py"],
      "env": {
        "YOUTUBE_API_KEY": "ваш_ключ"
      }
    }
  }
}
```

Замените `/path/to/youtube_research` на фактический путь к проекту.

### 4. Перезапуск

Перезапустите Claude Code — инструменты `youtube_search`, `youtube_video_info` и `youtube_transcript` станут доступны.

## Примеры использования

В Claude Code:

- «Найди видео про Python asyncio» → вызовет `youtube_search`
- «Покажи информацию о видео https://youtu.be/dQw4w9WgXcQ» → вызовет `youtube_video_info`
- «Получи субтитры этого видео: https://youtube.com/watch?v=...» → вызовет `youtube_transcript`
