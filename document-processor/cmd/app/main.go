// Package main provides the entry point for the document processor application
package main

import (
	"document-processor/internal/api"
	"document-processor/internal/converter"
	"document-processor/internal/model"
	"document-processor/internal/util"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	// Define command-line flags
	port := flag.Int("port", 8080, "Port to run the API server on")
	outputDir := flag.String("output", "./output", "Directory to save converted PDF files")
	runMode := flag.String("mode", "api", "Run mode: 'api' or 'cli'")
	flag.Parse()

	// Create the converter manager with default converters
	manager := converter.CreateDefaultManager()

	// If running in API mode, start the API server
	if *runMode == "api" {
		fmt.Println("Document to PDF Converter API")
		fmt.Println("--------------------------")
		fmt.Printf("API server will use output directory: %s\n", *outputDir)

		// Start the API server
		err := api.StartServer(*port, manager, *outputDir)
		if err != nil {
			fmt.Printf("Error starting API server: %v\n", err)
			os.Exit(1)
		}
	} else {
		// Command-line mode (original functionality)
		fmt.Println("Document to PDF Converter")
		fmt.Println("--------------------------")

		// Check if a file path was provided
		args := flag.Args()
		if len(args) < 1 {
			fmt.Println("Usage: app [flags] <file_path>")
			fmt.Println("\nFlags:")
			flag.PrintDefaults()
			printSupportedFormats()
			return
		}

		filePath := args[0]

		// Process the file
		err := processFile(filePath, manager, *outputDir)
		if err != nil {
			fmt.Printf("Error: %v\n", err)
			os.Exit(1)
		}
	}
}

// processFile converts the specified file to PDF
func processFile(filePath string, manager *converter.ConverterManager, outputDir string) error {
	// Check if file exists
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return fmt.Errorf("file not found: %s", filePath)
	}

	// Open the file
	file, err := os.Open(filePath)
	if err != nil {
		return fmt.Errorf("failed to open file: %w", err)
	}
	defer file.Close()

	// Get file info
	fileInfo, err := file.Stat()
	if err != nil {
		return fmt.Errorf("failed to get file info: %w", err)
	}

	// Create a document from the file
	document := model.NewDocument(fileInfo.Name(), file, fileInfo.Size())

	// If we couldn't determine format from the filename, try to detect it
	if document.Format == "" {
		// Reset the file pointer to the beginning
		file.Seek(0, 0)

		// Create a format detector
		detector := util.NewFormatDetector()

		// Detect format
		format, err := detector.DetectFormat(file)
		if err != nil {
			return fmt.Errorf("failed to detect format: %w", err)
		}

		// Set the detected format
		document.Format = format

		// Reset the file pointer again
		file.Seek(0, 0)
	}

	// Create output PDF file path
	outputPath := getOutputPath(filePath, outputDir)

	fmt.Printf("Converting %s to %s...\n", filePath, outputPath)

	// Create output file
	outputFile, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("failed to create output file: %w", err)
	}
	defer outputFile.Close()

	// Convert the document to PDF
	err = manager.ConvertToPDF(document, outputFile)
	if err != nil {
		return fmt.Errorf("conversion failed: %w", err)
	}

	fmt.Println("Conversion completed successfully!")
	return nil
}

// getOutputPath generates an output PDF file path from the input file path
func getOutputPath(filePath string, outputDir string) string {
	// Create the output directory if it doesn't exist
	if outputDir != "" {
		os.MkdirAll(outputDir, 0755)
	}

	_, filename := filepath.Split(filePath)
	baseName := filename[:len(filename)-len(filepath.Ext(filename))]

	if outputDir != "" {
		return filepath.Join(outputDir, baseName+".pdf")
	}

	dir := filepath.Dir(filePath)
	return filepath.Join(dir, baseName+".pdf")
}

// printSupportedFormats prints the supported file formats
func printSupportedFormats() {
	fmt.Println("\nSupported file formats:")
	fmt.Println("- DOCX (.docx)")
	fmt.Println("- TXT  (.txt)")
	fmt.Println("- Markdown (.md)")
	fmt.Println("- HTML (.html)")
	fmt.Println("- XLSX (.xlsx)")
	fmt.Println("- PPTX (.pptx)")
}
