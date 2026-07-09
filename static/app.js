const state = {
  data: null,
  payload: {},
  stats: null,
  filteredWorkers: [],
  selectedWorker: "",
  previewTab: "journal",
  formStep: 0,
  photoAttachments: [],
  certificateAttachments: [],
  safetySignature: null,
  siteSignature: null,
};

const $ = (id) => document.getElementById(id);
const FORM_STEP_COUNT = 4;
const COURSE_TONES = {
  "정기교육": "regular",
  "채용시교육": "hire",
  "작업내용 변경교육": "change",
  "특별교육": "special",
  "관리감독자": "supervisor",
  "특수형태근로종사자": "special-worker",
  "물질안전보건자료": "msds",
  "소음/난청": "noise",
  "혹서기 온열질환": "heat",
};
const TARGET_DISPLAY_OVERRIDES = {
  "50-2": "2)그 밖의 근로자 - 가) 판매업무에 직접 종사하는 근로자",
  "50-3": "2)그 밖의 근로자 - 나) 판매업무에 직접 종사하는 근자외의 근로자",
  "71": "특수형태근로종사자 최초 노무 제공 시 교육 - 단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우",
  "1-39)71)": "특수형태근로종사자 특별교육 - 단기간 작업 또는 간헐적 작업에 노무를 제공하는 경우",
};
const CONTEXT_TARGET_SHEETS = new Set([
  "51-1", "51-2", "52-1", "52-2",
  "1-39(1)", "1-39(2)", "1-39(3)", "1-39(4)",
  "1-39(2-1)", "1-39(2-2)", "1-39(2-3)",
]);

