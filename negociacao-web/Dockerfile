FROM --platform=linux/amd64 node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_API_BASE=http://localhost:5006
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM --platform=linux/amd64 nginx:1.27
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
