import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, Text, TouchableOpacity, useColorScheme, View } from 'react-native';
import { Colors, Spacing } from '../constants/theme';
import { usePushNotifications } from '../hooks/usePushNotifications';
import { AuthProvider, useAuth } from '../lib/auth';
import { CONFIG_ERROR } from '../lib/config';

function SignOutButton() {
  const { signOut } = useAuth();
  return (
    <TouchableOpacity onPress={() => void signOut()} accessibilityRole="button" accessibilityLabel="Sign out">
      <Text style={{ color: Colors.brandRed, fontWeight: '600' }}>Sign out</Text>
    </TouchableOpacity>
  );
}

function AppShell() {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const { session, loading } = useAuth();
  const bg = isDark ? Colors.darkBg : Colors.lightBg;
  const fg = isDark ? Colors.lightBg : Colors.darkBg;

  // Registers this device for 'X paid' pushes once an organiser is signed in, and
  // deep-links notification taps.
  usePushNotifications(session?.user.id);

  if (CONFIG_ERROR) {
    return (
      <View style={{ flex: 1, backgroundColor: bg, justifyContent: 'center', padding: Spacing.lg }}>
        <Text style={{ color: Colors.error, fontSize: 16, textAlign: 'center' }}>{CONFIG_ERROR}</Text>
      </View>
    );
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: bg, justifyContent: 'center' }}>
        <ActivityIndicator color={Colors.brandRed} />
      </View>
    );
  }

  const signedIn = !!session;

  return (
    <>
      <StatusBar style={isDark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: bg },
          headerTintColor: fg,
          headerTitleStyle: { fontWeight: '700' },
          contentStyle: { backgroundColor: bg },
        }}
      >
        {/* Guarded routes: unreachable (even by deep link) until signed in. */}
        <Stack.Protected guard={signedIn}>
          <Stack.Screen
            name="index"
            options={{ title: 'Bayar.lah 💸', headerRight: () => <SignOutButton /> }}
          />
          <Stack.Screen name="create" options={{ title: 'New Bill', presentation: 'modal' }} />
          <Stack.Screen name="bill/[id]" options={{ title: 'Bill', headerBackTitle: 'Back' }} />
          <Stack.Screen
            name="tangga"
            options={{ title: '🪜 Tangga', headerBackTitle: 'Bill', presentation: 'fullScreenModal' }}
          />
          <Stack.Screen
            name="roulette"
            options={{ title: '🎡 Pusing', headerBackTitle: 'Bill', presentation: 'fullScreenModal' }}
          />
        </Stack.Protected>
        <Stack.Protected guard={!signedIn}>
          <Stack.Screen name="login" options={{ headerShown: false }} />
        </Stack.Protected>
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
