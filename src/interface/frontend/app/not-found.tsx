import Link from "next/link";
import { ArrowLeft, AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-dark-bg">
      <div className="text-center">
        <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <AlertCircle size={40} className="text-red-500" />
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-dark-text mb-4">404</h1>
        <p className="text-xl text-dark-text-secondary mb-8">Page non trouvée</p>
        <p className="text-dark-text-secondary mb-8 max-w-md mx-auto">
          Désolé, la page que vous cherchez n'existe pas ou a été supprimée.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3 bg-accent-teal text-dark-bg font-semibold rounded-lg hover:bg-accent-teal-hover transition-colors"
        >
          <ArrowLeft size={18} />
          Retourner à l'accueil
        </Link>
      </div>
    </div>
  );
}
