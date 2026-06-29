export default function PoolSelector({ useSample, onChange, stats }) {
  const fullAvailable = stats?.full_pool_available

  return (
    <div className="flex items-center gap-3 bg-white border rounded-lg px-4 py-2 shadow-sm">
      <span className="text-sm text-gray-600 font-medium">Data pool:</span>
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="radio"
          name="pool"
          checked={!useSample}
          onChange={() => onChange(false)}
          disabled={!fullAvailable}
          className="text-indigo-600"
        />
        <span className="text-sm">
          Full ({stats?.full_pool_size?.toLocaleString() || '100K'})
          {!fullAvailable && ' — not found'}
        </span>
      </label>
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="radio"
          name="pool"
          checked={useSample}
          onChange={() => onChange(true)}
          className="text-indigo-600"
        />
        <span className="text-sm">Sample ({stats?.sample_candidates || 50})</span>
      </label>
    </div>
  )
}
