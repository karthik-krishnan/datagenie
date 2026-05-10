import Spinner from "../common/Spinner.jsx";

export default function GenerateButton({ onClick, loading }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 font-medium"
    >
      {loading ? <Spinner /> : "Generate & Download"}
    </button>
  );
}