function html(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, body) {
  const options = body ? {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(body),
  } : {};
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

function fillSelect(id, values, blank = false) {
  const select = $(id);
  select.innerHTML = "";
  if (blank) select.add(new Option("", ""));
  values.forEach((value) => select.add(new Option(value, value)));
}

function fillCourseSelect() {
  const select = $("course");
  select.innerHTML = "";
  const groups = new Map();
  state.data.courses.forEach((course) => {
    if (!groups.has(course.category)) groups.set(course.category, []);
    groups.get(course.category).push(course);
  });
  groups.forEach((courses, category) => {
    const group = document.createElement("optgroup");
    group.label = category;
    courses.forEach((course) => {
      const label = courseOptionLabel(course);
      const option = new Option(label, course.sheet);
      option.title = label;
      option.dataset.course = JSON.stringify(course);
      option.dataset.tone = courseTone(course.category);
      group.append(option);
    });
    select.add(group);
  });
}

function courseOptionLabel(course) {
  const taskLabel = courseTaskLabel(course);
  const pieces = [course.sheet, course.name, courseTargetDisplay(course)]
    .map((value) => String(value || "").trim())
    .filter(Boolean);
  if (taskLabel) pieces.push(`대상작업 ${taskLabel}`);
  return pieces.filter((value, index) => pieces.indexOf(value) === index).join(" · ");
}

function courseTargetDisplay(course) {
  const sheet = String(course?.sheet || "").trim();
  const displayTarget = String(course?.display_target ?? course?.displayTarget ?? "").trim();
  if (displayTarget) return displayTarget;
  const target = String(course?.course_target ?? course?.courseTarget ?? course?.target ?? "").trim();
  if (TARGET_DISPLAY_OVERRIDES[sheet]) return TARGET_DISPLAY_OVERRIDES[sheet];
  if (course?.name === "가. 정기교육" && target === "가) 판매업무에 직접 종사하는 근로자") {
    return TARGET_DISPLAY_OVERRIDES["50-2"];
  }
  if (course?.name === "가. 정기교육" && target === "나) 판매업무에 직접 종사하는 근자외의 근로자") {
    return TARGET_DISPLAY_OVERRIDES["50-3"];
  }
  return target;
}

function courseTargetUiDisplay(course) {
  const sheet = String(course?.sheet || "").trim();
  const name = String(course?.name ?? course?.course_name ?? course?.courseName ?? "").trim();
  const target = courseTargetDisplay(course);
  if (!target || !name || target.includes(name) || !CONTEXT_TARGET_SHEETS.has(sheet)) return target;
  return `${name} - ${target}`;
}

function courseDisplayName(row) {
  const name = String(row?.course_name ?? row?.courseName ?? row?.name ?? "").trim();
  const target = courseTargetDisplay(row);
  if (target && target !== name) return name ? `${name} - ${target}` : target;
  return name || target || "-";
}

function selectedCourse() {
  const option = $("course").selectedOptions[0];
  return option ? JSON.parse(option.dataset.course) : state.data.courses[0];
}

function selectedTask() {
  return state.data.specialTasks.find((task) => task.code === $("specialTask").value) || state.data.specialTasks[0];
}

function selectedTask2() {
  return state.data.specialTasks.find((task) => task.code === $("specialTask2").value) || state.data.specialTasks[1] || state.data.specialTasks[0];
}

function contentForCourse(course = selectedCourse()) {
  return course.template === "special" || course.template === "dual_special"
    ? selectedTask()
    : state.data.specialTasks.find((row) => row.code === course.content_code) || {};
}

function contentCodes(course = selectedCourse()) {
  return String(course.content_code || "").split(",").map((code) => code.trim()).filter(Boolean);
}

function courseTaskLabel(course = selectedCourse()) {
  if (!course || !["special", "dual_special"].includes(course.template)) return "";
  return contentCodes(course)
    .map((code) => state.data.specialTasks.find((task) => task.code === code)?.task_name || "")
    .filter(Boolean)
    .join(" / ");
}

function courseTone(category) {
  return COURSE_TONES[category] || "default";
}

function updateCourseDisplay(course = selectedCourse()) {
  const select = $("course");
  const taskLabel = courseTaskLabel(course);
  const targetLabel = courseTargetDisplay(course);
  const targetUiLabel = courseTargetUiDisplay(course);
  const chips = [
    `<span class="course-chip course-${courseTone(course.category)}">${html(course.category || "교육")}</span>`,
    `<span class="course-chip">법정 ${html(course.legal_hours || "-")}</span>`,
    `<span class="course-chip">${course.template === "dual_special" ? "특별 2종" : course.template === "special" ? "특별 양식" : "일반 양식"}</span>`,
    `<span class="course-chip course-chip-target">교육대상 ${html(targetUiLabel || "-")}</span>`,
  ];
  if (taskLabel) {
    chips.push(`<span class="course-chip course-chip-target course-chip-task">대상작업 ${html(taskLabel)}</span>`);
  }
  select.className = `course-select course-${courseTone(course.category)}`;
  $("legalHoursHint").textContent = `법정교육시간: ${course.legal_hours || "-"}`;
  $("courseSummary").innerHTML = chips.join("");
  select.title = [targetUiLabel || targetLabel, taskLabel && `대상작업 ${taskLabel}`].filter(Boolean).join("\n");
}

function updateSavePathHelp() {
  const value = $("saveDirectory").value.trim();
  $("savePathHelp").textContent = value
    ? `저장 위치: ${value}`
    : "경로를 입력하면 저장 시 PDF가 함께 생성됩니다. 비워두면 DB 기록만 저장합니다.";
}

function captionLines(id) {
  return $(id).value.split(/\r?\n/).map((line) => line.trim());
}

function attachmentsWithCaptions(items, captionsId) {
  const captions = captionLines(captionsId);
  return items.map((item, index) => ({
    name: item.name,
    dataUrl: item.dataUrl,
    caption: captions[index] || item.name,
  }));
}

function readImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, dataUrl: String(reader.result || "") });
    reader.onerror = () => reject(reader.error || new Error("파일을 읽지 못했습니다."));
    reader.readAsDataURL(file);
  });
}

async function readImageFiles(input, targetKey) {
  const files = Array.from(input.files || []).filter((file) => file.type.startsWith("image/"));
  state[targetKey] = await Promise.all(files.map(readImageFile));
  updateAttachmentHelp();
  renderPreview();
}

async function readSignatureFile(input, targetKey) {
  const file = Array.from(input.files || []).find((item) => item.type.startsWith("image/"));
  state[targetKey] = file ? await readImageFile(file) : null;
  updateSignatureHelp();
  renderPreview();
}

function updateAttachmentHelp() {
  const photos = state.photoAttachments.length;
  const certificates = state.certificateAttachments.length;
  $("attachmentHelp").textContent = photos || certificates
    ? `교육사진 ${photos}장, 기초이수증 ${certificates}장`
    : "첨부 파일 없음";
}

