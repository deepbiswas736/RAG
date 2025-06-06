# RAG Application Architecture

## Service Communication Architecture

This document explains the architecture of the RAG application's service communication pattern.

### Network Configuration

The application uses three distinct Docker networks:

1. **default**: The standard Docker network for basic connectivity
2. **internal_services**: A dedicated internal network for service-to-service communication
   - This network is marked as `internal: true` to isolate it from external access
   - Used for direct communication between services (UI → Query Service, etc.)
3. **rag_observability**: A specialized network for monitoring and observability services

### Service Discovery Approach

We use a hybrid approach for service discovery and communication:

#### External Access (Client Browser → Services)
- Uses Traefik as an API Gateway
- Traefik routes based on path prefixes (e.g., `/api/query` → query-service)
- Client-side code uses relative URLs with the `NEXT_PUBLIC_*` environment variables

#### Internal Access (Service → Service)
- Direct service-to-service communication over the `internal_services` network
- Services reference each other using their service names as hostnames
- Server-side code uses the `*_SERVICE_URL` environment variables (without NEXT_PUBLIC_)

### Environment Variables

The environment variables follow a consistent pattern:

1. **Client-side variables** (Browser JavaScript):
   - Prefixed with `NEXT_PUBLIC_`
   - Example: `NEXT_PUBLIC_QUERY_SERVICE_URL=/api/query`
   - These use relative paths that Traefik will route

2. **Server-side variables** (Next.js API routes):
   - No `NEXT_PUBLIC_` prefix
   - Example: `QUERY_SERVICE_URL=http://query-service:8003`
   - These use direct Docker network hostnames and ports

3. **Configuration flags**:
   - `USE_TRAEFIK_ROUTING`: Boolean controlling whether to use Traefik or direct communication

### Streaming Response Handling

For streaming responses (like from the query service), we use direct service-to-service communication instead of proxying through Traefik to ensure reliable streaming data delivery. This approach:

- Reduces latency
- Prevents buffering issues 
- Simplifies the network path for critical real-time data

### Port Mapping Strategy

In production:
- Only expose necessary ports to the host machine
- Consider removing direct port mappings where possible
- Use Traefik for all external access

For development:
- Direct port mappings are useful for debugging
- They allow direct access to services for testing

### Future Enhancements

Consider implementing:
1. Service registry for dynamic service discovery
2. Health checks for all services
3. Circuit breakers for resilient communication
4. Consistent logging and monitoring across all services
