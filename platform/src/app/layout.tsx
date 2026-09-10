import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HeartOracle — Multimodal Cardiac Intelligence Platform",
  description:
    "Enterprise control tower for the ORACLE pipeline: measured cardiac MRI quantification (5-fold attention U-Net ensemble, ONNX INT8), audited advisory reports, modality-adapter roadmap, AI governance and security center. Research Use Only.",
  keywords: [
    "HeartOracle",
    "ORACLE",
    "cardiac MRI",
    "ejection fraction",
    "ONNX",
    "RAG",
    "AI governance",
    "GMLP",
    "ISO 14971",
    "clinical decision support",
  ],
  authors: [{ name: "Dalfino" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "HeartOracle — Multimodal Cardiac Intelligence Platform",
    description:
      "Measured, audited, cited. ORACLE advises — physicians decide. Research Use Only.",
    siteName: "HeartOracle",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased bg-background text-foreground`}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
