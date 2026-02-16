# Build stage
FROM node:22 AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Optional: Add custom nginx configuration if needed for SPA routing (e.g. try_files)
# For now, default configuration should be sufficient for simple testing, 
# but for SPA routing (React Router) we usually need a custom conf.
# Since we don't have React Router yet, default is fine.
# If we encounter 404 on refresh, we'll add it.

EXPOSE 80

COPY nginx.conf /etc/nginx/conf.d/default.conf

CMD ["nginx", "-g", "daemon off;"]
