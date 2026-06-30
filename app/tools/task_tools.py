from datetime import datetime
from typing import List, Dict, Any
from langchain_core.tools import tool
from app.db.session import get_db
from app.db.models import Task

@tool
def add_task(description: str, source: str = "manual") -> Dict[str, Any]:
    """Adds a new task to the personal task list.
    
    Args:
        description: Description of the task.
        source: The source of the task, e.g. "email:<thread_id>" or "manual".
        
    Returns:
        The created task object as a dictionary.
    """
    try:
        with get_db() as db:
            task = Task(
                description=description,
                source=source,
                status="open",
                created_at=datetime.utcnow()
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task.to_dict()
    except Exception as e:
        return {"error": f"Failed to add task: {str(e)}"}

@tool
def list_tasks(status: str = "open") -> List[Dict[str, Any]]:
    """Lists tasks matching the specified status.
    
    Args:
        status: The task status to filter by, e.g. "open" or "completed".
        
    Returns:
        A list of task dictionary objects.
    """
    try:
        with get_db() as db:
            tasks = db.query(Task).filter(Task.status == status).all()
            return [t.to_dict() for t in tasks]
    except Exception as e:
        return [{"error": f"Failed to list tasks: {str(e)}"}]

@tool
def complete_task(task_id: int) -> Dict[str, Any]:
    """Marks a task as completed in the personal task list.
    
    Args:
        task_id: The ID of the task to complete.
        
    Returns:
        A status dictionary.
    """
    try:
        with get_db() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return {"error": f"Task with ID {task_id} not found."}
            
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(task)
            return {
                "status": "completed",
                "task": task.to_dict()
            }
    except Exception as e:
        return {"error": f"Failed to complete task: {str(e)}"}
