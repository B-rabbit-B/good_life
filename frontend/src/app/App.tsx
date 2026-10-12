import { QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { CoverProvider } from '../components/cover'
import { GlassModeProvider } from '../components/glass/GlassModeProvider'
import { ToastProvider } from '../components/Toast'
import { queryClient } from './queryClient'
import { routes } from './routes'

const router = createBrowserRouter(routes)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <GlassModeProvider>
        <CoverProvider>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </CoverProvider>
      </GlassModeProvider>
    </QueryClientProvider>
  )
}
