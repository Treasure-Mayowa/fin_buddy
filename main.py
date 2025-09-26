#!/usr/bin/env python3

"""Entry point for the app"""
import os
from app.main import app
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()
port = int(os.getenv("PORT", 8000))
environment = os.getenv("ENVIRONMENT", "development")
host = os.getenv("HOST", "0.0.0.0")

if __name__ == "__main__":
    import uvicorn
    # Disable reload in production
    reload_mode = environment == "development"
    uvicorn.run("main:app", host=host, port=port, reload=reload_mode)