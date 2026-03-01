import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

const _inter = Inter({ subsets: ['latin'] })
const _jetbrainsMono = JetBrains_Mono({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Deep Research Agent',
  description: 'AI-powered deep research agent that generates comprehensive reports on any topic',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/sparkle.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/sparkle.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/sparkle.png',
        type: 'image/svg+xml',
      },
    ],
    apple: '/sparkle.png',
  },
}

export const viewport: Viewport = {
  themeColor: '#1a1a2e',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem storageKey="akro-theme">
          {children}
          <Analytics />
        </ThemeProvider>
      </body>
    </html>
  )
}
