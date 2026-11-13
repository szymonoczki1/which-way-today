import { describe, expect, it } from "vitest";

import {
  formatClock,
  formatDeparture,
  formatCo2,
  formatCost,
  formatDistance,
  formatDuration,
  describeWeather,
} from "./format";

describe("formatDuration", () => {
  it.each([
    [0, "0 min"],
    [0.4, "1 min"], // never show "0 min" for a real, non-zero trip
    [5.3, "5 min"],
    [59.6, "1 h"],
    [60, "1 h"],
    [65, "1 h 5 min"],
    [125.2, "2 h 5 min"],
  ])("%s min -> %s", (minutes, expected) => {
    expect(formatDuration(minutes)).toBe(expected);
  });
});

describe("formatCost", () => {
  it.each([
    [0, "Free"],
    [null, "Varies"], // unknown: depends on operator / ticket
    [1.21, "1.21 zł"],
    [4.8, "4.80 zł"],
  ])("%s -> %s", (pln, expected) => {
    expect(formatCost(pln)).toBe(expected);
  });
});

describe("formatCo2", () => {
  it.each([
    [0, "0 g"],
    [161, "161 g"],
    [999, "999 g"],
    [1000, "1.0 kg"],
    [2456, "2.5 kg"],
  ])("%s g -> %s", (grams, expected) => {
    expect(formatCo2(grams)).toBe(expected);
  });
});

describe("formatDistance", () => {
  it.each([
    [0, "0 km"],
    [0.04, "<0.1 km"], // don't show "0 km" next to "1 min"
    [0.35, "0.4 km"],
    [2.68, "2.7 km"],
    [12.04, "12 km"],
  ])("%s km -> %s", (km, expected) => {
    expect(formatDistance(km)).toBe(expected);
  });
});

describe("describeWeather", () => {
  it("labels known WMO codes", () => {
    expect(describeWeather(0).label).toBe("Clear sky");
    expect(describeWeather(61).label).toMatch(/rain/i);
    expect(describeWeather(80).label).toMatch(/shower/i);
    expect(describeWeather(95).label).toMatch(/thunder/i);
  });

  it("falls back for unknown codes instead of crashing", () => {
    expect(describeWeather(1234).label).toBe("Unknown conditions");
  });
});

describe("formatClock", () => {
  it("shows Gdańsk local time for a UTC timestamp (winter and summer)", () => {
    expect(formatClock("2026-11-14T07:04:00Z")).toBe("08:04");
    expect(formatClock("2026-07-01T06:30:00Z")).toBe("08:30");
  });
});

describe("formatDeparture", () => {
  const now = new Date("2026-11-14T22:30:00Z"); // 23:30 in Gdańsk, Sat 14 Nov

  it("shows just the time for a departure later today", () => {
    expect(formatDeparture("2026-11-14T22:45:00Z", now)).toBe("23:45");
  });

  it("says tomorrow for an early-morning departure the next day", () => {
    expect(formatDeparture("2026-11-15T03:30:00Z", now)).toBe("04:30 tomorrow");
  });

  it("names the day when it's further out", () => {
    expect(formatDeparture("2026-11-16T07:00:00Z", now)).toBe("08:00 on Mon");
  });

  it("uses Gdańsk dates, not UTC dates", () => {
    // 23:30 UTC on the 14th is already 00:30 on the 15th in Gdańsk.
    const lateUtc = new Date("2026-11-14T23:30:00Z");
    expect(formatDeparture("2026-11-15T07:00:00Z", lateUtc)).toBe("08:00");
  });
});
