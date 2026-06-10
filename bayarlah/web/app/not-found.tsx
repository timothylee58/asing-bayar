export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="text-center">
        <div className="text-5xl mb-4">🔍</div>
        <h1 className="text-2xl font-extrabold text-stone-900">Bill not found</h1>
        <p className="text-stone-500 mt-2">This link may have expired or been cancelled.</p>
      </div>
    </div>
  );
}
