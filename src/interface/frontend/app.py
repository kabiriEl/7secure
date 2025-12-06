"""Streamlit interface for SafariNewsletter."""

import json
from datetime import datetime

import requests
import streamlit as st

# Configuration de la page
st.set_page_config(
    page_title="Safari Newsletter - Veille Cybersécurité",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personnalisé
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .header-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .newsletter-container {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
    }
    .section-title {
        color: #667eea;
        font-size: 1.5rem;
        font-weight: bold;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .loading-spinner {
        text-align: center;
        padding: 2rem;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #e0e0e0;
        color: #666;
        font-size: 0.9rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header-container">
        <h1>🦁 Safari Newsletter</h1>
        <p style="font-size: 1.1rem; margin: 0;">Veille quotidienne en cybersécurité</p>
        <p style="margin-top: 0.5rem; opacity: 0.9;">Agrégation et analyse intelligente des menaces de sécurité</p>
    </div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ Configuration")
    
    # API URL configuration
    api_url = st.text_input(
        "URL de l'API",
        value="http://localhost:8000",
        help="Adresse de base du serveur backend"
    )
    
    st.markdown("---")
    
    # Information
    st.subheader("ℹ️ À propos")
    st.info("""
    **Safari Newsletter** agrège automatiquement :
    - Articles de cybersécurité
    - Alertes de menaces
    - Vulnérabilités critiques
    - Tendances en sécurité
    
    Mis à jour quotidiennement via IA.
    """)

# Main content
col1, col2 = st.columns([3, 1])

with col1:
    st.title("📰 Newsletter du jour")

with col2:
    st.metric("Date", datetime.now().strftime("%d/%m/%Y"))

# Controls
col1, col2, col3 = st.columns(3)

with col1:
    generate_button = st.button(
        "🚀 Générer la newsletter",
        key="generate_btn",
        use_container_width=True,
        type="primary"
    )

with col2:
    refresh_button = st.button(
        "🔄 Rafraîchir",
        key="refresh_btn",
        use_container_width=True
    )

with col3:
    export_button = st.button(
        "💾 Télécharger",
        key="export_btn",
        use_container_width=True
    )

st.markdown("---")

# State management
if "newsletter_content" not in st.session_state:
    st.session_state.newsletter_content = None
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False
if "error_message" not in st.session_state:
    st.session_state.error_message = None

# Handle button clicks
if generate_button:
    st.session_state.is_loading = True
    st.session_state.error_message = None

if refresh_button:
    st.session_state.newsletter_content = None
    st.session_state.error_message = None
    st.rerun()

# Generate newsletter
if st.session_state.is_loading:
    with st.spinner("⏳ Génération de la newsletter en cours..."):
        try:
            endpoint = f"{api_url}/run-daily-newsletter"
            response = requests.post(endpoint, timeout=300)
            response.raise_for_status()
            
            data = response.json()
            st.session_state.newsletter_content = data.get("content", "")
            st.session_state.error_message = None
            
            st.success("✅ Newsletter générée avec succès!")
            st.session_state.is_loading = False
            
        except requests.exceptions.ConnectionError:  # pylint: disable=broad-except
            st.session_state.error_message = (
                "❌ Impossible de se connecter à l'API. Vérifiez le serveur."
            )
            st.session_state.is_loading = False
        except requests.exceptions.Timeout:  # pylint: disable=broad-except
            st.session_state.error_message = (
                "⏱️ Délai d'attente dépassé. Génération trop longue."
            )
            st.session_state.is_loading = False
        except requests.exceptions.RequestException as e:
            st.session_state.error_message = f"❌ Erreur API: {str(e)}"
            st.session_state.is_loading = False
        except json.JSONDecodeError:
            st.session_state.error_message = "❌ Erreur de format de réponse."
            st.session_state.is_loading = False
        except ValueError as e:
            st.session_state.error_message = f"❌ Erreur: {str(e)}"
            st.session_state.is_loading = False

# Display content
if st.session_state.error_message:
    st.markdown(f"""
        <div class="error-message">
            {st.session_state.error_message}
        </div>
    """, unsafe_allow_html=True)

if st.session_state.newsletter_content:
    st.markdown("""
        <div class="newsletter-container">
    """, unsafe_allow_html=True)
    
    # Display newsletter content
    st.markdown(st.session_state.newsletter_content)
    
    st.markdown("""
        </div>
    """, unsafe_allow_html=True)
    
    # Export functionality
    if export_button:
        # Créer un fichier texte à télécharger
        filename = f"newsletter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(
            label="📥 Télécharger en TXT",
            data=st.session_state.newsletter_content,
            file_name=filename,
            mime="text/plain"
        )
        
        # Créer un fichier Markdown à télécharger
        md_filename = f"newsletter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        st.download_button(
            label="📥 Télécharger en Markdown",
            data=st.session_state.newsletter_content,
            file_name=md_filename,
            mime="text/markdown"
        )

elif not st.session_state.is_loading and st.session_state.newsletter_content is None:
    st.info("""
    👉 **Cliquez sur "Générer la newsletter"** pour lancer le traitement.
    
    Le système va :
    1. 🔍 Scraper les sources de cybersécurité
    2. 🧹 Nettoyer et traiter les articles
    3. 📊 Générer les embeddings
    4. 🤖 Utiliser l'IA pour créer la newsletter
    """)

# Footer
st.markdown("""
    <div class="footer">
        <p>Safari Newsletter v1.0 | Veille cybersécurité automatisée</p>
        <p>Dernière mise à jour: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
    </div>
""", unsafe_allow_html=True)
