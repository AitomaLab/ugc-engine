import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "./Sidebar";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Aitoma Studio",
  description: "AI-powered UGC content engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased min-h-screen text-[#1A1A1F]`}>
        {/* Background Mesh */}
        <div className="fixed inset-0 -z-10" style={{
          background: '#F0F4FF',
          backgroundImage: `
            radial-gradient(ellipse at 20% 30%, rgba(51,122,255,0.12) 0%, transparent 60%),
            radial-gradient(ellipse at 80% 70%, rgba(199,187,253,0.15) 0%, transparent 60%),
            radial-gradient(ellipse at 50% 10%, rgba(51,200,255,0.08) 0%, transparent 50%)
          `
        }} />
        {/* Main App Layout */}
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <div className="max-w-6xl mx-auto p-8 lg:p-12">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
