# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the working directory
COPY requirements.txt ./

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application source code into the container
COPY . .

# Expose the port Gradio runs on
EXPOSE 7860

# Define the command to run the application when the container starts
CMD ["python", "personal_db_assistant.py"]
