from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
import httpx
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
import json 
import os

router = APIRouter(prefix="/customers", tags=["Customers"])
NODEJS_API_BASE = "https://verce-ankurs-projects-b664b274.vercel.app/api/v1"  # Update with actual Node.js API URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://projectvaypar:Ankur@cluster0.vppsc.mongodb.net/")
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client.get_database("test")

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

# Fetch customer_id from name
async def get_customer_id_by_name(name: str):
    customer = await db.customers.find_one({"name": name})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return str(customer["_id"])

# Function to detect intent
def detect_intent(intent: str, data: Dict[str, Any]):
    if intent == "create_customer":
        print(NODEJS_API_BASE)
        return f"{NODEJS_API_BASE}/customer/customer-register", "POST", data
    elif intent == "update_customer":
        return f"{NODEJS_API_BASE}/customer/customer-register", "PUT", data
    elif intent == "delete_customer":
        return f"{NODEJS_API_BASE}/customer/customer-delete", "DELETE", data
    elif intent == "get_outstanding_bill":
        return f"{NODEJS_API_BASE}/customer/customer-outstanding", "GET", data
    elif intent == "get_total_bill":
        return f"{NODEJS_API_BASE}/customer/customer-totalBill", "GET", data
    elif intent == "get_customer_by_name" or intent == "get_customer_details":
        return f"{NODEJS_API_BASE}/dealer/get-by-name", "POST", data
    else:
        raise HTTPException(status_code=400, detail=f"Invalid customer intent: {intent}")

async def handle_intent(intent: str, data: Dict[str, Any], token: str):
    """
    Handle customer intents with improved error handling for missing fields
    """
    # For get_customer_details or get_customer_by_name with name but no customerId
    if (intent == "get_customer_details" or intent == "get_customer_by_name") and "customerId" not in data:
        if "name" in data:
            try:
                data["customerName"] = data["name"]  # Use name for the API endpoint
                # Some APIs might still need ID, so try to get it but don't fail if we can't
                try:
                    data["customerId"] = await get_customer_id_by_name(data["name"])
                except:
                    pass
            except Exception as e:
                pass
        elif "email" in data:
            try:
                data["customerId"] = await get_customer_id(data["email"])
            except Exception as e:
                pass
    
    # For update_customer, delete_customer, get_outstanding_bill, get_total_bill
    # Try to get customerId from email if customerId not provided
    elif intent in ["update_customer", "delete_customer", "get_outstanding_bill", "get_total_bill"] and "customerId" not in data:
        if "email" in data:
            try:
                data["customerId"] = await get_customer_id(data["email"])
            except Exception as e:
                pass
        elif "name" in data:
            try:
                data["customerId"] = await get_customer_id_by_name(data["name"])
            except Exception as e:
                pass
    
    # For update_customer, ensure we're passing all the possible update fields
    if intent == "update_customer":
        update_data = {k: v for k, v in data.items() if v is not None}
        data = update_data
    
    url, method, payload = detect_intent(intent, data)
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                print(f"Making POST request to: {url}")
                print(f"Request Headers: {headers}")
                print(f"Request Payload: {json.dumps(payload, indent=2)}")

                response = await client.post(url, json=payload, headers=headers)
            elif method == "PUT":
               
                
                response = await client.put(url, json=payload, headers=headers)
            elif method == "DELETE":
                if payload:
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
                return {
                    "status": "error",
                    "message": error_detail if isinstance(error_detail, str) else json.dumps(error_detail)
                }
            
            result = response.json()
            result["status"] = "success"
            return result
        except httpx.RequestError as exc:
            return {
                "status": "error",
                "message": f"API request failed: {str(exc)}"
            }
        

# Pydantic model for customer deletion by name
class CustomerDelete(BaseModel):
    name: str

# New endpoint to delete a customer using their name
@router.delete("/delete/by-name")
async def delete_customer_by_name(customer: CustomerDelete, token: str = Depends(oauth2_scheme)):
    # Convert the request body to a dictionary
    data = customer.dict()
    
    # Call the handle_intent function with the "delete_customer" intent.
    result = await handle_intent("delete_customer", data, token)
    
    # If deletion failed, raise an error with the message from the Node.js API
    if result.get("status") != "success":
        raise HTTPException(status_code=400, detail=result.get("message"))
    
    # Wrap the response in the desired format.
    # Here, we assume that result["data"] (or the entire result) contains the deleted customer's details.
    return {
        "statusCode": 200,
        "data": result.get("data", result),
        "message": "Customer deleted successfully",
        "success": True,
        "status": "success",
        "conversation_id": "67d232676e7a77a715d19330"
    }