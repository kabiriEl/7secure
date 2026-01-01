import os
import time
import hashlib
from typing import List, Optional, Dict, Any

import jwt
import requests


class GhostPublisher:
    """
    Publish posts to Ghost Admin API (draft by default).
    Works with Ghost(Pro) and self-hosted Ghost.

    Env vars:
      - GHOST_URL (e.g., https://jamalia.ghost.io)
      - GHOST_ADMIN_API_KEY (format: id:secret)
    """

    def __init__(self, ghost_url: Optional[str] = None, admin_api_key: Optional[str] = None) -> None:
        self.ghost_url = (ghost_url or os.getenv("GHOST_URL", "")).rstrip("/")
        self.admin_api_key = admin_api_key or os.getenv("GHOST_ADMIN_API_KEY", "")

        if not self.ghost_url:
            raise ValueError("Missing GHOST_URL")
        if not self.admin_api_key or ":" not in self.admin_api_key:
            raise ValueError("Missing or invalid GHOST_ADMIN_API_KEY (expected 'id:secret')")

        self.key_id, self.key_secret = self.admin_api_key.split(":", 1)
        self.api_base = f"{self.ghost_url}/ghost/api/admin"

    def _make_jwt(self) -> str:
        """
        Ghost Admin API uses a JWT signed with the 'secret' part of the Admin API key.
        """
        # Ghost expects the secret decoded from hex
        secret = bytes.fromhex(self.key_secret)

        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 5 * 60,  # 5 minutes
            "aud": "/admin/",
        }
        token = jwt.encode(payload, secret, algorithm="HS256", headers={"kid": self.key_id})
        # pyjwt may return bytes in older versions
        return token.decode("utf-8") if isinstance(token, bytes) else token

    @staticmethod
    def _stable_slug(title: str, suffix: str = "") -> str:
        base = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
        while "--" in base:
            base = base.replace("--", "-")
        if suffix:
            base = f"{base}-{suffix}"
        return base[:180]

    @staticmethod
    def _content_hash(html: str) -> str:
        return hashlib.sha256(html.encode("utf-8")).hexdigest()[:10]

    def create_post_from_html(
        self,
        title: str,
        html: str,
        tags: Optional[List[str]] = None,
        status: str = "published",
        excerpt: Optional[str] = None,
        feature_image: Optional[str] = None,
        canonical_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a post using ?source=html so Ghost converts HTML into editor format.
        """
        token = self._make_jwt()
        headers = {
            "Authorization": f"Ghost {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        tag_objects = []
        if tags:
            tag_objects = [{"name": t} for t in tags if t and t.strip()]

        # Add a deterministic suffix to avoid slug collisions
        slug_suffix = self._content_hash(html)
        slug = self._stable_slug(title, suffix=slug_suffix)

        post: Dict[str, Any] = {
            "title": title,
            "slug": slug,
            "html": html,
            "status": status,  # "draft" or "published"
        }
        if tag_objects:
            post["tags"] = tag_objects
        if excerpt:
            post["custom_excerpt"] = excerpt
        if feature_image:
            post["feature_image"] = feature_image
        if canonical_url:
            post["canonical_url"] = canonical_url

        url = f"{self.api_base}/posts/?source=html"
        resp = requests.post(url, headers=headers, json={"posts": [post]}, timeout=30)

        if resp.status_code >= 300:
            raise RuntimeError(
                f"Ghost create_post failed: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        return data["posts"][0]
