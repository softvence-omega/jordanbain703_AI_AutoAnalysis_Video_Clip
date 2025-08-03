from fastapi import FastAPI, Request
import uvicorn
from app.routes import router 

app = FastAPI()

app.include_router(router)

@app.get("/")
def read_root():
    return {"message": "FastAPI is running ✅"}
        

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# 'projectId': 22510226