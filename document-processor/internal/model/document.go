// Package model contains data structures used in the document processor
package model

import (
	"io"
	"path/filepath"
	"time"
)

// Format represents supported document formats
type Format string

// Supported document formats
const (
	FormatDOCX Format = "docx"
	FormatPPTX Format = "pptx"
	FormatXLSX Format = "xlsx"
	FormatHTML Format = "html"
	FormatTXT  Format = "txt"
	FormatMD   Format = "md"
	FormatPDF  Format = "pdf"
)

// Document represents a document to be processed
type Document struct {
	// ID is a unique identifier for the document
	ID string

	// Name is the original filename
	Name string

	// Format is the document format (extension)
	Format Format

	// Content is a reader that provides access to the document content
	Content io.Reader

	// Size is the document size in bytes
	Size int64

	// CreatedAt is the time when the document was created
	CreatedAt time.Time
}

// NewDocument creates a new Document from the given parameters
func NewDocument(name string, content io.Reader, size int64) *Document {
	ext := filepath.Ext(name)
	if ext != "" {
		// Remove the leading dot from extension
		ext = ext[1:]
	}

	return &Document{
		ID:        generateID(),
		Name:      name,
		Format:    Format(ext),
		Content:   content,
		Size:      size,
		CreatedAt: time.Now(),
	}
}

// generateID generates a unique ID for a document
func generateID() string {
	// In a real application, you'd use a proper UUID library
	return time.Now().Format("20060102150405")
}
