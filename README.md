# YouTube Research MCP Server

An MCP server for YouTube integration with Claude Code — search videos, get metadata, and fetch transcripts.

## Tools

| Tool | Description |
|---|---|
| `youtube_search(query, max_results)` | Search videos by query |
| `youtube_video_info(video_url_or_id)` | Get video metadata by URL or ID |
| `youtube_transcript(video_url_or_id, lang)` | Fetch video subtitles with timestamps |

## Setup

### 1. Get a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Navigate to **APIs & Services → Library**
4. Find and enable **YouTube Data API v3**
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → API Key**
7. Copy the key

### 2. Install Dependencies

```bash
cd /path/to/youtube_research
uv sync
```

### 3. Configure Claude Code

Create `~/.claude/.mcp.json` (global — available in all projects):

```json
{
  "mcpServers": {
    "youtube-research": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/youtube_research", "server.py"],
      "env": {
        "YOUTUBE_API_KEY": "your_key"
      }
    }
  }
}
```

Replace `/path/to/youtube_research` with the actual path to the project.

> **Important:** `.mcp.json` contains your API key — do not commit it to git.

Alternatively, place `.mcp.json` in the project root — the server will only be available when working from that directory.

### 4. Restart

Restart Claude Code — `youtube_search`, `youtube_video_info`, and `youtube_transcript` tools will become available.

## Remote Access (SSE)

To use with Claude.ai web chat or other remote MCP clients, run the server in SSE mode on a VPS:

```bash
YOUTUBE_API_KEY=your_key uv run server.py --sse --port 8000
```

Options:
- `--sse` — enable SSE transport (default is stdio)
- `--host` — bind address (default: `0.0.0.0`)
- `--port` — port number (default: `8000`)

The server will be available at `http://your-vps:8000/sse`.

## Usage Examples

In Claude Code:

- "Find videos about Python asyncio" → calls `youtube_search`
- "Show info for https://youtu.be/dQw4w9WgXcQ" → calls `youtube_video_info`
- "Get subtitles for this video: https://youtube.com/watch?v=..." → calls `youtube_transcript`
