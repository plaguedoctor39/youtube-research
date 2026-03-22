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
    """Extract video ID from a YouTube URL or return as-is if already an ID."""
    url_or_id = url_or_id.strip()
    m = _YOUTUBE_URL_RE.search(url_or_id)
    if m:
        return m.group(1)
    if _VIDEO_ID_RE.match(url_or_id):
        return url_or_id
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def parse_duration(iso: str) -> str:
    """Convert ISO 8601 duration (PT1H2M3S) to a human-readable format."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    if h:
        return f"{h}:{mi:02d}:{s:02d}"
    return f"{mi}:{s:02d}"


def get_youtube_client():
    """Lazy singleton for the YouTube API client."""
    global _yt_client
    if _yt_client is None:
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "YOUTUBE_API_KEY environment variable is not set. "
                "Get a key from Google Cloud Console: "
                "APIs & Services -> Credentials -> Create API Key, "
                "then enable YouTube Data API v3."
            )
        _yt_client = build("youtube", "v3", developerKey=api_key)
    return _yt_client


def _format_video(snippet: dict, details: dict, stats: dict, video_id: str) -> dict:
    """Build a unified video metadata dict."""
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
    """Search YouTube videos by query.

    Returns a list of videos with metadata: id, title, description,
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
            return f"YouTube API quota error: {e}"
        return f"YouTube API error: {e}"
    except RuntimeError as e:
        return str(e)


@mcp.tool
def youtube_video_info(video_url_or_id: str) -> dict | str:
    """Get video metadata by URL or ID.

    Returns: id, title, description, duration, view_count, published_at, channel.
    Direct lookup by video ID — no search required.
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
            return f"Video not found: {video_id}"

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
        return f"YouTube API error: {e}"
    except RuntimeError as e:
        return str(e)


@mcp.tool
def youtube_transcript(video_url_or_id: str, lang: list[str] = ["ru", "en"]) -> str:
    """Get subtitles/transcript for a YouTube video.

    Accepts a video URL or ID. Returns timestamped text.
    Looks for Russian subtitles first, then English by default.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
    except ValueError as e:
        return str(e)

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=lang)

        header = (
            f"Video ID: {transcript.video_id}\n"
            f"Language: {transcript.language} ({transcript.language_code})\n"
            f"Auto-generated: {'yes' if transcript.is_generated else 'no'}\n"
            f"---\n"
        )

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
        return f"Subtitles are disabled for this video ({video_id})."
    except NoTranscriptFound:
        return (
            f"No transcript found for languages {lang} (video: {video_id}). "
            f"Try a different language."
        )
    except VideoUnavailable:
        return f"Video unavailable: {video_id}"
    except InvalidVideoId:
        return f"Invalid video ID: {video_url_or_id}"
    except CouldNotRetrieveTranscript as e:
        return f"Could not retrieve transcript: {e}"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Research MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run as SSE server (for remote/web access)")
    parser.add_argument("--host", default="0.0.0.0", help="SSE server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="SSE server port (default: 8000)")
    args = parser.parse_args()

    if args.sse:
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio", show_banner=False)
