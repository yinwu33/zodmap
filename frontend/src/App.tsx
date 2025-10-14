import { useCallback, useEffect, useMemo, useRef, useState, Fragment } from 'react';
import { MapContainer, Polyline, TileLayer, Tooltip, useMap, CircleMarker } from 'react-leaflet';
import type {
  LatLngBoundsExpression,
  LatLngExpression,
  LeafletEvent,
  LeafletEventHandlerFn,
  Map as LeafletMap,
} from 'leaflet';

import { fetchLogDetail, fetchLogImage, fetchLogs } from './api';
import type {
  DrivingLogDetail,
  DrivingLogListItem,
} from './types';

interface LogState {
  summary: DrivingLogListItem;
  detail?: DrivingLogDetail;
  loading: boolean;
  error?: string;
}

interface PreviewState {
  logId: string;
  imageUrl?: string;
  loading: boolean;
  error?: string;
}

const COLORS = ['#ef4444', '#22c55e', '#3b82f6', '#a855f7', '#f59e0b', '#14b8a6', '#8b5cf6'];
const DEFAULT_CENTER: LatLngExpression = [59.3293, 18.0686];
const DEFAULT_ZOOM = 14;
const DISPLAY_ZOOM_THRESHOLD = 14;
const DEFAULT_WEIGHT = 4;
const HIGHLIGHT_WEIGHT = 7;
const HIGHLIGHT_COLOR = '#f97316';
const INACTIVE_OPACITY = 0.7;
const LOGS_PAGE_SIZE = 50;

// Focus the map when lastActivatedLog changes (or when its detail arrives)
function FocusController({
  lastActivatedLog,
  logState,
}: {
  lastActivatedLog?: string;
  logState: Map<string, LogState>;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map || !lastActivatedLog) return;

    const entry = logState.get(lastActivatedLog);
    const detail = entry?.detail;
    if (!detail || !detail.trajectory || detail.trajectory.length === 0) {
      return;
    }

    const first = detail.trajectory[0];
    const bounds = detail.bounds;

    if (bounds) {
      const leafletBounds: LatLngBoundsExpression = [
        [bounds.min_lat, bounds.min_lon],
        [bounds.max_lat, bounds.max_lon],
      ];
      const zoom = map.getBoundsZoom(leafletBounds, false, [60, 60]);
      const targetZoom = Math.max(zoom, DISPLAY_ZOOM_THRESHOLD);
      map.setView([first.lat, first.lon], targetZoom, { animate: true });
    } else {
      const targetZoom = Math.max(map.getZoom(), DISPLAY_ZOOM_THRESHOLD);
      map.setView([first.lat, first.lon], targetZoom, { animate: true });
    }
  }, [lastActivatedLog, logState, map]);

  return null;
}

