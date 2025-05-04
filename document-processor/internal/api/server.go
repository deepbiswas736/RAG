package api

import (
	"document-processor/internal/converter"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

// Service information
const (
	ServiceName    = "document-processor"
	ServiceVersion = "1.0.0"
)

// StartServer initializes and starts the HTTP server
func StartServer(port int, converterMgr *converter.ConverterManager, outputDir string) error {
	// Create a new server
	server := NewServer(converterMgr, outputDir)

	// Create a new router and register handlers
	mux := http.NewServeMux()

	// Register service discovery endpoints
	mux.HandleFunc("/health", server.HealthCheckHandler)
	mux.HandleFunc("/service-info", server.ServiceInfoHandler)

	// Register API endpoints
	mux.HandleFunc("/api/detect", server.DetectFormatHandler)
	mux.HandleFunc("/api/convert", server.ConvertToPDFHandler)

	// Create the HTTP server
	httpServer := &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      mux,
		ReadTimeout:  60 * time.Second,
		WriteTimeout: 300 * time.Second, // Allow for longer conversion times
		IdleTimeout:  120 * time.Second,
	}

	// Start the server
	log.Printf("Starting document-processor API server on port %d...\n", port)
	return httpServer.ListenAndServe()
}

// HealthCheckHandler returns the health status of the service
func (s *Server) HealthCheckHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"healthy"}`))
}

// ServiceInfoHandler returns information about this service for service discovery
func (s *Server) ServiceInfoHandler(w http.ResponseWriter, r *http.Request) {
	hostname, _ := os.Hostname()

	info := map[string]interface{}{
		"service":  ServiceName,
		"version":  ServiceVersion,
		"hostname": hostname,
		"endpoints": []string{
			"/api/detect",
			"/api/convert",
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	jsonResponse, _ := json.Marshal(info)
	w.Write(jsonResponse)
}
