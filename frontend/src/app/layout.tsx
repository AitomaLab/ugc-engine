import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UGC Engine | Premium Video SaaS",
  description: "AI-Powered UGC Video Generation Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased text-slate-200`}>
        <div className="flex min-h-screen bg-slate-950">
          {/* Sidebar */}
          <aside className="w-64 border-r border-slate-800 bg-slate-900/50 backdrop-blur-xl flex flex-col sticky top-0 h-screen">
            <div className="p-6 border-b border-slate-800">
              <h1 className="text-xl font-bold gradient-text">UGC Engine</h1>
              <p className="text-xs text-slate-500 mt-1 uppercase tracking-widest font-semibold">Production Platform</p>
            </div>

            <nav className="flex-1 p-4 space-y-2 mt-4">
              <Link href="/" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-slate-800/50 transition-all text-slate-300 hover:text-white group">
                <span className="opacity-70 group-hover:opacity-100 italic transition-opacity">⚡</span>
                <span className="font-medium">Dashboard</span>
              </Link>
              <Link href="/generate" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-slate-800/50 transition-all text-slate-300 hover:text-white group">
                <span className="opacity-70 group-hover:opacity-100 italic transition-opacity">🎬</span>
                <span className="font-medium">New Generation</span>
              </Link>
              <Link href="/history" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-slate-800/50 transition-all text-slate-300 hover:text-white group">
                <span className="opacity-70 group-hover:opacity-100 italic transition-opacity">📜</span>
                <span className="font-medium">Job History</span>
              </Link>
              <Link href="/manage" className="flex items-center space-x-3 p-3 rounded-lg hover:bg-slate-800/50 transition-all text-slate-300 hover:text-white group">
                <span className="opacity-70 group-hover:opacity-100 italic transition-opacity">📦</span>
                <span className="font-medium">Assets Management</span>
              </Link>
            </nav>

            <div className="p-6 border-t border-slate-800">
              <div className="flex items-center space-x-3 text-slate-400 text-sm">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 border border-blue-500/20 flex items-center justify-center text-blue-400 font-bold">U</div>
                <div className="overflow-hidden">
                  <p className="text-white font-medium truncate">User Profile</p>
                  <p className="text-xs opacity-60">Pro Account</p>
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1 overflow-auto bg-slate-950">
            <div className="max-w-6xl mx-auto p-8 lg:p-12">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
