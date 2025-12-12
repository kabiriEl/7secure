"""
Filtering tool for SafariNewsletter.

Étape intermédiaire entre :
scraping → filtering → preprocessing.

Objectifs :
- dédupliquer les articles
- détecter la catégorie via mots clés
- scorer les articles
- appliquer les règles de diversité (source, catégorie)
- sélectionner max 10 articles pertinents
"""

import re
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from difflib import SequenceMatcher

# ---------------------------
# Charger les catégories & keywords
# ---------------------------

CATEGORIES = {
    "AI Security & Threats": [
        "AI-attacks", "model-evasion", "adversarial-examples", "AI-malware",
        "data-poisoning", "prompt-injection", "model-inference", "synthetic-media",
        "automation-abuse", "AI-monitoring", "AI Governance", "AI safety", "Shadow AI",
    ],
    "Threat Intelligence": [
        "threat-hunting", "anomaly-detection", "TTP-analysis", "IOC-tracking",
        "campaign-mapping", "threat-feeds", "actor-profiling", "behavioral-signals",
    ],
    "Malware & Ransomware": [
        "ransomware", "polymorphism", "infostealers", "botnets", "loaders",
        "droppers", "payloads", "encryption-attacks", "obfuscation", "persistence",
    ],
    "Vulnerabilities & Exploits": [
        "zero-day", "CVE", "exploit-chain", "RCE", "privilege-escalation",
        "buffer-overflow", "injection-flaw", "sandbox-escape", "code-execution",
        "patching",
    ],
    "Cloud & SaaS Security": [
        "cloud-misconfig", "workload-security", "secret-management", "token-abuse",
        "storage-leak", "serverless", "multi-tenant", "network-segmentation",
        "posture-management", "container-threats", "OAuth-abuse", "app-permissions",
        "SaaS-drift", "shadow-SaaS", "tenant-isolation",
    ],
    "IAM": [
        "MFA", "passkeys", "SSO", "provisioning", "deprovisioning", "identity-fabric",
        "entitlement-management", "account-takeover", "credential-stuffing",
        "zero-trust",
    ],
    "SOC & Automation": [
        "SIEM", "SOAR", "telemetry", "alert-ranking", "playbooks", "enrichment",
        "correlation-rules", "forensic-automation", "triage-automation",
        "event-normalization",
    ],
    "Data Protection & Privacy": [
        "encryption", "DLP", "anonymization", "pseudonymization", "data-minimization",
        "retention-policy", "privacy-controls", "breach-notification", "access-logging",
        "secure-storage",
    ],
    "Human Factors": [
        "phishing", "vishing", "social-engineering", "insider-risk", "awareness",
        "training", "password-hygiene", "misclicks", "shadow-IT", "human-error",
    ],
    "Compliance & Regulation": [
        "audit-controls", "SOC2", "ISO27001", "PCI-DSS", "NIS2", "governance-risk",
        "regulatory-mapping", "data-sovereignty", "reporting-requirements",
        "certification", "NIST",
    ],
    "Data Breaches": [
        "credential-leak", "unauthorized-access", "token-theft", "data-exposure",
        "breach-timeline", "impact-assessment", "containment", "incident-response",
        "compromise-indicators", "data breach",
    ],
}

TOP_PRIORITY = {"zero-day", "data breach", "ransomware", "AI-attacks"}


# ---------------------------
# Matching catégorie + score
# ---------------------------

def analyze_article(article: Dict[str, Any]) -> Tuple[str, int, int]:
    text = (article.get("title", "") + " " + article.get("html", "")).lower()

    best_category = None
    best_score = 0
    priority = 0

    for cat, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_category = cat

        # Top priority
        if any(tp in text for tp in TOP_PRIORITY):
            priority = 1

    return best_category, best_score, priority


# ---------------------------
# Déduplication
# ---------------------------

def is_similar(a: str, b: str, threshold: float = 0.80) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def deduplicate(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique = []
    for art in articles:
        if not any(is_similar(art["title"], u["title"]) for u in unique):
            unique.append(art)
    return unique


# ---------------------------
# Sélection finale (max 10)
# ---------------------------

def select_top_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Regrouper par source
    by_source = defaultdict(list)
    for art in articles:
        domain = re.sub(r"^www\.", "", art["url"].split('/')[2])
        by_source[domain].append(art)

    # Règles :
    # - score élevé
    # - priorité
    # - diversité source (max 2)
    # - diversité catégorie (max 3)

    final = []
    source_count = defaultdict(int)
    category_count = defaultdict(int)

    # Trier par priorité → score → trending (répétition)
    articles_sorted = sorted(
        articles,
        key=lambda x: (x["priority"], x["score"], x["trending"]),
        reverse=True,
    )

    for art in articles_sorted:
        domain = re.sub(r"^www\.", "", art["url"].split('/')[2])
        cat = art["category"]

        if source_count[domain] >= 2:
            continue
        if category_count[cat] >= 3:
            continue
        if len(final) >= 10:
            break

        final.append(art)
        source_count[domain] += 1
        category_count[cat] += 1

    return final


# ---------------------------
# MAIN INTERFACE
# ---------------------------

def filter_articles(raw_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtre complet avant preprocessing."""

    # 1) Déduplication
    raw_articles = deduplicate(raw_articles)

    # 2) Analyse catégorie + scoring
    enriched = []
    title_count = defaultdict(int)
    for art in raw_articles:
        cat, score, priority = analyze_article(art)
        title_count[art["title"]] += 1

        art["category"] = cat
        art["score"] = score
        art["priority"] = priority
        art["trending"] = title_count[art["title"]]  # trending score
        enriched.append(art)

    # 3) Sélection finale
    final = select_top_articles(enriched)

    print(f"[FILTER] Articles filtrés : {len(final)}")
    return final
