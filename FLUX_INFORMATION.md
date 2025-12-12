# 📰 Safari Newsletter - Flux d'Information Complet (A à Z)

## Vue d'ensemble globale

```
USER INTERFACE (Next.js)
         ↓
   API Backend (FastAPI)
         ↓
   LangGraph Pipeline
    (8 étapes séquentielles)
         ↓
   Bases de données
   (MongoDB + Chroma)
         ↓
   Ollama LLM (IA)
         ↓
   HTML Newsletter
         ↓
   Affichage utilisateur
```

---

## 🎯 Étape 1: L'utilisateur clique sur "Générer la newsletter"

**Où:** `src/interface/frontend/app/page.tsx` (Next.js Frontend)

### Action utilisateur:
```typescript
const generateNewsletter = async () => {
  const response = await axios.post('http://localhost:8000/run-daily-newsletter');
  setNewsletter(response.data); // Affiche la réponse
};
```

**Résultat:** Une requête POST est envoyée au serveur backend sur le port 8000.

---

## 🔌 Étape 2: API Backend reçoit la requête

**Où:** `src/interface/backend/api.py` (FastAPI)

### Code:
```python
@app.post("/run-daily-newsletter")
def run_daily_newsletter():
    state = pipeline_app.invoke({"question": DAILY_QUESTION})
    rag_answer = state.get("rag_answer", "")
    newsletter_html = state.get("newsletter_html", "")
    return {"content": rag_answer, "html": newsletter_html}
```

**Ce qui se passe:**
1. Reçoit la requête POST
2. Démarre le pipeline LangGraph avec une question
3. Attend que le pipeline complet se termine
4. Retourne le contenu texte + HTML au frontend

---

## 🔄 Étape 3: Pipeline LangGraph (Le cœur du système)

**Où:** `src/pipeline/workflow.py`

Le pipeline est composé de **8 nœuds connectés** qui s'exécutent **séquentiellement**:

### 3.1️⃣ NŒUD 1: SCRAPING (Collecte des articles)

**Fichier:** `src/tools/scraper.py`

```
scrape_node()
    ↓
scrape_sources()
    ↓
    • Récupère 3 flux RSS:
      - Krebs on Security
      - The Hacker News
      - ThreatPost
    ↓
    • Extrait: titre, URL, date, résumé HTML
    ↓
    État: raw_articles = [30-50 articles bruts]
```

**Données extraites:**
- `title`: Titre de l'article
- `url`: Lien vers l'article
- `published`: Date de publication
- `summary_html`: Résumé en HTML
- `html`: Contenu HTML complet

---

### 3.2️⃣ NŒUD 2: FILTRAGE (Sélection intelligente)

**Fichier:** `src/tools/filtering.py`

```
filter_node()
    ↓
filter_articles(raw_articles)
    ↓
    • Analyse les articles avec:
      1. CATÉGORISATION: Score par keywords
         (malware, vulnerability, breach, etc.)
      
      2. DÉDUPLICATION: Supprime les doublons
         (> 80% de similitude)
      
      3. SÉLECTION TOP-10:
         - Max 2 articles par source
         - Max 3 articles par catégorie
         - Max 10 articles total
    ↓
    État: filtered_articles = [~10 articles de qualité]
```

**Exemple de scoring:**
```
Article: "New Zero-Day Vulnerability Found in Apache"
- Keywords: vulnerability (10 pts) + apache (5 pts) = Score 15
- Source: KrebsOnSecurity (priorité haute)
- Résultat: ✅ Sélectionné
```

---

### 3.3️⃣ NŒUD 3: PRÉTRAITEMENT (Nettoyage du contenu)

**Fichier:** `src/tools/preprocess.py`

```
preprocess_node()
    ↓
preprocess_articles(filtered_articles)
    ↓
    Pour chaque article:
      1. Extraire le texte brut du HTML
      2. Supprimer les balises HTML inutiles
      3. Nettoyer les espaces blancs
      4. Normaliser le texte
    ↓
    État: clean_articles = [articles avec contenu texte pur]
```

**Exemple de transformation:**
```
Avant:
<p>CRITICAL: <strong>Security</strong> threat detected...</p>

Après:
"CRITICAL: Security threat detected..."
```

---

### 3.4️⃣ NŒUD 4: RÉSUMÉ (Synthèse par IA)

**Fichier:** `src/tools/summarizer.py`

```
summarize_node()
    ↓
summarize_articles(clean_articles)
    ↓
    Pour chaque article:
      1. Envoyer le texte à Ollama (phi3:mini)
      2. IA génère un résumé court
      3. Parser la réponse JSON streamée
      4. Cacher le résumé
    ↓
    État: summaries = [articles avec résumés générés par IA]
```

**Interaction avec Ollama:**
```
REQUEST to http://localhost:11434/api/chat
{
  "model": "phi3:mini",
  "messages": [{
    "role": "user",
    "content": "Résume cet article en 3 phrases: ..."
  }],
  "stream": false
}

RESPONSE (streamed newline-delimited JSON):
{"message":{"content":"Voici le résumé: ..."}}
```