function App() {
  const [logState, setLogState] = useState<Map<string, LogState>>(new Map());
  const [logOrder, setLogOrder] = useState<string[]>([]);
  const [activeLogs, setActiveLogs] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | undefined>();
  const [isLoadingSummaries, setIsLoadingSummaries] = useState<boolean>(true);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [totalLogs, setTotalLogs] = useState<number | null>(null);
  const [nextOffset, setNextOffset] = useState<number | null>(0);
  const [panelOpen, setPanelOpen] = useState<boolean>(false);
  const [lastActivatedLog, setLastActivatedLog] = useState<string | undefined>();
  const mapRef = useRef<LeafletMap | null>(null);
  const [mapReady, setMapReady] = useState<boolean>(false);
  const [currentZoom, setCurrentZoom] = useState<number>(DEFAULT_ZOOM);
  const [hoveredLogId, setHoveredLogId] = useState<string | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState<boolean>(false);
  const [previewState, setPreviewState] = useState<PreviewState | null>(null);
  const previewImageUrlRef = useRef<string | null>(null);
  const previewRequestIdRef = useRef(0);
  const selectAllRef = useRef<HTMLInputElement | null>(null);
  const allLogIds = logOrder;
  const isAllSelected = allLogIds.length > 0 && allLogIds.every((logId) => activeLogs.has(logId));
  const isIndeterminate = allLogIds.length > 0 && activeLogs.size > 0 && !isAllSelected;

  const loadLogs = useCallback(async (offset: number) => {
    const isInitial = offset === 0;
    console.log('[App] Loading driving log summaries', { offset, limit: LOGS_PAGE_SIZE });
    if (isInitial) {
      setIsLoadingSummaries(true);
      setError(undefined);
    } else {
      setIsLoadingMore(true);
    }

    try {
      const response = await fetchLogs({ limit: LOGS_PAGE_SIZE, offset });
      console.log('[App] Loaded driving log summaries', {
        offset,
        received: response.items.length,
        total: response.total,
        nextOffset: response.next_offset,
      });
      setTotalLogs(response.total);
      setNextOffset(response.next_offset ?? null);
      setError(undefined);
      setLogState((prev) => {
        const base = isInitial ? new Map<string, LogState>() : new Map(prev);
        response.items.forEach((log) => {
          const existing = base.get(log.log_id);
          if (existing) {
            base.set(log.log_id, { ...existing, summary: log });
          } else {
            base.set(log.log_id, { summary: log, loading: false });
          }
        });
        return base;
      });
      setLogOrder((prev) => {
        const baseOrder = isInitial ? [] : prev;
        const seen = new Set(baseOrder);
        const appended: string[] = [];
        response.items.forEach((log) => {
          if (!seen.has(log.log_id)) {
            seen.add(log.log_id);
            appended.push(log.log_id);
          }
        });
        return isInitial ? appended : [...baseOrder, ...appended];
      });
    } catch (err) {
      console.error('[App] Failed to load log summaries', err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (isInitial) {
        setIsLoadingSummaries(false);
      } else {
        setIsLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadLogs(0);
  }, [loadLogs]);

  useEffect(() => () => {
    if (previewImageUrlRef.current) {
      URL.revokeObjectURL(previewImageUrlRef.current);
      previewImageUrlRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current) {
      return;
    }

    const map = mapRef.current;
    const handleZoom: LeafletEventHandlerFn = (event) => {
      const target = (event?.target ?? map) as LeafletMap;
      setCurrentZoom(target.getZoom());
    };

    setCurrentZoom(map.getZoom());
    map.on('zoomend', handleZoom);
    map.on('zoom', handleZoom);

    return () => {
      map.off('zoomend', handleZoom);
      map.off('zoom', handleZoom);
    };
  }, [mapReady]);

  useEffect(() => {
    activeLogs.forEach((logId) => {
      setLogState((prev) => {
        const next = new Map(prev);
        const entry = next.get(logId);
        if (!entry || entry.detail || entry.loading) {
          return prev;
        }

        next.set(logId, { ...entry, loading: true });
        void fetchLogDetail(logId)
          .then((detail) => {
            console.log('[App] Loaded log detail', detail);
            setLogState((current) => {
              const updated = new Map(current);
              const state = updated.get(logId);
              if (!state) {
                return current;
              }
              updated.set(logId, { ...state, detail, loading: false, error: undefined });
              return updated;
            });
          })
          .catch((err) => {
            console.error('[App] Failed to load log detail', { logId, err });
            setLogState((current) => {
              const updated = new Map(current);
              const state = updated.get(logId);
              if (!state) {
                return current;
              }
              updated.set(logId, {
                ...state,
                loading: false,
                error: err instanceof Error ? err.message : String(err),
              });
              return updated;
            });
          });
        return next;
      });
    });
  }, [activeLogs]);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  const polylineData = useMemo(() => {
    const layers: { logId: string; color: string; points: LatLngExpression[]; detail?: DrivingLogDetail }[] = [];
    let colorIndex = 0;

    activeLogs.forEach((logId) => {
      const entry = logState.get(logId);
      const detail = entry?.detail;
      const points = detail?.trajectory;

      if (points && points.length > 0) {
        const latLngs: LatLngExpression[] = points.map((point) => [point.lat, point.lon]);
        const color = COLORS[colorIndex % COLORS.length];
        colorIndex += 1;
        layers.push({ logId, color, points: latLngs, detail });
      }
    });

    return layers;
  }, [activeLogs, logState]);

  const handlePolylineClick = useCallback((logId: string) => {
    console.log('[App] Requesting trajectory preview', logId);
    setLastActivatedLog(logId);
    setIsPreviewOpen(true);
    previewRequestIdRef.current += 1;
    const requestId = previewRequestIdRef.current;
    setPreviewState({ logId, loading: true });

    fetchLogImage(logId)
      .then((url) => {
        if (previewRequestIdRef.current !== requestId) {
          URL.revokeObjectURL(url);
          return;
        }
        if (previewImageUrlRef.current) {
          URL.revokeObjectURL(previewImageUrlRef.current);
        }
        previewImageUrlRef.current = url;
        setPreviewState({ logId, imageUrl: url, loading: false });
      })
      .catch((err) => {
        if (previewRequestIdRef.current !== requestId) {
          return;
        }
        console.error('[App] Failed to load log preview', { logId, err });
        if (previewImageUrlRef.current) {
          URL.revokeObjectURL(previewImageUrlRef.current);
          previewImageUrlRef.current = null;
        }
        setPreviewState({
          logId,
          loading: false,
          error: err instanceof Error ? err.message : String(err),
        });
      });
  }, []);

  const closePreview = useCallback(() => {
    previewRequestIdRef.current += 1;
    if (previewImageUrlRef.current) {
      URL.revokeObjectURL(previewImageUrlRef.current);
      previewImageUrlRef.current = null;
    }
    setIsPreviewOpen(false);
    setPreviewState(null);
  }, []);

  const previewDetail = previewState?.logId
    ? logState.get(previewState.logId)?.detail
    : undefined;

  const shouldRenderTrajectories = currentZoom >= DISPLAY_ZOOM_THRESHOLD;

  useEffect(() => {
    if (!shouldRenderTrajectories) {
      setHoveredLogId(null);
    }
  }, [shouldRenderTrajectories]);

  const baseStatus = !shouldRenderTrajectories
    ? `Zoom to level ${DISPLAY_ZOOM_THRESHOLD}+ to show trajectories (current ${currentZoom.toFixed(1)})`
    : activeLogs.size === 0
      ? 'Select logs to display trajectories'
      : `${activeLogs.size} log layer(s) active`;
  const loadStatus =
    totalLogs !== null
      ? `Loaded ${logOrder.length}/${totalLogs} logs`
      : `Loaded ${logOrder.length} log${logOrder.length === 1 ? '' : 's'}`;
  const statusMessage = `${baseStatus} • ${loadStatus}`;

  return (
    <div className="map-root">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom
        whenCreated={(map) => {
          mapRef.current = map;
          setCurrentZoom(map.getZoom());
          setMapReady(true);
        }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
        />
        {/* New: focus controller that uses useMap() */}
        <FocusController lastActivatedLog={lastActivatedLog} logState={logState} />

        {shouldRenderTrajectories &&
          polylineData.map((layer) => {
            const isHovered = hoveredLogId === layer.logId;
            const color = isHovered ? HIGHLIGHT_COLOR : layer.color;
            return (
              <Fragment key={layer.logId}>
                <CircleMarker
                  center={layer.points[0]}
                  radius={6}
                  pathOptions={{
                    color,
                    fillColor: color,
                    fillOpacity: 1,
                    opacity: 1,
                    weight: 2,
                  }}
                  eventHandlers={{
                    mouseover: (event: LeafletEvent) => {
                      setHoveredLogId(layer.logId);
                      const target = event.target as unknown as { bringToFront?: () => void };
                      target?.bringToFront?.();
                    },
                    mouseout: () => {
                      setHoveredLogId((current) => (current === layer.logId ? null : current));
                    },
                    click: () => handlePolylineClick(layer.logId),
                  }}
                />
                <Polyline
                  positions={layer.points}
                  pathOptions={{
                    color,
                    weight: isHovered ? HIGHLIGHT_WEIGHT : DEFAULT_WEIGHT,
                    opacity: isHovered ? 1 : INACTIVE_OPACITY,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                  className={`trajectory-line${isHovered ? ' highlight' : ''}`}
                  eventHandlers={{
                    mouseover: (event: LeafletEvent) => {
                      setHoveredLogId(layer.logId);
                      const target = event.target as unknown as { bringToFront?: () => void };
                      target?.bringToFront?.();
                    },
                    mouseout: () => {
                      setHoveredLogId((current) => (current === layer.logId ? null : current));
                    },
                    click: () => handlePolylineClick(layer.logId),
                  }}
                >
                  {layer.detail && isHovered && (
                    <Tooltip sticky className="log-tooltip">
                      <div className="tooltip-content">
                        <div className="tooltip-title">{layer.logId}</div>
                        <div className="tooltip-row">Samples: {layer.detail.num_points}</div>
                        {layer.detail.bounds && (
                          <div className="tooltip-row">
                            Bounds: {layer.detail.bounds.min_lat.toFixed(4)}, {layer.detail.bounds.min_lon.toFixed(4)} → {layer.detail.bounds.max_lat.toFixed(4)}, {layer.detail.bounds.max_lon.toFixed(4)}
                          </div>
                        )}
                        <div className="tooltip-hint">Click to open image preview</div>
                      </div>
                    </Tooltip>
                  )}
                </Polyline>
              </Fragment>
            );
          })}
      </MapContainer>

      <div className={`control-panel ${panelOpen ? 'open' : 'collapsed'}`}>
        <button
          type="button"
          className="panel-toggle"
          onClick={() => setPanelOpen((prev) => !prev)}
        >
          {panelOpen ? 'Hide Logs' : 'Show Logs'}
        </button>

        {panelOpen && (
          <div className="panel-content">
            <h2>Driving Logs</h2>
            <div className="panel-summary">
              Loaded {logOrder.length}
              {totalLogs !== null ? ` / ${totalLogs}` : ''} log{(totalLogs ?? logOrder.length) === 1 ? '' : 's'}
            </div>
            {error && <div className="error-banner">{error}</div>}
            {!shouldRenderTrajectories && (
              <div className="panel-warning">
                Zoom to level {DISPLAY_ZOOM_THRESHOLD}+ to view trajectories (current {currentZoom.toFixed(1)})
              </div>
            )}
            {isLoadingSummaries ? (
              <p>Loading logs…</p>
            ) : (
              <div className="log-list">
                {logOrder.length === 0 && (
                  <div className="log-empty">No logs available</div>
                )}
                {logOrder.length > 0 && (
                  <label className="log-item">
                    <input
                      type="checkbox"
                      ref={selectAllRef}
                      checked={isAllSelected}
                      disabled={isLoadingSummaries || logOrder.length === 0}
                      onChange={(event) => {
                        const { checked: isChecked } = event.target;
                        console.log('[App] Toggle select all log layers', { enabled: isChecked });
                        if (isChecked) {
                          setActiveLogs(() => new Set<string>(allLogIds));
                        } else {
                          setActiveLogs(() => new Set<string>());
                          setLastActivatedLog(undefined);
                          setHoveredLogId(null);
                          closePreview();
                        }
                      }}
                    />
                    <div>
                      <div>Select Loaded</div>
                      <div className="log-metadata">Toggle all loaded log layers</div>
                    </div>
                  </label>
                )}
                {logOrder.map((logId) => {
                  const log = logState.get(logId);
                  if (!log) {
                    return null;
                  }
                  const checked = activeLogs.has(log.summary.log_id);
                  const sampleCount = log.detail?.num_points ?? log.summary.num_points;
                  return (
                    <label key={log.summary.log_id} className="log-item">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          const { checked: isChecked } = event.target;
                          console.log('[App] Toggle log layer', {
                            logId: log.summary.log_id,
                            enabled: isChecked,
                          });
                          setActiveLogs((prev) => {
                            const next = new Set(prev);
                            if (isChecked) {
                              next.add(log.summary.log_id);
                            } else {
                              next.delete(log.summary.log_id);
                            }
                            return next;
                          });
                          if (isChecked) {
                            setLastActivatedLog(log.summary.log_id);
                            console.log('[App] Enabled log layer via list', log.summary.log_id);
                          } else if (lastActivatedLog === log.summary.log_id) {
                            setLastActivatedLog(undefined);
                            console.log('[App] Disabled log layer via list', log.summary.log_id);
                          }
                          if (!isChecked) {
                            if (hoveredLogId === log.summary.log_id) {
                              setHoveredLogId(null);
                            }
                            if (previewState?.logId === log.summary.log_id) {
                              closePreview();
                            }
                          }
                        }}
                      />
                      <div>
                        <div>{log.summary.log_id}</div>
                        {sampleCount !== undefined && (
                          <div className="log-metadata">{sampleCount} samples</div>
                        )}
                        {log.loading && <div className="log-metadata">Loading trajectory…</div>}
                        {log.error && <div className="error-banner">{log.error}</div>}
                      </div>
                    </label>
                  );
                })}
                {nextOffset !== null && (
                  <button
                    type="button"
                    className="load-more-button"
                    onClick={() => {
                      if (nextOffset !== null && !isLoadingMore) {
                        void loadLogs(nextOffset);
                      }
                    }}
                    disabled={isLoadingMore}
                  >
                    {isLoadingMore
                      ? 'Loading more…'
                      : totalLogs !== null
                        ? `Load more logs (${logOrder.length}/${totalLogs})`
                        : 'Load more logs'}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className={`preview-panel ${isPreviewOpen ? 'open' : ''}`}>
        <div className="preview-header">
          <div className="preview-title">
            {previewState?.logId ? `Log ${previewState.logId}` : 'Log Preview'}
          </div>
          <button type="button" className="preview-close" onClick={closePreview}>
            ×
          </button>
        </div>
        <div className="preview-body">
          {previewState?.loading && <p>Loading image…</p>}
          {previewState?.error && !previewState.loading && (
            <div className="error-banner">{previewState.error}</div>
          )}
          {previewState?.imageUrl && !previewState.loading && !previewState.error && (
            <img
              src={previewState.imageUrl}
              alt={`Driving log ${previewState.logId}`}
              className="preview-image"
            />
          )}
          {previewDetail && (
            <div className="preview-meta">
              <div className="preview-meta-row">
                <span>Samples</span>
                <span>{previewDetail.num_points}</span>
              </div>
              {previewDetail.bounds && (
                <div className="preview-meta-row">
                  <span>Bounds</span>
                  <span>
                    {previewDetail.bounds.min_lat.toFixed(4)}, {previewDetail.bounds.min_lon.toFixed(4)} →
                    {' '}
                    {previewDetail.bounds.max_lat.toFixed(4)}, {previewDetail.bounds.max_lon.toFixed(4)}
                  </span>
                </div>
              )}
            </div>
          )}
          {!previewState && <p>Click a trajectory to view its image</p>}
        </div>
      </div>

      <div className="status-bar">{statusMessage}</div>
    </div>
  );
}

export default App;
