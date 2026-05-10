export default function Spinner({ size = 5 }) {
  const cls = `inline-block animate-spin rounded-full border-2 border-gray-300 border-t-indigo-600 h-${size} w-${size}`;
  return <span className={cls} role="status" aria-label="loading" />;
}
