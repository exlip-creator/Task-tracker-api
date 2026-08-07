import os
import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from dotenv import load_dotenv

from app.main import app, get_db

load_dotenv()
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DATABASE_URL)
    yield pool
    await pool.close()

@pytest.fixture(autouse=True)
async def set_up_db(db_pool):
    async with db_pool.acquire() as connection:
        await connection.execute("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE;")
    yield

@pytest.fixture
async def client(db_pool):
    async def override_get_db():
        async with db_pool.acquire() as connection:
            yield connection

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()

async def test_all_methods_tasks(client):
    # 1.Make sure the tasks database is empty
    response = await client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []

    # 2.Create a new task
    task_data = {"title": "Test Task", "description": "This is a test."}
    response = await client.post("/tasks", json=task_data)
    assert response.status_code == 201

    data = response.json()

    # 3.Check the response data
    assert data["id"] == 1
    assert data["title"] == "Test Task"
    assert data["description"] == "This is a test."
    assert data["completed"] is False

    # 4.Check that the task is now in the database
    response = await client.get("/tasks")
    assert len(response.json()) == 1

    # 5.Complete the task
    response = await client.patch(f"/tasks/{data['id']}/complete")
    assert response.json()["completed"] is True

    # 6.Delete the task
    response = await client.delete(f"/tasks/{data['id']}")
    assert response.status_code == 204

async def test_many_tasks(client):
    new_tasks = [
        {"title": f"Title {i}", "description": f"Description {i}"}
        for i in range(1, 101)
    ]

    for task in new_tasks:
        respones = await client.post("/tasks", json=task)
        assert respones.status_code == 201

    respones = await client.get("/tasks")
    assert respones.status_code == 200
    data = respones.json()
    assert len(data) == 100

    assert "Title 2" in data
    assert "Title 33" in data
    assert "Title 78" in data
    assert "Title 90" in data

async def test_prometheus_metrics(client):
    # Check that the metrics endpoint is available  
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text