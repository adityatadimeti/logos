# Logos Frontend (React + Vite)

A simple React UI for the Logos banking assistant.

## Prereqs
- Backend running with an `/api/ask` endpoint (Flask app, default `http://127.0.0.1:5001`).
- Node 18+ / PNPM or NPM.

## Dev
```bash
cd frontend
npm install   # or pnpm install
npm run dev
```
Open http://localhost:5173

The dev server proxies `/api` to the backend at `http://127.0.0.1:5001` by default. To point elsewhere:
```bash
VITE_API_TARGET=http://your-backend:5001 npm run dev
```

## Build
```bash
npm run build
npm run preview
```

## Notes
- Ask a question and the UI will POST to `/api/ask` and render the response. If the response includes `image_base64`, it will render the image.
- Styling is in `src/styles.css`. 