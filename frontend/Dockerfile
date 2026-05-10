FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Use .template so envsubst can substitute $BACKEND_URL at container start
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template

EXPOSE 80

# envsubst replaces ${BACKEND_URL} in the nginx config at startup.
# Default falls back to Docker Compose service name (local dev).
# In production set: BACKEND_URL=https://datagenie-zvt6.onrender.com
ENV BACKEND_URL=http://backend:8000

# Only substitute the BACKEND_URL variable; leave nginx's own $uri/$host etc. untouched.
CMD ["/bin/sh", "-c", "envsubst '${BACKEND_URL}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
