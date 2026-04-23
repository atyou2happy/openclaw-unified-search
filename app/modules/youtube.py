"""YouTube video search module — extract structured data from ytInitialData."""

import logging
import re
import json
import httpx
from app.config import Config
from app.models import SearchRequest, SearchResult
from app.modules.base import BaseSearchModule

logger = logging.getLogger(__name__)

YT_INITIAL = re.compile(r'var ytInitialData\s*=\s*(\{.*?\});', re.DOTALL)


class YouTubeModule(BaseSearchModule):
    name = "youtube"
    description = "YouTube 视频搜索（免费）"

    async def health_check(self) -> bool:
        return True

    async def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.query.strip()
        max_results = request.max_results
        proxy = Config.get_proxy()
        results = []

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(timeout=20, proxy=proxy, follow_redirects=True) as client:
                r = await client.get(
                    "https://www.youtube.com/results",
                    params={"search_query": query},
                    headers=headers,
                )
                if r.status_code != 200:
                    return results

                match = YT_INITIAL.search(r.text)
                if not match:
                    return results

                data = json.loads(match.group(1))
                contents = (
                    data.get("contents", {})
                    .get("twoColumnSearchResultsRenderer", {})
                    .get("primaryContents", {})
                    .get("sectionListRenderer", {})
                    .get("contents", [])
                )

                seen = set()
                for section in contents:
                    for item in section.get("itemSectionRenderer", {}).get("contents", []):
                        vr = item.get("videoRenderer", {})
                        vid = vr.get("videoId", "")
                        if not vid or vid in seen:
                            continue
                        seen.add(vid)

                        title_runs = vr.get("title", {}).get("runs", [{}])
                        title = title_runs[0].get("text", "") if title_runs else ""
                        channel = ""
                        owner = vr.get("ownerText", {}).get("runs", [{}])
                        if owner:
                            channel = owner[0].get("text", "")
                        views = vr.get("viewCountText", {}).get("simpleText", "")
                        length = vr.get("lengthText", {}).get("simpleText", "")

                        results.append(SearchResult(
                            title=f"[YouTube] {title}",
                            url=f"https://www.youtube.com/watch?v={vid}",
                            snippet=f"{channel} · {views}" + (f" · {length}" if length else ""),
                            source=self.name,
                            relevance=0.5,
                            metadata={
                                "video_id": vid,
                                "channel": channel,
                                "views": views,
                                "length": length,
                            },
                        ))
                        if len(results) >= max_results:
                            break
                    if len(results) >= max_results:
                        break

        except Exception as e:
            logger.error(f"YouTube search error: {e}")

        return results[:max_results]
