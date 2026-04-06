from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from main import graph
from langchain_core.messages import HumanMessage

app = FastAPI()

class ChatRequest(BaseModel):
    text: str
    sender: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    config = {"configurable": {"thread_id": request.sender}}
    
    # 1. Provide the new input from WhatsApp
    input_data = {"messages": [HumanMessage(content=request.text)]}
    
    # 2. Invoke the graph. 
    # If it was interrupted, this 'input_data' acts as the answer it was waiting for.
    final_state = await graph.ainvoke(input_data, config)
    
    # 3. Get the message to send back
    ai_reply = final_state["messages"][-1].content
    print(ai_reply)

    return {"reply": ai_reply}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)