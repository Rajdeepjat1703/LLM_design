from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import httpx
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
import json 

router = APIRouter(prefix="/customers", tags=["Customers"])
NODEJS_API_BASE = "http://localhost:5000/api/v1"  # Update with actual Node.js API URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017"  # Update with actual MongoDB URI
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.get_database("vypar")  # Update with actual database name

# Pydantic Schemas
class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str

class CustomerUpdate(BaseModel):
    
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gstNumber: Optional[str] = None
    outstandingBill: Optional[float] = None
    TotalBill: Optional[float] = None
    

# Fetch customer_id from MongoDB
async def get_customer_id(email: str):
    customer = await db.customers.find_one({"email": email})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return str(customer["_id"])

# Function to detect intent
def detect_intent(intent: str, data: Dict[str, Any]):
    if intent == "create_customer":
        return f"{NODEJS_API_BASE}/customer/customer-register", "POST", data
    elif intent == "update_customer":
        
        return f"{NODEJS_API_BASE}/customer/customer-register", "PUT", data
    elif intent == "delete_customer":
        return f"{NODEJS_API_BASE}/customer/customer-delete", "DELETE",data
    elif intent == "get_outstanding_bill":
        return f"{NODEJS_API_BASE}/customer/customer-outstanding", "GET",data
    elif intent == "get_total_bill":
        return f"{NODEJS_API_BASE}/customer/customer-totalBill", "GET", data
    else:
        raise HTTPException(status_code=400, detail=f"Invalid customer intent: {intent}")

async def handle_intent(intent: str, data: Dict[str, Any], token: str = Depends(oauth2_scheme)):
    if intent == "create_customer" and not all(k in data for k in ["name", "email", "phone"]):
        raise HTTPException(status_code=400, detail="Name, email, and phone are required for creating a customer")
    elif intent in ["update_customer", "delete_customer", "get_outstanding_bill", "get_total_bill"] and "customerId" not in data:
        if "email" in data:
            data["customerId"] = await get_customer_id(data["email"])
        else:
            raise HTTPException(status_code=400, detail="customerId or email is required")
    
    # For update_customer, ensure we're passing all the possible update fields
    if intent == "update_customer":
        # Keep all fields that are not None
        update_data = {k: v for k, v in data.items() if v is not None}
        # Make sure we're not losing any fields from the original data
        data = update_data
    
    url, method, payload = detect_intent(intent, data)
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                response = await client.post(url, json=payload, headers=headers)
            elif method == "PUT":
                print(f"Sending update request with payload: {payload}")
                response = await client.put(url, json=payload, headers=headers)
            elif method == "DELETE":
                if payload:
                    # Using the request method for DELETE with a JSON body
                    response = await client.request("DELETE", url, json=payload, headers=headers)
                else:
                    response = await client.delete(url, headers=headers)
            elif method == "GET":
                if payload:
                    response = await client.request("GET", url, json=payload, headers=headers)
                else:
                    response = await client.get(url, headers=headers)
            else:
                raise HTTPException(status_code=500, detail="Unsupported HTTP method")

            if response.status_code >= 400:
                error_detail = response.json() if response.headers.get("content-type") == "application/json" else response.text
                raise HTTPException(status_code=response.status_code, detail=error_detail)
            return response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"API request failed: {str(exc)}")