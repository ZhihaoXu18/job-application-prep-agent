const $ = (id) => document.getElementById(id);
let activeJob = null;
let activePacket = "";
let activeReviewRevision = "";
let reviewDirty = false;
let directionFingerprint = "";
let confirmedRoles = null;
let directionRequestVersion = 0;
const termLabels = {"8_month_confirmed": "8 个月已确认", "4_month_only": "仅 4 个月", "variable_or_unclear": "任期待确认"};
const statusLabels = {prepared: "已准备", applied: "已申请", interview: "面试", rejected: "未通过", no_response: "暂无回复", offer: "收到 offer"};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showNotice(message, error = false) {
  const node = $("feedbackNotice");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.hidden = false;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function sourceMode() {
  return document.querySelector('input[name="sourceType"]:checked').value;
}

function syncSourceMode() {
  const mode = sourceMode();
  $("urlFields").hidden = mode !== "url";
  $("textFields").hidden = mode !== "text";
}

function appendInline(node, text) {
  text.split("**").forEach((part, index) => {
    if (index % 2) node.append(element("strong", "", part));
    else node.append(document.createTextNode(part));
  });
}

function tableCells(line) {
  return line.replaceAll("\\|", "\uE000").split("|").slice(1, -1)
    .map((cell) => cell.replaceAll("\uE000", "|").trim());
}

function renderPacket(markdown) {
  const root = $("packetText");
  root.replaceChildren();
  const lines = markdown.split(/\r?\n/);
  let index = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index++; continue; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const node = element(heading[1].length === 1 ? "h3" : heading[1].length === 2 ? "h4" : "h5", "");
      appendInline(node, heading[2]);
      root.append(node);
      index++;
      continue;
    }
    if (line.startsWith("|") && /^\|[\s:|-]+\|$/.test((lines[index + 1] || "").trim())) {
      const table = element("table", "");
      const head = element("thead", "");
      const headerRow = element("tr", "");
      for (const cell of tableCells(line)) headerRow.append(element("th", "", cell));
      head.append(headerRow);
      table.append(head);
      const body = element("tbody", "");
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const row = element("tr", "");
        for (const cell of tableCells(lines[index].trim())) row.append(element("td", "", cell));
        body.append(row);
        index++;
      }
      table.append(body);
      root.append(table);
      continue;
    }
    if (line.startsWith("- ")) {
      const list = element("ul", "");
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        const item = element("li", "");
        appendInline(item, lines[index].trim().slice(2));
        list.append(item);
        index++;
      }
      root.append(list);
      continue;
    }
    const paragraph = element("p", "");
    const parts = [];
    while (index < lines.length && lines[index].trim() &&
      !/^(#{1,3}\s|\|\s|-\s)/.test(lines[index].trim())) {
      parts.push(lines[index].trim());
      index++;
    }
    if (!parts.length) { index++; continue; }
    appendInline(paragraph, parts.join(" "));
    root.append(paragraph);
  }
}

async function encodedFile(file) {
  if (file.size > 2500000) throw new Error("履历文件超过 2.5 MB 限制。");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 16384;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return {name: file.name, data: btoa(binary)};
}

async function candidatePayload() {
  const payload = {
    resume_text: $("resumeText").value,
    profile_json: $("profileFile").files[0] ? await $("profileFile").files[0].text() : "",
  };
  const file = $("resumeFile").files[0];
  if (!payload.resume_text.trim() && file) payload.resume_file = await encodedFile(file);
  return payload;
}

function invalidateDirections() {
  directionRequestVersion++;
  directionFingerprint = "";
  confirmedRoles = null;
  $("directionPanel").hidden = true;
  $("directionSearch").hidden = true;
  $("directionStatus").textContent = "简历或 profile 已更改；如需使用方向建议，请重新分析并确认。";
}

async function suggestDirections() {
  const button = $("suggestDirections");
  const version = ++directionRequestVersion;
  button.disabled = true;
  try {
    const result = await api("/api/directions", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Job-Agent": "local-ui"},
      body: JSON.stringify(await candidatePayload()),
    });
    if (version !== directionRequestVersion) return;
    directionFingerprint = result.resume_fingerprint;
    confirmedRoles = null;
    $("directionSearch").hidden = true;
    const list = $("directionResults");
    list.replaceChildren();
    for (const suggestion of result.suggestions) {
      const item = element("div", "direction-item");
      item.append(element("strong", "", suggestion.role));
      for (const quote of suggestion.evidence) item.append(element("small", "", `简历原文：${quote}`));
      list.append(item);
    }
    if (!result.suggestions.length) {
      list.append(element("p", "direction-empty", "没有足够明确的线索；你仍可手动输入目标岗位。"));
    }
    $("directionRoles").value = (result.current_roles.length
      ? result.current_roles : result.suggestions.map((item) => item.role)).join("\n");
    $("directionPanel").hidden = false;
    $("directionStatus").textContent = "方向仅为草案；修改后点击“确认这些方向”才会用于新职位分析。";
  } catch (error) {
    if (version === directionRequestVersion) {
      $("directionStatus").textContent = `无法分析方向：${error.message}`;
    }
  } finally {
    button.disabled = false;
  }
}