**Parsing robuste:**
- ✅ Tentative 1: Parse JSON complet
- ✅ Tentative 2: Parse JSON newline-delimited
- ✅ Tentative 3: Extraction de substring JSON
- ✅ Tentative 4: Texte brut fallback

---

### 3.5️⃣ NŒUD 5: EMBEDDING (Vectorisation)

**Fichier:** `src/tools/embedding.py`

```
embed_node()
    ↓
upsert_embeddings(summaries)
    ↓
    1. PURGER MongoDB:
       - DROP collection "articles"
    
    2. INSÉRER dans MongoDB:
       - Stocke les articles résumés
    
    3. NETTOYER Chroma:
       - DELETE data/chroma_store
       - (Évite les corruptions)
    
    4. CRÉER Vector Store:
       - Pour chaque article, générer embedding
       - Modèle: all-MiniLM-L6-v2 (HuggingFace)
       - Stocker dans Chroma (SQLite)
    ↓
    Données persistées:
    - MongoDB: Articles complets
    - Chroma: Embeddings vectoriels
```

**Structure MongoDB:**
```json
{
  "_id": ObjectId(...),
  "title": "Security Breach at XYZ Corp",
  "url": "https://...",
  "published": "2025-12-11T10:30:00",
  "content": "This week a major breach...",
  "embedding_id": "abc123"
}
```

**Structure Chroma:**
```
Collection: "articles"
├── Document 1
│   ├── content: "This week a major breach..."
│   ├── embedding: [0.12, -0.45, 0.67, ...] (384 dimensions)
│   └── metadata: {title, url, published}
├── Document 2
│   └── ...
└── ...
```

---

### 3.6️⃣ NŒUD 6: RAG (Génération de newsletter)

**Fichier:** `src/tools/rag.py`

```
rag_node()
    ↓
answer_with_rag(question)
    ↓
    1. RÉCUPÉRATION:
       - Rechercher les 5 documents les plus proches
       - Utilisé Chroma pour similarité cosinus
       - Question: "Génère une newsletter..."
    
    2. SYNTHÈSE:
       - Envoyer les 5 résumés + question à Ollama
       - IA crée une newsletter formatée
    
    3. PARSING:
       - Parser la réponse streamée (même robustesse)
    
    ↓
    État: rag_answer = [Newsletter texte brut]
```

**Processus RAG détaillé:**

```
Question utilisateur:
"Génère une newsletter quotidienne qui résume les incidents, 
vulnérabilités, campagnes et tendances en cybersécurité..."

RETRIEVE (Récupérer):
├─ Embedding de la question → vecteur
├─ Recherche Chroma (similarité cosinus)
└─ Retour: 5 articles les plus pertinents

AUGMENT (Augmenter):
├─ Contexte = 5 résumés d'articles
├─ Prompt = Question + Contexte
└─ Combine question + articles pertinents

GENERATE (Générer):
├─ Envoyer à Ollama phi3:mini
├─ IA réfléchit et rédige la newsletter
└─ Parser la réponse streamed
```

**Exemple de prompt envoyé à Ollama:**
```
Contexte (5 articles pertinents):
1. "XYZ Corp hit by ransomware attack affecting 2M users..."
2. "Critical Apache vulnerability discovered with CVSS 9.8..."
3. "New APT group targets financial institutions..."
4. "Phishing campaign impersonates Microsoft..."
5. "Zero-day in Chrome allows privilege escalation..."

Question utilisateur:
"Génère une newsletter quotidienne qui résume les incidents..."

→ Ollama génère une newsletter structurée
```

---

### 3.7️⃣ NŒUD 7: GÉNÉRATION HTML (Formatage professionnel)

**Fichier:** `src/tools/html_generator.py`

```
html_node()
    ↓
generate_newsletter_html(rag_answer)
    ↓
    1. VÉRIFIER LE CACHE:
       - Hash SHA256 du texte de newsletter
       - Si trouvé → retourner HTML cached
    
    2. GÉNÉRER HTML:
       - Envoyer la newsletter texte à Ollama
       - Prompt: "Crée un beau HTML pour cette newsletter"
       - Ollama retourne du code HTML complet
    
    3. PARSER:
       - Extraire le HTML de la réponse streamée
    
    4. CACHER:
       - Stocker HTML dans _html_cache[hash] = html
       - Prochaine fois: pas d'appel Ollama
    ↓
    État: newsletter_html = [HTML formaté]
```

**Exemple de cache:**
```python
_html_cache = {
    'a7b4c3d2...': '<html><head>...',  # Hash → HTML
    'e8f1g2h3...': '<html><head>...',
}
```

**Performance:** 
- 1ère génération: ~10 secondes (appel Ollama)
- Prochaine fois (même contenu): <100ms (cache hit)

---

