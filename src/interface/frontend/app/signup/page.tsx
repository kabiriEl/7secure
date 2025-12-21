"use client";

"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Mail, Lock, User, ArrowRight } from "lucide-react";
import { signup } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (
      !formData.name ||
      !formData.email ||
      !formData.password ||
      !formData.confirmPassword
    ) {
      toast.error("Veuillez remplir tous les champs");
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      toast.error("Les mots de passe ne correspondent pas");
      return;
    }

    if (formData.password.length < 6) {
      toast.error("Le mot de passe doit contenir au moins 6 caractères");
      return;
    }

    setIsLoading(true);
    try {
      await signup({
        name: formData.name,
        email: formData.email,
        password: formData.password,
      });
      toast.success("Inscription réussie! Veuillez vous connecter.");
      router.push("/login");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Erreur lors de l'inscription";
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-dark-bg">
      <div className="w-full max-w-md">
        <div className="bg-dark-bg-secondary rounded-lg border border-white/10 p-8">
          {/* Title */}
          <h1 className="text-3xl font-bold text-dark-text mb-2">S'inscrire</h1>
          <p className="text-dark-text-secondary mb-8">
            Créez votre compte VeilleCyber gratuitement
          </p>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Name */}
            <div>
              <label
                htmlFor="name"
                className="block text-sm font-semibold text-dark-text mb-2"
              >
                Nom complet
              </label>
              <div className="relative">
                <User
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                  size={18}
                />
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  className="w-full pl-12 pr-4 py-2 rounded-lg bg-dark-bg border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
                  placeholder="Votre nom"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-semibold text-dark-text mb-2"
              >
                Email
              </label>
              <div className="relative">
                <Mail
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                  size={18}
                />
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  className="w-full pl-12 pr-4 py-2 rounded-lg bg-dark-bg border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
                  placeholder="votre@email.com"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-semibold text-dark-text mb-2"
              >
                Mot de passe
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                  size={18}
                />
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  className="w-full pl-12 pr-4 py-2 rounded-lg bg-dark-bg border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
                  placeholder="••••••••"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-semibold text-dark-text mb-2"
              >
                Confirmer le mot de passe
              </label>
              <div className="relative">
                <Lock
                  className="absolute left-4 top-1/2 transform -translate-y-1/2 text-dark-text-secondary pointer-events-none"
                  size={18}
                />
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className="w-full pl-12 pr-4 py-2 rounded-lg bg-dark-bg border border-white/10 text-dark-text placeholder-dark-text-secondary focus:border-accent-teal focus:outline-none transition-colors"
                  placeholder="••••••••"
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2 rounded-lg bg-accent-teal text-dark-bg font-semibold hover:bg-accent-teal-hover transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isLoading ? "Inscription..." : "S'inscrire"}
              {!isLoading && <ArrowRight size={18} />}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-white/10"></div>
            <span className="text-dark-text-secondary text-sm">ou</span>
            <div className="flex-1 h-px bg-white/10"></div>
          </div>

          {/* Login Link */}
          <p className="text-center text-dark-text-secondary">
            Vous avez déjà un compte?{" "}
            <Link
              href="/login"
              className="text-accent-teal hover:text-accent-teal-hover transition-colors font-semibold"
            >
              Se connecter
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
