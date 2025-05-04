import React, { useState, useEffect, useRef } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ScrollView,
  ActivityIndicator,
  Alert,
  FlatList
} from 'react-native';
import { queryService } from '../../services/queryService';
import Markdown from 'react-native-markdown-display';

interface QueryResult {
  query_id: string;
  answer: string;
  preview: string;
  status: 'completed' | 'processing' | 'error';
  source_count: number;
  sources?: {
    source: string;
    content: string;
    metadata?: {
      page_number?: number;
      content_type?: string;
    };
  }[];
}

const AsyncQueryScreen = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [queryId, setQueryId] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [completedQueries, setCompletedQueries] = useState<Array<{
    query_id: string;
    preview: string;
    status: string;
    source_count: number;
  }>>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch query history on component mount
  useEffect(() => {
    fetchQueryHistory();
    return () => {
      // Clean up polling interval on unmount
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const fetchQueryHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const history = await queryService.getQueryHistory();
      setCompletedQueries(history);
    } catch (error) {
      console.error('Error fetching query history:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleSubmit = async () => {
    if (!query.trim()) {
      Alert.alert('Error', 'Please enter a query');
      return;
    }

    setIsLoading(true);
    setResult(null);

    try {
      // Submit async query
      const { query_id } = await queryService.submitAsyncQuery(query);
      setQueryId(query_id);
      
      // Start polling for results
      startPolling(query_id);
    } catch (error) {
      console.error('Error submitting async query:', error);
      Alert.alert('Error', 'Failed to submit query. Please try again.');
      setIsLoading(false);
    }
  };

  const startPolling = (queryId: string) => {
    setIsPolling(true);
    
    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    
    // Set up polling interval
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await queryService.checkAsyncQueryStatus(queryId);
        
        if (data.status === 'completed' || data.status === 'error') {
          // Stop polling when query is complete or errored
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          
          setResult(data);
          setIsLoading(false);
          setIsPolling(false);
          
          // Refresh history
          fetchQueryHistory();
        }
      } catch (error) {
        console.error('Error polling query status:', error);
        
        // Stop polling on error
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        
        setIsPolling(false);
        setIsLoading(false);
        Alert.alert('Error', 'Failed to get query results. Please try again.');
      }
    }, 2000); // Poll every 2 seconds
  };

  const loadQueryResult = async (queryId: string) => {
    setIsLoading(true);
    try {
      const data = await queryService.checkAsyncQueryStatus(queryId);
      setResult(data);
    } catch (error) {
      console.error('Error fetching query result:', error);
      Alert.alert('Error', 'Failed to load query result. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Fix the renderSource function to handle optional sources array
  const renderSource = ({ item, index }: { 
    item: NonNullable<QueryResult['sources']>[number], 
    index: number 
  }) => (
    <View style={styles.sourceItem}>
      <Text style={styles.sourceTitle}>{item.source}</Text>
      <View style={styles.sourceMetadata}>
        {item.metadata?.page_number && (
          <Text style={styles.metadataText}>Page: {item.metadata.page_number}</Text>
        )}
        {item.metadata?.content_type && (
          <Text style={styles.metadataText}>Type: {item.metadata.content_type}</Text>
        )}
      </View>
      <Text style={styles.sourceContent}>{item.content}</Text>
    </View>
  );

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

      {(isLoading || result) && (
        <View style={styles.resultContainer}>
          <Text style={styles.resultTitle}>Answer:</Text>
          <ScrollView 
            style={styles.resultScroll}
            ref={scrollViewRef}
          >
            {isLoading && !result && (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#0066cc" />
                <Text style={styles.loadingText}>
                  {isPolling ? 'Processing query. This may take some time...' : 'Submitting query...'}
                </Text>
              </View>
            )}
            
            {result && (
              <>
                <Markdown style={markdownStyles}>
                  {result.answer || 'No answer available'}
                </Markdown>
                
                {result.sources && result.sources.length > 0 && (
                  <View style={styles.sourcesContainer}>
                    <View style={styles.sourcesHeader}>
                      <Text style={styles.sourcesTitle}>Sources:</Text>
                      <TouchableOpacity onPress={() => setShowSources(!showSources)}>
                        <Text style={styles.sourceToggleButton}>
                          {showSources ? 'Hide Sources' : 'Show Sources'}
                        </Text>
                      </TouchableOpacity>
                    </View>
                    
                    {showSources && (
                      <FlatList
                        data={result.sources}
                        renderItem={renderSource}
                        keyExtractor={(_, index) => `source-${index}`}
                        scrollEnabled={false}
                      />
                    )}
                  </View>
                )}
              </>
            )}
          </ScrollView>
        </View>
      )}

      <View style={styles.historyContainer}>
        <Text style={styles.historyTitle}>Previous Queries</Text>
        {isLoadingHistory ? (
          <ActivityIndicator size="small" color="#0066cc" />
        ) : completedQueries.length > 0 ? (
          <FlatList
            data={completedQueries}
            keyExtractor={(item) => item.query_id}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.historyItem}
                onPress={() => loadQueryResult(item.query_id)}
              >
                <Text style={styles.historyQuery} numberOfLines={1} ellipsizeMode="tail">
                  {item.preview}
                </Text>
                <View style={styles.historyMeta}>
                  <Text style={styles.historyStatus}>
                    {item.status === 'completed' ? '✓' : '⚠️'} {item.source_count} sources
                  </Text>
                </View>
              </TouchableOpacity>
            )}
            style={styles.historyList}
          />
        ) : (
          <Text style={styles.emptyText}>No previous queries</Text>
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
    textAlign: 'center',
  },
  sourcesContainer: {
    marginTop: 16,
    borderTopWidth: 1,
    borderColor: '#eee',
    paddingTop: 12,
  },
  sourcesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sourcesTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  sourceToggleButton: {
    color: '#0066cc',
  },
  sourceItem: {
    borderWidth: 1,
    borderColor: '#eee',
    borderRadius: 4,
    padding: 12,
    marginBottom: 8,
  },
  sourceTitle: {
    fontWeight: '500',
    marginBottom: 4,
  },
  sourceMetadata: {
    flexDirection: 'row',
    marginBottom: 4,
  },
  metadataText: {
    fontSize: 12,
    color: '#666',
    marginRight: 12,
  },
  sourceContent: {
    fontSize: 14,
    color: '#444',
    borderLeftWidth: 2,
    borderLeftColor: '#ddd',
    paddingLeft: 8,
    marginTop: 4,
  },
  historyContainer: {
    marginTop: 16,
    maxHeight: 200,
  },
  historyTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  historyList: {
    maxHeight: 180,
  },
  historyItem: {
    backgroundColor: 'white',
    padding: 12,
    borderRadius: 4,
    marginBottom: 6,
    borderLeftWidth: 3,
    borderLeftColor: '#0066cc',
  },
  historyQuery: {
    fontSize: 14,
  },
  historyMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  historyStatus: {
    fontSize: 12,
    color: '#666',
  },
  emptyText: {
    color: '#666',
    fontStyle: 'italic',
    textAlign: 'center',
    padding: 12,
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

export default AsyncQueryScreen;