import Spinner from "../common/Spinner.jsx";

export default function GenerateButton({ onClick, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center h-10 px-5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 text-base font-medium"
    >
      {loading ? <Spinner /> : "Generate & Download"}
    </button>
  );
}
