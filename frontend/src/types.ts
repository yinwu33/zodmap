export interface BoundingBox {
  min_lat: number;
  min_lon: number;
  max_lat: number;
  max_lon: number;
}

export interface TrajectoryPoint {
  lat: number;
  lon: number;
}

export interface DrivingLogListItem {
  log_id: string;
  num_points?: number;
  bounds?: BoundingBox;
}

export interface DrivingLogDetail extends DrivingLogListItem {
  trajectory: TrajectoryPoint[];
}
