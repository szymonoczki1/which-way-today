from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.clients import nominatim, open_meteo, osrm


def _response(
    status_code: int = 200, *, json: object = None, text: str | None = None
) -> httpx.Response:
    # Real httpx.Response objects so raise_for_status() and json() run for real
    # (a MagicMock can never produce a decode error).
    request = httpx.Request("GET", "https://upstream.test")
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json=json, request=request)


HTML_PAGE = "<html><body>Too many requests</body></html>"


class TestGeocode:
    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> Iterator[None]:
        nominatim._cache.clear()
        yield
        nominatim._cache.clear()

    @patch("app.clients.nominatim.httpx.get")
    def test_returns_coordinates_on_success(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(
            json=[{"lat": "54.35", "lon": "18.64", "display_name": "Gdansk, Poland"}]
        )

        result = nominatim.geocode("Gdansk")

        assert result is not None
        assert result.lat == 54.35
        assert result.lon == 18.64
        mock_get.assert_called_once()
        kwargs = mock_get.call_args.kwargs
        assert kwargs["headers"]["User-Agent"] == nominatim.USER_AGENT
        assert kwargs["headers"]["User-Agent"].startswith("which-way-today")
        assert kwargs["params"] == {"q": "Gdansk", "format": "json", "limit": 1}

    @patch("app.clients.nominatim.httpx.get")
    def test_returns_none_on_empty_results(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(json=[])

        assert nominatim.geocode("a place that does not exist anywhere xyz123") is None

    @patch("app.clients.nominatim.httpx.get")
    def test_returns_none_on_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.TimeoutException("timed out")

        assert nominatim.geocode("Gdansk") is None

    @pytest.mark.parametrize("status_code", [403, 429])
    @patch("app.clients.nominatim.httpx.get")
    def test_returns_none_when_blocked(self, mock_get: MagicMock, status_code: int) -> None:
        mock_get.return_value = _response(status_code, json={"error": "blocked"})

        assert nominatim.geocode("Gdansk") is None

    @patch("app.clients.nominatim.httpx.get")
    def test_returns_none_on_non_json_body(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(text=HTML_PAGE)

        assert nominatim.geocode("Gdansk") is None

    @pytest.mark.parametrize(
        "body",
        [
            {"error": "Unable to geocode"},
            [{"lat": "54.35", "lon": "18.64"}],  # missing display_name
            [{"lat": None, "lon": "18.64", "display_name": "x"}],
        ],
    )
    @patch("app.clients.nominatim.httpx.get")
    def test_returns_none_on_unexpected_shape(self, mock_get: MagicMock, body: object) -> None:
        mock_get.return_value = _response(json=body)

        assert nominatim.geocode("Gdansk") is None

    @patch("app.clients.nominatim.httpx.get")
    def test_caches_successful_lookups(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(
            json=[{"lat": "54.35", "lon": "18.64", "display_name": "Gdansk, Poland"}]
        )

        first = nominatim.geocode("Gdansk")
        second = nominatim.geocode("  gdansk ")

        assert first == second
        mock_get.assert_called_once()

    @patch("app.clients.nominatim.httpx.get")
    def test_does_not_cache_failures(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = [
            httpx.TimeoutException("timed out"),
            _response(json=[{"lat": "54.35", "lon": "18.64", "display_name": "Gdansk"}]),
        ]

        assert nominatim.geocode("Gdansk") is None
        assert nominatim.geocode("Gdansk") is not None
        assert mock_get.call_count == 2


OSRM_OK = {
    "code": "Ok",
    "routes": [
        {
            "distance": 1200.0,
            "duration": 900.0,
            "geometry": {"coordinates": [[18.64, 54.35], [18.61, 54.37]]},
        }
    ],
}


class TestRoute:
    @patch("app.clients.osrm.httpx.get")
    def test_returns_route_on_success(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(json=OSRM_OK)

        result = osrm.get_route(54.35, 18.64, 54.37, 18.61, "walking")

        assert result is not None
        assert result.distance_m == 1200.0
        assert result.duration_s == 900.0
        assert result.geometry[0] == [54.35, 18.64]  # flipped from OSRM's [lon, lat]

    @pytest.mark.parametrize(
        ("profile", "expected_prefix"),
        [
            # The project-osrm.org demo only serves the car profile; walking/cycling
            # must go to the FOSSGIS servers or they silently return car routes.
            ("driving", "https://router.project-osrm.org/route/v1/driving/"),
            ("walking", "https://routing.openstreetmap.de/routed-foot/route/v1/driving/"),
            ("cycling", "https://routing.openstreetmap.de/routed-bike/route/v1/driving/"),
        ],
    )
    @patch("app.clients.osrm.httpx.get")
    def test_uses_server_matching_profile_with_lon_lat_order(
        self, mock_get: MagicMock, profile: osrm.OsrmProfile, expected_prefix: str
    ) -> None:
        mock_get.return_value = _response(json=OSRM_OK)

        osrm.get_route(54.35, 18.64, 54.37, 18.61, profile)

        url = mock_get.call_args.args[0]
        assert url == expected_prefix + "18.640000,54.350000;18.610000,54.370000"

    @patch("app.clients.osrm.httpx.get")
    def test_formats_tiny_coordinates_without_scientific_notation(
        self, mock_get: MagicMock
    ) -> None:
        mock_get.return_value = _response(json=OSRM_OK)

        osrm.get_route(0.00001, 0.00001, 1.0, 1.0, "driving")

        url = mock_get.call_args.args[0]
        assert "e-" not in url
        assert url.endswith("/0.000010,0.000010;1.000000,1.000000")

    @patch("app.clients.osrm.httpx.get")
    def test_returns_none_when_no_route_found(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(json={"code": "NoRoute", "routes": []})

        assert osrm.get_route(0.0, 0.0, 0.0, 0.0, "walking") is None

    @patch("app.clients.osrm.httpx.get")
    def test_returns_none_on_connect_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.ConnectError("connection failed")

        assert osrm.get_route(54.35, 18.64, 54.37, 18.61, "driving") is None

    @patch("app.clients.osrm.httpx.get")
    def test_returns_none_on_server_error(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(400, json={"code": "InvalidQuery"})

        assert osrm.get_route(54.35, 18.64, 54.37, 18.61, "driving") is None

    @patch("app.clients.osrm.httpx.get")
    def test_returns_none_on_non_json_body(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(text=HTML_PAGE)

        assert osrm.get_route(54.35, 18.64, 54.37, 18.61, "driving") is None

    @pytest.mark.parametrize("missing_key", ["distance", "duration", "geometry"])
    @patch("app.clients.osrm.httpx.get")
    def test_returns_none_on_route_missing_key(self, mock_get: MagicMock, missing_key: str) -> None:
        route = {k: v for k, v in OSRM_OK["routes"][0].items() if k != missing_key}
        mock_get.return_value = _response(json={"code": "Ok", "routes": [route]})

        assert osrm.get_route(54.35, 18.64, 54.37, 18.61, "driving") is None


WEATHER_OK = {
    "current": {
        "temperature_2m": 5.0,
        "precipitation": 2.0,
        "wind_speed_10m": 20.0,
        "weather_code": 61,
    }
}


class TestWeather:
    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_weather_on_success(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(json=WEATHER_OK)

        result = open_meteo.get_current_weather(54.35, 18.64)

        assert result is not None
        assert result.weather_code == 61
        assert result.wind_speed_kmh == 20.0

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_server_error(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(500, json={})

        assert open_meteo.get_current_weather(54.35, 18.64) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.TimeoutException("timed out")

        assert open_meteo.get_current_weather(54.35, 18.64) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_non_json_body(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(text=HTML_PAGE)

        assert open_meteo.get_current_weather(54.35, 18.64) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_without_current_block(self, mock_get: MagicMock) -> None:
        mock_get.return_value = _response(json={"latitude": 54.35})

        assert open_meteo.get_current_weather(54.35, 18.64) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_null_values(self, mock_get: MagicMock) -> None:
        body = {"current": {**WEATHER_OK["current"], "temperature_2m": None}}
        mock_get.return_value = _response(json=body)

        assert open_meteo.get_current_weather(54.35, 18.64) is None


@pytest.mark.parametrize("module", [nominatim, osrm, open_meteo])
def test_connect_timeout_is_shorter_than_read_timeout(module: object) -> None:
    timeout = module.TIMEOUT  # type: ignore[attr-defined]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect is not None and timeout.read is not None
    assert timeout.connect < timeout.read
