package converter

import (
	"document-processor/internal/model"
	"fmt"
	"io"
)

// ConverterManager manages document converters and selects the appropriate one
// This is the "context" in the strategy pattern
type ConverterManager struct {
	converters []Converter
}

// NewConverterManager creates a new converter manager with the given converters
func NewConverterManager(converters ...Converter) *ConverterManager {
	return &ConverterManager{
		converters: converters,
	}
}

// RegisterConverter adds a new converter to the manager
func (m *ConverterManager) RegisterConverter(converter Converter) {
	m.converters = append(m.converters, converter)
}

// ConvertToPDF converts a document to PDF using the appropriate converter
func (m *ConverterManager) ConvertToPDF(document *model.Document, output io.Writer) error {
	// Find the appropriate converter for the document format
	for _, converter := range m.converters {
		if converter.CanConvert(document) {
			return converter.Convert(document, output)
		}
	}

	return fmt.Errorf("no converter found for format: %s", document.Format)
}

// CreateDefaultManager creates a converter manager with the default set of converters
func CreateDefaultManager() *ConverterManager {
	manager := NewConverterManager()

	// Register all available converters
	manager.RegisterConverter(NewDOCXConverter())
	manager.RegisterConverter(NewTXTConverter())
	manager.RegisterConverter(NewMDConverter())
	manager.RegisterConverter(NewPNGConverter())
	manager.RegisterConverter(NewJPEGConverter())
	// Add more converters as they are implemented

	return manager
}
