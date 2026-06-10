import { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  useColorScheme,
} from 'react-native';
import { useRouter } from 'expo-router';
import { listBills } from '../lib/api';
import { Colors, Spacing, Radius } from '../constants/theme';
import type { Bill } from '../types';

export default function HomeScreen() {
  const router = useRouter();
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listBills();
      setBills(data);
    } catch {
      // unauthenticated — show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const textColor = isDark ? Colors.lightBg : Colors.darkBg;
  const cardBg = isDark ? Colors.gray700 : Colors.white;
  const subText = isDark ? Colors.gray300 : Colors.gray500;

  return (
    <View style={[styles.container, { backgroundColor: isDark ? Colors.darkBg : Colors.lightBg }]}>
      <FlatList
        data={bills}
        keyExtractor={(b) => b.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={Colors.brandRed} />}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={[styles.emptyTitle, { color: textColor }]}>No bills yet</Text>
              <Text style={[styles.emptyHint, { color: subText }]}>Tap + to create your first bill</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.card, { backgroundColor: cardBg }]}
            onPress={() => router.push(`/bill/${item.id}`)}
            activeOpacity={0.75}
          >
            <View style={styles.cardRow}>
              <Text style={styles.emoji}>{item.emoji_tag}</Text>
              <View style={styles.cardBody}>
                <Text style={[styles.cardTitle, { color: textColor }]}>{item.title}</Text>
                <Text style={[styles.cardSub, { color: subText }]}>
                  RM {item.total_amount.toFixed(2)} · {item.status}
                </Text>
              </View>
              <View style={[styles.badge, { backgroundColor: item.status === 'completed' ? Colors.forestGreen : Colors.brandRed }]}>
                <Text style={styles.badgeText}>{item.status === 'completed' ? 'Done' : 'Active'}</Text>
              </View>
            </View>
          </TouchableOpacity>
        )}
      />
      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push('/create')}
        activeOpacity={0.85}
      >
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  list: { padding: Spacing.md, gap: Spacing.sm, paddingBottom: 100 },
  card: {
    borderRadius: Radius.card,
    padding: Spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  emoji: { fontSize: 28 },
  cardBody: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: '600' },
  cardSub: { fontSize: 13, marginTop: 2 },
  badge: { borderRadius: Radius.chip, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText: { color: '#fff', fontSize: 12, fontWeight: '600' },
  empty: { alignItems: 'center', marginTop: 80, gap: Spacing.sm },
  emptyTitle: { fontSize: 20, fontWeight: '700' },
  emptyHint: { fontSize: 14 },
  fab: {
    position: 'absolute',
    bottom: Spacing.xl,
    right: Spacing.xl,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.brandRed,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.brandRed,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  fabText: { color: '#fff', fontSize: 28, fontWeight: '300', lineHeight: 32 },
});
