/**
 * Runtime configuration.
 *
 * Values come from EXPO_PUBLIC_* environment variables, which Expo inlines into the
 * bundle at build time (it only recognises the literal `process.env.EXPO_PUBLIC_X`
 * form, so do not refactor these into a dynamic lookup).
 *
 * Before this, the API and Supabase settings were read from `app.json` "extra" while
 * eas.json set EXPO_PUBLIC_* variables that nothing read - so a production build
 * shipped pointing at localhost with an empty Supabase URL.
 */
const strip = (url: string) => url.replace(/\/+$/, '');

export const API_URL = strip(process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000');
export const WEB_URL = strip(process.env.EXPO_PUBLIC_WEB_URL ?? 'http://localhost:3000');
export const WS_URL = API_URL.replace(/^http/, 'ws');

export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

/** Non-null when the app cannot work; the root layout shows it instead of crashing. */
export const CONFIG_ERROR: string | null =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? null
    : 'This build is missing EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_ANON_KEY.';
