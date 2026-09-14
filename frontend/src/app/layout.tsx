import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Spatial PeerRing — AI Tutoring Environment',
  description: 'Adaptive 3D Multi-Agent Learning & Evaluation System',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
