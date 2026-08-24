const TERMINAL_STATES = ["FINAL_READY", "COMPLETED", "FAILED", "PRINT_FAILED"];
const STATUS_LABELS = { QUEUED: "Đang xếp hàng", LOGGING_IN: "Đang kết nối", DOWNLOADING: "Đang tải phiếu đặt hàng", PROCESSING: "Đang xử lý dữ liệu", FINAL_READY: "PDF đã sẵn sàng", PRINTING: "Đang in", COMPLETED: "Đã in xong", FAILED: "Không thể hoàn tất", PRINT_FAILED: "In thất bại" };
const ERROR_LABELS = { FAILED: "Không thể hoàn tất quy trình. Bạn có thể thử lại.", PRINT_FAILED: "Không thể in file PDF. File vẫn được giữ lại để thử lại." };

function automationDashboard() {
  return {
    deliveryDate: "", autoPrint: false, printOptionsOpen: false, copies: 2, pageRange: "", paperSize: "A5", layout: "portrait", fitMode: "fit",
    view: "idle", job: null, polling: null, pollFailures: 0, errorMessage: null, isPrinting: false,
    get isRunning() { return this.job && !TERMINAL_STATES.includes(this.job.status); },
    get progress() { return Math.max(0, Math.min(100, Number(this.job?.progress || 0))); },
    get statusLabel() { return STATUS_LABELS[this.job?.status] || "Đang xử lý"; },
    get downloadUrl() { return this.job ? `${AUTOMATION_API_BASE}/api/automation/jobs/${encodeURIComponent(this.job.automationJobId)}/download` : "#"; },
    init() { this.clearPolling(); },
    options() { return { copies: this.copies, ...(this.pageRange.trim() ? { pageRange: this.pageRange.trim() } : {}), paperSize: this.paperSize, layout: this.layout, fitMode: this.fitMode }; },
    async execute() {
      if (this.isRunning) return;
      this.clearPolling(); this.errorMessage = null; this.job = null;
      if (!this.deliveryDate) { this.errorMessage = "Vui lòng chọn ngày giao hàng."; return; }
      try { this.job = await startJob(this.deliveryDate, this.autoPrint, this.options()); this.view = "running"; this.startPolling(); }
      catch (error) { this.errorMessage = "Không thể bắt đầu quy trình. Vui lòng thử lại."; this.view = "idle"; }
    },
    startPolling() { this.clearPolling(); this.pollFailures = 0; this.polling = setInterval(() => this.poll(), 1800); this.poll(); },
    async poll() {
      if (!this.job || !this.isRunning) { this.clearPolling(); return; }
      try { this.job = await getJob(this.job.automationJobId); this.pollFailures = 0; this.updateView(); }
      catch (error) { this.pollFailures += 1; if (this.pollFailures >= 3) { this.errorMessage = "Mất kết nối trong lúc xử lý. Vui lòng thử lại."; this.clearPolling(); this.view = "failure"; } }
    },
    updateView() {
      if (!this.job || !TERMINAL_STATES.includes(this.job.status)) { this.view = "running"; return; }
      this.clearPolling(); this.view = this.job.status === "FINAL_READY" ? "success" : this.job.status === "COMPLETED" ? "printed" : this.job.status === "PRINT_FAILED" ? "printFailed" : "failure";
      this.errorMessage = ERROR_LABELS[this.job.status] || null;
    },
    async print() {
      if (!this.job || this.isPrinting) return;
      this.isPrinting = true; this.errorMessage = null;
      try { this.job = await triggerPrint(this.job.automationJobId); this.updateView(); }
      catch (error) { this.errorMessage = "Không thể in file PDF. Vui lòng thử lại."; this.view = "printFailed"; }
      finally { this.isPrinting = false; }
    },
    resetForRetry() { this.clearPolling(); this.job = null; this.errorMessage = null; this.view = "idle"; },
    clearPolling() { if (this.polling !== null) { clearInterval(this.polling); this.polling = null; } },
    destroy() { this.clearPolling(); },
  };
}
