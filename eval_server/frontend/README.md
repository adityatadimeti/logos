# Logos Eval Server Frontend

A React.js frontend for the Logos evaluation server, providing a unified dashboard for observability, interventions, and system monitoring.

## Features

- **Unified Dashboard**: Comprehensive view combining traces, interventions, and system status
- **Real-time Monitoring**: Live updates of AI agent interventions and trace data
- **Trace Analysis**: Individual trace details with span-level debugging
- **System Health**: Database connectivity, service status, and performance metrics

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Running backend services:
  - Brain Server (port 5000)
  - Observability Server (port 5051)

### Installation

```bash
cd eval_server/frontend
npm install
```

### Development

```bash
npm run dev
```

The frontend will be available at `http://localhost:3001`

### Build

```bash
npm run build
```

## Architecture

### Components

- `Dashboard.tsx` - Unified dashboard with traces, interventions, and system status
- `TraceView.tsx` - Individual trace details and event analysis
- `Layout.tsx` - Simple navigation and layout wrapper

### API Integration

The frontend communicates with backend services via:

- `/brain/*` - Proxied to Brain Server (port 5000)
- `/api/*` - Proxied to Observability Server (port 5051)

### Styling

Uses the same dark theme and styling as the original observability dashboard:

- Dark color scheme with purple accents
- Modern card-based layouts
- Responsive design
- Real-time status indicators

## Backend Integration

The frontend expects these endpoints:

### Brain Server (port 5000)
- `GET /history` - Intervention history

### Observability Server (port 5051)  
- `GET /status` - System status and database connectivity
- `GET /dashboard` - Dashboard data with traces and insights (JSON)
- `GET /trace/:id` - Individual trace details and events (JSON)

## Real-time Updates

- Dashboard: Refreshes every 10 seconds
- Auto-refresh pauses when tab is not visible

## Navigation

- **Dashboard** (`/`) - Unified observability dashboard
- **Trace Details** (`/trace/:id`) - Individual trace analysis

## Key Features

- **Unified View**: Single dashboard combining all monitoring data
- **Real-time Data**: Live updates from both Brain Server and Observability Server  
- **Trace Links**: Clickable trace IDs for detailed investigation
- **System Health**: Database status, service health, and performance metrics
- **Clean Backend**: Pure JSON APIs without HTML templates
