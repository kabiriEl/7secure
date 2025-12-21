"use client";

"use client";

import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Mail, Bell, Check, ArrowRight } from "lucide-react";
import { subscribe } from "@/lib/api";

export default function SubscribePage() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email) {
      toast.error("Veuillez entrer votre email");
      return;
    }

    setIsLoading(true);
    try {
      await subscribe(email);
      setIsSubscribed(true);
      toast.success("Inscription à la newsletter réussie!");
      setEmail("");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Erreur lors de l'inscription";
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-dark-bg">
      <div className="w-full max-w-2xl">
        {isSubscribed ? (
          <div className="bg-dark-bg-secondary rounded-lg border border-accent-teal/30 p-12 text-center">
            <div className="w-16 h-16 bg-accent-teal/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <Check size={32} className="text-accent-teal" />
            </div>
            <h1 className="text-3xl font-bold text-dark-text mb-2">
              Merci de votre inscription!
            </h1>
            <p className="text-dark-text-secondary mb-8">
              Vous recevrez désormais les dernières actualités en cybersécurité chaque
              jour. Vérifiez votre email pour confirmer votre inscription.
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors"
            >
              Retourner à l'accueil
              <ArrowRight size={18} />
            </Link>
          </div>
        ) : (
          <div className="bg-dark-bg-secondary rounded-lg border border-white/10 p-8 sm:p-12">
            {/* Title */}
            <h1 className="text-4xl font-bold text-dark-text mb-4">
              S'abonner à la newsletter
            </h1>
            <p className="text-lg text-dark-text-secondary mb-12">
              Recevez quotidiennement les meilleures actualités en cybersécurité, les
              dernières menaces et les analyses approfondies directement dans votre boîte
              de réception.
            </p>

            {/* Benefits */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-12">
              <div className="flex flex-col items-start gap-3">
                <div className="w-10 h-10 bg-accent-teal/20 rounded-lg flex items-center justify-center">
                  <Bell size={20} className="text-accent-teal" />
                </div>
                <h3 className="font-semibold text-dark-text">
                  Notifications quotidiennes
                </h3>
                <p className="text-sm text-dark-text-secondary">
                  Recevez les actualités les plus importantes chaque jour
                </p>
              </div>

              <div className="flex flex-col items-start gap-3">
                <div className="w-10 h-10 bg-accent-teal/20 rounded-lg flex items-center justify-center">
                  <Mail size={20} className="text-accent-teal" />
                </div>
                <h3 className="font-semibold text-dark-text">Analyses approfondies</h3>
                <p className="text-sm text-dark-text-secondary">
                  Comprenez les implications réelles des menaces
                </p>
              </div>

              <div className="flex flex-col items-start gap-3">
                <div className="w-10 h-10 bg-accent-teal/20 rounded-lg flex items-center justify-center">
                  <Check size={20} className="text-accent-teal" />
                </div>
                <h3 className="font-semibold text-dark-text">Contenu curatisé</h3>
                <p className="text-sm text-dark-text-secondary">
                  Sélectionné par nos experts en cybersécurité
                </p>
              </div>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-semibold text-dark-text mb-2"
                >
                  Adresse email
                </label>
                <div className="relative">
                  <Mail
                    className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                    size={20}
                  />
                  <input
                    type="email"
                    id="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-12 pr-4 py-3 rounded-lg bg-dark-bg border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors text-lg"
                    placeholder="votre@email.com"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {/* Terms */}
              <p className="text-xs text-dark-text-secondary">
                En vous inscrivant, vous acceptez nos{" "}
                <Link href="#" className="text-accent-teal hover:underline">
                  conditions d'utilisation
                </Link>{" "}
                et notre{" "}
                <Link href="#" className="text-accent-teal hover:underline">
                  politique de confidentialité
                </Link>
                .
              </p>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-3 rounded-lg bg-accent-teal text-dark-bg font-semibold hover:bg-accent-teal-hover transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-lg"
              >
                {isLoading ? "Inscription en cours..." : "S'abonner"}
                {!isLoading && <ArrowRight size={20} />}
              </button>
            </form>

            {/* Login Link */}
            <p className="text-center text-dark-text-secondary mt-8">
              Vous avez déjà un compte?{" "}
              <Link
                href="/login"
                className="text-accent-teal hover:text-accent-teal-hover transition-colors font-semibold"
              >
                Se connecter
              </Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
