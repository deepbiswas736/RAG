package converter

import (
	"document-processor/internal/model"
	"fmt"
	"io"
)

// MDConverter implements the Converter interface for Markdown files
type MDConverter struct{}

// NewMDConverter creates a new Markdown converter
func NewMDConverter() *MDConverter {
	return &MDConverter{}
}

// Convert converts a Markdown document to PDF
func (c *MDConverter) Convert(document *model.Document, output io.Writer) error {
	fmt.Println("Converting Markdown document to PDF:", document.Name)

	// Read the content from the document
	content, err := io.ReadAll(document.Content)
	if err != nil {
		return fmt.Errorf("failed to read Markdown content: %w", err)
	}

	// In a real implementation, we would:
	// 1. Parse the markdown to HTML
	// 2. Convert HTML to PDF using a library like wkhtmltopdf or similar
	// For now, we'll just write a placeholder message
	_, err = fmt.Fprintf(output, "PDF converted from Markdown document: %s\nOriginal size: %d bytes\nContent length: %d bytes\n",
		document.Name, document.Size, len(content))

	return err
}

// CanConvert checks if this converter can handle the given document
func (c *MDConverter) CanConvert(document *model.Document) bool {
	return document.Format == model.FormatMD
}
