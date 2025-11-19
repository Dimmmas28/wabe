from pydantic import BaseModel, Field, HttpUrl


class Task(BaseModel):
    """Model for Mind2Web task definition"""

    task_id: str = Field(
        description="Unique identifier for each task",
        examples=["mind2web_001", "task_wikipedia_search"],
    )
    website: HttpUrl = Field(
        description="Website URL",
        examples=["https://www.wikipedia.org", "https://www.amazon.com"],
    )
    confirmed_task: str = Field(
        description="Task description",
        examples=[
            "Search for 'Albert Einstein' on Wikipedia and verify the article appears"
        ],
    )
    reference_length: int = Field(
        ge=1,
        description="Number of steps required for a human annotator to complete the task",
        examples=[5, 10, 15],
    )
    level: str = Field(
        description="Difficulty level of the task",
        examples=["easy", "medium", "hard"],
    )
