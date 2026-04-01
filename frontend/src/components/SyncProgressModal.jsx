import { Clock3 } from "lucide-react";

export default function SyncProgressModal({ open, title, description }) {
  if (!open) {
    return null;
  }

  return (
    <div className="sync-modal-backdrop" role="presentation">
      <section
        className="card sync-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sync-modal-title"
        aria-describedby="sync-modal-description"
      >
        <div className="sync-modal__clock" aria-hidden="true">
          <div className="sync-modal__clock-ring" />
          <Clock3 size={28} strokeWidth={2.2} />
        </div>
        <h2 id="sync-modal-title">{title}</h2>
        <p id="sync-modal-description">
          {description || "Hệ thống đang kết nối Google Earth Engine và xử lý dữ liệu. Quá trình này có thể mất vài phút."}
        </p>
        <div className="sync-modal__progress" aria-hidden="true">
          <div className="sync-modal__progress-line" />
        </div>
        <div className="sync-modal__hint">Vui lòng chờ trong giây lát, cửa sổ sẽ tự đóng khi hoàn tất.</div>
      </section>
    </div>
  );
}
