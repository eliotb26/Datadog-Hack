# SIGNAL Frontend - Quick Start Guide

## Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

## Installation & Setup

1. Navigate to the frontend directory:
```bash
cd code/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

4. Open your browser to `http://localhost:3000`

## First Steps

### 1. Create a Company Profile
- Click "New Company" in the sidebar
- Fill out the onboarding form with your brand details
- Submit to create your first company profile

### 2. View Trend Signals
- Navigate to "Trend Signals" in the sidebar
- Click "Refresh" to fetch live data from Polymarket
- Signals show probability, momentum, and volume metrics

### 3. Generate Campaigns
- Go to "Campaigns" page
- Click "Generate Campaigns"
- Select a company and a trend signal
- Wait for AI to generate 3 campaign concepts

### 4. Review Campaign Details
- Click on any campaign card to see full details
- Review headline, body copy, visual direction
- Check safety scores and channel recommendations
- Approve campaigns when ready

### 5. View Analytics
- Navigate to "Analytics" to see:
  - Agent learning curves over time
  - Signal calibration accuracy
  - The three self-improving loops

## Demo Flow (7 minutes)

For hackathon presentations, follow this sequence:

1. **Dashboard** (30s) - Show system overview and health
2. **Onboarding** (1m) - Create a company profile live
3. **Trend Signals** (1m) - Refresh and show live Polymarket data
4. **Generate Campaigns** (2m) - Generate 3 concepts, show results
5. **Campaign Detail** (1m) - Deep dive into one campaign
6. **Analytics** (1.5m) - Show learning curves and loops diagram
7. **Wrap-up** (30s) - Trigger feedback loop, show system improving

## Troubleshooting

### API Connection Issues
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify proxy configuration in `vite.config.ts`

### No Data Showing
- Backend may not have data yet
- Try creating a company first
- Refresh signals manually
- Generate some campaigns

### Build Errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`
- Check Node.js version: `node --version` (should be 18+)

## Production Build

```bash
npm run build
npm run preview
```

The built files in `dist/` can be served by any static file server.

## Key Features

- **Real-time Updates** - Live Polymarket data integration
- **AI Campaign Generation** - Multi-agent pipeline visualization
- **Learning Analytics** - Visual feedback loops and metrics
- **Responsive Design** - Works on desktop and mobile
- **Type Safety** - Full TypeScript coverage
- **Modern Stack** - React 18, Vite, Tailwind CSS

## Next Steps

- Explore the Analytics page to understand the three loops
- Generate multiple campaigns to see variety
- Check Settings to manage company profiles
- Review the main README.md for architecture details
