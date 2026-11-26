import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '@/components/Navbar';
import { GeminiKeyBanner } from '@/components/GeminiKeyBanner';
import { AuthProvider } from '@/context/AuthContext';
import { ThemeProvider } from '@/context/ThemeContext';

export const metadata: Metadata = {
  title: 'Reel Studio — Automated AI Vertical Video Generator',
  description: 'Turn any long recording, YouTube, Twitch, or Kick URL into viral 30-150 second vertical reels with captions and karaoke subtitles.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('reelstudio_theme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  var theme = saved || (prefersDark ? 'dark' : 'light');
                  document.documentElement.classList.remove('light', 'dark');
                  document.documentElement.classList.add(theme);
                  document.documentElement.setAttribute('data-theme', theme);
                  document.documentElement.style.colorScheme = theme;
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-page text-text-primary antialiased font-body min-h-screen selection:bg-accent selection:text-white">
        <ThemeProvider>
          <AuthProvider>
            <GeminiKeyBanner />
            <Navbar />
            <main className="min-h-[calc(100vh-7rem)]">{children}</main>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