function confirmDirections() {
  if (!directionFingerprint) return;
  const roles = $("directionRoles").value.split(/\r?\n/).map((role) => role.trim()).filter(Boolean);
  if (roles.length > 5 || roles.some((role) => role.length > 100) ||
      new Set(roles.map((role) => role.toLocaleLowerCase())).size !== roles.length) {
    $("directionStatus").textContent = "最多确认 5 个不重复的方向，每个方向不超过 100 字符。";
    return;
  }
  confirmedRoles = roles;
  const search = $("directionSearch");
  const links = $("directionSearchLinks");
  links.replaceChildren();
  for (const role of roles) {
    const link = element("a", "", `搜索 ${role} ↗`);
    link.href = `https://www.google.com/search?q=${encodeURIComponent(`${role} Canada co-op jobs`)}`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    links.append(link);
  }
  search.hidden = roles.length === 0;
  $("directionStatus").textContent = roles.length
    ? `已确认：${roles.join("、")}。后续新职位分析会使用这些目标方向。`
    : "已确认不设置目标岗位；后续分析不会假设你的求职方向。";
}

function generatedDraft(packet) {
  const start = packet.indexOf("## Short application draft");
  if (start < 0) return "";
  const from = start + "## Short application draft".length;
  const end = packet.indexOf("## Your actions", from);
  return packet.slice(from, end < 0 ? undefined : end).trim();
}

function reviewChecks() {
  return {
    posting_status: $("checkPosting").checked,
    term_and_dates: $("checkTerm").checked,
    resume_and_draft: $("checkClaims").checked,
  };
}

function updateReviewProgress() {
  const count = Object.values(reviewChecks()).filter(Boolean).length;
  $("reviewProgress").textContent = `${count} / 3 已核对`;
  const ready = Boolean(activeJob && activeReviewRevision && !reviewDirty &&
    count === 3 && $("editedDraft").value.trim());
  $("downloadApplication").disabled = !ready;
  $("exportReadiness").textContent = ready
    ? "可以下载。文件只包含已保存的申请段落，不含私人备注或审阅包。"
    : reviewDirty ? "有未保存的修改；完成核对并保存后可下载。"
    : "填写申请段落，完成三项核对并保存后可下载。";
}

function markReviewDirty() {
  if (!activeJob) return;
  reviewDirty = true;
  $("reviewSavedAt").textContent = "有未保存的修改；原始生成包不会被修改。";
  updateReviewProgress();
}

function canLeaveReview() {
  return !reviewDirty || window.confirm("当前人工审阅有未保存的修改。确定离开这份职位吗？");
}

function showPacket(job, packet, duplicate = false, review = {}) {
  $("feedbackNotice").hidden = true;
  activeJob = job;
  activePacket = packet;
  activeReviewRevision = review.revision || "";
  reviewDirty = false;
  $("emptyResult").hidden = true;
  $("result").hidden = false;
  $("resultTitle").textContent = `${job.title || "未注明职位"} — ${job.employer || "未注明雇主"}`;
  $("resultMeta").textContent = `Job ID: ${job.job_id} · ${job.prepared_at || ""}`;
  $("resultBadge").textContent = duplicate ? "已在 tracker 中 · 未重复分析" : "准备完成 · 尚未提交";
  renderPacket(packet);
  $("editedDraft").value = review.saved ? review.draft : generatedDraft(packet);
  $("reviewNotes").value = review.notes || "";
  $("checkPosting").checked = Boolean(review.checks?.posting_status);
  $("checkTerm").checked = Boolean(review.checks?.term_and_dates);
  $("checkClaims").checked = Boolean(review.checks?.resume_and_draft);
  $("reviewSavedAt").textContent = review.saved
    ? `已保存于 ${review.saved_at}；原始生成包保持不变。`
    : "尚未保存；原始生成包不会被修改。";
  updateReviewProgress();
  $("statusSelect").value = job.status || "prepared";
  $("result").scrollIntoView({behavior: "smooth", block: "start"});
}

