const CARD_VERSION = "0.3.36";
const DAYS = [
  ["monday", "Mo"],
  ["tuesday", "Di"],
  ["wednesday", "Mi"],
  ["thursday", "Do"],
  ["friday", "Fr"],
];

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const isSchulmanagerSensor = (stateObj) => {
  const entityId = stateObj?.entity_id || "";
  const attrs = stateObj?.attributes || {};
  return (
    entityId.startsWith("sensor.") &&
    (entityId.includes("schulmanager") || String(attrs.friendly_name || "").toLowerCase().includes("schulmanager"))
  );
};

const isTimetableEntity = (stateObj) => {
  const entityId = stateObj?.entity_id || "";
  const attrs = stateObj?.attributes || {};
  const friendlyName = String(attrs.friendly_name || "").toLowerCase();
  return (
    entityId.startsWith("sensor.") &&
    (attrs.week_details !== undefined ||
      attrs.week_rows !== undefined ||
      attrs.schedule_parser !== undefined ||
      entityId.includes("stundenplan_woche") ||
      friendlyName.includes("stundenplan woche"))
  );
};

const isHomeworkEntity = (stateObj) => {
  const entityId = stateObj?.entity_id || "";
  const attrs = stateObj?.attributes || {};
  const friendlyName = String(attrs.friendly_name || "").toLowerCase();
  return (
    entityId.startsWith("sensor.") &&
    (entityId.includes("homework") ||
      entityId.includes("hausaufgaben") ||
      friendlyName.includes("homework") ||
      friendlyName.includes("hausaufgaben")) &&
    !attrs.week_details &&
    !attrs.week_rows
  );
};

const minutesToTime = (minutes) => {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
};

const getLessonTime = (lesson) => {
  const n = Number(lesson);
  if (!Number.isFinite(n) || n < 1) return "";
  let start = 8 * 60 + (n - 1) * 45;
  if (n >= 3) start += 15;
  if (n >= 5) start += 20;
  if (n >= 7) start += 10;
  return `${minutesToTime(start)}-${minutesToTime(start + 45)}`;
};

const getPauseRow = (lesson, isToday) => {
  const n = Number(lesson);
  let time = "";
  let label = "";
  if (n === 2) { time = "09:30-09:45"; label = "Pause · 15 Min"; }
  else if (n === 4) { time = "11:15-11:35"; label = "Pause · 20 Min"; }
  else if (n === 6) { time = "13:05-13:15"; label = "Pause · 10 Min"; }
  else return "";

  const todayIndex = DAYS.findIndex(([key]) => isToday(key));
  const labelIndex = todayIndex >= 0 ? todayIndex : 0;

  const cells = DAYS.map(([key], i) => {
    const colClass = `day-col-${i % 2}`;
    const todayClass = isToday(key) ? " is-today" : "";
    const labelClass = i === labelIndex ? " pause-label" : "";
    return `<td class="${colClass}${todayClass}${labelClass}">${i === labelIndex ? label : ""}</td>`;
  }).join("");

  return `<tr class="pause-row"><td class="pause-time">${time}</td>${cells}</tr>`;
};

const formatDate = (isoDate) => {
  if (!isoDate) return "";
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
};

const formatUpdateTime = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const renderTitleRow = (title, stateObj) => {
  const updated = formatUpdateTime(stateObj?.attributes?.last_successful_update);
  return `
    <div class="title-row">
      <div class="card-title">${title}</div>
      ${updated ? `<div class="last-update">Aktualisiert ${escapeHtml(updated)}</div>` : ""}
    </div>
  `;
};

