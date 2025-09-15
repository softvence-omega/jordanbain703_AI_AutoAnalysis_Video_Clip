from fastapi import FastAPI, Request
import uvicorn
from app.routes import router 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Reelty AI API",
    docs_url="/ai-api/v1",
)

origins = [
    "http://65.49.81.27:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "FastAPI is running ✅"}
        

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# 'projectId': 22510226