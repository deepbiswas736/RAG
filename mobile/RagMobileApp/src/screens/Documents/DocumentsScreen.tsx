import React from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  Image
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../../navigation/AppNavigator';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const DocumentsScreen = () => {
  const navigation = useNavigation<NavigationProp>();

  // Feature items to display
  const features = [
    'Document upload and management with automatic processing',
    'Advanced chunking and embedding for optimal retrieval',
    'Synchronous queries for immediate responses',
    'Asynchronous queries for complex document processing',
    'Support for various document formats',
    'Secure document storage and handling'
  ];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header Section */}
        <View style={styles.header}>
          <Text style={styles.title}>RAG Document System</Text>
          <Text style={styles.subtitle}>
            Mobile Document Management & Query System
          </Text>
        </View>

        {/* App Logo/Icon Section */}
        <View style={styles.logoContainer}>
          {/* You can replace this with your actual app logo */}
          <View style={styles.logoPlaceholder}>
            <Text style={styles.logoText}>RAG</Text>
          </View>
        </View>

        {/* App Description */}
        <View style={styles.descriptionContainer}>
          <Text style={styles.descriptionText}>
            Our Retrieval-Augmented Generation (RAG) system combines the power of large language models with 
            a specialized document retrieval system to deliver precise, contextual answers based on your uploaded documents.
          </Text>
        </View>

        {/* Features Section */}
        <View style={styles.featuresContainer}>
          <Text style={styles.sectionTitle}>Key Features</Text>
          {features.map((feature, index) => (
            <View key={index} style={styles.featureItem}>
              <View style={styles.bullet} />
              <Text style={styles.featureText}>{feature}</Text>
            </View>
          ))}
        </View>

        {/* Navigation Buttons */}
        <View style={styles.navigationButtons}>
          <TouchableOpacity 
            style={[styles.navigationButton, styles.documentsButton]} 
            onPress={() => navigation.navigate('Documents')}
          >
            <Text style={styles.buttonText}>Manage Documents</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.navigationButton, styles.syncQueryButton]} 
            onPress={() => navigation.navigate('SyncQuery')}
          >
            <Text style={styles.buttonText}>Sync Query</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.navigationButton, styles.asyncQueryButton]} 
            onPress={() => navigation.navigate('AsyncQuery')}
          >
            <Text style={styles.buttonText}>Async Query</Text>
          </TouchableOpacity>
        </View>

        {/* Footer */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>© 2025 RAG Document System</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  scrollContent: {
    padding: 16,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    marginTop: 8,
    textAlign: 'center',
  },
  logoContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 24,
  },
  logoPlaceholder: {
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: '#0066cc',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  logoText: {
    fontSize: 40,
    fontWeight: 'bold',
    color: '#fff',
  },
  descriptionContainer: {
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
  },
  descriptionText: {
    fontSize: 16,
    color: '#333',
    lineHeight: 24,
    textAlign: 'center',
  },
  featuresContainer: {
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  bullet: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#0066cc',
    marginTop: 6,
    marginRight: 8,
  },
  featureText: {
    flex: 1,
    fontSize: 15,
    color: '#444',
    lineHeight: 20,
  },
  navigationButtons: {
    marginBottom: 24,
  },
  navigationButton: {
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
  },
  documentsButton: {
    backgroundColor: '#0066cc',
  },
  syncQueryButton: {
    backgroundColor: '#4caf50',
  },
  asyncQueryButton: {
    backgroundColor: '#9c27b0',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  footer: {
    alignItems: 'center',
    marginTop: 8,
  },
  footerText: {
    fontSize: 14,
    color: '#888',
  },
});

export default DocumentsScreen;