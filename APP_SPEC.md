# Project Specification: Full-Stack Data Storage Microservices

## Architecture Overview
Build a full-stack data storage application strictly using a microservices architecture. The system must include the following completely decoupled services:
1. **Frontend Service:** The user interface for interacting with the data.
2. **Backend Service:** The API layer responsible for business logic, data routing, and communicating with the database.
3. **Database Service:** The persistent storage layer for the application.

## Docker & Infrastructure Requirements
- **Multi-Stage Builds:** Every custom microservice (frontend and backend) MUST be containerized using strictly Docker multi-stage builds. 
- **Minimal Image Size:** You must prioritize the absolute smallest Docker image sizes possible. Use lightweight base images (like `alpine` or `distroless`) and ensure that zero build-time dependencies (like compilers or dev-dependencies) make it into the final production image stage.
- **Single-Command Startup:** You must generate a root-level `docker-compose.yml` file that orchestrates all three services (Frontend, Backend, Database). The configuration must ensure that the entire application, including network bridging and volume mounts, successfully boots up using exactly one command: `docker-compose up --build`.