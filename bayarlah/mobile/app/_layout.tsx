import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useColorScheme } from 'react-native';
import { Colors } from '../constants/theme';
import { usePushNotifications } from '../hooks/usePushNotifications';

function AppShell() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  usePushNotifications(); // register at app start, deep-link on tap

  return (
    <>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: isDark ? Colors.darkBg : Colors.lightBg },
          headerTintColor: isDark ? Colors.lightBg : Colors.darkBg,
          headerTitleStyle: { fontWeight: '700' },
          contentStyle: { backgroundColor: isDark ? Colors.darkBg : Colors.lightBg },
        }}
      >
        <Stack.Screen name="index" options={{ title: 'Bayar.lah 💸' }} />
        <Stack.Screen name="create" options={{ title: 'New Bill', presentation: 'modal' }} />
        <Stack.Screen name="bill/[id]" options={{ title: 'Bill', headerBackTitle: 'Back' }} />
        <Stack.Screen name="tangga" options={{ title: '🪜 Tangga', headerBackTitle: 'Bill', presentation: 'fullScreenModal' }} />
        <Stack.Screen name="roulette" options={{ title: '🎡 Pusing', headerBackTitle: 'Bill', presentation: 'fullScreenModal' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return <AppShell />;
}
