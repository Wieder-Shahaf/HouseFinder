async def test_health_endpoint(client):
    """GET /api/health returns HTTP 200 with status ok and scrapers dict."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "scrapers" in data
    assert "yad2" in data["scrapers"]
    yad2 = data["scrapers"]["yad2"]
    assert "last_run" in yad2
    assert "listings_inserted" in yad2
    assert "success" in yad2
