# Use a specific Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install the required packages
RUN pip install --no-cache-dir flask

# Make port 80 available to the world outside this container
EXPOSE 80

# Run add.py when the container launches
CMD ["python", "add.py"]
