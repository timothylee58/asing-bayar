export const Colors = {
  brandRed: '#C8410A',
  turmericGold: '#BA7517',
  forestGreen: '#1D9E75',
  darkBg: '#0F0D0B',
  lightBg: '#FAFAF8',
  white: '#FFFFFF',
  black: '#000000',
  gray100: '#F5F5F4',
  gray300: '#D6D3D1',
  gray500: '#78716C',
  gray700: '#44403C',
  error: '#DC2626',
} as const;

export const Radius = {
  card: 12,
  chip: 20,
  avatar: 50,
  button: 12,
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const EMOJI_TAGS = ['🍽️', '🏠', '✈️', '🎮', '🎉', '⚽', '🛒', '💼'] as const;

export const PAYMENT_METHODS = [
  { key: 'duitnow', label: 'DuitNow QR', emoji: '🇲🇾' },
  { key: 'tng', label: 'Touch \'n Go', emoji: '💳' },
  { key: 'bank', label: 'Bank Transfer', emoji: '🏦' },
  { key: 'cash', label: 'Cash', emoji: '💵' },
] as const;
