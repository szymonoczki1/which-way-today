from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.clients import transitous
from app.clients.transitous import decode_polyline

GET = "app.clients.transitous.httpx.get"
ZTM = "Zarząd Transportu Miejskiego w Gdańsku"


def _encode(points: list[tuple[float, float]], precision: int = 6) -> str:
    """Reference Google polyline encoder, to build realistic fixtures."""
    factor = 10**precision
    out, prev_lat, prev_lon = [], 0, 0
    for lat, lon in points:
        ilat, ilon = round(lat * factor), round(lon * factor)
        for delta in (ilat - prev_lat, ilon - prev_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)


def _leg(mode: str, start: str, end: str, points, **extra: object) -> dict:
    leg = {
        "mode": mode,
        "startTime": start,
        "endTime": end,
        "duration": (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds,
        "from": {"name": extra.pop("from_name", "A")},
        "to": {"name": extra.pop("to_name", "B")},
        "legGeometry": {"points": _encode(points), "precision": 6, "length": len(points)},
    }
    leg.update(extra)
    return leg


STATION = (54.3557, 18.6440)
STOP_A = (54.3560, 18.6450)
STOP_B = (54.3700, 18.6150)
UNI = (54.3713, 18.6123)


def _itinerary(start: str, end: str, legs: list[dict], transfers: int = 0) -> dict:
    return {
        "startTime": start,
        "endTime": end,
        "duration": (datetime.fromisoformat(end) - datetime.fromisoformat(start)).seconds,
        "transfers": transfers,
        "legs": legs,
    }


TRAM_TRIP = _itinerary(
    "2026-11-14T07:00:00Z",
    "2026-11-14T07:25:00Z",
    [
        _leg(
            "WALK",
            "2026-11-14T07:00:00Z",
            "2026-11-14T07:04:00Z",
            [STATION, STOP_A],
            distance=264.0,
            to_name="Dworzec Główny 01",
        ),
        _leg(
            "TRAM",
            "2026-11-14T07:04:00Z",
            "2026-11-14T07:15:00Z",
            [STOP_A, STOP_B],
            routeShortName="6",
            headsign="Jelitkowo",
            agencyName=ZTM,
            from_name="Dworzec Główny 01",
            to_name="Miszewskiego 01",
        ),
        _leg(
            "WALK",
            "2026-11-14T07:15:00Z",
            "2026-11-14T07:25:00Z",
            [STOP_B, UNI],
            distance=650.0,
            from_name="Miszewskiego 01",
        ),
    ],
)
# Leaves later but arrives first: should win over TRAM_TRIP.
FAST_TRIP = _itinerary(
    "2026-11-14T07:12:00Z",
    "2026-11-14T07:22:00Z",
    [
        _leg(
            "BUS",
            "2026-11-14T07:12:00Z",
            "2026-11-14T07:22:00Z",
            [STATION, UNI],
            routeShortName="168",
            headsign="Oliwa",
            agencyName=ZTM,
        ),
    ],
)


def _response(body: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://api.test"))


DEPART = datetime(2026, 11, 14, 7, 0, tzinfo=UTC)


def _plan():
    return transitous.plan(*STATION, *UNI, depart_at=DEPART)


class TestDecodePolyline:
    def test_google_reference_example_at_precision_5(self) -> None:
        # From Google's polyline algorithm documentation.
        points = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision=5)
        assert points == [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]

    def test_round_trips_precision_6(self) -> None:
        assert decode_polyline(_encode([STATION, UNI])) == [list(STATION), list(UNI)]

    def test_empty_string(self) -> None:
        assert decode_polyline("") == []


class TestPlan:
    @patch(GET)
    def test_maps_the_itinerary_into_legs(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response({"itineraries": [TRAM_TRIP], "direct": []})

        journey = _plan()

        assert journey is not None
        assert journey.duration_min == 25
        assert journey.transfers == 0
        assert [leg.mode for leg in journey.legs] == ["WALK", "TRAM", "WALK"]
        tram = journey.legs[1]
        assert (tram.line, tram.headsign, tram.agency) == ("6", "Jelitkowo", ZTM)
        assert (tram.from_name, tram.to_name) == ("Dworzec Główny 01", "Miszewskiego 01")
        assert tram.start_time == "2026-11-14T07:04:00Z"
        assert tram.geometry == [list(STOP_A), list(STOP_B)]
        # Walk legs carry a distance; ride legs are measured along their geometry.
        assert journey.legs[0].distance_km == pytest.approx(0.264)
        assert tram.distance_km == pytest.approx(2.6, abs=0.3)

    @patch(GET)
    def test_sends_coordinates_time_and_a_descriptive_user_agent(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response({"itineraries": [TRAM_TRIP]})

        _plan()

        url = mock_get.call_args.args[0]
        params = mock_get.call_args.kwargs["params"]
        headers = mock_get.call_args.kwargs["headers"]
        assert url == "https://api.transitous.org/api/v6/plan"
        assert params["fromPlace"] == "54.355700,18.644000"
        assert params["toPlace"] == "54.371300,18.612300"
        assert params["time"] == "2026-11-14T07:00:00Z"
        # All public transport modes (Transitous default), not just buses.
        assert "transitModes" not in params
        assert headers["User-Agent"].startswith("which-way-today")

    @patch(GET)
    def test_picks_the_itinerary_that_arrives_first(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response({"itineraries": [TRAM_TRIP, FAST_TRIP]})

        journey = _plan()

        assert journey is not None
        assert journey.legs[0].line == "168"

    @pytest.mark.parametrize(
        "body",
        [
            {"itineraries": []},  # no connection (e.g. middle of the night, rural)
            {"direct": []},
            {"itineraries": [{"legs": "nope"}]},
            ["not", "an", "object"],
        ],
    )
    @patch(GET)
    def test_returns_none_without_usable_itineraries(
        self, mock_get: MagicMock, body: object
    ) -> None:
        mock_get.return_value = _response(body)

        assert _plan() is None

    @patch(GET)
    def test_returns_none_on_http_error_timeout_or_non_json(self, mock_get: MagicMock) -> None:
        for outcome in (
            _response({"error": "x"}, status=429),
            httpx.ReadTimeout("slow"),
            httpx.Response(200, text="<html>", request=httpx.Request("GET", "https://api.test")),
        ):
            if isinstance(outcome, Exception):
                mock_get.side_effect, mock_get.return_value = outcome, None
            else:
                mock_get.side_effect, mock_get.return_value = None, outcome
            assert _plan() is None

    @patch(GET)
    def test_tolerates_missing_optional_leg_fields(self, mock_get: MagicMock) -> None:
        sparse = _leg(
            "REGIONAL_RAIL", "2026-11-14T07:00:00Z", "2026-11-14T07:20:00Z", [STATION, UNI]
        )
        del sparse["from"]["name"]
        mock_get.return_value = _response(
            {"itineraries": [_itinerary("2026-11-14T07:00:00Z", "2026-11-14T07:20:00Z", [sparse])]}
        )

        journey = _plan()

        assert journey is not None
        leg = journey.legs[0]
        assert leg.line is None and leg.agency is None and leg.headsign is None
        assert leg.from_name == ""


class TestRobustness:
    @patch(GET)
    def test_compares_arrival_instants_not_strings(self, mock_get: MagicMock) -> None:
        # 08:04+01:00 (= 07:04Z) arrives before 07:30Z, though it sorts after as text.
        early = {**FAST_TRIP, "endTime": "2026-11-14T08:04:00+01:00"}
        late = {**TRAM_TRIP, "endTime": "2026-11-14T07:30:00Z"}
        mock_get.return_value = _response({"itineraries": [late, early]})

        journey = _plan()

        assert journey is not None
        assert journey.legs[0].line == "168"
        # Times are normalised to UTC "Z" form for the API contract.
        assert journey.end_time == "2026-11-14T07:04:00Z"

    @pytest.mark.parametrize("points", ["_p~iF", "~~~~", "\x01\x01\x01\x01"])
    @patch(GET)
    def test_malformed_geometry_falls_back_instead_of_bad_numbers(
        self, mock_get: MagicMock, points: str
    ) -> None:
        bad = {**TRAM_TRIP["legs"][1], "legGeometry": {"points": points, "precision": 6}}
        trip = {**TRAM_TRIP, "legs": [TRAM_TRIP["legs"][0], bad, TRAM_TRIP["legs"][2]]}
        mock_get.return_value = _response({"itineraries": [trip]})

        assert _plan() is None

    @patch(GET)
    def test_unparseable_time_falls_back(self, mock_get: MagicMock) -> None:
        trip = {**TRAM_TRIP, "endTime": "soon"}
        mock_get.return_value = _response({"itineraries": [trip]})

        assert _plan() is None
