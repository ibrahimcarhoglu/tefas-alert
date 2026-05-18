import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "sonner";
import Navbar from "@/components/layout/Navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TEFAS Platform — Fon Analizi & Anomali Tespiti",
  description:
    "TEFAS fonlarını analiz edin, nakit akışını takip edin, anomali alarmlarını görün. Türkiye'nin en kapsamlı fon analiz platformu.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('theme');
                  if (theme === 'light' || (!theme && window.matchMedia('(prefers-color-scheme: light)').matches)) {
                    document.documentElement.classList.add('light');
                    document.documentElement.classList.remove('dark');
                  } else {
                    document.documentElement.classList.add('dark');
                    document.documentElement.classList.remove('light');
                  }
                } catch (e) {}
              })();
            `
          }}
        />
      </head>
      <body className={`${inter.className} bg-background text-foreground antialiased transition-colors duration-200`}>
        <Navbar />
        <main className="min-h-[calc(100vh-64px)]">{children}</main>
        <Toaster
          position="top-right"
          theme="dark"
          toastOptions={{
            style: {
              background: "var(--card-bg)",
              border: "1px solid var(--card-border)",
              color: "var(--foreground)",
            },
          }}
        />
      </body>
    </html>
  );
}
