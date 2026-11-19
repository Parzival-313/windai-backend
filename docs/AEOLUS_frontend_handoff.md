# AEOLUS backend handoff

**Purpose:** give the backend developer a starting contract for replacing the standalone demo's in-memory data and direct weather request with persistent, site-scoped services.

**Current UI source:** [`aeolus-wind-farm-digital-twin (1).html`](./aeolus-wind-farm-digital-twin%20%281%29.html)

## Executive summary

The current app is a single HTML file. Its `Store` is in-memory, it seeds five example sites at boot, and it calls Open-Meteo directly from the browser for a short-range forecast. There is no application API, authentication, durable site storage, historical wind dataset, annual energy model, wake-loss model, or climate-adjustment service.

The dashboard already has a site-specific 10-year AEP section, but its AEP values are placeholders. The backend must not populate them from the short-range forecast or copy values from the bundled Cox's Bazar sample report. The original PDF viewer can load a PDF from a URL or `Blob`; it does not generate an assessment.

## Current app behavior and data

### Site and turbine model

The frontend currently represents a site approximately as:

```json
{
  "id": "frontend-generated-id",
  "name": "Site name",
  "lat": 21.815,
  "lon": 91.86,
  "radius": 1600,
  "count": 10,
  "model": "g62",
  "layoutDir": 200,
  "layoutAligned": false,
  "turbines": [
    { "id": "T01", "lat": 21.81, "lon": 91.86, "manual": false, "outside": false }
  ]
}
```

| Field | Meaning / units |
| --- | --- |
| `lat`, `lon` | Site centre in WGS84 decimal degrees |
| `radius` | Screening boundary radius in metres; the UI draws a circular boundary |
| `count` | Requested turbine count |
| `model` | Generic model key: `g36`, `g45`, or `g62` |
| `layoutDir` | Layout alignment direction in degrees, conventionally wind-from |
| `turbines[]` | Generated or manually repositioned positions; turbine IDs such as `T01` |
| `manual` | Whether the position was moved by the user |
| `outside` | Derived by the frontend from site centre and radius; do not treat as trusted input |

Generic turbine classes in the frontend:

| Model key | Display class | Rated power | Rotor diameter | Hub height |
| --- | --- | ---: | ---: | ---: |
| `g36` | 3.6 MW class | 3600 kW | 120 m | 90 m |
| `g45` | 4.5 MW class | 4500 kW | 145 m | 105 m |
| `g62` | 6.2 MW class | 6200 kW | 170 m | 125 m |

These are screening-only generic curves, not vendor models. Do not treat them as procurement recommendations.

### Wind forecast

- Provider today: Open-Meteo forecast API, called directly by the browser.
- Request variables: hourly wind speed at 100 m, direction at 100 m, and speed at 10 m; speed units are m/s and timezone is GMT/UTC.
- The frontend requests three forecast days, then keeps up to 48 hourly samples starting around the current time.
- It stores timestamps plus parallel arrays (`s100`, `d100`, `s10`) and forecast-grid elevation.
- Hub-height speed is derived with the fixed power law `vHub = v100 * (hubHeight / 100)^0.143`.
- The current 48-hour mean power-curve result is gross and excludes wake/electrical losses. It is not annual AEP and cannot establish seasonality or P50/P75/P90.
- A manual wind override is a transient UI input. It is not a measured resource record.

### Persistence, sample data, and reports

- No `localStorage` or application persistence is present. Sites and edits are lost on reload.
- Five Bangladesh study sites are hard-coded at boot for demo use; these should become fixtures or be removed from production startup.
- Site IDs are generated in the browser today. The API should issue stable IDs.
- The Cox's Bazar PDF is only a bundled sample fallback for a matching site. It is not a data source for other sites.
- The viewer looks for a report URL on `site.reportPdfUrl`, `site.reportOutput.pdfUrl`, or `site.report.pdfUrl`; it also supports the optional `window.AEOLUS_REPORT_PIPELINE.resolvePdfUrl(site)` hook. Returned sources may be a URL/string, `Response`, `Blob`, or `{ url }`.
- When a PDF is absent, the UI shows an unavailable state. Keep that behavior rather than fabricating a report.

## Recommended implementation sequence

