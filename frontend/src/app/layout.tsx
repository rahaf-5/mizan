import type { Metadata, Viewport } from "next";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "@fontsource/ibm-plex-sans-arabic/700.css";
import "@fontsource/amiri-quran/400.css";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { defaultLocale, getDictionary, localeConfig } from "@/i18n";

const t = getDictionary();

export const metadata: Metadata = {
  title: t.meta.title,
  description: t.meta.description,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const { lang, dir } = localeConfig[defaultLocale];
  return (
    <html lang={lang} dir={dir}>
      <body className="min-h-dvh antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
