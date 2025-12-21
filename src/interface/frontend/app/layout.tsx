import type { Metadata } from "next";
import { Toaster } from "sonner";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "VeilleCyber - Actualités Cybersécurité",
  description:
    "Restez informé des dernières actualités en cybersécurité et menaces numériques",
  keywords: ["cybersécurité", "actualités", "sécurité informatique", "menaces"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-dark-bg text-dark-text">
        <Header />
        <main className="min-h-screen">{children}</main>
        <Footer />
        <Toaster position="bottom-right" theme="dark" />
      </body>
    </html>
  );
}
