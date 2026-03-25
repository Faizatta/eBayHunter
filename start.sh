#!/bin/bash
# Go to backend folder
cd backend

# Restore dependencies
dotnet restore

# Run the backend
dotnet run --urls=http://0.0.0.0:$PORT