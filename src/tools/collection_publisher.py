"""
Collection Publisher - Publie les stories de la newsletter comme posts Ghost.

Objectif: Transformer les stories de la newsletter en posts individuels prêts à lire.
"""

import json
import os
import time
from typing import Any, Dict, Optional

import jwt
import requests
from ollama import Client as OllamaClient
from src.tools.category_classifier import classify_top_categories


ALLOWED_TAGS = [
    "AI Security & Threats",
    "Threat Intelligence",
    "Malware & Ransomware",
    "Vulnerabilities & Exploits",
    "Cloud & SaaS Security",
    "IAM",
    "SOC & Automation",
    "Data Protection & Privacy",
    "Compliance & Regulation",
    "Data Breaches",
]


def _reformulate_with_llm(title: str, description: str, category: str) -> tuple[str, str]:
    """Reformule une story via LLM pour un meilleur contenu.
    
    Returns:
        (new_title, content) - Le nouveau titre (2 phrases) et le contenu reformulé
    """
    try:
        # Configuration (même méthode que html_generator.py)
        api_key = os.getenv("OLLAMA_API_KEY", "").strip()
        model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")
        
        if not api_key:
            print("[COLLECTION] ⚠️  OLLAMA_API_KEY missing, using original")
            return (title, description)
        
        # Client Ollama (même config que newsletter)
        client = OllamaClient(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        
        prompt = f"""You are a cybersecurity analyst. Rewrite this story for defenders.

Original Title: {title}
Details: {description}

Generate:
1. TITLE: A SHORT catchy headline (max 15 words). Just the headline, nothing else.
2. CONTENT: 2-3 clear paragraphs explaining what happened, the impact, and why defenders should care.

Format EXACTLY like this:
TITLE: [short headline here]

CONTENT:
[paragraph 1]

[paragraph 2]

No markdown, no asterisks, no formatting."""

        response = client.generate(
            model=model,
            prompt=prompt,
            stream=False,
            options={"temperature": 0.7}
        )
        
        reformulated = response.get("response", "").strip()
        
        # Parser le titre et le contenu
        new_title = title
        content = description
        
        if "TITLE:" in reformulated and "CONTENT:" in reformulated:
            parts = reformulated.split("CONTENT:", 1)
            title_part = parts[0].replace("TITLE:", "").strip()
            content_part = parts[1].strip()
            
            # Nettoie le markdown
            title_part = title_part.replace("**", "").replace("##", "").replace("*", "").strip()
            content_part = content_part.replace("**", "").replace("##", "").replace("*", "").strip()
            
            # Limite le titre à 200 chars max (évite les titres trop longs)
            if len(title_part) > 200:
                # Coupe au dernier point ou espace avant 200 chars
                cut_point = title_part[:200].rfind(".")
                if cut_point == -1:
                    cut_point = title_part[:200].rfind(" ")
                if cut_point > 50:
                    title_part = title_part[:cut_point + 1].strip()
                else:
                    title_part = title_part[:200].strip() + "..."
            
            if len(title_part) > 10 and len(content_part) > 50:
                new_title = title_part
                content = content_part
                print(f"[COLLECTION] ✓ LLM: title={len(new_title)} chars, content={len(content)} chars")
                return (new_title, content)
        
        print("[COLLECTION] ⚠️  LLM parsing failed, using original")
        return (title, description)
            
    except Exception as e:
        print(f"[COLLECTION] ⚠️  LLM failed: {e}, using original")
        return description


def _build_ghost_jwt(admin_key: str) -> str:
    """Génère un JWT pour Ghost Admin API."""
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
        headers={"alg": "HS256", "kid": api_id, "typ": "JWT"}
    )


