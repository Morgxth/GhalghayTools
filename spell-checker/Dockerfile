# Stage 1: Build React frontend
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Spring Boot JAR (with frontend baked in)
FROM eclipse-temurin:25-jdk AS backend-build
WORKDIR /app
COPY . .
COPY --from=frontend-build /app/frontend/dist src/main/resources/static/
RUN chmod +x gradlew && ./gradlew bootJar --no-daemon -q

# Stage 3: Minimal runtime image
FROM eclipse-temurin:25-jre
WORKDIR /app
COPY --from=backend-build /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
