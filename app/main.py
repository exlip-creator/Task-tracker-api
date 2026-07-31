import os
from fastapi import FastAPI, HTTPException, status, Depends
from contextlib import asynccontextmanager
from typing import List
from prometheus_fastapi_instrumentator import Instrumentator
import asyncpg
from dotenv import load_dotenv

from app.schemas import TaskCreate, Task

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

db_pool: asyncpg.Pool = None

instrumentator = Instrumentator(should_group_status_codes=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    instrumentator.expose(app, endpoint="/metrics", tags=["Infrastructure"])
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)

    yield

    if db_pool:
        await db_pool.close()

async def get_db():
    async with db_pool.acquire() as connection:
        yield connection

app = FastAPI(
    lifespan=lifespan,
    title="Task Tracker API",
    description="A simple API for task tracking with Prometheus instrumentation.",
    version="1.0.0"
)

instrumentator.instrument(app) 

@app.get("/tasks", response_model=List[Task], tags=["Tasks"])
async def get_tasks(db: asyncpg.Connection = Depends(get_db)):
    query = "SELECT id, title, description, completed FROM tasks ORDER BY id DESC;"
    rows = await db.fetch(query)
    return [dict(row) for row in rows]

@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
async def create_task(task_in: TaskCreate, db: asyncpg.Connection = Depends(get_db)):
    query = """
        INSERT INTO tasks (title, description) VALUES ($1, $2)
        RETURNING id, title, description, completed;
    """
    row = await db.fetchrow(query, task_in.title, task_in.description)
    return dict(row)

@app.patch("/tasks/{task_id}/complete", response_model=Task, tags=["Tasks"])
async def complete_task(task_id: int, db: asyncpg.Connection = Depends(get_db)):
    query = """
        UPDATE tasks
        SET completed = TRUE WHERE id = $1
        RETURNING id, title, description, completed;
    """
    row = await db.fetchrow(query, task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(row)

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Tasks"])
async def delete_task(task_id: int, db: asyncpg.Connection = Depends(get_db)):
    query = "DELETE FROM tasks WHERE id = $1 RETURNING id;"
    row = await db.fetchrow(query, task_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return None