def publish_stories_as_collection_posts(
    rag_answer: str, 
    images_index: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Publie chaque story comme un post Ghost.
    
    Args:
        rag_answer: JSON contenant les stories
        images_index: Mapping URL story → URL image Ghost
        
    Returns:
        {"collection_posts_count": int, "collection_posts_failed": int}
    """
    # Configuration
    ghost_url = os.getenv("GHOST_ADMIN_API_URL", "").rstrip("/")
    admin_key = os.getenv("GHOST_ADMIN_API_KEY", "")
    
    if not ghost_url or not admin_key:
        print("[COLLECTION] ❌ Missing Ghost configuration")
        return {"collection_posts_count": 0, "collection_posts_failed": 0}
    
    images_index = images_index or {}
    
    # Extraire stories
    try:
        data = json.loads(rag_answer)
        stories = data.get("stories", [])
        print(f"[COLLECTION] 📥 Extracted {len(stories)} stories")
    except Exception as e:
        print(f"[COLLECTION] ❌ Failed to parse JSON: {e}")
        return {"collection_posts_count": 0, "collection_posts_failed": 0}
    
    if not stories:
        return {"collection_posts_count": 0, "collection_posts_failed": 0}
    
    # Générer JWT
    token = _build_ghost_jwt(admin_key)
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
    }
    
    published = 0
    failed = 0
    
    # Publier chaque story
    for idx, story in enumerate(stories, 1):
        try:
            title = story.get("title", "").strip()
            description = story.get("description", "").strip()
            category = story.get("category", "Threat Intelligence")
            url = story.get("url", "").strip()
            
            if not title or not description:
                print(f"[COLLECTION] ⚠️  Story {idx}: Missing title or description")
                failed += 1
                continue
            
            # Reformuler avec LLM (même méthode que newsletter)
            print(f"[COLLECTION] 🔄 Story {idx}: Reformulating...")
            new_title, content = _reformulate_with_llm(title, description, category)
            
            # Tag valide
            # Tags (3 catégories) via classification statique
            tag_list = [t for t in classify_top_categories(story, top_k=3) if t in ALLOWED_TAGS]
            if not tag_list:
                tag_list = ["Threat Intelligence"]
            if len(tag_list) < 3:
                for allowed in ALLOWED_TAGS:
                    if allowed not in tag_list:
                        tag_list.append(allowed)
                    if len(tag_list) >= 3:
                        break
            
            # Image si disponible (sera utilisée comme feature_image uniquement)
            image_url = story.get("image_url") or images_index.get(url)
            
            # HTML structure professionnelle (sans image, car déjà en feature_image)
            html = f"""<article class="story-article">
<div class="story-content">
{chr(10).join(f"<p>{p.strip()}</p>" for p in content.split(chr(10)) if p.strip())}
<footer class="story-footer">
<p><strong>Categories:</strong> {', '.join(tag_list)}</p>
<p><strong>Source:</strong> <a href="{url}" target="_blank" rel="noopener">Read original article</a></p>
</footer>
</div>
</article>"""
            
            # Post data avec nouveau titre LLM (pas d'excerpt pour éviter duplication)
            post = {
                "title": new_title,
                "html": html,
                "featured": True,  # Pour filtrer sur page collection
                "tags": [{"name": t} for t in tag_list],
                "status": "published",
            }
            
            if image_url:
                post["feature_image"] = image_url
            
            # Publier
            resp = requests.post(
                f"{ghost_url}/ghost/api/admin/posts/?source=html",
                json={"posts": [post]},
                headers=headers,
                timeout=30
            )
            
            if resp.status_code < 300:
                post_id = resp.json().get("posts", [{}])[0].get("id", "")
                print(f"[COLLECTION] ✅ Story {idx}: Published (id={post_id}, tag={tag})")
                published += 1
            else:
                print(f"[COLLECTION] ❌ Story {idx}: Failed ({resp.status_code})")
                failed += 1
                
        except Exception as e:
            print(f"[COLLECTION] ❌ Story {idx}: Error - {e}")
            failed += 1
    
    print(f"[COLLECTION] 📊 Result: {published} published, {failed} failed")
    
    return {
        "collection_posts_count": published,
        "collection_posts_failed": failed,
    }
