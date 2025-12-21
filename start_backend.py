#!/usr/bin/env python3
"""
Script pour démarrer le serveur FastAPI backend.
Usage: python start_backend.py
"""

import uvicorn
import sys
import os

# Ajouter le répertoire racine au path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Démarrage du serveur FastAPI backend...")
    print("📍 URL: http://localhost:8000")
    print("📚 Documentation API: http://localhost:8000/docs")
    print("\nAppuyez sur Ctrl+C pour arrêter le serveur\n")
    
    uvicorn.run(
        "src.interface.backend.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Rechargement automatique en développement
        log_level="info"
    )
