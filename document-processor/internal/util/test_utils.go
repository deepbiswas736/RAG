package util

import (
	"document-processor/internal/model"
	"io"
	"strings"
)

// CreateTestDocument creates a test document with the given format and content
func CreateTestDocument(name string, format model.Format, content string) *model.Document {
	reader := strings.NewReader(content)
	return &model.Document{
		ID:      "test-doc",
		Name:    name,
		Format:  format,
		Content: reader,
		Size:    int64(len(content)),
	}
}

// CreateTestDocumentReader creates a document from a reader
func CreateTestDocumentReader(name string, format model.Format, content io.Reader, size int64) *model.Document {
	return &model.Document{
		ID:      "test-doc",
		Name:    name,
		Format:  format,
		Content: content,
		Size:    size,
	}
}