function updateSignatureHelp() {
  const names = [];
  if (state.safetySignature) names.push("안전관리자");
  if (state.siteSignature) names.push("현장소장");
  $("signatureHelp").textContent = names.length ? `${names.join(", ")} 서명 적용` : "서명 이미지 없음";
}

function readPayload() {
  const course = selectedCourse();
  const task = contentForCourse(course);
  const h1 = Number($("session1Hours").value || 0);
  const h2 = Number($("session2Hours").value || 0);
  const attendees = $("attendees").value.split(/\r?\n/).filter((line) => line.trim()).length;
  return {
    projectName: $("projectName").value,
    saveDirectory: $("saveDirectory").value,
    date: $("date").value,
    sheet: course.sheet,
    courseName: course.name,
    category: course.category,
    target: course.target,
    displayTarget: courseTargetDisplay(course),
    legalHours: course.legal_hours,
    template: course.template,
    contentCode: course.content_code,
    headcount: $("headcount").value,
    attendeeCount: attendees || $("headcount").value,
    trades: [$("trade0").value, $("trade1").value, $("trade2").value, $("trade3").value, $("trade4").value].filter(Boolean),
    session1Start: $("session1Start").value,
    session1Hours: $("session1Hours").value,
    session2Start: $("session2Start").value,
    session2Hours: $("session2Hours").value,
    totalHours: h1 + h2,
    instructor: $("instructor").value,
    place: $("place").value,
    method: $("method").value,
    material: $("material").value,
    taskName: task.task_name || course.name,
    taskName2: course.template === "dual_special" ? selectedTask2().task_name : "",
    content: task.content || "",
    content2: course.template === "dual_special" ? selectedTask2().content || "" : "",
    extraContent: $("extraContent").value,
    attendees: $("attendees").value,
    approvalSignatures: {
      safety: state.safetySignature,
      site: state.siteSignature,
    },
    photoAttachments: attachmentsWithCaptions(state.photoAttachments, "photoCaptions"),
    certificateAttachments: attachmentsWithCaptions(state.certificateAttachments, "certificateCaptions"),
  };
}

async function renderPreview() {
  state.payload = readPayload();
  const { html } = await api("/api/render-report", { ...state.payload, renderScope: state.previewTab });
  $("preview").innerHTML = html;
  updatePreviewTabs();
  updateDraftStrip();
}

function updatePreviewTabs() {
  const tabLabels = {
    journal: "교육일지",
    photos: `교육사진대지 (${state.photoAttachments.length})`,
    certificates: `기초이수증 (${state.certificateAttachments.length})`,
  };
  document.querySelectorAll("[data-preview-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.previewTab === state.previewTab);
    button.textContent = tabLabels[button.dataset.previewTab] || button.textContent;
  });
  const labels = {
    journal: state.payload.template === "dual_special" ? "A4 특별 2종 묶음 양식" : state.payload.template === "special" ? "A4 2페이지 특별교육 양식" : "A4 1페이지 일반교육 양식",
    photos: "A4 교육사진대지",
    certificates: "A4 기초이수증 사진대지",
  };
  $("previewMeta").textContent = labels[state.previewTab] || labels.journal;
}

function setPreviewTab(tab) {
  state.previewTab = tab;
  renderPreview();
}

function setFormStep(step) {
  state.formStep = Math.max(0, Math.min(FORM_STEP_COUNT - 1, Number(step) || 0));
  $("reportForm").dataset.step = String(state.formStep);
  document.querySelectorAll("[data-form-step]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.formStep) === state.formStep);
  });
  $("formStepMeta").textContent = `${state.formStep + 1} / ${FORM_STEP_COUNT}`;
  $("prevFormStep").disabled = state.formStep === 0;
  $("nextFormStep").disabled = state.formStep === FORM_STEP_COUNT - 1;
  $("nextFormStep").textContent = state.formStep === FORM_STEP_COUNT - 1 ? "마침" : "다음";
}

function moveFormStep(offset) {
  setFormStep(state.formStep + offset);
}

function updateDraftStrip() {
  const payload = state.payload || readPayload();
  const course = state.data.courses.find((item) => item.sheet === payload.sheet);
  const attendeeCount = payload.attendees.split(/\r?\n/).filter((line) => line.trim()).length;
  const draftCourse = payload.courseName || "-";
  const draftTarget = courseTargetUiDisplay(course || payload) || "-";
  $("draftCourse").textContent = draftCourse;
  $("draftCourse").title = draftCourse;
  $("draftTarget").textContent = draftTarget;
  $("draftTarget").title = draftTarget;
  $("draftAttendees").textContent = `${attendeeCount}명`;
  $("draftHours").textContent = `${payload.totalHours || 0}시간`;
  $("draftTemplate").textContent = payload.template === "dual_special" ? "특별 2종" : payload.template === "special" ? "특별 2페이지" : "일반 1페이지";
  $("attendeeHelp").textContent = `현재 참석자 ${attendeeCount}명, 저장 시 근로자별 이수 기록에 자동 누적됩니다.`;
}

function applyCourse() {
  const course = selectedCourse();
  updateCourseDisplay(course);
  document.body.classList.toggle("is-special", course.template === "special" || course.template === "dual_special");
  document.body.classList.toggle("is-dual-special", course.template === "dual_special");
  if (course.template === "special" || course.template === "dual_special") {
    const codes = contentCodes(course);
    const task = state.data.specialTasks.find((row) => row.code === (codes[0] || course.content_code)) || state.data.specialTasks[0];
    $("specialTask").value = task.code;
    if (course.template === "dual_special") {
      const task2 = state.data.specialTasks.find((row) => row.code === (codes[1] || "")) || state.data.specialTasks[1] || task;
      $("specialTask2").value = task2.code;
    }
  }
  updateContentPreview();
  renderPreview();
}

function updateContentPreview() {
  const task = contentForCourse();
  if (selectedCourse().template === "dual_special") {
    const task2 = selectedTask2();
    $("contentPreview").innerHTML = `
      <strong>1. ${html(task.task_name || "")}</strong><br>${html(task.content || "DB 설정에서 교육내용을 입력하세요.").replaceAll("\n", "<br>")}
      <hr>
      <strong>2. ${html(task2.task_name || "")}</strong><br>${html(task2.content || "DB 설정에서 교육내용을 입력하세요.").replaceAll("\n", "<br>")}
    `;
    return;
  }
  $("contentPreview").innerHTML = html(task.content || "DB 설정에서 교육내용을 입력하세요.").replaceAll("\n", "<br>");
}

function loadDefaults() {
  const options = state.data.options;
  fillCourseSelect();
  ["specialTask", "specialTask2"].forEach((id) => {
    fillSelect(id, state.data.specialTasks.map((row) => row.code), false);
    Array.from($(id).options).forEach((option) => {
      const task = state.data.specialTasks.find((row) => row.code === option.value);
      option.textContent = task ? `${task.code}. ${task.task_name}` : option.value;
    });
  });
  ["trade0", "trade1", "trade2", "trade3", "trade4"].forEach((id) => fillSelect(id, options.trade, true));
  ["session1Start", "session2Start"].forEach((id) => fillSelect(id, options.time, true));
  fillSelect("method", options.method);
  fillSelect("place", options.place);
  fillSelect("instructor", options.instructor);

  $("projectName").value = state.data.settings.projectName || "";
  $("saveDirectory").value = state.data.settings.saveDirectory || "";
  updateSavePathHelp();
  $("date").value = new Date().toISOString().slice(0, 10);
  $("headcount").value = "3";
  $("trade0").value = options.trade[0] || "";
  $("session1Start").value = options.time[1] || options.time[0] || "";
  $("session1Hours").value = "1";
  $("session2Hours").value = "";
  $("material").value = "자체 교안";
  $("extraContent").value = "•";
  $("attendees").value = "홍길동\n김철수\n이영희";
  $("photoCaptions").value = "";
  $("certificateCaptions").value = "";
  state.photoAttachments = [];
  state.certificateAttachments = [];
  state.safetySignature = null;
  state.siteSignature = null;
  updateSignatureHelp();
  updateAttachmentHelp();
  applyCourse();
}

function loadSettingsForm() {
  $("settingProjectName").value = state.data.settings.projectName || "";
  $("settingTrade").value = state.data.options.trade.join("\n");
  $("settingTime").value = state.data.options.time.join("\n");
  $("settingMethod").value = state.data.options.method.join("\n");
  $("settingPlace").value = state.data.options.place.join("\n");
  $("settingInstructor").value = state.data.options.instructor.join("\n");
  renderCourseEditor();
  renderContentEditor();
}

async function saveSettings() {
  state.data = await api("/api/settings", {
    settings: { projectName: $("settingProjectName").value },
    options: {
      trade: $("settingTrade").value.split(/\r?\n/),
      time: $("settingTime").value.split(/\r?\n/),
      method: $("settingMethod").value.split(/\r?\n/),
      place: $("settingPlace").value.split(/\r?\n/),
      instructor: $("settingInstructor").value.split(/\r?\n/),
    },
    courses: readCourseEditor(),
    educationContent: readContentEditor(),
  });
  loadDefaults();
  loadSettingsForm();
  alert("DB 설정을 저장했습니다.");
}

async function saveDocumentSettings() {
  state.data = await api("/api/settings", {
    settings: {
      saveDirectory: $("saveDirectory").value,
    },
  });
  updateSavePathHelp();
  alert("문서 설정을 저장했습니다.");
}

function renderCourseEditor() {
  $("courseEditor").innerHTML = state.data.courses.map((course) => `
    <div class="db-row course-row">
      <label>시트<input data-field="sheet" value="${html(course.sheet)}"></label>
      <label>구분<input data-field="category" value="${html(course.category)}"></label>
      <label>교육명<input data-field="name" value="${html(course.name)}"></label>
      <label class="target-wide">원본 교육대상<textarea data-field="target" rows="4">${html(course.target)}</textarea></label>
      <label class="target-wide">출력 교육대상<textarea data-field="display_target" rows="4">${html(course.display_target || courseTargetDisplay(course))}</textarea></label>
      <label>법정교육시간<input data-field="legal_hours" value="${html(course.legal_hours)}"></label>
      <label>양식<select data-field="template"><option value="regular">일반</option><option value="special">특별</option><option value="dual_special">특별 2종</option></select></label>
      <label>내용코드<input data-field="content_code" value="${html(course.content_code)}"></label>
    </div>
  `).join("");
  document.querySelectorAll(".course-row").forEach((row, index) => {
    row.querySelector('[data-field="template"]').value = state.data.courses[index].template || "regular";
  });
}

function renderContentEditor() {
  $("contentEditor").innerHTML = state.data.specialTasks.map(contentRowHtml).join("");
}

function contentRowHtml(row) {
  return `
    <div class="db-row content-row">
      <label>코드<input data-field="code" value="${html(row.code)}"></label>
      <label>작업명·교육명<input data-field="task_name" value="${html(row.task_name)}"></label>
      <label class="wide">교육내용<textarea data-field="content" rows="5">${html(row.content)}</textarea></label>
    </div>
  `;
}

function readCourseEditor() {
  return Array.from(document.querySelectorAll(".course-row")).map((row) => ({
    sheet: row.querySelector('[data-field="sheet"]').value,
    category: row.querySelector('[data-field="category"]').value,
    name: row.querySelector('[data-field="name"]').value,
    target: row.querySelector('[data-field="target"]').value,
    display_target: row.querySelector('[data-field="display_target"]').value,
    legal_hours: row.querySelector('[data-field="legal_hours"]').value,
    template: row.querySelector('[data-field="template"]').value,
    content_code: row.querySelector('[data-field="content_code"]').value,
  }));
}

function readContentEditor() {
  return Array.from(document.querySelectorAll(".content-row")).map((row) => ({
    code: row.querySelector('[data-field="code"]').value,
    task_name: row.querySelector('[data-field="task_name"]').value,
    content: row.querySelector('[data-field="content"]').value,
  }));
}

async function saveReport() {
  const payload = readPayload();
  const result = await api("/api/save-report", payload);
  if (result.exportPath) {
    alert(`저장했습니다.\n기록 번호: ${result.id}\nPDF: ${result.exportPath}`);
  } else if (result.exportError) {
    alert(`DB에는 저장했습니다.\n기록 번호: ${result.id}\nPDF 저장 실패: ${result.exportError}`);
  } else {
    alert(`저장했습니다. 기록 번호: ${result.id}`);
  }
  loadRecords();
  loadStats();
}

async function loadRecords() {
  const { reports } = await api("/api/reports");
  $("recordList").innerHTML = reports.length
    ? reports.map((row) => `<div class="record-row"><strong>${html(row.courseDisplayName || row.title)}</strong><span>교육인원 ${html(row.educationCount || "0")}명</span><small>${html(row.created_at)}</small></div>`).join("")
    : "<div class=\"record-row\"><strong>저장된 기록이 없습니다.</strong><small></small></div>";
}

async function clearRecords() {
  if (!confirm("저장된 교육일지 기록과 근로자 이수 기록을 모두 초기화할까요?")) return;
  const result = await api("/api/clear-reports", { confirm: true });
  await loadRecords();
  await loadStats();
  alert(`초기화했습니다.\n저장 기록 ${result.deletedReports}건\n근로자 이수 기록 ${result.deletedWorkerRecords}건`);
}

async function loadStats() {
  const data = await api("/api/worker-stats");
  state.stats = data;
  $("statReports").textContent = data.summary.total_reports || 0;
  $("statWorkers").textContent = data.summary.total_workers || 0;
  $("statCompletions").textContent = data.summary.total_completions || 0;
  $("statHours").textContent = `${data.summary.total_hours || 0}시간`;
  filterWorkerStats();
  $("courseStatsRows").innerHTML = data.courses.length
    ? data.courses.map((row) => `<tr><td>${html(courseDisplayName(row))}</td><td>${row.worker_count}</td><td>${row.completion_count}</td><td>${row.total_hours}</td></tr>`).join("")
    : "<tr><td colspan=\"4\">교육과정 통계가 없습니다.</td></tr>";
  $("monthlyStatsRows").innerHTML = data.monthly.length
    ? data.monthly.map((row) => `<tr><td>${html(row.month)}</td><td>${row.report_count}</td><td>${row.worker_count}</td><td>${row.completion_count}</td><td>${row.total_hours}</td></tr>`).join("")
    : "<tr><td colspan=\"5\">월별 기록이 없습니다.</td></tr>";
}

function filterWorkerStats() {
  if (!state.stats) return;
  const query = $("workerSearch").value.trim();
  state.filteredWorkers = state.stats.workers.filter((row) => !query || row.worker_name.includes(query));
  $("workerStatsRows").innerHTML = state.filteredWorkers.length
    ? state.filteredWorkers.map((row, index) => `<tr><td>${html(row.worker_name)}</td><td>${row.completion_count}</td><td>${row.total_hours}</td><td>${html(row.last_date)}</td><td>${html(row.courses)}</td><td><button type="button" data-worker-index="${index}">조회</button></td></tr>`).join("")
    : "<tr><td colspan=\"6\">검색된 근로자가 없습니다.</td></tr>";
  if (!state.filteredWorkers.some((row) => row.worker_name === state.selectedWorker)) {
    state.selectedWorker = state.filteredWorkers[0]?.worker_name || "";
  }
  renderWorkerDetail(state.selectedWorker);
}

function renderWorkerDetail(workerName) {
  if (!state.stats || !workerName) {
    $("workerDetailTitle").textContent = "근로자 개별 조회";
    $("workerDetailSummary").textContent = "근로자를 선택하면 개인 이수 내역이 표시됩니다.";
    $("workerDetailRows").innerHTML = "<tr><td colspan=\"6\">조회할 근로자가 없습니다.</td></tr>";
    return;
  }
  const records = state.stats.records.filter((row) => row.worker_name === workerName);
  const totalHours = records.reduce((sum, row) => sum + Number(row.completed_hours || 0), 0);
  $("workerDetailTitle").textContent = `${workerName} 이수 내역`;
  $("workerDetailSummary").textContent = `총 ${records.length}건, ${totalHours}시간 이수`;
  $("workerDetailRows").innerHTML = records.length
    ? records.map((row) => `<tr><td>${html(row.training_date)}</td><td>${html(courseDisplayName(row))}</td><td>${html(row.category)}</td><td>${row.completed_hours}</td><td>${html(row.legal_hours)}</td><td>${html(row.project_name)}</td></tr>`).join("")
    : "<tr><td colspan=\"6\">이수 기록이 없습니다.</td></tr>";
}

function switchView(view) {
  document.body.dataset.view = view;
  document.querySelectorAll(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${view}`));
  document.querySelectorAll(".nav-button").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  if (location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
  if (view === "records") loadRecords();
  if (view === "stats") loadStats();
}

function setSettingsStep(step) {
  const allowed = ["basic", "courses", "content"];
  const nextStep = allowed.includes(step) ? step : "basic";
  $("view-settings").dataset.settingsStep = nextStep;
  document.querySelectorAll("[data-settings-target]").forEach((button) => {
    const isActive = button.dataset.settingsTarget === nextStep;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function setStatsStep(step) {
  const allowed = ["workers", "detail", "courses", "monthly"];
  const nextStep = allowed.includes(step) ? step : "workers";
  $("view-stats").dataset.statsStep = nextStep;
  document.querySelectorAll("[data-stats-target]").forEach((button) => {
    const isActive = button.dataset.statsTarget === nextStep;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

async function start() {
  state.data = await api("/api/bootstrap");
  loadDefaults();
  loadSettingsForm();
  loadRecords();
  loadStats();
  document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  document.querySelectorAll("[data-settings-target]").forEach((button) => button.addEventListener("click", () => setSettingsStep(button.dataset.settingsTarget)));
  document.querySelectorAll("[data-stats-target]").forEach((button) => button.addEventListener("click", () => setStatsStep(button.dataset.statsTarget)));
  setSettingsStep($("view-settings").dataset.settingsStep);
  setStatsStep($("view-stats").dataset.statsStep);
  const initialView = location.hash.replace("#", "");
  if (["write", "document", "settings", "records", "stats"].includes(initialView)) switchView(initialView);
  else document.body.dataset.view = "write";
  $("course").addEventListener("change", applyCourse);
  $("specialTask").addEventListener("change", () => {
    updateContentPreview();
    renderPreview();
  });
  $("specialTask2").addEventListener("change", () => {
    updateContentPreview();
    renderPreview();
  });
  $("reportForm").addEventListener("input", renderPreview);
  $("reportForm").addEventListener("change", renderPreview);
  $("saveDirectory").addEventListener("input", updateSavePathHelp);
  document.querySelectorAll("[data-form-step]").forEach((button) => button.addEventListener("click", () => setFormStep(button.dataset.formStep)));
  $("prevFormStep").addEventListener("click", () => moveFormStep(-1));
  $("nextFormStep").addEventListener("click", () => moveFormStep(1));
  document.querySelectorAll("[data-preview-tab]").forEach((button) => button.addEventListener("click", () => setPreviewTab(button.dataset.previewTab)));
  $("safetySignatureFile").addEventListener("change", () => readSignatureFile($("safetySignatureFile"), "safetySignature").catch((error) => alert(error.message)));
  $("siteSignatureFile").addEventListener("change", () => readSignatureFile($("siteSignatureFile"), "siteSignature").catch((error) => alert(error.message)));
  $("photoFiles").addEventListener("change", () => readImageFiles($("photoFiles"), "photoAttachments").catch((error) => alert(error.message)));
  $("certificateFiles").addEventListener("change", () => readImageFiles($("certificateFiles"), "certificateAttachments").catch((error) => alert(error.message)));
  $("refreshPreview").addEventListener("click", renderPreview);
  $("printReport").addEventListener("click", () => window.print());
  $("saveReport").addEventListener("click", saveReport);
  $("saveDocumentSettings").addEventListener("click", saveDocumentSettings);
  $("saveSettings").addEventListener("click", saveSettings);
  $("reloadRecords").addEventListener("click", loadRecords);
  $("clearRecords").addEventListener("click", () => clearRecords().catch((error) => alert(error.message)));
  $("reloadStats").addEventListener("click", loadStats);
  $("workerSearch").addEventListener("input", filterWorkerStats);
  $("workerStatsRows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-worker-index]");
    if (!button) return;
    const row = state.filteredWorkers[Number(button.dataset.workerIndex)];
    state.selectedWorker = row ? row.worker_name : "";
    renderWorkerDetail(state.selectedWorker);
    setStatsStep("detail");
  });
  $("addContentRow").addEventListener("click", () => {
    state.data.specialTasks.push({ code: "", task_name: "", content: "" });
    renderContentEditor();
  });
  setFormStep(0);
}

start().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<main class="app-error"><h1>앱을 시작하지 못했습니다</h1><pre>${error.message}</pre></main>`;
});
