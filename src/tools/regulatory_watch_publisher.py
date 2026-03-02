"""
Regulatory Watch Publisher - Publie les stories 'Compliance & Regulation' comme posts Ghost.

Chaque post reçoit le tag interne #Regulatory-Watch pour n'apparaître
que dans la page dédiée.
"""
import json
import os
import time
from typing import Any, Dict, Optional

import jwt
import requests

from src.tools.collection_publisher import _reformulate_with_llm


INTERNAL_TAG = "#Regulatory-Watch"
TARGET_CATEGORY = "Compliance & Regulation"


def _build_ghost_jwt(admin_key: str) -> str:
    api_id, api_secret = admin_key.split(":")

    iat = int(time.time())
    payload = {
        "iat": iat,
        "exp": iat + 300,
        "aud": "/admin/",
    }

    return jwt.encode(
        payload,
        bytes.fromhex(api_secret),
        algorithm="HS256",
        headers={"alg": "HS256", "kid": api_id, "typ": "JWT"},
    )


def publish_regulatory_watch_posts(
    rag_answer: str,
    images_index: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Publie les stories de catégorie Compliance & Regulation.

    Returns:
        {"regwatch_posts_count": int, "regwatch_posts_failed": int}
    """
    ghost_url = os.getenv("GHOST_ADMIN_API_URL", "").rstrip("/")
    admin_key = os.getenv("GHOST_ADMIN_API_KEY", "")

    if not ghost_url or not admin_key:
        print("[REGWATCH] ❌ Missing Ghost configuration")
        return {"regwatch_posts_count": 0, "regwatch_posts_failed": 0}

    images_index = images_index or {}

    try:
        data = json.loads(rag_answer)
        stories = data.get("stories", [])
        print(f"[REGWATCH] 📥 Extracted {len(stories)} stories")
    except Exception as e:
        print(f"[REGWATCH] ❌ Failed to parse JSON: {e}")
        return {"regwatch_posts_count": 0, "regwatch_posts_failed": 0}

    if not stories:
        return {"regwatch_posts_count": 0, "regwatch_posts_failed": 0}

    token = _build_ghost_jwt(admin_key)
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
    }

    published = 0
    failed = 0

    for idx, story in enumerate(stories, 1):
        try:
            category = story.get("category", "")
            if category != TARGET_CATEGORY:
                continue

            title = story.get("title", "").strip()
            description = story.get("description", "").strip()
            url = story.get("url", "").strip()

            if not title or not description:
                print(f"[REGWATCH] ⚠️  Story {idx}: Missing title or description")
                failed += 1
                continue

            # Reformuler avec LLM (même méthode que collection)
            print(f"[REGWATCH] 🔄 Story {idx}: Reformulating...")
            new_title, content = _reformulate_with_llm(title, description, category)

            image_url = story.get("image_url") or images_index.get(url)

            html = f"""<article class=\"regwatch-article\">
<div class=\"regwatch-content\">
{chr(10).join(f"<p>{p.strip()}</p>" for p in content.split(chr(10)) if p.strip())}
<p><strong>Source:</strong> <a href=\"{url}\" target=\"_blank\" rel=\"noopener\">Read original article</a></p>
</div>
</article>"""

            post: Dict[str, Any] = {
                "title": new_title,
                "html": html,
                "featured": False,
                "tags": [{"name": INTERNAL_TAG}],
                "status": "published",
                "type": "post",
            }

            if image_url:
                post["feature_image"] = image_url

            resp = requests.post(
                f"{ghost_url}/ghost/api/admin/posts/?source=html",
                json={"posts": [post]},
                headers=headers,
                timeout=30,
            )

            if resp.status_code < 300:
                post_id = resp.json().get("posts", [{}])[0].get("id", "")
                print(f"[REGWATCH] ✅ Story {idx}: Published (id={post_id})")
                published += 1
            else:
                print(f"[REGWATCH] ❌ Story {idx}: Failed ({resp.status_code})")
                failed += 1

        except Exception as e:
            print(f"[REGWATCH] ❌ Story {idx}: Error - {e}")
            failed += 1

    print(f"[REGWATCH] 📊 Result: {published} published, {failed} failed")
    return {"regwatch_posts_count": published, "regwatch_posts_failed": failed}
