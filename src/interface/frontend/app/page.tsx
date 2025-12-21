"use client";

import { useEffect, useState } from "react";
import {
  Newsletter,
  fetchNewsletters,
  generateNewsletter,
  GeneratedNewsletter,
  checkBackendHealth,
} from "@/lib/api";
import NewsletterCard from "@/components/NewsletterCard";
import FeaturedNewsletter from "@/components/FeaturedNewsletter";
import { Loader } from "lucide-react";

export default function Home() {
  const [newsletters, setNewsletters] = useState<Newsletter[]>([]);
  const [selectedNewsletter, setSelectedNewsletter] = useState<Newsletter | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generatedNewsletter, setGeneratedNewsletter] = useState<GeneratedNewsletter | null>(null);

  useEffect(() => {
    async function loadNewsletters() {
      try {
        setIsLoading(true);
        
        // Vérifier d'abord si le backend est accessible
        const isBackendHealthy = await checkBackendHealth();
        if (!isBackendHealthy) {
          setError(
            "⚠️ Le serveur backend n'est pas accessible.\n\n" +
            "Pour démarrer le backend :\n" +
            "1. Ouvrez un terminal\n" +
            "2. Exécutez : python start_backend.py\n" +
            "3. Attendez que le serveur démarre sur http://localhost:8000\n" +
            "4. Rafraîchissez cette page"
          );
          setIsLoading(false);
          return;
        }
        
        const data = await fetchNewsletters();
        setNewsletters(data);
        if (data.length > 0) {
          setSelectedNewsletter(data[0]);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Erreur inconnue";
        if (errorMessage.includes("Failed to fetch") || errorMessage.includes("NetworkError")) {
          setError(
            "⚠️ Impossible de se connecter au serveur backend.\n\n" +
            "Vérifications à faire :\n" +
            "1. Le serveur FastAPI est-il démarré ? (python start_backend.py)\n" +
            "2. Le serveur écoute-t-il sur http://localhost:8000 ?\n" +
            "3. Y a-t-il un firewall qui bloque la connexion ?\n\n" +
            "URL du backend attendue : http://localhost:8000"
          );
        } else {
          setError(`Erreur lors du chargement des newsletters: ${errorMessage}`);
        }
        console.error("Error loading newsletters:", err);
      } finally {
        setIsLoading(false);
      }
    }

    loadNewsletters();
  }, []);

  const handleGenerateNewsletter = async () => {
    try {
      setIsGenerating(true);
      setGenerationError(null);
      const result = await generateNewsletter();
      setGeneratedNewsletter(result);
      
      // Recharger la liste des newsletters après génération
      try {
        const data = await fetchNewsletters();
        setNewsletters(data);
        if (data.length > 0) {
          setSelectedNewsletter(data[0]);
        }
      } catch (err) {
        console.error("Error reloading newsletters:", err);
      }
    } catch (err) {
      console.error("Generation error:", err);
      setGenerationError("Échec de la création de la newsletter.");
    } finally {
      setIsGenerating(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-2xl">
          <h2 className="text-2xl font-bold text-dark-text mb-4">Erreur de connexion</h2>
          <div className="bg-dark-bg-secondary border border-red-500/50 rounded-lg p-6 mb-4">
            <pre className="text-left text-sm text-dark-text-secondary whitespace-pre-wrap font-mono">
              {error}
            </pre>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors"
          >
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-dark-bg">
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-wide text-accent-teal font-semibold">
              Pipeline quotidien
            </p>
            <h2 className="text-3xl font-bold text-dark-text">
              Générer la newsletter du jour
            </h2>
            <p className="text-dark-text-secondary">
              Lance le pipeline et affiche le rendu HTML généré par le backend.
            </p>
          </div>
          <button
            onClick={handleGenerateNewsletter}
            disabled={isGenerating}
            className="inline-flex items-center justify-center px-5 py-3 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors disabled:opacity-60"
          >
            {isGenerating ? "Génération en cours..." : "Créer la newsletter"}
          </button>
        </div>
        {generationError && (
          <div className="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-red-100">
            {generationError}
          </div>
        )}
        {generatedNewsletter && (
          <div className="mt-8 rounded-xl border border-white/10 bg-dark-bg-secondary/60 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-semibold text-dark-text">Newsletter générée</h3>
              <span className="text-sm text-dark-text-secondary">
                Contenu issu du pipeline backend
              </span>
            </div>
            <div
              className="prose prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: generatedNewsletter.html }}
            />
          </div>
        )}
      </section>

      {/* Featured Newsletter Section */}
      {selectedNewsletter && !isLoading && (
        <FeaturedNewsletter newsletter={selectedNewsletter} />
      )}

      {/* Newsletters Grid Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-dark-text mb-2">
            Toutes les actualités
          </h2>
          <p className="text-dark-text-secondary">
            Explorez nos dernières analyses et rapports en cybersécurité
          </p>
        </div>

        {isLoading ? (
          <div className="flex justify-center items-center py-20">
            <Loader className="animate-spin text-accent-teal" size={40} />
          </div>
        ) : newsletters.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-dark-text-secondary">
              Aucune newsletter trouvée. Veuillez vérifier la connexion au serveur API.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {newsletters.map((newsletter) => (
              <NewsletterCard
                key={newsletter._id}
                newsletter={newsletter}
                isSelected={selectedNewsletter?._id === newsletter._id}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
