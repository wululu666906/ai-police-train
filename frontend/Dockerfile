FROM node:20-alpine AS build-stage

WORKDIR /app

ARG VITE_API_URL=/api
ARG VITE_SPEECH_PROVIDER=auto
ARG VITE_IFLYTEK_VAD_EOS=1600

ENV VITE_API_URL=$VITE_API_URL \
    VITE_SPEECH_PROVIDER=$VITE_SPEECH_PROVIDER \
    VITE_IFLYTEK_VAD_EOS=$VITE_IFLYTEK_VAD_EOS

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
