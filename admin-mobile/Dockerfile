FROM node:20-alpine AS build

WORKDIR /app/admin-mobile

COPY admin-mobile/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY admin-mobile/ ./
COPY frontend-shared/ /app/frontend-shared/
RUN npm run build

FROM nginx:alpine

COPY admin-mobile/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/admin-mobile/dist /usr/share/nginx/html

EXPOSE 80
