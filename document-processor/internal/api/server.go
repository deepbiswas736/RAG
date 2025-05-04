package api

import (
	"document-processor/internal/converter"
	"fmt"
	"net/http"
	"time"
)

// StartServer initializes and starts the HTTP server
func StartServer(port int, converterMgr *converter.ConverterManager, outputDir string) error {
	// Create a new server
	server := NewServer(converterMgr, outputDir)

	// Create a new router and register handlers
	mux := http.NewServeMux()

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
	fmt.Printf("Starting API server on port %d...\n", port)
	return httpServer.ListenAndServe()
}
