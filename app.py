from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Adding middlware to solve the CORS problem for me
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.wakili.me/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def greet_json():
    return {"Hello": "World!"}
