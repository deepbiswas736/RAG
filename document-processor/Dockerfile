FROM golang:1.20-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Copy source files
COPY cmd/ ./cmd/
COPY internal/ ./internal/

# Build the application
RUN go build -o document-processor ./cmd/app

# Final stage
FROM alpine:latest

WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/document-processor .

# Create output directory
RUN mkdir -p /output

# Set environment variables
ENV OUTPUT_DIR=/output

# Expose the port
EXPOSE 8081

# Run the application
CMD ["./document-processor"]
