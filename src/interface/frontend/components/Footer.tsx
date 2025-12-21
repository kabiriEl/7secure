"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Mail, Send } from "lucide-react";
import { subscribe } from "@/lib/api";

export default function Footer() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubscribe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Veuillez entrer votre email");
      return;
    }

    setIsLoading(true);
    try {
      await subscribe(email);
      toast.success("Inscrit avec succès! Vérifiez votre email.");
      setEmail("");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Erreur lors de l'inscription";
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <footer className="bg-dark-bg-secondary border-t border-white/10 mt-20">
      {/* Newsletter Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="max-w-2xl">
          <h3 className="text-3xl sm:text-4xl font-bold mb-4 text-dark-text">
            Restez informé des dernières actualités
          </h3>
          <p className="text-dark-text-secondary mb-6">
            Recevez chaque jour les actualités majeures en cybersécurité et menaces
            numériques
          </p>

          <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Mail
                className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                size={20}
              />
              <input
                type="email"
                placeholder="Votre adresse email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-dark-bg text-dark-text rounded-full border border-white/10 focus:border-accent-teal focus:outline-none transition-colors"
              />
            </div>
            <button
              type="submit"
              disabled={isLoading}
              className="px-8 py-3 rounded-full bg-accent-teal text-dark-bg font-semibold hover:bg-accent-teal-hover transition-colors disabled:opacity-50 flex items-center justify-center gap-2 whitespace-nowrap"
            >
              <Send size={18} />
              {isLoading ? "Inscription..." : "S'abonner"}
            </button>
          </form>
        </div>
      </div>

      {/* Bottom Footer */}
      <div className="bg-dark-bg border-t border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 text-dark-text-secondary text-sm">
            <div className="flex items-center space-x-2">
              <span className="text-accent-teal">●</span>
              <span className="font-semibold">VeilleCyber</span>
            </div>
            <div className="flex gap-6">
              <Link href="#" className="hover:text-dark-text transition-colors">
                Politique de confidentialité
              </Link>
              <Link href="#" className="hover:text-dark-text transition-colors">
                Conditions d'utilisation
              </Link>
            </div>
            <span>
              &copy; {new Date().getFullYear()} VeilleCyber. Tous droits réservés.
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
}
