export default function StatCard({ label, value }) {
  return (
    <div className="card stat">
      <h4>{label}</h4>
      <p>{value}</p>
    </div>
  );
}
