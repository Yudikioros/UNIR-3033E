# Use a lightweight Node.js image
FROM node:20-alpine

# Set the working directory
WORKDIR /app

# Copy dependency files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy the rest of the source code
COPY . .

# Expose the Next.js port
EXPOSE 3000

# Start the application in development mode
CMD ["npm", "run", "dev"]