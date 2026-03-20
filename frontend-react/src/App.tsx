// App.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Dashboard } from './pages/Dashboard';
import { Deals } from './pages/Deals';
import { Arbitrage } from './pages/Arbitrage';
import { Products } from './pages/Products';
import { Scraper } from './pages/Scraper';
import { Queries } from './pages/Queries';
import { Telemetry } from './pages/Telemetry';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/deals" element={<Deals />} />
              <Route path="/arbitrage" element={<Arbitrage />} />
              <Route path="/products" element={<Products />} />
              <Route path="/scraper" element={<Scraper />} />
              <Route path="/queries" element={<Queries />} />
              <Route path="/telemetry" element={<Telemetry />} />
            </Routes>
          </ErrorBoundary>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