### 3.8️⃣ NŒUD 8: FIN DU PIPELINE

```
html_node() → État final
    ↓
    État complète contient:
    {
      "question": "...",
      "raw_articles": [...],
      "filtered_articles": [...],
      "clean_articles": [...],
      "summaries": [...],
      "rag_answer": "Newsletter texte",
      "newsletter_html": "<html>...</html>"
    }
    ↓
Pipeline terminé → Retour à l'API
```

---

## 📤 Étape 4: Retour de la réponse au frontend

**Où:** `src/interface/backend/api.py`

```python
return {
    "content": state.get("rag_answer", ""),      # Texte brut
    "html": state.get("newsletter_html", "")     # HTML formaté
}
```

**Réponse HTTP:**
```json
{
  "content": "Newsletter du 11 décembre 2025...",
  "html": "<html><head>...</head><body>...</body></html>"
}
```

---

## 🎨 Étape 5: Affichage dans le frontend Next.js

**Où:** `src/interface/frontend/app/page.tsx`

```typescript
// Réception et stockage
const response = await axios.post(`${apiUrl}/run-daily-newsletter`);
setNewsletter(response.data);

// Affichage
<div dangerouslySetInnerHTML={{ __html: newsletter.html }} />
```

**Résultat:** 
- 📱 Interface moderne (dark mode)
- 📄 Newsletter formatée en HTML
- ⬇️ Boutons de téléchargement (TXT, Markdown, HTML)

---

## 🗄️ Bases de données utilisées

### MongoDB
```
Database: safari_newsletter
Collections:
├── articles
│   ├── title: string
│   ├── url: string
│   ├── published: datetime
│   ├── content: string (texte nettoyé)
│   └── metadata: object
└── (optionnel) summaries, embeddings...
```

### Chroma (Vector Store)
```
Location: data/chroma_store/
├── chroma.sqlite3 (base de données)
├── <collection_id>/
│   ├── data.parquet (embeddings)
│   └── metadata.parquet
```

---

## 🤖 Services externes

### Ollama (IA locale)
```
Port: 11434
Model: phi3:mini
Endpoints utilisées:
- POST /api/chat → Résumé + Newsletter + HTML
```

### RSS Feeds (Sources de données)
```
1. https://krebsonsecurity.com/feed/
2. https://feeds.thehackernews.com/feed
3. https://threatpost.com/feed/
```

---

## 📊 Volume de données à chaque étape

```
1. SCRAPING: 30-50 articles bruts
        ↓
2. FILTRAGE: ~10 articles sélectionnés
        ↓
3. PRÉTRAITEMENT: 10 articles nettoyés
        ↓
4. RÉSUMÉ: 10 résumés générés par IA
        ↓
5. EMBEDDING: 10 vecteurs (384-dim) + MongoDB
        ↓
6. RAG: 5 documents récupérés
        ↓
7. HTML: 1 newsletter formatée
        ↓
8. RÉPONSE: 1 réponse HTTP JSON
```

---

## ⏱️ Temps d'exécution par étape

```
1. Scraping:     ~2-3 secondes
2. Filtrage:     ~0.5 secondes
3. Prétraitement: ~0.5 secondes
4. Résumé (10×): ~30-40 secondes (Ollama)
5. Embedding:    ~2-3 secondes
6. RAG:          ~10-15 secondes (Ollama)
7. HTML:         ~10-15 secondes (Ollama) ou <100ms (cache)
─────────────────────────────────
TOTAL:           ~60-80 secondes (sans cache)
                 ~50-60 secondes (avec cache HTML)
```

---

## 🔒 Gestion des erreurs

### Chroma (Vector Store)
- **Problème:** Corruption de la BD SQLite
- **Solution:** Auto-cleanup + retry x3
- **Délai:** 1 seconde entre tentatives

### Ollama (Streaming)
- **Problème:** JSON newline-delimited
- **Solution:** Multi-pass parsing (4 fallbacks)
- **Délai:** Aucun timeout

### Caching
- **HTML:** Cache SHA256 en-mémoire
- **Résumés:** Pas de cache (chaque appel)

---

## 🎯 Résumé du flux complet

```
USER CLICKS "Générer"
         ↓
Next.js → FastAPI POST /run-daily-newsletter
         ↓
Pipeline LangGraph démarre
    ├── Scrape: Collecte RSS
    ├── Filter: Sélectionne top-10
    ├── Preprocess: Nettoie HTML
    ├── Summarize: IA résume (Ollama)
    ├── Embed: Vectorise (HuggingFace)
    ├── RAG: Génère newsletter (Ollama + Chroma)
    ├── HTML: Formate en HTML (Ollama + cache)
    └── Return: État complet
         ↓
FastAPI retourne JSON {content, html}
         ↓
Next.js affiche newsletter formatée
         ↓
USER VOIT NEWSLETTER COMPLÈTE ✅
```

---

**Fin de la documentation du flux!** 🎉
