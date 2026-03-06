FROM node:20-slim

# Install Python and necessary build tools
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Set up a Python virtual environment to avoid pip conflicts
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set the working directory
WORKDIR /app

# Copy package files and install Node.js dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy Python requirements and install them
COPY lead-scraper/requirements.txt ./lead-scraper/
RUN pip install -r lead-scraper/requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables
ENV NODE_ENV=production
# Force the app to use the Python inside our virtual environment
ENV LEAD_SCRAPER_PYTHON="python"

# Build the Next.js application
RUN npm run build

# Expose the port Next.js uses
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