function renderQueue(markdown) {
  const list = $("queueList");
  list.replaceChildren();
  const sections = markdown.split(/^## /m).slice(1);
  if (!sections.length) {
    list.append(element("div", "muted-empty", "暂无批次队列。先用命令行批量准备职位，或在上方准备单个职位。"));
    return;
  }
  for (const section of sections) {
    const lines = section.trim().split("\n");
    const title = lines[0].replace(/^\d+\.\s*/, "");
    const score = (section.match(/^- Review score: (-?\d+)/m) || ["", "0"])[1];
    const term = (section.match(/^- Term: ([^\n]+)/m) || ["", "unknown"])[1];
    const item = element("div", "queue-item");
    item.append(element("span", "queue-rank", String(list.children.length + 1).padStart(2, "0")));
    const main = element("div", "queue-main");
    main.append(element("strong", "", title), element("small", "", `任期：${termLabels[term] || "未注明"}`));
    item.append(main, element("span", "queue-score", `${score} 分`));
    list.append(item);
  }
}

function renderJobs(jobs) {
  const list = $("jobList");
  list.replaceChildren();
  $("jobCount").textContent = String(jobs.length);
  if (!jobs.length) {
    list.append(element("div", "muted-empty", "还没有职位记录。"));
    return;
  }
  for (const job of jobs) {
    const button = element("button", "job-item");
    button.type = "button";
    const main = element("div", "job-main");
    main.append(element("strong", "", `${job.title || "未注明职位"} — ${job.employer || "未注明雇主"}`), element("small", "", `ID ${job.job_id}`));
    button.append(main, element("span", "job-status", statusLabels[job.status] || job.status || "已准备"));
    button.addEventListener("click", async () => {
      if (!canLeaveReview()) return;
      try {
        const result = await api(`/api/packet?id=${encodeURIComponent(job.job_id)}`);
        showPacket(result.job, result.packet, true, result.review);
      } catch (error) {
        showNotice(error.message, true);
      }
    });
    list.append(button);
  }
}

async function refreshState() {
  const state = await api("/api/state");
  const notice = $("keyNotice");
  notice.className = `notice ${state.api_key_ready ? "ready" : "missing"}`;
  notice.textContent = state.api_key_ready
    ? "模型密钥已在本地服务中配置。生成新职位审阅包会产生 API 费用。"
    : "尚未配置 OPENAI_API_KEY。仍可探索简历方向、浏览已有结果；生成新职位前请在启动服务的终端配置密钥。";
  renderQueue(state.queue);
  renderJobs(state.jobs);
}

async function prepare(event) {
  event.preventDefault();
  if (!canLeaveReview()) return;
  const button = $("prepareButton");
  button.disabled = true;
  button.firstElementChild.textContent = "正在准备，请稍候…";
  $("feedbackNotice").hidden = true;
  try {
    const payload = {
      ...await candidatePayload(),
      source_type: sourceMode(),
      url: $("jobUrl").value,
      posting_text: $("postingText").value,
    };
    if (confirmedRoles !== null) {
      payload.confirmed_roles = confirmedRoles;
      payload.direction_fingerprint = directionFingerprint;
    }
    const result = await api("/api/prepare", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Job-Agent": "local-ui"},
      body: JSON.stringify(payload),
    });
    showPacket(result.job, result.packet, result.duplicate, result.review);
    showNotice(result.duplicate ? "这个职位已在 tracker 中，已打开原有审阅包；没有再次调用模型。" : "审阅包已生成。请逐项核对原始职位页面与履历事实。");
    await refreshState();
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = "生成审阅包";
  }
}

async function saveStatus() {
  if (!activeJob) return;
  const status = $("statusSelect").value;
  try {
    const result = await api("/api/feedback", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Job-Agent": "local-ui"},
      body: JSON.stringify({job_id: activeJob.job_id, status}),
    });
    activeJob = result.job;
    showNotice("本地 tracker 已更新。此操作没有向雇主发送申请。");
    await refreshState();
  } catch (error) {
    showNotice(error.message, true);
  }
}

