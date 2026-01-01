"use client";

import { useEffect, useMemo, useState } from "react";
import { Newsletter, fetchNewsletters, checkBackendHealth } from "@/lib/api";
import NewsletterCard from "@/components/NewsletterCard";
import { Loader } from "lucide-react";

export default function HistoriquePage() {
  const [newsletters, setNewsletters] = useState<Newsletter[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const CATEGORY_BADGES = [
    "Data Breaches",
    "Compliance & Regulation",
    "Human Factors",
    "Data Protection & Privacy",
    "SOC & Automation",
    "IAM",
    "Cloud & SaaS Security",
    "Vulnerabilities & Exploits",
    "Malware & Ransomware",
    "Threat Intelligence",
    "AI Security & Threats",
  ];

  const filteredNewsletters = useMemo(() => {
    if (!activeTag) return newsletters;
    return newsletters.filter(n => (n.tags || []).includes(activeTag));
  }, [newsletters, activeTag]);

  useEffect(() => {
    async function loadAll() {
      try {
        setIsLoading(true);
        const healthy = await checkBackendHealth();
        if (!healthy) {
          setError("Le serveur backend n'est pas accessible.");
          setIsLoading(false);
          return;
        }
        const data = await fetchNewsletters();
        setNewsletters(data);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Erreur inconnue";
        setError(msg);
      } finally {
        setIsLoading(false);
      }
    }
    loadAll();
  }, []);

  return (
    <div className="bg-dark-bg min-h-screen w-full overflow-x-hidden">
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold text-dark-text mb-2">Historique des newsletters</h1>
            <p className="text-dark-text-secondary">Parcourez l'ensemble des parutions enregistrées</p>
          </div>
          <a href="/" className="text-accent-teal hover:text-accent-teal-hover">Retour à l'accueil</a>
        </div>
      </section>

      {isLoading ? (
        <div className="flex justify-center items-center py-20">
          <Loader className="animate-spin text-accent-teal" size={40} />
        </div>
      ) : error ? (
        <div className="max-w-3xl mx-auto px-4 text-dark-text-secondary">{error}</div>
      ) : newsletters.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-dark-text-secondary">Aucune newsletter enregistrée.</p>
        </div>
      ) : (
        <>
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-6">
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setActiveTag(null)}
                className={`px-3 py-1 text-sm font-semibold rounded-full border ${
                  activeTag === null
                    ? "bg-accent-teal text-dark-bg border-transparent"
                    : "border-white/10 text-dark-text-secondary hover:border-accent-teal"
                }`}
              >
                Tous
              </button>
              {CATEGORY_BADGES.map(tag => (
                <button
                  key={tag}
                  onClick={() => setActiveTag(tag)}
                  className={`px-3 py-1 text-sm font-semibold rounded-full ${
                    activeTag === tag
                      ? "bg-accent-teal text-dark-bg"
                      : "bg-dark-bg-secondary border border-white/10 text-dark-text hover:border-accent-teal"
                  }`}
                >
                  {tag}
                </button>
              ))}
            </div>
          </section>
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 w-full">
              {filteredNewsletters.map((nl) => (
                <NewsletterCard key={nl._id} newsletter={nl} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
