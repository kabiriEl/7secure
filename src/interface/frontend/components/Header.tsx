"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Search } from "lucide-react";

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-white/10">
      <nav className="bg-dark-bg px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center space-x-2 text-2xl font-bold text-dark-text hover:text-accent-teal transition-colors"
          >
            <span className="text-accent-teal">●</span>
            <span>VeilleCyber</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            <Link
              href="/"
              className="text-dark-text-secondary hover:text-dark-text transition-colors"
            >
              Accueil
            </Link>
            <Link
              href="#about"
              className="text-dark-text-secondary hover:text-dark-text transition-colors"
            >
              À propos
            </Link>
          </div>

          {/* Right Actions */}
          <div className="hidden md:flex items-center space-x-4">
            <button
              className="p-2 text-dark-text-secondary hover:text-dark-text transition-colors"
              aria-label="Search"
            >
              <Search size={20} />
            </button>
            <Link
              href="/login"
              className="text-dark-text-secondary hover:text-dark-text transition-colors"
            >
              Se connecter
            </Link>
            <Link
              href="/subscribe"
              className="px-6 py-2 rounded-full bg-accent-teal text-dark-bg font-semibold hover:bg-accent-teal-hover transition-colors"
            >
              S'abonner
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2 text-dark-text-secondary hover:text-dark-text transition-colors"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-label="Toggle menu"
          >
            {isMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden mt-4 space-y-3 pb-4 border-t border-white/10 pt-4">
            <Link
              href="/"
              className="block text-dark-text-secondary hover:text-dark-text transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Accueil
            </Link>
            <Link
              href="#about"
              className="block text-dark-text-secondary hover:text-dark-text transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              À propos
            </Link>
            <Link
              href="/login"
              className="block text-dark-text-secondary hover:text-dark-text transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Se connecter
            </Link>
            <Link
              href="/subscribe"
              className="block px-6 py-2 rounded-full bg-accent-teal text-dark-bg font-semibold text-center hover:bg-accent-teal-hover transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              S'abonner
            </Link>
          </div>
        )}
      </nav>
    </header>
  );
}
