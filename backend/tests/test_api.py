async def test_health_endpoint(client):
    """GET /api/health returns HTTP 200 with {status: ok}."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
