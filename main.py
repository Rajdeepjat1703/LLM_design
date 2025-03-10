import os
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from typing import Dict, Any, List, Optional
from customer import router as customer_router, detect_intent as customer_detect_intent, handle_intent as customer_handle_intent
from product import router as product_router
from sales import router as sales_router
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.human import HumanMessage
from pydantic import BaseModel
import json
import re
from fastapi.security import OAuth2PasswordBearer

app = FastAPI(title="Vypar app")

# Load API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Include the specific routers
app.include_router(customer_router)
app.include_router(product_router)
app.include_router(sales_router)

class IntentRequest(BaseModel):
    user_query: str
    
class DetectedIntent(BaseModel):
    category: str
    intent: str
    data: Dict[str, Any]

def get_intent_from_ai_agent(query: str):
    """
    Use the LLM to determine the category, intent, and extract relevant data from user query
    """
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    
    system_prompt = """
    You are an AI assistant that detects intents from user queries and extracts relevant data.
    Your task is to categorize the user's request into one of three categories: 'customer', 'product', or 'sales'.
    
    For each category, determine the specific intent:
    
    For 'customer' category:
    - create_customer: Create a new customer (requires name, email, phone)
    - update_customer: Update customer details (requires customerId and at least one field to update)
    - delete_customer: Delete a customer (requires customerId)
    - get_outstanding_bill: Get customer's outstanding bill (requires customerId)
    - get_total_bill: Get customer's total bill (requires customerId)
    
    For 'product' category:
    - create_product: Create a new product (requires name, gstRate, rate)
    - update_product: Update product details (requires productId and at least one field to update)
    - delete_product: Delete a product (requires productId)
    - get_product_by_name: Get product by name (requires name)
    
    For 'sales' category:
    - create_sale: Create a new sale (requires customerId, products array, paymentMethod, optional amountPaid)
    - generate_invoice: Generate an invoice (requires saleId, recipientEmail)
    
    Extract all relevant data for the detected intent.
    Respond with a JSON object containing 'category', 'intent', and 'data' fields.
    """
    
    agent = create_react_agent(model=llm, tools=[], state_modifier=system_prompt)
    
    messages = [HumanMessage(content=query)]
    state = {"messages": messages}
    
    response = agent.invoke(state)
    ai_messages = [message for message in response.get("messages", []) if isinstance(message, AIMessage)]
    
    if not ai_messages:
        raise HTTPException(status_code=500, detail="Failed to process intent with AI")
    
    try:
        response_content = ai_messages[-1].content
        json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
        json_str = json_match.group(1) if json_match else response_content
        json_str = re.sub(r'^[^{]*({.*})[^}]*$', r'\1', json_str, flags=re.DOTALL)
        intent_data = json.loads(json_str)
        return intent_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse intent from AI response: {str(e)}")

# Helper function to extract token from Authorization header
async def get_token_from_authorization(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    return parts[1]

@app.post("/process-query")
async def process_natural_language_query(
    request: IntentRequest,
    token: str = Depends(get_token_from_authorization)
):
    """
    Process a natural language query to determine intent and action
    """
    intent_data = get_intent_from_ai_agent(request.user_query)
    
    if not all(k in intent_data for k in ["category", "intent", "data"]):
        raise HTTPException(status_code=500, detail="Invalid intent format from AI")
    
    category = intent_data["category"]
    intent = intent_data["intent"]
    data = intent_data["data"]
    
    if category == "customer":
        return await customer_handle_intent(intent, data, token)
    elif category == "product":
        return await product_router.handle_intent(intent, data, token)
    elif category == "sales":
        return await sales_router.handle_intent(intent, data, token)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

@app.post("/intent")
async def handle_intent(
    category: str, 
    intent: str, 
    data: Dict[str, Any],
    token: str = Depends(oauth2_scheme)
):
    """
    Main intent handler that routes to the appropriate category module
    """
    if category == "customer":
        return await customer_handle_intent(intent, data, token)
    elif category == "product":
        return await product_router.handle_intent(intent, data, token)
    elif category == "sales":
        return await sales_router.handle_intent(intent, data, token)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)