import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  FlatList, 
  StyleSheet, 
  TouchableOpacity, 
  Alert,
  ActivityIndicator
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import DocumentPicker from 'react-native-document-picker';
import { RootStackParamList } from '../../navigation/AppNavigator';
import { documentService } from '../../services/documentService';
import { Document } from '../../types/document';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const DocumentsScreen = () => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const navigation = useNavigation<NavigationProp>();

  // Fetch documents on component mount
  useEffect(() => {
    fetchDocuments();
  }, []);

  // Function to fetch documents
  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const docs = await documentService.getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error('Error fetching documents:', error);
      Alert.alert('Error', 'Failed to load documents. Please try again.');
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  };

  // Handle document upload
  const handleDocumentUpload = async () => {
    try {
      const result = await DocumentPicker.pick({
        type: [DocumentPicker.types.pdf, DocumentPicker.types.plainText, DocumentPicker.types.doc, DocumentPicker.types.docx],
      });
      
      // Single file selected
      const fileUri = result[0].uri;
      setIsLoading(true);
      
      await documentService.uploadDocument(fileUri);
      Alert.alert('Success', 'Document uploaded successfully');
      fetchDocuments();
    } catch (err) {
      if (DocumentPicker.isCancel(err)) {
        // User cancelled the picker
      } else {
        console.error('Error picking document:', err);
        Alert.alert('Error', 'Failed to upload document. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle document deletion
  const handleDeleteDocument = (id: string) => {
    Alert.alert(
      'Confirm Delete',
      'Are you sure you want to delete this document?',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Delete', 
          style: 'destructive',
          onPress: async () => {
            setIsLoading(true);
            try {
              await documentService.deleteDocument(id);
              fetchDocuments();
            } catch (error) {
              console.error('Error deleting document:', error);
              Alert.alert('Error', 'Failed to delete document. Please try again.');
            } finally {
              setIsLoading(false);
            }
          }
        },
      ]
    );
  };

  // Handle document download
  const handleDownloadDocument = async (id: string, title: string) => {
    setIsLoading(true);
    try {
      const filePath = await documentService.downloadDocument(id, title);
      Alert.alert('Success', `Document downloaded to: ${filePath}`);
    } catch (error) {
      console.error('Error downloading document:', error);
      Alert.alert('Error', 'Failed to download document. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Render document item
  const renderDocumentItem = ({ item }: { item: Document }) => (
    <View style={styles.documentItem}>
      <Text style={styles.documentTitle}>{item.title || item.file || `Document ${item.id}`}</Text>
      <View style={styles.actions}>
        <TouchableOpacity 
          style={[styles.button, styles.downloadButton]} 
          onPress={() => handleDownloadDocument(item.id, item.title)}
        >
          <Text style={styles.buttonText}>Download</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          style={[styles.button, styles.deleteButton]} 
          onPress={() => handleDeleteDocument(item.id)}
        >
          <Text style={styles.buttonText}>Delete</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Header Section */}
      <View style={styles.header}>
        <Text style={styles.title}>Document Management</Text>
        <Text style={styles.subtitle}>
          Upload and manage documents for use with the RAG system
        </Text>
      </View>

      {/* Action Buttons */}
      <View style={styles.actionButtons}>
        <TouchableOpacity 
          style={[styles.button, styles.uploadButton]} 
          onPress={handleDocumentUpload}
          disabled={isLoading}
        >
          <Text style={styles.buttonText}>Upload Document</Text>
        </TouchableOpacity>
        <View style={styles.navButtons}>
          <TouchableOpacity 
            style={[styles.button, styles.queryButton]} 
            onPress={() => navigation.navigate('SyncQuery')}
          >
            <Text style={styles.buttonText}>Sync Query</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.button, styles.queryButton]} 
            onPress={() => navigation.navigate('AsyncQuery')}
          >
            <Text style={styles.buttonText}>Async Query</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Documents List */}
      <View style={styles.listContainer}>
        <Text style={styles.sectionTitle}>Uploaded Documents</Text>
        {isLoading && !refreshing ? (
          <ActivityIndicator size="large" color="#0066cc" />
        ) : (
          <FlatList
            data={documents}
            renderItem={renderDocumentItem}
            keyExtractor={(item) => item.id}
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              fetchDocuments();
            }}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>No documents uploaded yet</Text>
              </View>
            }
          />
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  actionButtons: {
    marginBottom: 16,
  },
  navButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  button: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 5,
    alignItems: 'center',
    marginVertical: 5,
  },
  uploadButton: {
    backgroundColor: '#0066cc',
  },
  queryButton: {
    backgroundColor: '#5c5cd6',
    flex: 1,
    marginHorizontal: 5,
  },
  downloadButton: {
    backgroundColor: '#4caf50',
    marginRight: 8,
  },
  deleteButton: {
    backgroundColor: '#f44336',
  },
  buttonText: {
    color: 'white',
    fontWeight: '600',
  },
  listContainer: {
    flex: 1,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  documentItem: {
    backgroundColor: 'white',
    padding: 16,
    marginVertical: 8,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 1,
    elevation: 2,
  },
  documentTitle: {
    fontSize: 16,
    fontWeight: '500',
    marginBottom: 8,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
  },
});

export default DocumentsScreen;