async function saveReview() {
  if (!activeJob) return;
  const button = $("saveReview");
  const jobId = activeJob.job_id;
  const fields = {draft: $("editedDraft").value, notes: $("reviewNotes").value, checks: reviewChecks()};
  button.disabled = true;
  try {
    const result = await api("/api/review", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Job-Agent": "local-ui"},
      body: JSON.stringify({
        job_id: jobId,
        ...fields,
        base_revision: activeReviewRevision,
      }),
    });
    if (activeJob?.job_id !== jobId) return;
    activeReviewRevision = result.review.revision;
    reviewDirty = fields.draft !== $("editedDraft").value || fields.notes !== $("reviewNotes").value ||
      JSON.stringify(fields.checks) !== JSON.stringify(reviewChecks());
    $("reviewSavedAt").textContent = reviewDirty
      ? "先前版本已保存；当前仍有未保存的修改。"
      : `已保存于 ${result.review.saved_at}；原始生成包保持不变。`;
    updateReviewProgress();
    showNotice(reviewDirty ? "先前版本已保存，请保存当前修改后再导出。" : "人工审阅已保存在本机。没有向雇主发送任何内容。");
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    button.disabled = false;
  }
}

function downloadText(name, contents, mime = "text/markdown") {
  const blob = new Blob([contents], {type: `${mime};charset=utf-8`});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadPacket() {
  if (!activePacket || !activeJob) return;
  downloadText(`${activeJob.job_id}-generated.md`, activePacket);
}

function downloadReviewed() {
  if (!activeJob) return;
  const checks = reviewChecks();
  const lines = [
    `# Personal review worksheet — ${activeJob.title || "Untitled role"}`,
    "", `Job ID: ${activeJob.job_id}`,
    "This is a local working draft, not an application or proof of eligibility.",
    "", "## My edited application paragraph", "", $("editedDraft").value || "(Not written)",
    "", "## My manual checks", "",
    `- [${checks.posting_status ? "x" : " "}] I checked whether the employer posting is still accepting applications.`,
    `- [${checks.term_and_dates ? "x" : " "}] I verified the term and dates against the employer posting.`,
    `- [${checks.resume_and_draft ? "x" : " "}] I verified resume and draft claims against my own evidence.`,
    "", "## Private notes — do not send to an employer", "", $("reviewNotes").value || "(None)",
    "", "## Original generated packet for reference", "", activePacket,
  ];
  downloadText(`${activeJob.job_id}-my-review.md`, lines.join("\n"));
}

async function downloadApplication() {
  if (!activeJob || $("downloadApplication").disabled) return;
  const jobId = activeJob.job_id;
  const revision = activeReviewRevision;
  const button = $("downloadApplication");
  button.disabled = true;
  try {
    const result = await api("/api/export", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Job-Agent": "local-ui"},
      body: JSON.stringify({job_id: jobId, base_revision: revision}),
    });
    if (activeJob?.job_id !== jobId || reviewDirty || activeReviewRevision !== revision) return;
    downloadText(result.filename, result.text, "text/plain");
    showNotice("已请求下载申请段落，仅包含已保存的正文。请自行提交并在提交后记录申请状态。");
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    updateReviewProgress();
  }
}

document.querySelectorAll('input[name="sourceType"]').forEach((radio) => radio.addEventListener("change", syncSourceMode));
$("resumeFile").addEventListener("change", () => { $("resumeFileName").textContent = $("resumeFile").files[0]?.name || "尚未选择文件"; invalidateDirections(); });
$("resumeText").addEventListener("input", invalidateDirections);
$("profileFile").addEventListener("change", () => { $("profileFileName").textContent = $("profileFile").files[0]?.name || "未提供则不假设偏好"; invalidateDirections(); });
$("suggestDirections").addEventListener("click", suggestDirections);
$("confirmDirections").addEventListener("click", confirmDirections);
$("directionRoles").addEventListener("input", () => {
  confirmedRoles = null;
  $("directionSearch").hidden = true;
  $("directionStatus").textContent = "方向有未确认的修改；请再次点击“确认这些方向”。";
});
$("prepareForm").addEventListener("submit", prepare);
$("saveStatus").addEventListener("click", saveStatus);
$("saveReview").addEventListener("click", saveReview);
$("downloadPacket").addEventListener("click", downloadPacket);
$("downloadReviewed").addEventListener("click", downloadReviewed);
$("downloadApplication").addEventListener("click", downloadApplication);
$("editedDraft").addEventListener("input", () => { $("checkClaims").checked = false; });
for (const id of ["editedDraft", "reviewNotes", "checkPosting", "checkTerm", "checkClaims"]) {
  $(id).addEventListener("input", markReviewDirty);
  $(id).addEventListener("change", markReviewDirty);
}
syncSourceMode();
refreshState().catch((error) => showNotice(error.message, true));
