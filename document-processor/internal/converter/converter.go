// Package converter contains the strategies for converting different file formats to PDF
package converter

import (
	"document-processor/internal/model"
	"io"
)

// Converter defines the interface for converting documents to PDF
// This follows the Strategy Pattern where different implementations handle specific file formats
type Converter interface {
	// Convert converts a document to PDF and writes the result to the given writer
	Convert(document *model.Document, output io.Writer) error

	// CanConvert checks if this converter can handle the given document format
	CanConvert(document *model.Document) bool
}