### Phase 1 — persisted sites and forecast service

1. Add authenticated, user-scoped site CRUD.
2. Move forecast retrieval behind the backend (or a provider adapter) so the browser does not own provider policy, secrets, caching, or rate limits.
3. Return a normalized forecast contract with explicit timestamps, units, source, and coverage.
4. Persist site configuration and user-moved turbine positions. Recompute derived layout flags server-side or mark them clearly as frontend-derived.
5. Add request/loading/error states in the UI and retry behavior for transient forecast failures.

### Phase 2 — assessed energy yield and PDF delivery

1. Ingest a site-specific long-term wind series, with source, period, resolution, hub-height handling, completeness, and quality metadata.
2. Integrate turbine performance and plant-loss models. Document the assumptions and model/version used.
3. Produce the annual exceedance distribution, year-by-year series, monthly profile, interannual variability, and loss bridge.
4. Expose a versioned assessment result and a generated PDF attached to that assessment.
5. Keep climate adjustment as a separate optional result, only after a validated site-relevant model and indices exist.

Do not block Phase 1 on Phase 2. Until Phase 2 has valid inputs, keep the AEP page explicitly unavailable.

## Suggested HTTP API

These routes are a proposal, not existing endpoints. Keep the final paths consistent with the backend team's conventions.

### Sites

```text
GET    /api/v1/sites
POST   /api/v1/sites
GET    /api/v1/sites/{siteId}
PATCH  /api/v1/sites/{siteId}
DELETE /api/v1/sites/{siteId}
```

The response should carry stable IDs, timestamps, and a revision/version for conflict handling. A response can retain the current flat field names initially to minimize frontend changes. Validate latitude/longitude ranges, positive radius, supported model keys, turbine count limits, unique turbine IDs, and user ownership.

Use partial updates for site name, coordinates, radius, count, turbine class, layout direction, and manual turbine positions. A location change should invalidate or refresh location-dependent forecast and assessment data. A model/count/layout change should invalidate derived capacity/yield values, not the underlying wind observations.

### Forecast

```text
GET /api/v1/sites/{siteId}/wind-forecast?hours=48
```

Suggested response:

```json
{
  "siteId": "stable-id",
  "provider": "provider-name",
  "retrievedAt": "2026-11-15T00:00:00Z",
  "validFrom": "2026-11-15T01:00:00Z",
  "validTo": "2026-11-17T00:00:00Z",
  "units": {
    "windSpeed": "m/s",
    "windDirection": "degrees_from_north",
    "elevation": "m"
  },
  "elevationM": 12,
  "hours": [
    {
      "time": "2026-11-15T01:00:00Z",
      "windSpeed100m": 8.2,
      "windDirection100m": 215,
      "windSpeed10m": 5.1
    }
  ]
}
```

The example is illustrative only, not a site reading. Return actual UTC ISO-8601 timestamps and source metadata. If the provider fails, return a non-2xx response with a structured error; do not return empty arrays shaped like a successful forecast.

### Assessment results

The UI needs a clear distinction between “not requested,” “processing,” “ready,” and “unavailable/failed.” Suggested endpoints:

```text
POST /api/v1/sites/{siteId}/assessments
GET  /api/v1/sites/{siteId}/assessments/{assessmentId}
GET  /api/v1/sites/{siteId}/assessments/latest
GET  /api/v1/sites/{siteId}/assessments/{assessmentId}/report.pdf
```

Suggested result shape:

```json
{
  "assessmentId": "stable-id",
  "siteId": "stable-id",
  "status": "ready",
  "generatedAt": "2026-11-15T00:00:00Z",
  "modelVersion": "energy-model-version",
  "coverage": {
    "windSource": "source-and-dataset",
    "periodStart": "2016-01-01",
    "periodEnd": "2025-12-31",
    "hubHeightM": 100,
    "completenessPct": 98.5
  },
  "energy": {
    "unit": "MWh/year",
    "grossAep": { "p50": null, "p75": null, "p90": null },
    "netAep": { "p50": null, "p75": null, "p90": null },
    "netCapacityFactor": null,
    "p90ToP50Ratio": null
  },
  "losses": {
    "wakePct": null,
    "electricalPct": null,
    "otherPct": null
  },
  "annualSeries": [
    { "year": 2020, "grossAepMWh": null, "netAepMWh": null }
  ],
  "monthlyProfile": [
    { "month": 1, "meanNetAepMWh": null, "annualSharePct": null }
  ],
  "variability": {
    "interannualStdDevPct": null,
    "bestYear": null,
    "worstYear": null
  },
  "assumptions": [],
  "limitations": [],
  "reportPdfUrl": "/api/v1/sites/stable-id/assessments/assessment-id/report.pdf"
}
```

