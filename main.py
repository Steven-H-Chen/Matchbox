from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root() -> dict[str, str]:
    """
    Health-check endpoint.
    Visiting http://127.0.0.1:8000/ should return: {"status": "up"}
    """
    return {"status": "up"}
