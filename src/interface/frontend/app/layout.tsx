import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Safari Newsletter - Veille Cybersécurité',
  description: 'Newsletter quotidienne de cybersécurité générée par IA',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr">
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
