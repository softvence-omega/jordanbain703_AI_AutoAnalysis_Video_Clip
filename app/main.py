from fastapi import FastAPI, Request
import uvicorn
from app.routes import router 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Reelty AI API",
    docs_url="/ai-api/v1",
)

# origins = [
#     "http://localhost:5173",  # frontend
#     "http://127.0.0.1:5173"
# ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL
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