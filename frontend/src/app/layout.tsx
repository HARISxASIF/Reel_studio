import type { Metadata } from 'next';
import './globals.css';
import { Navbar } from '@/components/Navbar';
import { GeminiKeyBanner } from '@/components/GeminiKeyBanner';

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
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        <GeminiKeyBanner />
        <Navbar />
        <main className="min-h-[calc(100vh-4rem)]">{children}</main>
      </body>
    </html>
  );
}
