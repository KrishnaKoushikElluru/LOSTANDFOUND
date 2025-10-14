#!/bin/bash
# Oracle Cloud Always Free deployment script

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv git

# Clone repository
git clone https://github.com/kumarason2030/LOSTANDFOUND.git
cd LOSTANDFOUND
git checkout feature/ml-integration

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install PM2 for process management
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g pm2

# Start the application with PM2
pm2 start "uvicorn src.api:app --host 0.0.0.0 --port 8000" --name "lostnfound-api"
pm2 startup
pm2 save

echo "Backend deployed successfully!"
echo "Access your API at: http://YOUR_ORACLE_CLOUD_IP:8000"
