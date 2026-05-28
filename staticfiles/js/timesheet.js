

document.addEventListener("input", function (event) {
  if (!event.target.classList.contains("job-input")) return;

  const name = event.target.getAttribute("name") || "";
  const match = name.match(/^entry_(\d{4}-\d{2}-\d{2})_(\d+)_job_number$/);
  if (!match) return;

  const day = match[1];
  const row = match[2];
  const partJob = document.querySelector(`[name="entry_${day}_${row}_part_ee_stock_job_number"]`);

  if (partJob && !partJob.dataset.userEdited) {
    partJob.value = event.target.value;
  }
});

document.addEventListener("input", function (event) {
  if (!event.target.classList.contains("part-job-input")) return;
  event.target.dataset.userEdited = "true";
});
