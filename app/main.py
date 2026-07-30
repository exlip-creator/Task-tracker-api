from fastapi import FastAPI, HTTPException, status
from typing import List
from prometheus_fastapi_instrumentator import Instrumentator
from uuid import uuid4

from app.schemas import TaskCreate, Task

app = FastAPI(
    title="Task Tracker API",
    description="A simple API for task tracking with Prometheus instrumentation.",
    version="1.0.0"
)

instrumentator = Instrumentator(
    should_group_status_codes=False,
)
instrumentator.instrument(app)

@app.on_event("startup")
async def startup_event():
    instrumentator.expose(app, endpoint="/metrics", tags=["Infrastructure"])

TASKS_DB: List[Task] = []

@app.get("/tasks", response_model=List[Task], tags=["Tasks"])
async def get_tasks():
    return TASKS_DB

@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_task(task_in: TaskCreate):
    current_id = str(uuid4())
    new_task = Task(
        id=current_id,
        title=task_in.title,
        description=task_in.description,
        completed=False
    )

    TASKS_DB.append(new_task)
    return new_task

@app.patch("/tasks/{task_id}/complete", response_model=Task, tags=["Tasks"])
async def complete_task(task_id: str):
    for task in TASKS_DB:
        if task.id == task_id:
            task.completed = True
            return task
        
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
async def delete_task(task_id: str):
    for task in TASKS_DB:
        if task.id == task_id:
            TASKS_DB.remove(task)
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")