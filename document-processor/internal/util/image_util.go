// Package util contains utility functions for the document processor
package util

import (
	"fmt"
	"image"
	_ "image/jpeg" // Register JPEG decoder
	_ "image/png"  // Register PNG decoder
	"os"
)

// GetImageDimensions returns the width and height of an image file in pixels
func GetImageDimensions(filePath string) (float64, float64) {
	file, err := os.Open(filePath)
	if err != nil {
		fmt.Printf("Warning: Could not open image file %s: %v\n", filePath, err)
		return 800, 600 // Default fallback dimensions
	}
	defer file.Close()

	config, _, err := image.DecodeConfig(file)
	if err != nil {
		fmt.Printf("Warning: Could not decode image dimensions for %s: %v\n", filePath, err)
		return 800, 600 // Default fallback dimensions
	}

	return float64(config.Width), float64(config.Height)
}
