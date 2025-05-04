package api

import "document-processor/internal/model"

// DetectResponse represents the response for format detection
type DetectResponse struct {
	Format     string `json:"format"`
	FormatName string `json:"formatName"`
	Success    bool   `json:"success"`
	Error      string `json:"error,omitempty"`
}

// ConversionResponse represents the response for document conversion
type ConversionResponse struct {
	Success      bool   `json:"success"`
	OriginalName string `json:"originalName,omitempty"`
	ResultName   string `json:"resultName,omitempty"`
	Format       string `json:"format,omitempty"`
	Size         int64  `json:"size,omitempty"`
	Error        string `json:"error,omitempty"`
	// If the file was streamed back, this will be empty
	Location string `json:"location,omitempty"`
}

// FormatInfo maps model.Format to display names
var FormatInfo = map[model.Format]string{
	model.FormatDOCX: "Microsoft Word Document",
	model.FormatPPTX: "Microsoft PowerPoint Presentation",
	model.FormatXLSX: "Microsoft Excel Spreadsheet",
	model.FormatHTML: "HTML Document",
	model.FormatTXT:  "Plain Text",
	model.FormatMD:   "Markdown Document",
	model.FormatPDF:  "PDF Document",
}
