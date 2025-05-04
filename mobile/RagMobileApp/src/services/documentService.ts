import api from './api';
// Define Document interface directly here instead of importing
export interface Document {
  id: string;
  title: string;
  file?: string;
  metadata?: Record<string, any>;
}

import { Platform } from 'react-native';
import RNFS from 'react-native-fs';

export const documentService = {
  /**
   * Fetch all documents
   */
  async getDocuments(): Promise<Document[]> {
    try {
      const response = await api.get('/documents/list');
      return response.data;
    } catch (error) {
      console.error('Error fetching documents:', error);
      throw error;
    }
  },

  /**
   * Upload a document
   * @param fileUri - The URI of the file to upload
   */
  async uploadDocument(fileUri: string): Promise<any> {
    try {
      // Create form data
      const formData = new FormData();
      
      // Get file name from URI
      const fileName = fileUri.split('/').pop() || 'document';
      
      // Get file type
      let fileType = 'application/octet-stream';
      if (fileName.endsWith('.pdf')) fileType = 'application/pdf';
      else if (fileName.endsWith('.txt')) fileType = 'text/plain';
      else if (fileName.endsWith('.docx')) fileType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      
      // Read file as base64 string if needed
      const fileContent = {
        uri: Platform.OS === 'android' ? fileUri : fileUri.replace('file://', ''),
        name: fileName,
        type: fileType,
      };
      
      formData.append('file', fileContent as any);
      
      const response = await api.post('/documents/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      return response.data;
    } catch (error) {
      console.error('Error uploading document:', error);
      throw error;
    }
  },

  /**
   * Delete a document
   * @param id - Document ID
   */
  async deleteDocument(id: string): Promise<any> {
    try {
      const response = await api.delete(`/documents/${id}`);
      return response.data;
    } catch (error) {
      console.error('Error deleting document:', error);
      throw error;
    }
  },

  /**
   * Download a document
   * @param id - Document ID
   * @param fileName - File name to save as
   */
  async downloadDocument(id: string, fileName: string): Promise<string> {
    try {
      const response = await api.get(`/documents/${id}/download`, {
        responseType: 'blob',
      });
      
      // Create directory if it doesn't exist
      const downloadDir = RNFS.DocumentDirectoryPath + '/downloads';
      await RNFS.mkdir(downloadDir);
      
      // Save the file
      const filePath = `${downloadDir}/${fileName || `document-${id}.pdf`}`;
      await RNFS.writeFile(filePath, response.data, 'base64');
      
      return filePath;
    } catch (error) {
      console.error('Error downloading document:', error);
      throw error;
    }
  },
};