// Lazy-loaded (see App.tsx) so Leaflet's JS and CSS only download once a trip
// is selected. react-leaflet owns the Leaflet instance's lifecycle, including
// StrictMode's double mount, so Leaflet's direct DOM mutation stays contained.
import "leaflet/dist/leaflet.css";

import type { LatLngBoundsExpression, LatLngTuple } from "leaflet";
import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  Pane,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";

import type { ModeOption, TripInput } from "../../lib/types";
import { MODE_STYLES } from "../comparison/modes";

interface RouteMapProps {
  /** A saved trip, or an unsaved route being checked (no id). */
  trip: TripInput & { id?: number };
  /** Comparison options; one line is drawn per option with live geometry. */
  routes?: ModeOption[];
}

export default function RouteMap({ trip, routes = [] }: RouteMapProps) {
  const origin: LatLngTuple = [trip.origin_lat, trip.origin_lon];
  const destination: LatLngTuple = [trip.destination_lat, trip.destination_lon];
  // A line needs at least two points; anything shorter is skipped.
  const lines = routes.filter(
    (route): route is ModeOption & { geometry: [number, number][] } =>
      route.geometry !== null && route.geometry.length >= 2,
  );
  // Fit to the routes too: a detour (river, one-way loop) can leave the
  // start/destination box and would otherwise be clipped.
  const fitPoints: LatLngTuple[] = [
    origin,
    destination,
    ...lines.flatMap((l) => l.geometry),
  ];

  return (
    <section
      aria-label={`Map from ${trip.origin_address} to ${trip.destination_address}`}
      className="h-72 overflow-hidden rounded-lg border border-slate-200 md:h-96"
    >
      <MapContainer
        bounds={[origin, destination]}
        boundsOptions={{ padding: [40, 40] }}
        className="h-full w-full"
      >
        {/* OSM tile usage policy requires visible attribution. */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {lines.map((route) => (
          <Polyline
            key={`${trip.id ?? "unsaved"}-${route.mode}`}
            positions={route.geometry}
            pathOptions={{
              color: MODE_STYLES[route.mode].color,
              dashArray: MODE_STYLES[route.mode].dashArray,
              weight: 5,
              opacity: 0.8,
            }}
          >
            <Tooltip sticky>{MODE_STYLES[route.mode].label}</Tooltip>
          </Polyline>
        ))}
        {/* Own pane above overlayPane (z 400): route lines arrive after the
            markers, so render order alone would draw them over the markers. */}
        <Pane name="endpoints" style={{ zIndex: 450 }}>
          {/* CircleMarkers instead of default pins: Leaflet's pin images break under bundlers. */}
          <CircleMarker
            center={origin}
            radius={8}
            pathOptions={{ color: "#059669", fillOpacity: 0.9 }}
          >
            <Tooltip>Start: {trip.origin_address}</Tooltip>
          </CircleMarker>
          <CircleMarker
            center={destination}
            radius={8}
            pathOptions={{ color: "#dc2626", fillOpacity: 0.9 }}
          >
            <Tooltip>Destination: {trip.destination_address}</Tooltip>
          </CircleMarker>
        </Pane>
        <FitBounds bounds={fitPoints} />
      </MapContainer>
    </section>
  );
}

/** MapContainer only reads `bounds` on mount; refit when the selected trip changes. */
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap();
  const key = JSON.stringify(bounds);
  useEffect(() => {
    map.fitBounds(JSON.parse(key) as LatLngBoundsExpression, {
      padding: [40, 40],
    });
  }, [map, key]);
  return null;
}