The `null` values above are schema placeholders, not zeroes or usable results. In production, a `ready` assessment must have all required metrics for its declared scope. If input coverage or model limitations prevent a metric from being calculated, return a per-metric availability/reason or mark the assessment partial; never silently coerce missing values to zero.

### PDF delivery

Prefer a same-origin authenticated PDF endpoint, or a signed URL whose lifetime covers viewing and downloading. The viewer fetches PDFs through PDF.js, so CORS and authorization must work for that request; the download action also needs a valid PDF response. Set `Content-Type: application/pdf` and a useful `Content-Disposition` filename. Return a clear 404/409 state when no report exists or generation is still in progress.

## AEP definitions and required report content

The AEP view is intended to cover the assessment-report contents below:

- P50, P75, and P90 annual energy exceedance levels.
- Gross annual AEP, wake-loss deduction, net annual AEP, and net capacity factor.
- Interannual variability, best/worst years, and the P90-to-P50 ratio.
- A year-by-year annual energy record with a P50 reference.
- Monthly mean AEP, monthly share of annual production, and seasonal contribution.
- Data coverage, source, model/assumption versions, and limitations.

Use consistent definitions across UI and PDF. Recommended convention: Pxx is the annual energy level with xx% probability of exceedance, with the time period and uncertainty method stated. Define whether annual series are gross or net and keep the P50 reference on the same basis. Use MWh/year (or another explicitly documented unit) for energy and expose capacity factor as a fraction in JSON, converting to percent only for display.

Before calculating these results, the service needs, at minimum:

- A representative multi-year wind resource series or validated long-term correlated dataset, with timestamps, height, source, gap handling, and quality/completeness metadata.
- A site-specific hub-height adjustment or direct hub-height data; the current fixed shear exponent is only a demo assumption.
- A turbine-specific power curve or an explicitly selected generic curve and operating assumptions.
- Wake, electrical, availability, environmental, and other loss assumptions for net AEP.
- A documented uncertainty and interannual variability method.
- Monthly/yearly aggregation rules, units, model version, and reproducible calculation inputs.

The live short-range forecast and a manual override are not substitutes for these inputs.

## Integration and frontend notes

- The report dashboard is rendered by `renderAssessmentDashboard(site)` in the standalone file. Its AEP section is currently hard-coded as unavailable; it does not yet consume assessment JSON.
- Keep the dashboard's distinction between current site configuration and assessment results. Site edits should not overwrite historical assessment snapshots; create a new assessment version when model inputs change.
- Surface backend states explicitly: loading, ready, stale, unavailable, and error. Include a human-readable reason for unavailable AEP/PDF data.
- Scope every record and report to the authenticated user/tenant. Do not accept client-provided `outside`, capacity, or assessment results as trusted facts.
- Include rate limiting, provider caching, request IDs, audit logs for site/assessment changes, and server-side validation.
- Add contract tests for unit conversion, UTC timestamps, missing-data behavior, ownership checks, report authorization, and deterministic assessment inputs.

## Handoff checklist

- [ ] Confirm backend language/framework, database, auth provider, deployment target, and API versioning conventions.
- [ ] Replace boot-time demo sites with fixtures or authenticated site loading.
- [ ] Implement site CRUD and durable turbine/layout edits.
- [ ] Proxy/cache the short-range forecast and normalize timestamps/units.
- [ ] Add assessment status and result contracts before wiring AEP UI values.
- [ ] Agree on data sources and calculation methodology with the energy-yield domain owner.
- [ ] Generate and attach a per-site, per-assessment PDF; do not use the bundled sample as generated output.
- [ ] Test ownership, validation, provider failure, partial coverage, retries, and stale assessments end-to-end.
