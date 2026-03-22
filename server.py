import os
import re

from fastmcp import FastMCP
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import (
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

mcp = FastMCP("youtube-research")

# --- Helpers ---

_YOUTUBE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)"
    r"([a-zA-Z0-9_-]{11})"
)
_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

_yt_client = None


def extract_video_id(url_or_id: str) -> str:
    """Извлекает video ID из URL или возвращает как есть, если это уже ID."""
    url_or_id = url_or_id.strip()
    m = _YOUTUBE_URL_RE.search(url_or_id)
    if m:
        return m.group(1)
    if _VIDEO_ID_RE.match(url_or_id):
        return url_or_id
    raise ValueError(f"Не удалось извлечь video ID из: {url_or_id}")


def parse_duration(iso: str) -> str:
    """Конвертирует ISO 8601 duration (PT1H2M3S) в читаемый формат."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    if h:
        return f"{h}:{mi:02d}:{s:02d}"
    return f"{mi}:{s:02d}"


def get_youtube_client():
    """Ленивый синглтон YouTube API клиента."""
    global _yt_client
    if _yt_client is None:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Переменная окружения YOUTUBE_API_KEY не установлена. "
                "Получите ключ в Google Cloud Console: "
                "APIs & Services → Credentials → Create API Key, "
                "затем включите YouTube Data API v3."
            )
        _yt_client = build("youtube", "v3", developerKey=api_key)
    return _yt_client


def _format_video(snippet: dict, details: dict, stats: dict, video_id: str) -> dict:
    """Формирует унифицированный словарь метаданных видео."""
    return {
        "id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "duration": parse_duration(details.get("duration", "")),
        "view_count": int(stats.get("viewCount", 0)),
        "published_at": snippet.get("publishedAt", ""),
        "channel": snippet.get("channelTitle", ""),
    }


# --- Tools ---


@mcp.tool
def youtube_search(query: str, max_results: int = 10) -> list[dict] | str:
    """Поиск видео на YouTube по запросу.

    Возвращает список видео с метаданными: id, title, description,
    duration, view_count, published_at, channel.
    """
    try:
        yt = get_youtube_client()

        search_resp = (
            yt.search()
            .list(part="snippet", type="video", q=query, maxResults=max_results, order="relevance")
            .execute()
        )

        ids = [item["id"]["videoId"] for item in search_resp.get("items", [])]
        if not ids:
            return []

        videos_resp = (
            yt.videos()
            .list(part="snippet,contentDetails,statistics", id=",".join(ids))
            .execute()
        )

        results = []
        for item in videos_resp.get("items", []):
            results.append(
                _format_video(
                    item["snippet"],
                    item["contentDetails"],
                    item.get("statistics", {}),
                    item["id"],
                )
            )
        return results

    except HttpError as e:
        if e.resp.status == 403:
            return f"Ошибка квоты YouTube API: {e}"
        return f"Ошибка YouTube API: {e}"
    except RuntimeError as e:
        return str(e)


@mcp.tool
def youtube_video_info(video_url_or_id: str) -> dict | str:
    """Получить метаданные видео по ссылке или ID.

    Возвращает: id, title, description, duration, view_count, published_at, channel.
    Не требует поиска — прямой запрос по ID видео.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
        yt = get_youtube_client()

        resp = (
            yt.videos()
            .list(part="snippet,contentDetails,statistics", id=video_id)
            .execute()
        )

        items = resp.get("items", [])
        if not items:
            return f"Видео не найдено: {video_id}"

        item = items[0]
        return _format_video(
            item["snippet"],
            item["contentDetails"],
            item.get("statistics", {}),
            item["id"],
        )

    except ValueError as e:
        return str(e)
    except HttpError as e:
        return f"Ошибка YouTube API: {e}"
    except RuntimeError as e:
        return str(e)


@mcp.tool
def youtube_transcript(video_url_or_id: str, lang: list[str] = ["ru", "en"]) -> str:
    """Получить субтитры/транскрипт видео YouTube.

    Принимает ссылку на видео или ID. Возвращает текст с таймкодами.
    По умолчанию ищет русские, затем английские субтитры.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return str(e)

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=lang)

        # Заголовок с метаданными
        header = (
            f"Video ID: {transcript.video_id}\n"
            f"Язык: {transcript.language} ({transcript.language_code})\n"
            f"Автогенерация: {'да' if transcript.is_generated else 'нет'}\n"
            f"---\n"
        )

        # Форматирование таймкодов
        lines = []
        for snippet in transcript:
            total_sec = int(snippet.start)
            minutes, seconds = divmod(total_sec, 60)
            hours, minutes = divmod(minutes, 60)
            if hours:
                ts = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                ts = f"{minutes}:{seconds:02d}"
            lines.append(f"[{ts}] {snippet.text}")

        return header + "\n".join(lines)

    except TranscriptsDisabled:
        return f"Субтитры отключены для этого видео ({video_id})."
    except NoTranscriptFound:
        return (
            f"Субтитры не найдены для языков {lang} (видео: {video_id}). "
            f"Попробуйте другой язык."
        )
    except VideoUnavailable:
        return f"Видео недоступно: {video_id}"
    except InvalidVideoId:
        return f"Некорректный ID видео: {video_url_or_id}"
    except CouldNotRetrieveTranscript as e:
        return f"Не удалось получить субтитры: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
