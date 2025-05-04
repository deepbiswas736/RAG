package converter

import (
	"document-processor/internal/model"
	"document-processor/internal/util"
	"fmt"
	_ "image/jpeg" // Register JPEG decoder
	"io"
	"math"
	"os"
	"path/filepath"
	"strings"

	"github.com/jung-kurt/gofpdf"
)

// JPEGConverter implements the Converter interface for JPEG/JPG image files
type JPEGConverter struct{}

// NewJPEGConverter creates a new JPEG/JPG converter
func NewJPEGConverter() *JPEGConverter {
	return &JPEGConverter{}
}

// Convert converts a JPEG/JPG image to PDF
func (c *JPEGConverter) Convert(document *model.Document, output io.Writer) error {
	fmt.Println("Converting JPEG/JPG image to PDF:", document.Name)

	// Read the content from the document
	content, err := io.ReadAll(document.Content)
	if err != nil {
		return fmt.Errorf("failed to read JPEG/JPG content: %w", err)
	}

	// Create a new PDF document
	pdf := gofpdf.New("P", "mm", "A4", "")
	pdf.AddPage()

	// Determine file extension
	ext := ".jpg"
	if strings.EqualFold(string(document.Format), "jpeg") {
		ext = ".jpeg"
	}

	// Create a temporary file for the image data
	tempFile := filepath.Join(os.TempDir(), document.ID+ext)
	if err := os.WriteFile(tempFile, content, 0644); err != nil {
		return fmt.Errorf("failed to write temporary JPEG/JPG file: %w", err)
	}
	defer os.Remove(tempFile) // Clean up after we're done

	// Get image dimensions and calculate scaling to fit page
	imageWidth, imageHeight := util.GetImageDimensions(tempFile)
	pageWidth, pageHeight := pdf.GetPageSize()

	// Allow for margins
	pageWidth -= 20
	pageHeight -= 20

	// Calculate scaling factor to maintain aspect ratio
	widthScale := pageWidth / imageWidth
	heightScale := pageHeight / imageHeight
	scale := math.Min(widthScale, heightScale)

	// Calculate dimensions of the image on the page
	width := imageWidth * scale
	height := imageHeight * scale

	// Calculate position to center image on page
	x := (pageWidth-width)/2 + 10
	y := (pageHeight-height)/2 + 10

	// Add the image to the PDF
	pdf.Image(tempFile, x, y, width, height, false, "", 0, "")

	// Write the PDF to the output
	return pdf.Output(output)
}

// CanConvert checks if this converter can handle the given document
func (c *JPEGConverter) CanConvert(document *model.Document) bool {
	return document.Format == model.FormatJPEG || document.Format == model.FormatJPG
}
