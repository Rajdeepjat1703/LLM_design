from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx

router = APIRouter(prefix="/products", tags=["Products"])
NODEJS_API_BASE = "http://localhost:5000/api/v1"  # Updated Node.js API URL

# Pydantic Schemas
class ProductCreate(BaseModel):
    name: str
    gstRate: float
    rate: float

class ProductUpdate(BaseModel):
    productId: str
    name: Optional[str] = None
    gstRate: Optional[float] = None
    rate: Optional[float] = None

# Function to detect intent
def detect_intent(intent: str, data: Dict[str, Any]):
    """
    Map product-related intents to appropriate API endpoints and HTTP methods
    """
    if intent == "create_product":
        return f"{NODEJS_API_BASE}/product/create-product", "POST", data
    
    elif intent == "update_product":
        return f"{NODEJS_API_BASE}/product/update-product", "PUT", data
    
    elif intent == "delete_product":
        product_id = data.get("productId")
        if not product_id:
            raise HTTPException(status_code=400, detail="productId is required for delete operation")
        return f"{NODEJS_API_BASE}/product/delete-product", "DELETE", {"productId": product_id}
    
    elif intent == "get_product_by_name":
        name = data.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="name is required to find a product")
        return f"{NODEJS_API_BASE}/product/get-by-name/find?name={name}", "GET", None
    
    elif intent == "get_all_products":
        return f"{NODEJS_API_BASE}/product/all", "GET", None
    
    else:
        raise HTTPException(status_code=400, detail=f"Invalid product intent: {intent}")


async def handle_intent(intent: str, data: Dict[str, Any]):
    """
    Process product-related intents with provided data and forward to Node.js API
    """
    # Validate data based on intent
    if intent == "create_product" and not all(k in data for k in ["name", "gstRate", "rate"]):
        raise HTTPException(status_code=400, detail="Name, gstRate, and rate are required for creating a product")
    
    elif intent == "update_product" and "productId" not in data:
        raise HTTPException(status_code=400, detail="productId is required for updating a product")
    
    # Get URL, method, and payload for the intent
    url, method, payload = detect_intent(intent, data)
    url = "http://localhost:5000/api/v1"
    
    # Make the API request
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                response = await client.post(url, json=payload)
            elif method == "PUT":
                response = await client.put(url, json=payload)
            elif method == "DELETE":
                response = await client.delete(url, params=payload)
            elif method == "GET":
                response = await client.get(url)
            else:
                raise HTTPException(status_code=500, detail="Unsupported HTTP method")
            
            # Check for errors in the response
            if response.status_code >= 400:
                error_detail = response.json() if response.headers.get("content-type") == "application/json" else response.text
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            
            # Return the response data
            return response.json()
            
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"API request failed: {str(exc)}")
