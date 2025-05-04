package api

import (
	"bytes"
	"document-processor/internal/converter"
	"document-processor/internal/model"
	"document-processor/internal/util"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Server represents the API server
type Server struct {
	formatDetector *util.FormatDetector
	converterMgr   *converter.ConverterManager
	outputDir      string
}

// NewServer creates a new API server
func NewServer(converterMgr *converter.ConverterManager, outputDir string) *Server {
	// Create the output directory if it doesn't exist
	if outputDir != "" {
		os.MkdirAll(outputDir, 0755)
	}

	return &Server{
		formatDetector: util.NewFormatDetector(),
		converterMgr:   converterMgr,
		outputDir:      outputDir,
	}
}

// DetectFormatHandler handles requests to detect a file's format
func (s *Server) DetectFormatHandler(w http.ResponseWriter, r *http.Request) {
	// Only support POST method
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Maximum file size (10MB)
	r.Body = http.MaxBytesReader(w, r.Body, 10*1024*1024)

	// Parse the multipart form, 10MB max memory
	err := r.ParseMultipartForm(10 << 20)
	if err != nil {
		responseWithError(w, "Failed to parse form", err)
		return
	}

	// Get the file from form data
	file, _, err := r.FormFile("file")
	if err != nil {
		responseWithError(w, "Failed to get file from form", err)
		return
	}
	defer file.Close()

	// Buffer the first part of the file for format detection
	var buf bytes.Buffer
	tee := io.TeeReader(file, &buf)

	// Detect format
	format, err := s.formatDetector.DetectFormat(tee)
	if err != nil {
		responseWithError(w, "Failed to detect format", err)
		return
	}

	// Create the response
	response := DetectResponse{
		Success:    format != "",
		Format:     string(format),
		FormatName: FormatInfo[format],
	}

	if format == "" {
		response.Success = false
		response.Error = "Unknown format"
	}

	// Return JSON response
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// ConvertToPDFHandler handles requests to convert files to PDF
func (s *Server) ConvertToPDFHandler(w http.ResponseWriter, r *http.Request) {
	// Only support POST method
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Maximum file size (50MB)
	r.Body = http.MaxBytesReader(w, r.Body, 50*1024*1024)

	// Parse the multipart form, 10MB max memory (files larger than this will be stored on disk)
	err := r.ParseMultipartForm(10 << 20)
	if err != nil {
		responseWithError(w, "Failed to parse form", err)
		return
	}

	// Get the file from form data
	file, header, err := r.FormFile("file")
	if err != nil {
		responseWithError(w, "Failed to get file from form", err)
		return
	}
	defer file.Close()

	// Read the uploaded file content into memory
	fileBytes, err := io.ReadAll(file)
	if err != nil {
		responseWithError(w, "Failed to read file content", err)
		return
	}

	// Create a document from the uploaded file
	document := &model.Document{
		ID:        fmt.Sprintf("%d", time.Now().UnixNano()),
		Name:      header.Filename,
		Content:   bytes.NewReader(fileBytes),
		Size:      header.Size,
		CreatedAt: time.Now(),
	}

	// Detect the format if not provided
	if document.Format == "" {
		format, err := s.formatDetector.DetectFormatFromBytes(fileBytes)
		if err != nil {
			responseWithError(w, "Failed to detect format", err)
			return
		}
		document.Format = format
	}

	// Create a buffer for the PDF output
	var pdfBuf bytes.Buffer

	// Convert the document to PDF using the appropriate converter
	err = s.converterMgr.ConvertToPDF(document, &pdfBuf)
	if err != nil {
		responseWithError(w, "Failed to convert document to PDF", err)
		return
	}

	// Check if we should save to disk or stream back
	saveToFile := r.FormValue("save") == "true"

	var response ConversionResponse
	response.Success = true
	response.OriginalName = document.Name
	response.Format = string(document.Format)
	response.Size = int64(pdfBuf.Len())

	// Get the base filename without extension
	baseName := strings.TrimSuffix(document.Name, filepath.Ext(document.Name))
	pdfFileName := baseName + ".pdf"
	response.ResultName = pdfFileName

	if saveToFile && s.outputDir != "" {
		// Save the PDF to disk
		outputPath := filepath.Join(s.outputDir, pdfFileName)
		err = os.WriteFile(outputPath, pdfBuf.Bytes(), 0644)
		if err != nil {
			responseWithError(w, "Failed to save PDF file", err)
			return
		}
		response.Location = outputPath

		// Return JSON response
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	} else {
		// Stream the PDF back to the client
		w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", pdfFileName))
		w.Header().Set("Content-Type", "application/pdf")
		w.Header().Set("Content-Length", fmt.Sprintf("%d", pdfBuf.Len()))
		w.WriteHeader(http.StatusOK)

		// Write the PDF content
		_, err = pdfBuf.WriteTo(w)
		if err != nil {
			// We can't return an error to the client at this point
			fmt.Println("Error writing response:", err)
		}
	}
}

// Helper function to return an error response in JSON format
func responseWithError(w http.ResponseWriter, message string, err error) {
	errMsg := message
	if err != nil {
		errMsg = fmt.Sprintf("%s: %v", message, err)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusBadRequest)
	json.NewEncoder(w).Encode(map[string]string{
		"success": "false",
		"error":   errMsg,
	})
}
