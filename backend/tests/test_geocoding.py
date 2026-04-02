"""Unit tests for backend/app/geocoding.py pure helper functions.

No DB, no HTTP, no Playwright — all pure-function tests.
"""
import hashlib

import pytest

from app.geocoding import (
    assign_neighborhood,
    haversine_meters,
    make_dedup_fingerprint,
)


class TestAssignNeighborhood:
    def test_karmel_center(self):
        # Mid-point of כרמל bounding box
        assert assign_neighborhood(32.805, 34.995) == "כרמל"

    def test_merkaz_center(self):
        # Point clearly inside מרכז העיר (lng > 35.02 avoids כרמל overlap)
        assert assign_neighborhood(32.825, 35.025) == "מרכז העיר"

    def test_neve_shanan_center(self):
        # Mid-point of נווה שאנן bounding box
        assert assign_neighborhood(32.815, 35.035) == "נווה שאנן"

    def test_outside_all_boxes_returns_none(self):
        # Tel Aviv coords — outside all Haifa neighborhoods
        assert assign_neighborhood(32.07, 34.79) is None

    def test_zero_zero_returns_none(self):
        assert assign_neighborhood(0.0, 0.0) is None

    def test_boundary_inclusive_lower(self):
        # Exactly on lower lat/lng boundary of כרמל (should be included)
        assert assign_neighborhood(32.78, 34.97) == "כרמל"

    def test_boundary_inclusive_upper(self):
        # Exactly on upper lat/lng boundary of כרמל (should be included)
        assert assign_neighborhood(32.83, 35.02) == "כרמל"


class TestMakeDedupFingerprint:
    def test_returns_64_char_hex(self):
        fp = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic(self):
        fp1 = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        fp2 = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        assert fp1 == fp2

    def test_different_price_produces_different_fingerprint(self):
        fp1 = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        fp2 = make_dedup_fingerprint(3500, 3.0, 32.8191, 34.9998)
        assert fp1 != fp2

    def test_lat_rounded_to_4_decimal_places(self):
        # Coords differing only past 4 decimal places produce the same fingerprint
        fp1 = make_dedup_fingerprint(3000, 3.0, 32.81910001, 34.99980001)
        fp2 = make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998)
        assert fp1 == fp2

    def test_matches_expected_sha256(self):
        key = "3000:3.0:32.8191:34.9998"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert make_dedup_fingerprint(3000, 3.0, 32.8191, 34.9998) == expected


class TestHaversineMeters:
    def test_same_point_is_zero(self):
        assert haversine_meters(32.8191, 34.9998, 32.8191, 34.9998) == 0.0

    def test_known_distance_under_100m(self):
        # Two points ~50m apart
        dist = haversine_meters(32.8191, 34.9998, 32.8195, 35.0000)
        assert dist < 100

    def test_known_distance_over_100m(self):
        # Two points ~110m apart (per research verification)
        dist = haversine_meters(32.8191, 34.9998, 32.8200, 35.0003)
        assert dist > 100

    def test_symmetry(self):
        d1 = haversine_meters(32.8191, 34.9998, 32.8200, 35.0003)
        d2 = haversine_meters(32.8200, 35.0003, 32.8191, 34.9998)
        assert abs(d1 - d2) < 0.001  # floating point symmetry
