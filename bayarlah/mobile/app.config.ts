import type { ExpoConfig } from 'expo/config';

/**
 * Dynamic Expo config (replaces app.json) so the build can be driven by environment
 * variables - and so a misconfigured release fails at build time instead of shipping.
 *
 * Why this exists: app.json hard-coded `apiUrl: http://localhost:8000` and an empty
 * Supabase URL while eas.json set EXPO_PUBLIC_* variables that the code never read, so
 * every EAS build would have pointed at localhost with no way to sign in.
 *
 * Release builds (EAS profiles `preview` / `production`) need these set as EAS
 * environment variables (`eas env:create`); local development reads a `.env` file.
 */
const profile = process.env.EAS_BUILD_PROFILE; // set by EAS Build: development | preview | production
const isRelease = profile === 'preview' || profile === 'production';

const REQUIRED_FOR_RELEASE = [
  'EXPO_PUBLIC_API_URL',
  'EXPO_PUBLIC_WEB_URL',
  'EXPO_PUBLIC_SUPABASE_URL',
  'EXPO_PUBLIC_SUPABASE_ANON_KEY',
  'EAS_PROJECT_ID', // needed to obtain Expo push tokens
] as const;

if (isRelease) {
  const missing = REQUIRED_FOR_RELEASE.filter((name) => !process.env[name]);
  if (missing.length > 0) {
    throw new Error(
      `Cannot build the "${profile}" profile: missing ${missing.join(', ')}. ` +
        'Set them as EAS environment variables (eas env:create).',
    );
  }
  if (/localhost|127\.0\.0\.1/.test(process.env.EXPO_PUBLIC_API_URL ?? '')) {
    throw new Error(`Cannot build the "${profile}" profile against a localhost EXPO_PUBLIC_API_URL.`);
  }
  if (profile === 'production' && !process.env.GOOGLE_SERVICES_JSON) {
    throw new Error(
      'Production Android builds need GOOGLE_SERVICES_JSON (an EAS file variable pointing at ' +
        'google-services.json) or push notifications will not work.',
    );
  }
}

const config: ExpoConfig = {
  name: 'Bayar.lah',
  slug: 'bayarlah',
  version: '1.0.0',
  scheme: 'bayarlah',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  ios: {
    supportsTablet: true,
    bundleIdentifier: 'com.timothylee.bayarlah',
  },
  android: {
    adaptiveIcon: {
      backgroundColor: '#0F0D0B',
      foregroundImage: './assets/android-icon-foreground.png',
      backgroundImage: './assets/android-icon-background.png',
      monochromeImage: './assets/android-icon-monochrome.png',
    },
    package: 'com.timothylee.bayarlah',
    predictiveBackGestureEnabled: false,
    // Not committed: supply it as an EAS file variable. Only referenced when provided,
    // so local `expo start` works without it.
    ...(process.env.GOOGLE_SERVICES_JSON ? { googleServicesFile: process.env.GOOGLE_SERVICES_JSON } : {}),
  },
  web: {
    favicon: './assets/favicon.png',
    bundler: 'metro',
  },
  plugins: [
    'expo-router',
    [
      'expo-notifications',
      {
        icon: './assets/icon.png',
        color: '#C8410A',
        defaultChannel: 'bayarlah',
        sounds: [],
      },
    ],
    [
      'expo-image-picker',
      {
        // Shown by iOS when asking for photo access to upload the DuitNow QR.
        photosPermission: 'Bayar.lah needs your photos so you can upload your DuitNow QR code.',
      },
    ],
  ],
  experiments: {
    typedRoutes: true,
  },
  extra: {
    eas: { projectId: process.env.EAS_PROJECT_ID },
  },
};

export default config;
