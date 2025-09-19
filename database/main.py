from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def hello():
    return {"message": "Hello, this is another endpoint!"}

@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id, "info": "This is item details"}
