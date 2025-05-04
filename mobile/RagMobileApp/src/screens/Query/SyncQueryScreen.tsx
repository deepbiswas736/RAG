import React, { useState, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ScrollView,
  ActivityIndicator,
  Alert
} from 'react-native';
import { queryService } from '../../services/queryService';
import Markdown from 'react-native-markdown-display';

const SyncQueryScreen = () => {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);

  const handleSubmit = async () => {
    if (!query.trim()) {
      Alert.alert('Error', 'Please enter a query');
      return;
    }

    setIsLoading(true);
    setResult('');

    try {
      // Get response as a stream
      const response = await queryService.submitSyncQuery(query);
      
      // Read the stream
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Failed to create stream reader');
      }

      // Process stream chunks
      const decoder = new TextDecoder();
      let done = false;
      
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          setResult(prev => prev + chunk);
        }
      }
    } catch (error) {
      console.error('Error during sync query:', error);
      setResult('An error occurred while processing your query.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.queryContainer}>
        <Text style={styles.label}>Enter your question:</Text>
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          placeholder="Type your question here..."
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          editable={!isLoading}
        />
        
        <TouchableOpacity
          style={[
            styles.submitButton,
            isLoading && styles.disabledButton
          ]}
          onPress={handleSubmit}
          disabled={isLoading}
        >
          <Text style={styles.buttonText}>
            {isLoading ? 'Processing...' : 'Submit Query'}
          </Text>
        </TouchableOpacity>
      </View>

      {(result || isLoading) && (
        <View style={styles.resultContainer}>
          <Text style={styles.resultTitle}>Answer:</Text>
          <ScrollView 
            style={styles.resultScroll}
            ref={scrollViewRef}
            onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          >
            {isLoading && !result && (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#0066cc" />
                <Text style={styles.loadingText}>Processing query...</Text>
              </View>
            )}
            
            <Markdown style={markdownStyles}>
              {result}
            </Markdown>
          </ScrollView>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f5f5f5',
  },
  queryContainer: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: 'white',
    borderColor: '#ddd',
    borderWidth: 1,
    borderRadius: 5,
    padding: 10,
    fontSize: 16,
    minHeight: 100,
  },
  submitButton: {
    backgroundColor: '#0066cc',
    paddingVertical: 12,
    borderRadius: 5,
    alignItems: 'center',
    marginTop: 12,
  },
  disabledButton: {
    backgroundColor: '#999',
  },
  buttonText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 16,
  },
  resultContainer: {
    flex: 1,
    borderTopWidth: 1,
    borderColor: '#ddd',
    paddingTop: 16,
  },
  resultTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  resultScroll: {
    flex: 1,
    backgroundColor: 'white',
    borderRadius: 5,
    padding: 12,
    borderColor: '#ddd',
    borderWidth: 1,
  },
  loadingContainer: {
    alignItems: 'center',
    padding: 16,
  },
  loadingText: {
    marginTop: 8,
    color: '#666',
  },
});

const markdownStyles = {
  body: {
    fontSize: 15,
    color: '#333',
  },
  heading1: {
    fontSize: 22,
    fontWeight: 'bold',
    marginTop: 10,
    marginBottom: 5,
  },
  heading2: {
    fontSize: 20,
    fontWeight: 'bold',
    marginTop: 10,
    marginBottom: 5,
  },
  paragraph: {
    marginTop: 5,
    marginBottom: 5,
  },
  list: {
    marginLeft: 20,
  },
  listItem: {
    marginBottom: 5,
  },
  code_block: {
    backgroundColor: '#f0f0f0',
    padding: 10,
    borderRadius: 4,
    fontFamily: 'monospace',
    marginVertical: 5,
  },
};

export default SyncQueryScreen;