# ClipForge AI — static frontend build served by nginx.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . ./
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Proxy /api to the backend service so the browser stays same-origin.
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
