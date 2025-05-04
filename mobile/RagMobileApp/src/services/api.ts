import axios from 'axios';

// Configure the base URL for your API - this should point to your backend server
// In development with a locally running backend, this may be:
const API_BASE_URL = 'http://10.0.2.2:8000'; // Use 10.0.2.2 for Android emulator to connect to localhost
// For iOS simulator, use: 'http://localhost:8000'
// For physical devices, use your machine's IP address: 'http://192.168.1.X:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 20000, // 20 seconds
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

export default api;