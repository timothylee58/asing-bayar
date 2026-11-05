import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  useColorScheme,
  View,
} from 'react-native';
import { useAuth } from '../lib/auth';
import { Colors, Radius, Spacing } from '../constants/theme';

type Step = 'email' | 'code';

/** Passwordless sign-in: we email a one-time code, the organiser types it in. */
export default function LoginScreen() {
  const { sendCode, verifyCode } = useAuth();
  const isDark = useColorScheme() === 'dark';
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const subText = isDark ? Colors.gray300 : Colors.gray500;
  const inputBg = isDark ? Colors.gray700 : Colors.white;
  const border = isDark ? Colors.gray500 : Colors.gray300;

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  };

  const requestCode = () =>
    run(async () => {
      await sendCode(email);
      setStep('code');
    });

  // On success the auth provider receives the new session and the router swaps this
  // screen for the app - nothing to navigate to here.
  const submitCode = () => run(() => verifyCode(email, code));

  const emailValid = /^\S+@\S+\.\S+$/.test(email.trim());
  const codeValid = /^\d{6,10}$/.test(code.trim());

  return (
    <KeyboardAvoidingView
      style={[styles.container, { backgroundColor: isDark ? Colors.darkBg : Colors.lightBg }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.inner}>
        <Text style={styles.logo}>💸</Text>
        <Text style={[styles.title, { color: textColor }]}>Bayar.lah</Text>
        <Text style={[styles.tagline, { color: subText }]}>Split duit, no awkward lah.</Text>

        {step === 'email' ? (
          <>
            <Text style={[styles.label, { color: subText }]}>Sign in with your email</Text>
            <TextInput
              style={[styles.input, { backgroundColor: inputBg, color: textColor, borderColor: border }]}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={subText}
              autoCapitalize="none"
              autoComplete="email"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              editable={!busy}
              onSubmitEditing={() => emailValid && requestCode()}
              returnKeyType="send"
            />
            <PrimaryButton
              label="Email me a code"
              busy={busy}
              disabled={!emailValid}
              onPress={requestCode}
            />
          </>
        ) : (
          <>
            <Text style={[styles.label, { color: subText }]}>
              Enter the code we sent to {email.trim()}
            </Text>
            <TextInput
              style={[styles.input, styles.codeInput, { backgroundColor: inputBg, color: textColor, borderColor: border }]}
              value={code}
              onChangeText={(v) => setCode(v.replace(/\D/g, ''))}
              placeholder="123456"
              placeholderTextColor={subText}
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              autoComplete="one-time-code"
              maxLength={10}
              editable={!busy}
              autoFocus
              onSubmitEditing={() => codeValid && submitCode()}
            />
            <PrimaryButton label="Sign in" busy={busy} disabled={!codeValid} onPress={submitCode} />
            <TouchableOpacity
              onPress={() => {
                setStep('email');
                setCode('');
                setError('');
              }}
              disabled={busy}
            >
              <Text style={[styles.link, { color: Colors.brandRed }]}>Use a different email</Text>
            </TouchableOpacity>
          </>
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
    </KeyboardAvoidingView>
  );
}

function PrimaryButton(props: { label: string; busy: boolean; disabled: boolean; onPress: () => void }) {
  const off = props.disabled || props.busy;
  return (
    <TouchableOpacity
      style={[styles.button, { opacity: off ? 0.5 : 1 }]}
      onPress={props.onPress}
      disabled={off}
      activeOpacity={0.85}
    >
      {props.busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>{props.label}</Text>}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  inner: { flex: 1, justifyContent: 'center', padding: Spacing.lg, gap: Spacing.md },
  logo: { fontSize: 56, textAlign: 'center' },
  title: { fontSize: 32, fontWeight: '800', textAlign: 'center' },
  tagline: { fontSize: 15, textAlign: 'center', marginBottom: Spacing.lg },
  label: { fontSize: 14, textAlign: 'center' },
  input: {
    borderWidth: 1,
    borderRadius: Radius.card,
    paddingHorizontal: Spacing.md,
    paddingVertical: 14,
    fontSize: 16,
  },
  codeInput: { textAlign: 'center', fontSize: 24, letterSpacing: 6, fontWeight: '700' },
  button: {
    backgroundColor: Colors.brandRed,
    borderRadius: Radius.button,
    paddingVertical: 15,
    alignItems: 'center',
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  link: { textAlign: 'center', fontSize: 14, fontWeight: '600', padding: Spacing.sm },
  error: { color: Colors.error, textAlign: 'center', fontSize: 14 },
});
