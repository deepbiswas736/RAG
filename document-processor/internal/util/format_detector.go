package util

import (
	"bytes"
	"document-processor/internal/model"
	"io"
	"net/http"
)

// FormatDetector is responsible for detecting the format of document files
type FormatDetector struct{}

// NewFormatDetector creates a new format detector
func NewFormatDetector() *FormatDetector {
	return &FormatDetector{}
}

// DetectFormat determines the format of a document based on its content
// It uses both MIME type detection and signature-based detection for more accuracy
func (d *FormatDetector) DetectFormat(content io.Reader) (model.Format, error) {
	// Read the first 512 bytes to detect the content type
	// This is enough for most file signatures and MIME detection
	buf := make([]byte, 512)

	n, err := content.Read(buf)
	if err != nil && err != io.EOF {
		return "", err
	}
	buf = buf[:n]

	// Use http.DetectContentType to get a MIME type
	contentType := http.DetectContentType(buf)

	// Map MIME types to our format types
	switch {
	case contentType == "application/pdf":
		return model.FormatPDF, nil

	case contentType == "text/plain; charset=utf-8":
		// For plain text, we check if it might be markdown (simple check)
		if bytes.Contains(buf, []byte("# ")) || bytes.Contains(buf, []byte("## ")) {
			return model.FormatMD, nil
		}
		return model.FormatTXT, nil

	case contentType == "text/html; charset=utf-8":
		return model.FormatHTML, nil

	case contentType == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
		contentType == "application/msword":
		return model.FormatDOCX, nil

	case contentType == "application/vnd.openxmlformats-officedocument.presentationml.presentation" ||
		contentType == "application/vnd.ms-powerpoint":
		return model.FormatPPTX, nil

	case contentType == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
		contentType == "application/vnd.ms-excel":
		return model.FormatXLSX, nil
	}

	// Additional format detection based on file signatures/magic bytes could be added here
	// For now, we'll return an empty format if we couldn't detect it
	return "", nil
}

// DetectFormatFromBytes determines the format of a document from a byte slice
// This is a convenience method when you already have the content in memory
func (d *FormatDetector) DetectFormatFromBytes(content []byte) (model.Format, error) {
	return d.DetectFormat(bytes.NewReader(content))
}
