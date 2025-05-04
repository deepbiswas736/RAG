package converter

import (
	"document-processor/internal/model"
	"fmt"
	"io"
)

// TXTConverter implements the Converter interface for plain text files
type TXTConverter struct{}

// NewTXTConverter creates a new TXT converter
func NewTXTConverter() *TXTConverter {
	return &TXTConverter{}
}

// Convert converts a text document to PDF
func (c *TXTConverter) Convert(document *model.Document, output io.Writer) error {
	fmt.Println("Converting TXT document to PDF:", document.Name)

	// Read the content from the document
	content, err := io.ReadAll(document.Content)
	if err != nil {
		return fmt.Errorf("failed to read TXT content: %w", err)
	}

	// In a real implementation, we would format the text and generate a PDF
	// For now, we'll just write a placeholder message
	_, err = fmt.Fprintf(output, "PDF converted from text document: %s\nOriginal size: %d bytes\nContent length: %d bytes\n",
		document.Name, document.Size, len(content))

	return err
}

// CanConvert checks if this converter can handle the given document
func (c *TXTConverter) CanConvert(document *model.Document) bool {
	return document.Format == model.FormatTXT
}
