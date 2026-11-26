FROM node:20-alpine AS base

WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install

# Copy application source
COPY . .

# Set environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Build Next.js application
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
