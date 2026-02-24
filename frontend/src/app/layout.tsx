import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Catering Services AI Pro',
  description: 'AI-powered assistant for corporate catering management',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
