import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

// Import screens with .tsx extension explicitly
import DocumentsScreen from '../screens/Documents/DocumentsScreen.tsx';
import SyncQueryScreen from '../screens/Query/SyncQueryScreen.tsx';
import AsyncQueryScreen from '../screens/Query/AsyncQueryScreen.tsx';

// Define the stack navigator param list
export type RootStackParamList = {
  Documents: undefined;
  SyncQuery: undefined;
  AsyncQuery: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function AppNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Documents">
        <Stack.Screen 
          name="Documents" 
          component={DocumentsScreen}
          options={{ title: 'Documents' }} 
        />
        <Stack.Screen 
          name="SyncQuery" 
          component={SyncQueryScreen}
          options={{ title: 'Synchronous Query' }} 
        />
        <Stack.Screen 
          name="AsyncQuery" 
          component={AsyncQueryScreen}
          options={{ title: 'Asynchronous Query' }} 
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
}