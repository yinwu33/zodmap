# ZodMap ADAS Visualisation

This project now exposes the ZOD driving log data through a FastAPI backend and a React + TypeScript frontend that renders the trajectories on top of a Leaflet map.

## Backend API

1. Create / activate your Python environment.
2. Install requirements: `pip install -r requirements.txt`.
3. Start the API server (default on port 8000): `uvicorn src.api:app --reload`.
4. Available endpoints:
   - `GET /api/logs` – list available log IDs (optionally includes metadata with `include_details=true`).
   - `GET /api/logs/{log_id}` – fetch the full trajectory and bounds for a single log.
   - `GET /api/logs/{log_id}/image` – download a JPEG preview image for the driving log.

## Frontend (TypeScript / Vite)

1. Ensure Node.js 18+ is available.
2. From the `frontend` folder run `npm install`.
3. Start the dev server with `npm run dev` (default on http://localhost:5173). The Vite dev server proxies `/api` to the backend.
4. Build for production with `npm run build`; a static bundle will be emitted to `frontend/dist`.

Set `VITE_API_BASE_URL` in a `.env` file under `frontend/` if you need to target a different backend origin.

## Development Notes

- The frontend shows a sidebar with toggleable driving log layers. Selecting a log lazily fetches its trajectory from the backend and draws it on the map.
- Trajectories are cached on the backend via `functools.lru_cache` to avoid repeatedly loading ZOD assets.
- Map tiles use the public OpenStreetMap tile server for convenience; replace the `TileLayer` URL if you have a preferred basemap provider.
