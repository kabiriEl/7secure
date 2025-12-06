# Safari Newsletter - Interface Frontend

## Installation et Lancement

### Prérequis
- Python 3.8+
- Environnement virtuel activé (`.venv`)
- Backend FastAPI en cours d'exécution

### Installation des dépendances

```bash
# Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

### Lancement du Backend

Dans un terminal :
```bash
uvicorn src.interface.backend.api:app --reload
```

Le backend s'exécutera sur `http://localhost:8000`

### Lancement du Frontend

Dans un autre terminal :
```bash
# Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# Lancer Streamlit
streamlit run src/interface/frontend/app.py
```

L'interface s'ouvrira automatiquement dans votre navigateur (généralement `http://localhost:8501`)

## Fonctionnalités

### 🚀 Générer la newsletter
Cliquez sur le bouton **"Générer la newsletter"** pour :
1. Scraper les sources RSS de cybersécurité (~100+ sources)
2. Nettoyer et traiter les articles
3. Générer les embeddings vectoriels
4. Utiliser l'IA (DeepSeek) pour créer une newsletter structurée

### 🔄 Rafraîchir
Réinitialise l'interface pour une nouvelle génération

### 💾 Télécharger
Exporte la newsletter en format :
- **TXT** : Texte brut simple
- **Markdown** : Format balisé pour manipulation ultérieure

## Configuration

### Modifier l'URL de l'API
Utilisez le champ dans la barre latérale pour changer l'adresse du serveur backend si nécessaire.

### Timeout et Performance
- Le timeout par défaut est de 300 secondes (5 minutes)
- La première exécution peut être plus longue (modèles à télécharger)
- Les exécutions suivantes sont généralement plus rapides

## Structure du Projet

```
src/interface/
├── backend/
│   ├── api.py              # Endpoint FastAPI
│   └── __init__.py
└── frontend/
    ├── app.py              # Interface Streamlit
    └── __init__.py
```

## Dépannage

### Erreur de connexion
- Vérifiez que le backend est en cours d'exécution
- Vérifiez l'URL de l'API dans les paramètres
- Vérifiez que le port 8000 est disponible

### Génération trop lente
- Patience lors de la première exécution
- Vérifiez les ressources système (RAM, CPU)
- Les modèles AI prennent du temps

### Pas d'articles générés
- Vérifiez que MongoDB est en cours d'exécution
- Vérifiez que les flux RSS sont accessibles
- Vérifiez les logs du backend

## Support

Pour plus d'informations, consultez :
- README.md (configuration générale)
- Logs du terminal backend
- Documentation Streamlit: https://docs.streamlit.io/
