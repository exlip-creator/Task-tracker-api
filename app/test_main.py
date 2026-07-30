import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app, TASKS_DB

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def clear_tasks_db():
    TASKS_DB.clear()
    yield

def is_valid_uuid(uuid_to_test, version=4):
    try:
        uuid_obj = uuid.UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return str(uuid_obj) == uuid_to_test

def test_all_methods_tasks(client):
    # 1.Make sure the tasks database is empty
    response = client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []

    # 2.Create a new task
    task_data = {"title": "Test Task", "description": "This is a test."}
    response = client.post("/tasks", json=task_data)
    assert response.status_code == 201

    data = response.json()

    # 3.Check the response data
    assert is_valid_uuid(data["id"])
    assert data["title"] == "Test Task"
    assert data["description"] == "This is a test."
    assert data["completed"] is False

    # 4.Check that the task is now in the database
    response = client.get("/tasks")
    assert len(response.json()) == 1

    # 5.Complete the task
    response = client.patch(f"/tasks/{data['id']}/complete")
    assert response.json()["completed"] is True

    # 6.Delete the task
    response = client.delete(f"/tasks/{data['id']}")
    assert response.status_code == 204


def test_prometheus_metrics(client):
    # Check that the metrics endpoint is available  
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text