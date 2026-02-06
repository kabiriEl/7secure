# Safari Newsletter

Application de génération automatique de newsletters de veille cybersécurité avec images.

## 🚀 Démarrage rapide

### Configuration

1. Copier le fichier `.env.example` vers `.env` et remplir les variables:
```bash
cp .env.example .env
```

2. Configurer Ghost CMS:
   - `GHOST_URL`: L'URL de votre site Ghost
   - `GHOST_ADMIN_API_KEY`: Clé API Admin pour publier les posts (format: `id:secret`)
   - `GHOST_CONTENT_API_KEY`: Clé API Content pour récupérer les posts (obtenue dans Ghost Admin > Integrations)
   - `GHOST_NEWSLETTER_SLUG`: Le slug de votre newsletter

### Backend (FastAPI)

1. Installer les dépendances Python :
```bash
pip install -r requirements.txt
```

2. Démarrer le serveur backend :
```bash
python start_backend.py
```

Le serveur sera accessible sur `http://localhost:8000`
- API Documentation: http://localhost:8000/docs
- Endpoints disponibles:
  - `GET /api/newsletters` - Liste toutes les newsletters depuis Ghost avec leurs images
  - `GET /api/newsletters/{id}` - Récupère une newsletter par ID avec son image
  - `POST /run-daily-newsletter` - Génère une nouvelle newsletter avec images

### Frontend (Next.js)

1. Aller dans le répertoire frontend :
```bash
cd src/interface/frontend
```

2. Installer les dépendances :
```bash
npm install
# ou
pnpm install
```

3. Démarrer le serveur de développement :
```bash
npm run dev
# ou
pnpm dev
```

Le frontend sera accessible sur `http://localhost:3000`

## ⚙️ Configuration

### Variables d'environnement

Créez un fichier `.env` à la racine du projet :

```env
# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=safarinewsletter
ARTICLES_COLLECTION=articles

# Hugging Face
HF_API_TOKEN=your_token_here

# Ollama (optionnel)
OLLAMA_API_KEY=your_key_here
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_MODEL=gpt-oss:20b-cloud

# Frontend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📝 Notes importantes

- **Le backend doit être démarré avant le frontend** pour que les appels API fonctionnent
- Si vous voyez l'erreur "Failed to fetch", vérifiez que le serveur FastAPI est bien démarré sur le port 8000
- MongoDB doit être installé et démarré pour stocker les newsletters 
