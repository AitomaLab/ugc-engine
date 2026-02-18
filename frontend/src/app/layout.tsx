import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "./Sidebar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UGC Engine | Creative Platform",
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
          <Sidebar />
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
