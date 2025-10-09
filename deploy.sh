#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Build and start the Docker containers
echo -e "${GREEN}Building and starting Docker containers...${NC}"
sudo docker compose up -d --build

# Step 2: Check the status of the containers
echo -e "${GREEN}Checking container status...${NC}"
sudo docker compose ps

# Step 3: Display logs for the API service
echo -e "${GREEN}Displaying logs for the API service...${NC}"
sudo docker compose logs api

# Step 4: Run database migrations (if applicable)
echo -e "${GREEN}Running database migrations...${NC}"
# Uncomment and modify the following line if migrations are needed
sudo docker compose exec api python manage.py migrate

# Step 5: Verify MongoDB initialization
echo -e "${GREEN}Verifying MongoDB initialization...${NC}"
sudo docker compose exec mongo mongo --eval "db.getSiblingDB('oxossi').getCollectionNames()"

# Step 6: Notify the user of successful deployment
echo -e "${GREEN}Deployment completed successfully!${NC}"
