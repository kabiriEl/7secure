"""
Category classifier for newsletters using keyword-based static classification.

This tool analyzes text content and assigns the most relevant category
based on keyword frequency matching.
"""

from typing import Dict, Any, List


# =========================
# Category Keywords (static classification)
# =========================
CATEGORIES_KEYWORDS = {
    "AI Security & Threats": [
        "ai-attacks", "model-evasion", "adversarial-examples", "ai-malware",
        "data-poisoning", "prompt-injection", "model-inference", "synthetic-media",
        "automation-abuse", "ai-monitoring", "ai governance", "ai safety", "shadow ai",
        "artificial intelligence", "machine learning", "deep learning", "llm", "chatgpt",
        "neural network", "ai model", "ai threat", "ai security", "generative ai",
    ],
    "Threat Intelligence": [
        "threat-hunting", "anomaly-detection", "ttp-analysis", "ioc-tracking",
        "campaign-mapping", "threat-feeds", "actor-profiling", "behavioral-signals",
        "threat actor", "apt", "advanced persistent", "threat intelligence", "cyber threat",
        "threat landscape", "threat detection", "indicators of compromise", "ioc",
    ],
    "Malware & Ransomware": [
        "ransomware", "polymorphism", "infostealers", "botnets", "loaders",
        "droppers", "payloads", "encryption-attacks", "obfuscation", "persistence",
        "malware", "trojan", "virus", "worm", "backdoor", "rootkit", "spyware",
        "cryptolocker", "lockbit", "blackcat", "conti", "revil", "malicious software",
    ],
    "Vulnerabilities & Exploits": [
        "zero-day", "cve", "exploit-chain", "rce", "privilege-escalation",
        "buffer-overflow", "injection-flaw", "sandbox-escape", "code-execution",
        "patching", "vulnerability", "exploit", "security flaw", "remote code execution",
        "sql injection", "xss", "cross-site", "security patch", "zero day",
    ],
    "Cloud & SaaS Security": [
        "cloud-misconfig", "workload-security", "secret-management", "token-abuse",
        "storage-leak", "serverless", "multi-tenant", "network-segmentation",
        "posture-management", "container-threats", "oauth-abuse", "app-permissions",
        "saas-drift", "shadow-saas", "tenant-isolation", "cloud security", "aws", "azure",
        "gcp", "s3 bucket", "kubernetes", "docker", "cloud storage", "cloud infrastructure",
    ],
    "IAM": [
        "mfa", "passkeys", "sso", "provisioning", "deprovisioning", "identity-fabric",
        "entitlement-management", "account-takeover", "credential-stuffing",
        "zero-trust", "identity", "access management", "authentication", "authorization",
        "single sign-on", "multi-factor", "identity access", "iam", "privileged access",
    ],
    "SOC & Automation": [
        "siem", "soar", "telemetry", "alert-ranking", "playbooks", "enrichment",
        "correlation-rules", "forensic-automation", "triage-automation",
        "event-normalization", "security operations", "incident response", "soc",
        "security monitoring", "log management", "security automation", "orchestration",
    ],
    "Data Protection & Privacy": [
        "encryption", "dlp", "anonymization", "pseudonymization", "data-minimization",
        "retention-policy", "privacy-controls", "breach-notification", "access-logging",
        "secure-storage", "data protection", "privacy", "gdpr", "data security",
        "personal data", "data loss prevention", "data privacy", "confidentiality",
    ],
    "Compliance & Regulation": [
        "audit-controls", "soc2", "iso27001", "pci-dss", "nis2", "governance-risk",
        "regulatory-mapping", "data-sovereignty", "reporting-requirements",
        "certification", "nist", "compliance", "regulation", "regulatory", "audit",
        "governance", "iso", "pci", "hipaa", "sox", "framework",
    ],
    "Data Breaches": [
        "credential-leak", "unauthorized-access", "token-theft", "data-exposure",
        "breach-timeline", "impact-assessment", "containment", "incident-response",
        "compromise-indicators", "data breach", "breach", "leaked", "exposed data",
        "compromised", "stolen data", "hacked", "cyber attack", "security incident",
    ],
}


def classify_category(text_content: Dict[str, Any]) -> str:
    """Classify content category based on keywords (static method).
    
    Args:
        text_content: Dictionary with text fields (title, description, key_points, etc.)
    
    Returns:
        The best matching category based on keyword frequency
    """
    # Combine all text fields
    text_parts = []
    
    # Add common text fields
    for field in ["title", "description", "why_it_matters", "content", "html", "summary"]:
        if field in text_content and text_content[field]:
            text_parts.append(str(text_content[field]))
    
    # Add key_points if it's a list
    key_points = text_content.get("key_points", [])
    if isinstance(key_points, list):
        text_parts.extend([str(kp) for kp in key_points])
    
    # Create single text for analysis (lowercase for case-insensitive matching)
    text = " ".join(text_parts).lower()
    
    if not text.strip():
        return "Threat Intelligence"  # Default fallback
    
    # Score each category
    best_category = "Threat Intelligence"  # Default fallback
    best_score = 0
    
    for category, keywords in CATEGORIES_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > best_score:
            best_score = score
            best_category = category
    
    return best_category


def classify_top_categories(text_content: Dict[str, Any], top_k: int = 3) -> List[str]:
    """Return top-k categories based on keyword frequency.

    Args:
        text_content: Dictionary with text fields (title, description, key_points, etc.)
        top_k: Number of categories to return

    Returns:
        List of category names ordered by relevance
    """
    # Combine all text fields
    text_parts = []

    for field in ["title", "description", "why_it_matters", "content", "html", "summary"]:
        if field in text_content and text_content[field]:
            text_parts.append(str(text_content[field]))

    key_points = text_content.get("key_points", [])
    if isinstance(key_points, list):
        text_parts.extend([str(kp) for kp in key_points])

    text = " ".join(text_parts).lower()
    if not text.strip():
        return ["Threat Intelligence"]

    scored: List[tuple[str, int]] = []
    for category, keywords in CATEGORIES_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > 0:
            scored.append((category, score))

    if not scored:
        return ["Threat Intelligence"]

    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max(1, top_k)]]


def classify_story(story: Dict[str, Any], verbose: bool = True) -> str:
    """Classify a single story and return its category.
    
    Args:
        story: Story dictionary with text fields
        verbose: Whether to print classification info
    
    Returns:
        Category name
    """
    category = classify_category(story)
    
    if verbose:
        title = story.get("title", "Untitled")[:50]
        print(f"[CLASSIFIER] '{title}...' → '{category}'")
    
    return category


def classify_stories(stories: List[Dict[str, Any]], verbose: bool = True) -> List[Dict[str, Any]]:
    """Classify multiple stories and add category field to each.
    
    Args:
        stories: List of story dictionaries
        verbose: Whether to print classification info
    
    Returns:
        List of stories with 'category' field added/updated
    """
    for idx, story in enumerate(stories):
        if not isinstance(story, dict):
            continue
        
        category = classify_category(story)
        story["category"] = category
        
        if verbose:
            title = story.get("title", "Untitled")[:50]
            print(f"[CLASSIFIER] Story {idx + 1}: '{title}...' → '{category}'")
    
    return stories


def get_all_categories() -> List[str]:
    """Return list of all available category names."""
    return list(CATEGORIES_KEYWORDS.keys())
