// Lazy-loaded (see App.tsx) so Leaflet's JS and CSS only download once a trip
// is selected. react-leaflet owns the Leaflet instance's lifecycle, including
// StrictMode's double mount, so Leaflet's direct DOM mutation stays contained.
import "leaflet/dist/leaflet.css";

import type { LatLngBoundsExpression, LatLngTuple } from "leaflet";
import { useEffect } from "react";
import {
  CircleMarker,
  MapContainer,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";

import type { Trip } from "../../lib/types";

interface RouteMapProps {
  trip: Trip;
}

export default function RouteMap({ trip }: RouteMapProps) {
  const origin: LatLngTuple = [trip.origin_lat, trip.origin_lon];
  const destination: LatLngTuple = [trip.destination_lat, trip.destination_lon];

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
        <FitBounds bounds={[origin, destination]} />
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
