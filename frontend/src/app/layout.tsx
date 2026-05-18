import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OpenHospital Sim — Command Center',
  description: 'AI-powered hospital digital twin simulator — operations dashboard',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface text-text-primary antialiased">{children}</body>
    </html>
  )
}
