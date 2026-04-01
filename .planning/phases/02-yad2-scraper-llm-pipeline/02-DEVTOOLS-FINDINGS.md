# Yad2 DevTools Findings

**Date:** 2026-04-02
**Source:** Browser DevTools inspection of yad2.co.il/realestate/rent

## Feed Endpoint

**Status:** HYPOTHESIS — not directly confirmed from Network tab.

Hypothesis URL: `https://gw.yad2.co.il/feed-search/realestate/rent`

User captured `gw.yad2.co.il` requests but not the specific feed endpoint path.
Decision: use hypothesis URL at build time and verify empirically when the scraper runs.

## Haifa City Code

**Status:** CONFIRMED

`city_code = 4000` — confirmed from `media-params` response: `"CityID": "4000"`

## Neighborhood Filtering

**Status:** CONFIRMED (partial)

The Yad2 API supports the `neighborhood=` query parameter.

| Neighborhood | API Code | Source |
|---|---|---|
| כרמל (Carmel) | 609 | Confirmed from `media-params` request `?neighborhood=609` |
| מרכז העיר (Downtown) | Unknown | Not captured in this session |
| נווה שאנן (Neve Shanan) | Unknown | Not captured in this session |

### Filtering Strategy

- **כרמל:** Pass `neighborhood=609` as API query parameter (API-level filter).
- **מרכז העיר and נווה שאנן:** Apply post-scrape filter on `address.neighborhood.text` field
  using `settings.yad2_neighborhoods` list. This matches the text value returned in the
  listing's address object.

## Response Shape

**Status:** CONFIRMED (from recommendations endpoint)

Listings are in a `data[0][n]` array. Each listing object contains:

| Field | Path | Type |
|---|---|---|
| Unique ID | `token` | string |
| Price | `price` | integer |
| Rooms | `additionalDetails.roomsCount` | float |
| Size | `additionalDetails.squareMeter` | integer |
| City ID | `address.city.id` | string |
| City name | `address.city.text` | string (Hebrew) |
| Neighborhood ID | `address.neighborhood.id` | string |
| Neighborhood name | `address.neighborhood.text` | string (Hebrew) |
| Street | `address.street.text` | string (Hebrew) |
| Latitude | `address.coords.lat` | float |
| Longitude | `address.coords.lon` | float |
| Description | `metaData.description` | string (Hebrew) |
| Cover image | `metaData.coverImage` | string (URL) |
| Created at | `dates.createdAt` | string (ISO 8601) |
| Updated at | `dates.updatedAt` | string (ISO 8601) |
| Search text | `searchText` | string (Hebrew, full-text) |

## Authentication

**Status:** CONFIRMED required

The API responds with a `guest_token` JWT in cookies. The `guest_token` cookie must be
included in all API requests.

Plan 02 scraper must either:
1. Obtain the `guest_token` cookie via a first HTTP request (browser or httpx), then pass
   it to subsequent feed requests, OR
2. Use Playwright to drive the browser, which will automatically maintain the cookie session.

## Summary for Plan 02

```
yad2_api_base_url = "https://gw.yad2.co.il/feed-search/realestate/rent"  # verify at runtime
yad2_city_code    = "4000"    # confirmed
yad2_neighborhood_id_carmel = 609  # confirmed

neighborhood filter strategy:
  כרמל           → API param: neighborhood=609
  מרכז העיר      → post-scrape: address.neighborhood.text contains "מרכז העיר"
  נווה שאנן      → post-scrape: address.neighborhood.text contains "נווה שאנן"

auth: include guest_token cookie in all API requests
```
