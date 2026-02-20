# Archive Arbitrage v2.0 Frontend

Modern React frontend for Archive Arbitrage platform.

## Features

- **Dashboard** — Real-time stats, grade distribution, velocity charts
- **Deals Browser** — Grid/list views, grade filters, sorting
- **Arbitrage** — Cross-platform opportunities with profit calculations
- **Products** — Catalog of high-velocity products

## Tech Stack

- React 18 + TypeScript
- TanStack Query (React Query) for data fetching
- React Router for navigation
- Tailwind CSS for styling
- Recharts for data visualization
- Vite for build tooling

## Development

```bash
cd frontend-react
npm install
npm run dev
```

The dev server runs on `http://localhost:3000` and proxies API calls to `http://localhost:8000`.

## Build

```bash
npm run build
```

Output goes to `../frontend-dist/` which is served by the FastAPI backend.

## Project Structure

```
frontend-react/
├── src/
│   ├── components/     # Reusable UI components
│   │   ├── Layout.tsx
│   │   ├── DealCard.tsx
│   │   ├── ArbitrageCard.tsx
│   │   ├── StatsCard.tsx
│   │   ├── FilterBar.tsx
│   │   └── ...
│   ├── pages/         # Route-level pages
│   │   ├── Dashboard.tsx
│   │   ├── Deals.tsx
│   │   ├── Arbitrage.tsx
│   │   └── Products.tsx
│   ├── hooks/         # Custom React hooks
│   │   └── useApi.ts
│   ├── utils/         # Utilities
│   │   └── api.ts
│   ├── types/         # TypeScript types
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── vite.config.ts
```

## API Integration

The frontend expects these API endpoints:

- `GET /api/items` — List items with filtering
- `GET /api/items/:id` — Get single item
- `GET /api/stats` — Dashboard statistics
- `GET /api/products` — Product catalog
- `GET /api/arbitrage` — Arbitrage opportunities
- `GET /api/brands` — List all brands

## Migration from v1

The old frontend in `../frontend/` is a single HTML file with vanilla JS.
This new React frontend will eventually replace it once fully built.

To switch:
1. Build the React app: `npm run build`
2. The API will automatically serve `frontend-dist/index.html`
