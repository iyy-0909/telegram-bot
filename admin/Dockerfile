FROM node:20-alpine AS admin-build

WORKDIR /app/admin

COPY admin/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY admin/ ./
RUN npm run build

FROM node:20-alpine AS mobile-build

WORKDIR /app/admin-mobile

COPY admin-mobile/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY admin-mobile/ ./
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=admin-build /app/admin/dist /usr/share/nginx/html
COPY --from=mobile-build /app/admin-mobile/dist /usr/share/nginx/html/mobile

EXPOSE 80
