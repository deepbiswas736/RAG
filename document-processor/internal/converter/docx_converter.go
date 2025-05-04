package converter

import (
	"document-processor/internal/model"
	"fmt"
	"io"
)

// DOCXConverter implements the Converter interface for DOCX files
type DOCXConverter struct{}

// NewDOCXConverter creates a new DOCX converter
func NewDOCXConverter() *DOCXConverter {
	return &DOCXConverter{}
}

// Convert converts a DOCX document to PDF
func (c *DOCXConverter) Convert(document *model.Document, output io.Writer) error {
	// In a real implementation, we would use a library like UniOffice, UniDoc, or call an external tool
	// This is a simplified placeholder implementation

	fmt.Println("Converting DOCX document to PDF:", document.Name)

	// Read the content from the document
	content, err := io.ReadAll(document.Content)
	if err != nil {
		return fmt.Errorf("failed to read DOCX content: %w", err)
	}

	// Here we would perform the actual conversion using a library
	// For now, we'll just write a placeholder message
	_, err = fmt.Fprintf(output, "PDF converted from DOCX document: %s\nOriginal size: %d bytes\nContent length: %d bytes\n",
		document.Name, document.Size, len(content))

	return err
}

// CanConvert checks if this converter can handle the given document
func (c *DOCXConverter) CanConvert(document *model.Document) bool {
	return document.Format == model.FormatDOCX
}
