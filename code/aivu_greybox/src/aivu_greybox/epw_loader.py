"""EPW (EnergyPlus Weather) file loader and 1-Hz interpolation.

The greybox test suite uses real Phoenix-July weather data instead of a
synthetic diurnal-sin proxy. This module reads an EPW file once and
provides slicing/interpolation utilities so any test can request a
48-hour (or shorter) window starting at any wall-clock hour.

EPW format reference: EnergyPlus Auxiliary Programs Documentation §2.9.
The relevant data columns for greybox:
  - [6]  dry-bulb temperature, °C
  - [7]  dew-point temperature, °C  (not currently consumed; could be used
         instead of RH for moisture state)
  - [8]  relative humidity, %
  - [9]  atmospheric pressure, Pa
  - [13] global horizontal solar radiation, Wh/m²
  - [21] wind speed, m/s

8,760 hourly rows for a full year (Jan 1 hour 1 through Dec 31 hour 24);
8,784 for a leap year (this 2024 AMY file is leap and has 8,760 — meaning
Feb 29 was filled or the file is non-leap-aligned; we don't depend on
calendar arithmetic, only on contiguous hourly records).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np


EPW_HEADER_LINES = 8

# Column indices in the comma-separated data rows
_COL_YEAR = 0
_COL_MONTH = 1
_COL_DAY = 2
_COL_HOUR = 3
_COL_T_DB = 6
_COL_T_DP = 7
_COL_RH = 8
_COL_P_ATM = 9
_COL_GHI = 13
_COL_WIND = 21


@dataclass(frozen=True)
class EPWHourlyData:
    """Hourly weather data from a parsed EPW file, plus the file's location
    metadata (latitude, longitude, elevation, atmospheric pressure default)."""

    location_name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    p_atm_default_pa: float  # the file's own header default (often the local sea-level adjusted value)

    # Per-hour arrays, length 8,760 for a typical year
    month: np.ndarray
    day: np.ndarray
    hour: np.ndarray  # 1..24 per EPW convention
    t_db_c: np.ndarray
    t_dp_c: np.ndarray
    rh_pct: np.ndarray
    p_atm_pa: np.ndarray
    ghi_w_per_m2: np.ndarray  # global horizontal irradiance (W/m² — EPW is Wh/m² but for hourly data that's numerically equivalent)
    wind_m_per_s: np.ndarray

    @property
    def num_hours(self) -> int:
        return self.t_db_c.shape[0]


def load_epw(epw_path: str | os.PathLike) -> EPWHourlyData:
    """Parse an EPW file. Reads the LOCATION header line for site metadata,
    then all hourly data rows."""
    with open(epw_path) as f:
        lines = f.readlines()

    # Parse LOCATION header
    loc_line = lines[0].strip()
    if not loc_line.startswith("LOCATION,"):
        raise ValueError(f"Expected LOCATION header on first line of {epw_path}")
    loc_fields = loc_line.split(",")
    # LOCATION,city,state,country,source,wmo,lat,lon,tz,elev
    location_name = loc_fields[1]
    latitude = float(loc_fields[6])
    longitude = float(loc_fields[7])
    elevation = float(loc_fields[9])

    # EPW header is 8 lines per spec; data starts at line 9 (index 8)
    data_lines = lines[EPW_HEADER_LINES:]

    n = len(data_lines)
    month = np.empty(n, dtype=np.int32)
    day = np.empty(n, dtype=np.int32)
    hour = np.empty(n, dtype=np.int32)
    t_db = np.empty(n)
    t_dp = np.empty(n)
    rh = np.empty(n)
    p_atm = np.empty(n)
    ghi = np.empty(n)
    wind = np.empty(n)

    for i, ln in enumerate(data_lines):
        fields = ln.split(",")
        month[i] = int(fields[_COL_MONTH])
        day[i] = int(fields[_COL_DAY])
        hour[i] = int(fields[_COL_HOUR])
        t_db[i] = float(fields[_COL_T_DB])
        t_dp[i] = float(fields[_COL_T_DP])
        rh[i] = float(fields[_COL_RH])
        p_atm[i] = float(fields[_COL_P_ATM])
        ghi[i] = float(fields[_COL_GHI])
        wind[i] = float(fields[_COL_WIND])

    # Use median P_atm (the EPW often varies P_atm slightly across hours)
    p_atm_default = float(np.median(p_atm))

    return EPWHourlyData(
        location_name=location_name,
        latitude_deg=latitude,
        longitude_deg=longitude,
        elevation_m=elevation,
        p_atm_default_pa=p_atm_default,
        month=month,
        day=day,
        hour=hour,
        t_db_c=t_db,
        t_dp_c=t_dp,
        rh_pct=rh,
        p_atm_pa=p_atm,
        ghi_w_per_m2=ghi,
        wind_m_per_s=wind,
    )


@dataclass(frozen=True)
class WeatherSlice1Hz:
    """A 1-Hz weather slice ready for forward-chain consumption.

    Same shape as `forward_chain.WeatherSeries` but with `start_*` metadata
    for traceability back to the source EPW hour.
    """

    monotonic_ns: np.ndarray
    t_outdoor_c: np.ndarray
    rh_outdoor_pct: np.ndarray
    solar_global_w_per_m2: np.ndarray
    wind_speed_m_per_s: np.ndarray
    p_atm_pa: np.ndarray  # interpolated to 1 Hz (mostly constant)

    start_month: int
    start_day: int
    start_hour: int  # 1..24 per EPW convention
    duration_seconds: int
    epw_location: str

    @property
    def n_samples(self) -> int:
        return self.t_outdoor_c.shape[0]


def slice_epw_to_1hz(
    epw: EPWHourlyData,
    start_month: int,
    start_day: int,
    start_hour: int,
    duration_hours: float,
    interpolation: str = "linear",
) -> WeatherSlice1Hz:
    """Slice the EPW data starting at (month, day, hour=start_hour) and
    extend for `duration_hours`, interpolated to 1-Hz cadence.

    EPW hour convention: hour 1 represents the period from 00:00 to 01:00,
    with the recorded value being end-of-hour (per EnergyPlus convention).
    For greybox we treat the EPW value as the value AT (hour - 1):00 local
    — i.e., row with hour=15 supplies the conditions at 14:00, the start
    of the 14:00-15:00 interval. This matches how envelope dynamics actually
    consume the input (instantaneous conditions, not period averages).

    Args:
        epw: parsed EPW data.
        start_month, start_day, start_hour: EPW row to start at (hour 1..24).
        duration_hours: window duration. Will be rounded up to the nearest
            hour for interpolation purposes.
        interpolation: 'linear' or 'hold' (zero-order hold of the start-of-hour
            value). 'linear' is the default — appropriate for smooth quantities
            like T and W; for solar GHI 'hold' may be more truthful but linear
            avoids step discontinuities in the forward-chain integration.

    Returns:
        WeatherSlice1Hz with 1-Hz arrays ready for forward-chain use.
    """
    if interpolation not in ("linear", "hold"):
        raise ValueError(f"interpolation must be 'linear' or 'hold', got {interpolation}")

    # Find the index of the start row
    matches = np.where(
        (epw.month == start_month)
        & (epw.day == start_day)
        & (epw.hour == start_hour)
    )[0]
    if matches.size == 0:
        raise ValueError(
            f"EPW file does not contain row for month={start_month}, "
            f"day={start_day}, hour={start_hour}"
        )
    start_idx = int(matches[0])

    n_hours_needed = int(np.ceil(duration_hours)) + 1  # +1 so we have endpoint for interpolation
    if start_idx + n_hours_needed > epw.num_hours:
        raise ValueError(
            f"EPW slice extends past end of file: start_idx={start_idx}, "
            f"need {n_hours_needed} hours, file has {epw.num_hours}"
        )

    # Hourly values at the start of each hour
    hourly_t = epw.t_db_c[start_idx : start_idx + n_hours_needed]
    hourly_rh = epw.rh_pct[start_idx : start_idx + n_hours_needed]
    hourly_ghi = epw.ghi_w_per_m2[start_idx : start_idx + n_hours_needed]
    hourly_wind = epw.wind_m_per_s[start_idx : start_idx + n_hours_needed]
    hourly_patm = epw.p_atm_pa[start_idx : start_idx + n_hours_needed]

    # Build 1-Hz target time grid in seconds
    n_seconds = int(duration_hours * 3600)
    t_seconds = np.arange(n_seconds, dtype=np.float64)

    # The interpolation x-axis: hour boundaries in seconds (0, 3600, 7200, ...)
    hour_seconds = np.arange(n_hours_needed, dtype=np.float64) * 3600.0

    if interpolation == "linear":
        t_1hz = np.interp(t_seconds, hour_seconds, hourly_t)
        rh_1hz = np.interp(t_seconds, hour_seconds, hourly_rh)
        ghi_1hz = np.interp(t_seconds, hour_seconds, hourly_ghi)
        wind_1hz = np.interp(t_seconds, hour_seconds, hourly_wind)
        patm_1hz = np.interp(t_seconds, hour_seconds, hourly_patm)
    else:  # 'hold'
        idx = np.minimum((t_seconds / 3600).astype(np.int64), n_hours_needed - 1)
        t_1hz = hourly_t[idx]
        rh_1hz = hourly_rh[idx]
        ghi_1hz = hourly_ghi[idx]
        wind_1hz = hourly_wind[idx]
        patm_1hz = hourly_patm[idx]

    monotonic_ns = (t_seconds * 1e9).astype(np.int64)

    return WeatherSlice1Hz(
        monotonic_ns=monotonic_ns,
        t_outdoor_c=t_1hz,
        rh_outdoor_pct=rh_1hz,
        solar_global_w_per_m2=ghi_1hz,
        wind_speed_m_per_s=wind_1hz,
        p_atm_pa=patm_1hz,
        start_month=start_month,
        start_day=start_day,
        start_hour=start_hour,
        duration_seconds=n_seconds,
        epw_location=epw.location_name,
    )


# ---------------------------------------------------------------------------
# Module-level cached load of the test-fixture Phoenix EPW
# ---------------------------------------------------------------------------


_CACHED_EPW: EPWHourlyData | None = None


def get_phoenix_2024_epw() -> EPWHourlyData:
    """Return the cached parsed Phoenix AMY 2024 EPW. Loads on first call.

    The EPW file is searched for in several locations in priority order:
      1. AIVU_PHOENIX_EPW_PATH environment variable, if set
      2. /mnt/user-data/uploads/Phoenix_AMY_2024.epw (the path it was
         uploaded to in the development session)
      3. tests/fixtures/Phoenix_AMY_2024.epw relative to this module
    """
    global _CACHED_EPW
    if _CACHED_EPW is not None:
        return _CACHED_EPW

    candidates: list[str] = []
    env_path = os.environ.get("AIVU_PHOENIX_EPW_PATH")
    if env_path:
        candidates.append(env_path)
    candidates.append("/mnt/user-data/uploads/Phoenix_AMY_2024.epw")
    # Relative-to-source fallback
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", "..", "tests", "fixtures", "Phoenix_AMY_2024.epw"))

    for path in candidates:
        if os.path.exists(path):
            _CACHED_EPW = load_epw(path)
            return _CACHED_EPW

    raise FileNotFoundError(
        "Phoenix EPW file not found. Set AIVU_PHOENIX_EPW_PATH or place "
        f"Phoenix_AMY_2024.epw at one of: {candidates}"
    )


def phoenix_july_slice(
    start_day: int = 15,
    start_hour: int = 1,
    duration_hours: float = 48.0,
) -> WeatherSlice1Hz:
    """Convenience: return a 1-Hz Phoenix-July slice from the AMY 2024 file.

    EPW hour convention: hours are numbered 1..24 within each day (NOT 0..23).
    Hour 1 represents the period from 00:00 to 01:00 local time, and is the
    first row of each day in the file. The default `start_hour=1` therefore
    means "start at midnight local time on `start_day`".

    Default: July 15 starting at midnight local, 48 hours long. The
    mid-month window avoids the calendar-month-boundary edge case while
    landing squarely in the high-cooling-load regime greybox is designed for.
    """
    epw = get_phoenix_2024_epw()
    return slice_epw_to_1hz(
        epw, start_month=7, start_day=start_day, start_hour=start_hour,
        duration_hours=duration_hours, interpolation="linear",
    )
