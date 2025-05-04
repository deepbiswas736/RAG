import api from './api';

export const queryService = {
  /**
   * Submit a synchronous query
   * @param query - The query text
   */
  async submitSyncQuery(query: string): Promise<Response> {
    try {
      // Use fetch instead of axios to handle streaming responses
      const response = await fetch(`${api.defaults.baseURL}/query/sync`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      
      return response;
    } catch (error) {
      console.error('Error submitting sync query:', error);
      throw error;
    }
  },

  /**
   * Submit an asynchronous query
   * @param query - The query text
   */
  async submitAsyncQuery(query: string): Promise<{ query_id: string }> {
    try {
      const response = await api.post('/query/async', { query });
      return response.data;
    } catch (error) {
      console.error('Error submitting async query:', error);
      throw error;
    }
  },

  /**
   * Check the status of an asynchronous query
   * @param queryId - The ID of the query
   */
  async checkAsyncQueryStatus(queryId: string): Promise<any> {
    try {
      const response = await api.get(`/query/async/${queryId}`);
      return response.data;
    } catch (error) {
      console.error('Error checking async query status:', error);
      throw error;
    }
  },

  /**
   * Get history of completed queries
   */
  async getQueryHistory(): Promise<any[]> {
    try {
      const response = await api.get('/query/history');
      return response.data;
    } catch (error) {
      console.error('Error fetching query history:', error);
      throw error;
    }
  },
};