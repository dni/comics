import { defineConfig } from 'vite'
import solid from 'vite-plugin-solid'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    solid(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Comic Library',
        short_name: 'Comics',
        description: 'Catalog, grade, and manage your comic book collection.',
        theme_color: '#b35c38',
        background_color: '#faf7f2',
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // /api is intentionally left off runtime caching - comic data and
        // auth state must always come from the network, never a stale cache.
        runtimeCaching: [
          {
            urlPattern: /^\/library\/.*/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'library-images',
              // library image URLs are cache-busted with a ?v=<updated_at>
              // query param on every edit, so caching by full URL is safe
              expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/library': 'http://127.0.0.1:8000',
    },
  },
})
