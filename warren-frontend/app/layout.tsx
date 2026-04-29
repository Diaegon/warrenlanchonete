import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Warren Lanchonete",
  description:
    "Seu portfólio analisado com a filosofia de Buffett. Sem frescura.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-nubank-dark text-nubank-text antialiased">
        <header className="border-b border-nubank-border bg-nubank-card/60 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-nubank-purple flex items-center justify-center font-bold text-white text-sm select-none">
              W
            </div>
            <div>
              <span className="font-bold text-white text-lg leading-none block">
                Warren Lanchonete
              </span>
              <span className="text-nubank-muted text-xs">
                filosofia de Buffett, preço de lanchonete
              </span>
            </div>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
