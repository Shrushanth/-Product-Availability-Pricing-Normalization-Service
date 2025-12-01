from fastapi import FastAPI
import uvicorn

from config import settings

app = FastAPI(title=" Product Availability & Pricing Normalization Service")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )