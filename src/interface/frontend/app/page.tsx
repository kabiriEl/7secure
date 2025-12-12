'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';

interface NewsletterData {
  content: string;
  html: string;
}

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newsletter, setNewsletter] = useState<NewsletterData | null>(null);
  const [apiUrl] = useState('http://localhost:8000');
  const [currentDate, setCurrentDate] = useState<string>('');

  // Initialiser la date une seule fois côté client pour éviter les hydration errors
  useEffect(() => {
    setCurrentDate(
      new Date().toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      })
    );
  }, []);

  const generateNewsletter = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(`${apiUrl}/run-daily-newsletter`);
      // Debug: log response to browser console to inspect payload
      // and set newsletter state as usual
      // eslint-disable-next-line no-console
      console.log('[FRONTEND] /run-daily-newsletter response', response.data);
      setNewsletter(response.data);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(
          `Erreur: ${err.message}. Vérifiez que le serveur backend est en cours d'exécution sur ${apiUrl}`
        );
      } else {
        setError('Une erreur inattendue s\'est produite');
      }
    } finally {
      setLoading(false);
    }
  };

  const downloadHTML = () => {
    if (!newsletter?.html) return;

    const element = document.createElement('a');
    const file = new Blob([newsletter.html], { type: 'text/html' });
    element.href = URL.createObjectURL(file);
    element.download = `newsletter_${new Date().toISOString().split('T')[0]}.html`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-900/50 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white">
                📰 Safari Newsletter
              </h1>
              <p className="mt-2 text-slate-400">
                Veille quotidienne en cybersécurité générée par IA
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-slate-400">Date</p>
              <p className="text-2xl font-semibold text-white">
                {currentDate || '...'}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        {/* Controls */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row">
          <button
            onClick={generateNewsletter}
            disabled={loading}
            className="flex-1 rounded-lg bg-gradient-to-r from-purple-600 to-purple-700 px-6 py-3 font-semibold text-white transition-all duration-200 hover:from-purple-700 hover:to-purple-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="loading-spinner w-5 h-5 border-2 border-white border-t-purple-400" />
                Génération en cours...
              </>
            ) : (
              <>
                ✨ Générer la newsletter
              </>
            )}
          </button>

          {newsletter && (
            <button
              onClick={() => setNewsletter(null)}
              className="rounded-lg border border-slate-600 px-6 py-3 font-semibold text-white transition-colors duration-200 hover:border-slate-500 hover:bg-slate-800"
            >
              🔄 Réinitialiser
            </button>
          )}

          {newsletter?.html && (
            <button
              onClick={downloadHTML}
              className="rounded-lg border border-green-600 px-6 py-3 font-semibold text-green-400 transition-colors duration-200 hover:border-green-500 hover:bg-green-950"
            >
              ⬇️ Télécharger
            </button>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-8 rounded-lg border border-red-500/50 bg-red-950/30 p-4 text-red-300">
            <p className="font-semibold">❌ Erreur</p>
            <p className="mt-1 text-sm">{error}</p>
          </div>
        )}

        {/* Newsletter Content */}
        {newsletter ? (
          <div className="newsletter-container p-8">
            <div
              className="html-content prose prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: newsletter.html }}
            />
            {/* Debug panel: show raw JSON for development */}
            <details className="mt-4 p-4 bg-slate-900/50 border border-slate-700 text-sm text-slate-300">
              <summary className="cursor-pointer font-semibold">Debug: réponse brute</summary>
              <pre className="mt-2 whitespace-pre-wrap">{JSON.stringify(newsletter, null, 2)}</pre>
            </details>
          </div>
        ) : (
          <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-12 text-center">
            <p className="text-lg text-slate-400">
              👉 Cliquez sur <strong>"Générer la newsletter"</strong> pour lancer le traitement.
            </p>
            <p className="mt-4 text-sm text-slate-500">
              Le système va scraper les sources, analyser les articles et générer une newsletter
              formatée avec IA.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-700 bg-slate-900/50 py-8 text-center text-sm text-slate-500">
        <p>Safari Newsletter v1.0 | Veille cybersécurité automatisée</p>
        <p className="mt-2">
          Dernière mise à jour: {currentDate || '...'}
        </p>
      </footer>
    </div>
  );
}