const fallbackToEntries = (value) => {
  const raw = String(value || "").trim();
  if (!raw || raw === "—") return [];

  return raw
    .split(/(?=\b\d+\.\s+)/g)
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((chunk) => {
      let text = chunk.replace(/^\d+\.\s*/, "").trim();
      const cancelled = /^ausgefallen\b/i.test(text);
      text = text.replace(/^ausgefallen\s+/i, "").trim();

      const parts = text.split(/\s+/).filter(Boolean);
      const roomStart = parts.findIndex((part, index) => {
        const next = parts[index + 1] || "";
        return /^[A-Z]$/.test(part) && /^-?\d/.test(next);
      });

      const beforeRoom = roomStart >= 0 ? parts.slice(0, roomStart) : parts;
      let room = roomStart >= 0 ? parts.slice(roomStart).join(" ") : "";
      let roomOld = "";
      const roomChange = room.match(/^(.+?)\s+\1\s*(?:->|→)\s*(.+)$/);
      if (roomChange) {
        roomOld = roomChange[1].trim();
        room = roomChange[2].trim();
      } else {
        const simpleRoomChange = room.match(/^(.+?)\s*(?:->|→)\s*(.+)$/);
        if (simpleRoomChange) {
          roomOld = simpleRoomChange[1].trim();
          room = simpleRoomChange[2].trim();
        }
      }

      return {
        subject: beforeRoom[0] || "",
        teacher: beforeRoom.slice(1).join(" "),
        room,
        room_old: roomOld,
        cancelled,
        room_changed: Boolean(roomOld) || /→|->/.test(room),
      };
    });
};

class SchulmanagerTimetableCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("schulmanager-timetable-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.entries(hass?.states || {}).find(([, stateObj]) =>
      isTimetableEntity(stateObj)
    )?.[0];
    return { entity: entity || "", title: "Stundenplan" };
  }

  setConfig(config) {
    this._config = { title: "Stundenplan", ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _renderEntry(entry) {
    const subject = escapeHtml(entry?.subject || "");
    const teacher = escapeHtml(entry?.teacher || "");
    const room = escapeHtml(entry?.room || "");
    const roomOld = escapeHtml(entry?.room_old || "");
    const subjectOld = escapeHtml(entry?.subject_old || "");
    const teacherOld = escapeHtml(entry?.teacher_old || "");
    const cancelled = Boolean(entry?.cancelled);
    const subjectChanged = Boolean(entry?.subject_changed);
    const teacherChanged = Boolean(entry?.teacher_changed);
    const roomChanged = Boolean(entry?.room_changed);
    const changed = Boolean(subjectChanged || teacherChanged || roomChanged);
    const badge = cancelled ? "Ausfall" : changed ? "Änderung" : "";
    const roomText = room
      ? `${roomOld && roomOld !== room ? `<span class="old-inline">${roomOld}</span> <span class="arrow">→</span> ` : ""}${room}`
      : "&nbsp;";

    if (!subject && !teacher && !room) return "";

    return `
      <div class="lesson-card ${cancelled ? "is-cancelled" : ""} ${changed ? "is-changed" : ""}">
        <div class="lesson-top">
          <div class="subject ${subjectChanged ? "changed-text" : ""}">
            ${subjectOld ? `<span class="old-inline">${subjectOld}</span> ` : ""}${subject}
          </div>
          ${teacher ? `<div class="teacher ${teacherChanged ? "changed-text" : ""}">${teacherOld ? `<span class="old-inline">${teacherOld}</span> ` : ""}${teacher}</div>` : ""}
        </div>
        <div class="lesson-bottom">
          ${badge ? `<div class="badge ${cancelled ? "cancelled" : "changed"}">${badge}</div>` : "<div></div>"}
          <div class="room ${roomChanged ? "changed-text" : ""}">${roomText}</div>
        </div>
      </div>
    `;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (!this._config || !this._hass) return;

    const entityId = this._config.entity;
    const stateObj = entityId ? this._hass.states[entityId] : undefined;
    const title = escapeHtml(this._config.title || "Stundenplan");

    if (!entityId) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="empty">Bitte einen Schulmanager-Stundenplan-Sensor auswählen.</div></ha-card>`;
      return;
    }

    if (!stateObj) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="empty">Entität nicht gefunden: ${escapeHtml(entityId)}</div></ha-card>`;
      return;
    }

    const attrs = stateObj.attributes || {};
    const weekDetails = attrs.week_details || {};
    const dayDates = attrs.day_dates || {};
    const fallbackRows = attrs.week_rows || [];
    const hasDetails = DAYS.some(([key]) => Array.isArray(weekDetails[key]) && weekDetails[key].length);
    const titleRow = renderTitleRow(title, stateObj);

    if (!hasDetails && !fallbackRows.length) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card>${titleRow}<div class="empty">Kein Stundenplan vorhanden.</div></ha-card>`;
      return;
    }

    const todayIso = new Date().toLocaleDateString("sv-SE");
    const isToday = (key) => dayDates[key] === todayIso;
    const lessonNumbers = hasDetails
      ? [
          ...new Set(
            DAYS.flatMap(([key]) =>
              (weekDetails[key] || [])
                .map((entry) => String(entry.lesson_number || "").trim())
                .filter(Boolean)
            )
          ),
        ].sort((a, b) => Number(a) - Number(b))
      : fallbackRows.map((row) => String(row.lesson || "").trim()).filter(Boolean);

    const headerCells = DAYS.map(([key, label], index) => {
      const dateLabel = formatDate(dayDates[key]);
      const todayClass = isToday(key) ? " is-today" : "";
      return `<th class="day-col-${index % 2}${todayClass}"><div class="day-header"><span>${label}</span>${dateLabel ? `<span class="date-label">${dateLabel}</span>` : ""}</div></th>`;
    }).join("");

    const bodyRows = lessonNumbers
      .map((lesson) => {
        const lessonTime = escapeHtml(getLessonTime(lesson));
        const cells = DAYS.map(([key, fallbackLabel], index) => {
          const className = (extra = "") => [`day-col-${index % 2}`, isToday(key) ? "is-today" : "", extra].filter(Boolean).join(" ");

          if (!hasDetails) {
            const row = fallbackRows.find((item) => String(item.lesson || "").trim() === lesson) || {};
            const fallbackEntries = fallbackToEntries(row[fallbackLabel]);
            if (!fallbackEntries.length) return `<td class="${className("empty-cell")}">—</td>`;
            return `<td class="${className()}">${fallbackEntries.map((entry) => this._renderEntry(entry)).join("")}</td>`;
          }

          const entries = (weekDetails[key] || [])
            .filter((entry) => String(entry.lesson_number || "").trim() === lesson)
            .sort((a, b) => Number(a.cell_index || 0) - Number(b.cell_index || 0));

          if (!entries.length) return `<td class="${className("empty-cell")}">—</td>`;
          return `<td class="${className()}">${entries.map((entry) => this._renderEntry(entry)).join("")}</td>`;
        }).join("");

        return `
          <tr>
            <td class="lesson-col">
              <div class="lesson-number">${escapeHtml(lesson)}</div>
              <div class="lesson-time">${lessonTime}</div>
            </td>
            ${cells}
          </tr>
        ${getPauseRow(lesson, isToday)}`;
      })
      .join("");

    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <ha-card>
        ${titleRow}
        <div class="timetable-wrapper" tabindex="0">
          <table class="timetable">
            <thead>
              <tr>
                <th class="lesson-col">Std</th>
                ${headerCells}
              </tr>
            </thead>
            <tbody>${bodyRows}</tbody>
          </table>
        </div>
      </ha-card>
    `;
  }

  _styles() {
    return `
      <style>
        :host {
          display: block;
          min-width: 0;
        }

        ha-card {
          padding: 16px;
          overflow: visible;
          text-align: left;
        }

        .title-row {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 14px;
          margin-bottom: 16px;
        }

        .card-title {
          min-width: 0;
          color: var(--primary-text-color);
          font-size: 24px;
          font-weight: 300;
          line-height: 1.2;
        }

        .last-update {
          flex: 0 0 auto;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 400;
          line-height: 1.2;
          opacity: 0.72;
          text-align: right;
          white-space: nowrap;
        }

        .timetable-wrapper {
          display: block;
          width: 100%;
          max-width: 100%;
          overflow-x: scroll;
          overflow-y: hidden;
          -webkit-overflow-scrolling: touch;
          overscroll-behavior-x: contain;
          touch-action: pan-x;
          scrollbar-width: thin;
          border: 1px solid rgba(var(--rgb-primary-text-color), 0.08);
          border-radius: 6px;
          background: rgba(var(--rgb-primary-text-color), 0.025);
          box-sizing: border-box;
        }

        .timetable-wrapper::-webkit-scrollbar {
          height: 8px;
        }

        .timetable-wrapper::-webkit-scrollbar-thumb {
          border-radius: 999px;
          background: rgba(var(--rgb-primary-text-color), 0.22);
        }

        .timetable {
          width: max(100%, 780px);
          min-width: 780px;
          border-collapse: collapse;
          table-layout: fixed;
          color: var(--primary-text-color);
          font-size: 14px;
        }

        .timetable th {
          padding: 9px 10px;
          border-bottom: 1px solid rgba(var(--rgb-primary-text-color), 0.08);
          color: var(--primary-text-color);
          font-weight: 700;
          text-align: left;
          white-space: nowrap;
        }

        .day-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          min-width: 0;
        }

        .date-label {
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 500;
          text-align: right;
        }

        .timetable th.day-col-0 {
          background: rgba(var(--rgb-primary-color), 0.10);
        }

        .timetable th.day-col-1 {
          background: rgba(var(--rgb-primary-color), 0.10);
        }

        .timetable th.is-today {
          position: relative;
          z-index: 2;
          background: rgba(var(--rgb-primary-color), 0.18);
          border-top: 2px solid rgba(var(--rgb-primary-color), 0.55);
          clip-path: inset(-3px -28px 0 -28px);
          box-shadow:
            5px 0 9px rgba(var(--rgb-primary-text-color), 0.20),
            -5px 0 9px rgba(var(--rgb-primary-text-color), 0.20);
        }

        .timetable td {
          padding: 10px;
          border-right: 1px solid rgba(var(--rgb-primary-text-color), 0.05);
          border-bottom: 1px solid rgba(var(--rgb-primary-text-color), 0.06);
          color: var(--secondary-text-color);
          vertical-align: top;
          line-height: 1.35;
          min-width: 0;
          max-width: 0;
          white-space: normal;
          overflow: hidden;
          overflow-wrap: anywhere;
        }

        .timetable td.day-col-0 {
          background: rgba(var(--rgb-primary-text-color), 0.018);
        }

        .timetable td.day-col-1 {
          background: rgba(var(--rgb-primary-color), 0.032);
        }

        .timetable td.is-today {
          position: relative;
          z-index: 2;
          background: rgba(var(--rgb-primary-color), 0.12);
          clip-path: inset(0 -28px);
          box-shadow:
            5px 0 9px rgba(var(--rgb-primary-text-color), 0.15),
            -5px 0 9px rgba(var(--rgb-primary-text-color), 0.15);
        }

        .timetable tr:last-child td.is-today {
          border-bottom: 2px solid rgba(var(--rgb-primary-color), 0.55);
          clip-path: inset(0 -28px 3px -28px);
          box-shadow:
            5px 0 9px rgba(var(--rgb-primary-text-color), 0.15),
            -5px 0 9px rgba(var(--rgb-primary-text-color), 0.15);
        }

        .timetable tr:last-child td {
          border-bottom: none;
        }

        .timetable th:last-child,
        .timetable td:last-child {
          border-right: none;
        }

        .lesson-col {
          width: 70px;
          text-align: center;
          color: var(--primary-text-color);
          font-weight: 700;
          background: rgba(var(--rgb-primary-color), 0.10);
          vertical-align: top;
        }

        .timetable th.lesson-col {
          color: var(--primary-color);
          background: rgba(var(--rgb-primary-color), 0.10);
          vertical-align: top;
        }

        .lesson-number {
          color: var(--primary-text-color);
          font-size: 18px;
          font-weight: 700;
          line-height: 1.1;
          text-align: center;
        }

        .lesson-time {
          margin-top: 3px;
          color: var(--secondary-text-color);
          font-size: 10px;
          font-weight: 400;
          line-height: 1.1;
          opacity: 0.72;
          text-align: center;
          white-space: nowrap;
        }

        .lesson-card {
          display: block;
          margin-bottom: 8px;
          padding: 8px 9px;
          border-radius: 5px;
          background: rgba(var(--rgb-primary-text-color), 0.028);
          min-width: 0;
          max-width: 100%;
          box-sizing: border-box;
          overflow: hidden;
        }

        .lesson-card:last-child {
          margin-bottom: 0;
        }

        .lesson-card.is-cancelled,
        .lesson-card.is-changed {
          background: rgba(var(--rgb-primary-text-color), 0.045);
        }

        .lesson-top,
        .lesson-bottom {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 8px;
          width: 100%;
          min-width: 0;
        }

        .lesson-top {
          margin-bottom: 4px;
        }

        .subject {
          flex: 1 1 auto;
          min-width: 0;
          color: var(--primary-text-color);
          font-size: 14px;
          font-weight: 700;
          line-height: 1.2;
          overflow-wrap: anywhere;
        }

        .teacher {
          flex: 0 0 auto;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 500;
          line-height: 1.2;
          opacity: 0.78;
          text-align: right;
          white-space: nowrap;
        }

        .lesson-bottom {
          color: var(--secondary-text-color);
          font-size: 11px;
          font-weight: 500;
          line-height: 1.25;
          opacity: 0.78;
        }

        .room {
          flex: 1 1 auto;
          min-width: 0;
          overflow-wrap: anywhere;
          text-align: right;
        }

        .changed-text {
          color: var(--warning-color);
          font-weight: 800;
          opacity: 1;
        }

        .arrow {
          color: var(--warning-color);
          font-weight: 800;
        }

        .old-inline {
          color: var(--secondary-text-color);
          font-weight: 500;
          text-decoration: line-through;
          opacity: 0.78;
        }

        .badge {
          flex: 0 0 auto;
          min-width: 0;
          padding: 2px 6px;
          border-radius: 4px;
          color: white;
          font-size: 9px;
          font-weight: 800;
          line-height: 1.2;
          text-align: center;
          text-transform: uppercase;
        }

        .badge.cancelled {
          background: var(--error-color);
        }

        .badge.changed {
          background: var(--warning-color);
          color: var(--primary-text-color);
        }

        .empty-cell {
          color: var(--disabled-text-color);
          text-align: center;
        }

        .pause-row td {
          padding: 6px 10px;
          border-bottom: 1px solid rgba(var(--rgb-primary-text-color), 0.05);
          background: rgba(var(--rgb-primary-color), 0.045);
          color: var(--secondary-text-color);
          font-size: 11px;
          line-height: 1.2;
          opacity: 0.82;
        }

        .pause-row td.pause-label {
          font-style: italic;
        }

        .pause-row td.is-today {
          background: rgba(var(--rgb-primary-color), 0.14);
          clip-path: inset(0 -28px);
          box-shadow:
            5px 0 9px rgba(var(--rgb-primary-text-color), 0.15),
            -5px 0 9px rgba(var(--rgb-primary-text-color), 0.15);
          opacity: 1;
        }

        .pause-time {
          width: 70px;
          background: rgba(var(--rgb-primary-color), 0.075);
          color: var(--secondary-text-color);
          font-size: 10px;
          text-align: center;
          white-space: nowrap;
        }

        .empty {
          padding: 14px;
          border-radius: 6px;
          background: rgba(var(--rgb-primary-text-color), 0.04);
          color: var(--secondary-text-color);
          text-align: left;
        }

        @media screen and (max-width: 700px) {
          ha-card {
            padding: 12px;
          }

          .timetable-wrapper {
            margin-right: -4px;
            padding-bottom: 4px;
          }

          .timetable {
            width: 720px;
            min-width: 720px;
            max-width: none;
            font-size: 13px;
          }

          .timetable th,
          .timetable td {
            padding: 9px 8px;
          }

          .lesson-col {
            width: 62px;
          }

          .lesson-card {
            padding: 7px;
          }

          .card-title {
            font-size: 19px;
          }

          .last-update {
            font-size: 10px;
          }
        }
      </style>
    `;
  }
}

class SchulmanagerHomeworkCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement("schulmanager-homework-card-editor");
  }

  static getStubConfig(hass) {
    const entity = Object.entries(hass?.states || {}).find(([, stateObj]) =>
      isHomeworkEntity(stateObj)
    )?.[0];
    return { entity: entity || "", title: "Hausaufgaben" };
  }

  setConfig(config) {
    this._config = { title: "Hausaufgaben", ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _renderEntry(entry) {
    const raw = String(entry ?? "");
    const index = raw.indexOf(":");
    const subject = index >= 0 ? escapeHtml(raw.substring(0, index).trim()) : escapeHtml(raw.trim());
    const task = index >= 0 ? escapeHtml(raw.substring(index + 1).trim()).replaceAll("\n", "<br>") : "";

    return `
      <article class="homework-entry">
        <div class="subject">${subject}</div>
        ${task ? `<div class="task">${task}</div>` : ""}
      </article>
    `;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (!this._config || !this._hass) return;

    const entityId = this._config.entity;
    const stateObj = entityId ? this._hass.states[entityId] : undefined;
    const title = escapeHtml(this._config.title || "Hausaufgaben");

    if (!entityId) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="empty">Bitte einen Schulmanager-Hausaufgaben-Sensor auswählen.</div></ha-card>`;
      return;
    }

    if (!stateObj) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card><div class="empty">Entität nicht gefunden: ${escapeHtml(entityId)}</div></ha-card>`;
      return;
    }

    const items = Array.isArray(stateObj.attributes?.items) ? stateObj.attributes.items : [];
    const titleRow = renderTitleRow(title, stateObj);
    if (!items.length) {
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card>${titleRow}<div class="empty">Keine Hausaufgaben vorhanden.</div></ha-card>`;
      return;
    }

    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <ha-card>
        ${titleRow}
        <div class="homework-timeline">
          ${items.map((item) => this._renderDay(item)).join("")}
        </div>
      </ha-card>
    `;
  }

  _renderDay(item) {
    const date = new Date(`${item?.date || ""}T00:00:00`);
    const validDate = !Number.isNaN(date.getTime());
    const weekday = validDate ? date.toLocaleDateString("de-DE", { weekday: "short" }).replace(".", "") : "";
    const day = validDate ? String(date.getDate()) : "";
    const month = validDate ? date.toLocaleDateString("de-DE", { month: "short" }).replace(".", "").toUpperCase() : "";
    const entries = Array.isArray(item?.entries) ? item.entries : [];

    return `
      <section class="homework-day">
        <div class="date-block">
          <div class="weekday">${escapeHtml(weekday)}</div>
          <div class="day">${escapeHtml(day)}</div>
          <div class="month">${escapeHtml(month)}</div>
        </div>
        <div class="entries">
          ${entries.map((entry) => this._renderEntry(entry)).join("")}
        </div>
      </section>
    `;
  }

  _styles() {
    return `
      <style>
        :host {
          display: block;
          min-width: 0;
        }

        ha-card {
          padding: 16px;
          overflow: hidden;
          text-align: left;
        }

        .title-row {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 14px;
          margin-bottom: 16px;
        }

        .card-title {
          min-width: 0;
          color: var(--primary-text-color);
          font-size: 24px;
          font-weight: 300;
          line-height: 1.2;
        }

        .last-update {
          flex: 0 0 auto;
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 400;
          line-height: 1.2;
          opacity: 0.72;
          text-align: right;
          white-space: nowrap;
        }

        .homework-timeline {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .homework-day {
          display: grid;
          grid-template-columns: 58px minmax(0, 1fr);
          gap: 14px;
          align-items: start;
        }

        .date-block {
          width: 58px;
          min-height: 78px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: flex-start;
          padding-top: 6px;
          box-sizing: border-box;
          color: var(--primary-text-color);
          line-height: 1.05;
          text-align: center;
        }

        .weekday {
          font-size: 15px;
          font-weight: 500;
          opacity: 0.82;
        }

        .day {
          font-size: 34px;
          font-weight: 400;
        }

        .month {
          font-size: 13px;
          font-weight: 500;
          opacity: 0.82;
        }

        .entries {
          display: flex;
          flex-direction: column;
          gap: 8px;
          min-width: 0;
          border-left: 3px solid var(--primary-color);
          padding-left: 12px;
        }

        .homework-entry {
          border-radius: 6px;
          background: rgba(var(--rgb-primary-text-color), 0.04);
          border: 1px solid rgba(var(--rgb-primary-text-color), 0.08);
          padding: 10px 12px;
          box-sizing: border-box;
          min-width: 0;
        }

        .subject {
          color: var(--primary-text-color);
          font-size: 14px;
          font-weight: 700;
          line-height: 1.25;
        }

        .task {
          margin-top: 4px;
          color: var(--secondary-text-color);
          font-size: 13px;
          line-height: 1.35;
          overflow-wrap: anywhere;
        }

        .empty {
          padding: 14px;
          border-radius: 6px;
          background: rgba(var(--rgb-primary-text-color), 0.04);
          color: var(--secondary-text-color);
          text-align: left;
        }

        @media screen and (max-width: 700px) {
          ha-card {
            padding: 12px;
          }

          .card-title {
            font-size: 19px;
          }

          .last-update {
            font-size: 10px;
          }

          .homework-day {
            grid-template-columns: 50px minmax(0, 1fr);
            gap: 10px;
          }

          .date-block {
            width: 50px;
          }

          .day {
            font-size: 30px;
          }
        }
      </style>
    `;
  }
}

class SchulmanagerEntityCardEditor extends HTMLElement {
  constructor(entityFilter, defaultTitle, entityLabel) {
    super();
    this._entityFilter = entityFilter;
    this._defaultTitle = defaultTitle;
    this._entityLabel = entityLabel;
  }

  setConfig(config) {
    this._config = { title: this._defaultTitle, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _valueChanged(ev) {
    if (!this._config) return;
    const target = ev.target;
    const key = target.configValue;
    const value = target.value ?? ev.detail?.value ?? "";
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });

    this.shadowRoot.innerHTML = `
      <style>
        .form {
          display: grid;
          gap: 12px;
        }
      </style>
      <div class="form">
        <ha-entity-picker
          label="${this._entityLabel}"
          allow-custom-entity
        ></ha-entity-picker>
        <ha-textfield
          label="Titel"
        ></ha-textfield>
      </div>
    `;

    const picker = this.shadowRoot.querySelector("ha-entity-picker");
    picker.hass = this._hass;
    picker.value = this._config.entity || "";
    picker.includeDomains = ["sensor"];
    picker.entityFilter = this._entityFilter;
    picker.configValue = "entity";
    picker.addEventListener("value-changed", (ev) => this._valueChanged(ev));

    const title = this.shadowRoot.querySelector("ha-textfield");
    title.value = this._config.title || this._defaultTitle;
    title.configValue = "title";
    title.addEventListener("input", (ev) => this._valueChanged(ev));
  }
}

class SchulmanagerTimetableCardEditor extends SchulmanagerEntityCardEditor {
  constructor() {
    super(isSchulmanagerSensor, "Stundenplan", "Stundenplan-Entität");
  }
}

class SchulmanagerHomeworkCardEditor extends SchulmanagerEntityCardEditor {
  constructor() {
    super(isSchulmanagerSensor, "Hausaufgaben", "Hausaufgaben-Entität");
  }
}

if (!customElements.get("schulmanager-timetable-card")) {
  customElements.define("schulmanager-timetable-card", SchulmanagerTimetableCard);
}

if (!customElements.get("schulmanager-timetable-card-editor")) {
  customElements.define("schulmanager-timetable-card-editor", SchulmanagerTimetableCardEditor);
}

if (!customElements.get("schulmanager-homework-card")) {
  customElements.define("schulmanager-homework-card", SchulmanagerHomeworkCard);
}

if (!customElements.get("schulmanager-homework-card-editor")) {
  customElements.define("schulmanager-homework-card-editor", SchulmanagerHomeworkCardEditor);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "schulmanager-timetable-card",
  name: "Schulmanager Stundenplan",
  description: "Stundenplan-Wochenansicht fuer Schulmanager",
  preview: false,
});
window.customCards.push({
  type: "schulmanager-homework-card",
  name: "Schulmanager Hausaufgaben",
  description: "Hausaufgaben-Timeline fuer Schulmanager",
  preview: false,
});

console.info(`%cSCHULMANAGER-TIMETABLE-CARD ${CARD_VERSION}`, "color: #03a9f4; font-weight: 700;");
