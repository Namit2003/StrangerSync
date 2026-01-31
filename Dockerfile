# Use a lightweight Python version
FROM python:3.11-slim

# Set the folder inside the container
WORKDIR /app

# 1. Install Dependencies
# We copy requirements.txt first to use Docker caching (faster builds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy the Application Code
# Copy the 'app' folder
COPY app ./app
# Copy the 'static' folder
COPY static ./static

# 3. Network Setup
# Expose port 8000 to the outside world
EXPOSE 8000

# 4. Start Command
# "0.0.0.0" is required for Docker to listen to external requests
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]