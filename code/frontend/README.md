# SIGNAL Frontend

Modern React + Vite frontend for the SIGNAL Content Intelligence Platform.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **Recharts** - Data visualization
- **Axios** - API client
- **Lucide React** - Icons

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
cd code/frontend
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

The dev server proxies API requests to `http://localhost:8000` (FastAPI backend).

### Build

```bash
npm run build
```

Built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── Layout.tsx      # Main layout with sidebar
│   ├── SignalCard.tsx  # Polymarket signal display
│   └── CampaignCard.tsx # Campaign preview card
├── pages/              # Route pages
│   ├── Dashboard.tsx   # Main overview
│   ├── Onboarding.tsx  # Company onboarding wizard
│   ├── TrendSignals.tsx # Live Polymarket signals
│   ├── Campaigns.tsx   # Campaign list and generation
│   ├── CampaignDetail.tsx # Single campaign view
│   ├── Analytics.tsx   # Learning curves and metrics
│   └── Settings.tsx    # Company profiles and config
├── lib/
│   ├── api.ts         # API client functions
│   ├── types.ts       # TypeScript interfaces
│   └── utils.ts       # Helper functions
├── App.tsx            # Root component with routing
├── main.tsx           # Entry point
└── index.css          # Global styles and Tailwind
```

## Features

### Dashboard
- Active trend signals overview
- Recent campaigns grid
- System health status
- Quick actions (trigger feedback loop)

### Onboarding
- Multi-step company profile creation
- Brand voice and audience definition
- Competitor tracking

### Trend Signals
- Live Polymarket data feed
- Probability and momentum indicators
- Volume and velocity metrics
- Manual refresh capability

### Campaigns
- AI-generated campaign concepts
- Campaign generation modal
- Status badges (draft, approved, posted)
- Channel recommendations
- Safety scores from Modulate
- Visual asset previews

### Campaign Detail
- Full campaign view
- Approval workflow
- Channel reasoning
- Visual direction notes

### Analytics
- Agent learning curve chart
- Polymarket signal calibration
- Three self-improving loops diagram
- Performance metrics

### Settings
- Company profile management
- System information

## API Integration

The frontend communicates with the FastAPI backend at `/api/v1`:

- `GET /companies` - List companies
- `POST /companies` - Create company
- `GET /signals` - Get trend signals
- `POST /signals/refresh` - Refresh from Polymarket
- `GET /campaigns` - List campaigns
- `POST /campaigns/generate` - Generate new campaigns
- `POST /campaigns/:id/approve` - Approve campaign
- `GET /analytics/*` - Analytics data
- `POST /feedback/trigger` - Trigger feedback loop

## Styling

Uses Tailwind CSS with a custom design system:

- Primary color: Blue (`#3b82f6`)
- Clean, modern interface
- Responsive grid layouts
- Smooth transitions and hover states
- Accessible color contrasts

## Development Notes

- All API calls are typed with TypeScript interfaces
- Error handling with try/catch and user alerts
- Loading states for async operations
- Responsive design for mobile and desktop
- Component-based architecture for reusability
