# ─── Stage 1: Build frontend ───────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Сначала только package.json — используем кэш слоёв Docker
COPY frontend/package*.json ./
RUN npm ci

# Копируем исходники и собираем production build
COPY frontend/ ./
RUN npm run build
# dist/ содержит index.html, assets/, manifest.webmanifest, sw.js


# ─── Stage 2: Build backend ─────────────────────────────────────────────────
FROM eclipse-temurin:21-jdk-alpine AS backend-builder
WORKDIR /app

# Gradle wrapper + зависимости (кэшируются пока build.gradle не изменился)
COPY gradlew .
COPY gradle gradle
COPY build.gradle .
COPY settings.gradle .
RUN chmod +x gradlew && ./gradlew dependencies --no-daemon

# Исходники бэкенда
COPY src src

# Вкладываем собранный фронтенд в static-ресурсы Spring Boot
# Spring автоматически раздаёт всё из resources/static/
COPY --from=frontend-builder /app/dist src/main/resources/static/

RUN ./gradlew bootJar --no-daemon -x test


# ─── Stage 3: Runtime ───────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=backend-builder /app/build/libs/*.jar app.jar
EXPOSE 8080
# -Djava.net.preferIPv6Addresses=true нужен для Fly.io private networking (.flycast/.internal — IPv6)
ENTRYPOINT ["java", "-Xmx400m", "-jar", "app.jar"]
