"use strict";

/* Mock of the continuous coverage panel of the feed seal page.
 *
 * Everything in the summary card, the timeline and the chain comes from one response of
 *   GET /v1/gtfs_feeds/{id}/continuous_coverage
 * The probation band is the one exception: it comes from the fresh_continuous criterion, which the
 * seal page already loads from GET /v1/gtfs_feeds/{id}/reliability.
 *
 * The chart is Apache ECharts, so the eventual React port is echarts-for-react over the same
 * option object built in chartOption() below.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAY = 86400000;

/* ---- dates --------------------------------------------------------------- */

const parseDay = (s) => (s ? new Date(s + "T00:00:00Z") : null);
const tsOfDay = (s) => (s ? parseDay(s).getTime() : null);

const fmtDay = (s) => {
  const d = parseDay(s);
  return d ? `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${String(d.getUTCFullYear()).slice(2)}` : "—";
};
const fmtStamp = (s) => {
  if (!s) return "no download date";
  const d = new Date(s);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
};
const fmtTs = (t) => {
  const d = new Date(t);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
};
const fmtSpan = (days) =>
  days == null ? "—" : days >= 365 ? `${(days / 365).toFixed(1)}yr` : `${days}d`;

/* ---- dom helpers --------------------------------------------------------- */

const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/* ---- state --------------------------------------------------------------- */

const state = {
  response: null,
  criterion: CRITERION,
  today: MOCK_TODAY,
  live: false,
  chart: null,
};

/* Two datasets can carry the exact same window, when a producer republishes without moving the
 * horizon. That is not a join worth drawing - the feed simply did not move. */
const sameWindow = (a, b) =>
  !!a && !!b && a.start === b.start && a.end === b.end;



/* ---- summary card -------------------------------------------------------- */

/* The fields the card reads, so the details block below it can name them exactly. */
const HEADLINE_FIELDS = [
  ["items[0].dataset_id", "which dataset the card describes"],
  ["items[0].is_latest", "confirms items[0] really is the feed's latest dataset"],
  ["items[0].coverage_window", "the start, end and length shown as the headline window"],
  ["items[0].coverage_window_source", "whether that window came from the calendars or from feed_info.txt"],
  ["items[0].within_max_coverage_window", "the two-year verdict on the right"],
  ["items[0].files[]", "the file chips"],
];
const CHAIN_FIELDS = [
  ["items[].gap_days", "counted across every item to decide the continuity verdict on the left"],
];

function renderSummary(items) {
  const latest = items.find((i) => i.is_latest) || items[0];

  // Continuity is a property of the whole chain, so it is read off every item. A card showing only
  // the latest dataset's two-year check would read as passing while a gap sat ten rows down.
  const gaps = items.filter((i) => i.gap_days != null);
  const continuity = $("continuity");
  continuity.className = "pill " + (gaps.length ? "fail" : "pass");
  continuity.textContent = gaps.length
    ? `${gaps.length} gap${gaps.length > 1 ? "s" : ""} in the chain`
    : "no gaps in the chain";

  $("summary-copy").textContent = gaps.length
    ? "Successive datasets should overlap so no service day goes uncovered. " +
      `${gaps.length === 1 ? "One dataset does not meet" : gaps.length + " datasets do not meet"} ` +
      "the one before it, leaving " + gaps.map((g) => g.gap_days + "d").join(", ") + " of service uncovered."
    : "Successive datasets overlap with no gaps, and the latest dataset's service window stays " +
      "within the two-year limit.";

  const win = latest ? latest.coverage_window : null;
  const verdict = $("verdict");
  verdict.className = "pill " + (win ? (latest.within_max_coverage_window ? "pass" : "fail") : "none");
  verdict.textContent = win
    ? `${fmtSpan(win.days)} window${latest.within_max_coverage_window ? "" : " — over the 2-year limit"}`
    : "no window reported";

  $("summary-files").replaceChildren(
    ...(latest ? latest.files : []).map((f) => {
      const c = el("span", "chip" + (f.present ? " on" : ""));
      c.append(el("span", null, f.present ? "✓" : "—"), el("span", null, f.name));
      return c;
    })
  );

  const host = $("summary-window");
  if (!win) {
    host.className = "nowin";
    host.textContent = latest
      ? `The latest dataset (${latest.dataset_id}) reports neither validated service dates nor a ` +
        "feed_info.txt window, so there is no coverage to measure yet."
      : "This feed has no datasets.";
  } else {
    host.className = "window";
    const box = (lbl, val, isEnd) => {
      const b = el("div", "wbox" + (isEnd ? " end" : ""));
      b.append(el("div", "lbl", lbl), el("div", "val", val));
      return b;
    };
    const span = el("div", "span");
    span.append(el("div", "n", fmtSpan(win.days)), el("div", "ar", "→"));
    host.replaceChildren(box("Coverage start", fmtDay(win.start)), span, box("Coverage end", fmtDay(win.end), true));
  }

  renderProvenance(latest);
}

/* Spells out that the headline is one item, not an aggregate - the endpoint returns no summary
 * object, so which item the card reads is a real question a reader will have. */
function renderProvenance(latest) {
  const d = $("provenance");
  d.replaceChildren();

  const sum = el("summary", null, "Which fields this card reads");
  d.append(sum);

  const intro = el("p", null,
    "The response carries no summary object. Every headline number here is read off a single item " +
    "— " + (latest ? latest.dataset_id : "none") + ", the first of the list — except the " +
    "continuity verdict, which is counted across the whole chain. Because the list is ordered " +
    "newest first, items[0] is the feed's current coverage."
  );
  d.append(intro);

  const table = el("table", "fields");
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  hr.append(el("th", null, "Field"), el("th", null, "Drives"));
  thead.append(hr);
  table.append(thead);

  const tb = document.createElement("tbody");
  for (const [field, drives] of HEADLINE_FIELDS.concat(CHAIN_FIELDS)) {
    const tr = document.createElement("tr");
    tr.append(el("td", "f", field), el("td", null, drives));
    tb.append(tr);
  }
  table.append(tb);
  d.append(table);

  if (latest) {
    const pre = el("pre", "json");
    pre.textContent = JSON.stringify(
      {
        dataset_id: latest.dataset_id,
        is_latest: latest.is_latest,
        coverage_window: latest.coverage_window,
        coverage_window_source: latest.coverage_window_source,
        within_max_coverage_window: latest.within_max_coverage_window,
        files: latest.files,
      },
      null,
      2
    );
    d.append(el("p", "cap", "items[0], the fields above only:"), pre);
  }
}

/* ---- probation, derived from the rule ------------------------------------ */

/* The rule, in full:
 *
 *   a gap is introduced -> IF AND ONLY IF the next upload has no gap -> probation starts on that
 *   upload's download date -> it runs 180 days -> another gap inside that window restarts the clock.
 *
 * This is applied to the coverage items rather than read off the criterion, because the criterion
 * serves `probation_ends_at` and no field for the start. Deriving it from the chain also means the
 * dates line up with rows a reader can see: every run below starts on the download date of a
 * dataset that is right there in the list.
 *
 * `items` arrives newest first, so it is walked in reverse - the rule is about what happened next.
 */
function probationRuns(items) {
  const runs = [];
  let awaitingCleanUpload = false;

  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i];
    const isOldest = i === items.length - 1;

    if (it.gap_days != null) {
      // A gap inside an open run breaks it: the clock restarts from the next clean upload rather
      // than carrying on from where it was.
      const open = runs.find(
        (r) => r.brokenBy == null && it.downloadedAt >= r.start && it.downloadedAt < r.end
      );
      if (open) open.brokenBy = { at: it.downloadedAt, dataset: it.dataset_id, days: it.gap_days };
      awaitingCleanUpload = true;
      continue;
    }

    // The oldest dataset has nothing before it, so it is not evidence that anything was repaired.
    if (awaitingCleanUpload && !isOldest) {
      runs.push({
        start: it.downloadedAt,
        end: it.downloadedAt + PROBATION_DAYS * DAY,
        startedBy: it.dataset_id,
        brokenBy: null,
      });
      awaitingCleanUpload = false;
    }
  }
  return runs;
}

/* Every gap, for the "seal withdrawn" markers. */
const gapEvents = (items) =>
  items.filter((it) => it.gap_days != null).map((it) => ({ at: it.downloadedAt, days: it.gap_days }));

/* Decorate items with a numeric download timestamp once, so the rule and the chart can compare
 * dates without re-parsing. */
function withTimes(items) {
  items.forEach((it) => {
    it.downloadedAt = it.downloaded_at ? new Date(it.downloaded_at).getTime() : null;
  });
  return items;
}

/* ---- the chart ----------------------------------------------------------- */

/* The chart has two different kinds of time on it, and keeping them apart is the whole point:
 *
 *   x  service dates - what a dataset claims to cover. This is where overlaps and gaps live.
 *   y  download dates - when we actually fetched each dataset. This is wall-clock time, so it is
 *      where the seal, probation and today belong.
 *
 * y is a real time axis rather than one row per dataset, so a probation band is an exact horizontal
 * band and can extend past the newest dataset. It also means the vertical distance between two rows
 * is the real time between publications - a quiet spell shows up as a visible vertical gap.
 */

const BAR_H = 12;
const PX_PER_MONTH = 17;   // vertical scale: enough that 30-day publications do not collide

function windowTs(item) {
  const w = item.coverage_window;
  return w ? { s: tsOfDay(w.start), e: tsOfDay(w.end) } : null;
}

function chartOption(items, criterion, todayTs) {
  const runs = probationRuns(items);
  const gaps = gapEvents(items);

  // The vertical extent has to hold the downloads, today and any probation that runs past both.
  const yStamps = items.map((i) => i.downloadedAt).filter((t) => t != null).concat([todayTs]);
  for (const r of runs) yStamps.push(r.start, r.brokenBy ? r.brokenBy.at : r.end);
  const yPad = DAY * 18;
  const yMin = Math.min(...yStamps) - yPad;
  const yMax = Math.max(...yStamps) + yPad;

  // Range bars. Dimensions: [downloadedAt, start, end, idx]
  const bars = [];
  items.forEach((it, i) => {
    const w = windowTs(it);
    if (!w || it.downloadedAt == null) return;
    bars.push({
      value: [it.downloadedAt, w.s, w.e, i],
      itemStyle: {
        color: it.is_latest ? css("--cal") : css("--cal-soft"),
        borderColor: css("--cal"),
        borderWidth: it.is_latest ? 0 : 1,
      },
    });
  });

  // Joins. Dimensions: [yNewer, yOlder, from, to, idx, isGap]
  const joins = [];
  items.forEach((it, i) => {
    const older = items[i + 1];
    if (!older) return;
    const wNew = windowTs(it);
    const wOld = windowTs(older);
    if (!wNew || !wOld || sameWindow(it.coverage_window, older.coverage_window)) return;

    const isGap = it.gap_days != null;
    if (!isGap && it.overlap_days == null) return;

    const from = isGap ? wOld.e : wNew.s;
    const to = isGap ? wNew.s : wOld.e;
    joins.push({
      value: [it.downloadedAt, older.downloadedAt, Math.min(from, to), Math.max(from, to), i, isGap ? 1 : 0],
      itemStyle: {
        color: isGap ? css("--fail-tint") : css("--pass"),
        borderColor: isGap ? css("--fail") : css("--pass"),
        borderWidth: isGap ? 1 : 0,
        borderType: "dashed",
      },
    });
  });

  // Probation is wall-clock, so it is a horizontal band on y. A run that was broken stops at the
  // gap that broke it and is shaded faintly, so the restart reads as two bands rather than one.
  const markAreas = runs.map((r) => [
    {
      yAxis: r.start,
      itemStyle: { color: r.brokenBy ? css("--warn-faint") : css("--warn-tint") },
    },
    { yAxis: r.brokenBy ? r.brokenBy.at : r.end },
  ]);

  const markLines = [];
  for (const g of gaps) {
    markLines.push({
      yAxis: g.at,
      lineStyle: { color: css("--fail"), width: 1.5, type: "solid" },
      label: { show: true, formatter: `gap of ${g.days}d: seal withdrawn`, color: css("--fail"),
        fontSize: 10, position: "insideEndTop" },
    });
  }
  for (const r of runs) {
    markLines.push({
      yAxis: r.start,
      lineStyle: { color: css("--warn"), width: 1.5, type: "solid" },
      label: { show: true, formatter: "probation starts", color: css("--warn"),
        fontSize: 10, position: "insideStartTop" },
    });
    if (!r.brokenBy) {
      markLines.push({
        yAxis: r.end,
        lineStyle: { color: css("--warn"), width: 1.5, type: "dashed" },
        label: { show: true, formatter: "probation ends", color: css("--warn"),
          fontSize: 10, position: "insideStartBottom" },
      });
    }
  }
  // Kept on the right rail: today can sit within a few weeks of a probation edge, and both labels
  // on the same side would overlap.
  markLines.push({
    yAxis: todayTs,
    lineStyle: { color: css("--ink"), width: 1.5, type: "dotted" },
    label: { show: true, formatter: "today", color: css("--ink"), fontSize: 10,
      position: "insideEndTop" },
  });

  const renderBar = (params, api) => {
    const y = api.coord([api.value(1), api.value(0)]);
    const x2 = api.coord([api.value(2), api.value(0)])[0];
    const rect = echarts.graphic.clipRectByRect(
      { x: y[0], y: y[1] - BAR_H / 2, width: Math.max(x2 - y[0], 2), height: BAR_H },
      { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height }
    );
    return rect && { type: "rect", shape: rect, style: api.style() };
  };

  const renderJoin = (params, api) => {
    const isGap = api.value(5) === 1;
    const a = api.coord([api.value(2), api.value(0)]);   // newer dataset
    const b = api.coord([api.value(3), api.value(1)]);   // older dataset
    const clip = { x: params.coordSys.x, y: params.coordSys.y,
                   width: params.coordSys.width, height: params.coordSys.height };

    if (isGap) {
      // A gap can be a couple of days wide against years of service, so it gets a floor of 3px -
      // otherwise the one thing the criterion turns on would be invisible until zoomed in.
      const top = Math.min(a[1], b[1]) - BAR_H / 2;
      const bottom = Math.max(a[1], b[1]) + BAR_H / 2;
      const rect = echarts.graphic.clipRectByRect(
        { x: a[0], y: top, width: Math.max(b[0] - a[0], 3), height: bottom - top }, clip
      );
      return rect && { type: "rect", shape: rect, style: api.style() };
    }

    // An overlap is a rule between the two rows. A healthy feed has one on every pair, so filling
    // the space would bury the bars; a rule reads as a connector.
    const mid = (a[1] + b[1]) / 2;
    const x1 = Math.min(a[0], b[0]);
    const x2 = Math.max(a[0], b[0]);
    const cap = 4;
    const colour = api.visual("color");
    return {
      type: "group",
      clipPath: { type: "rect", shape: clip },
      children: [
        { type: "rect", shape: { x: x1, y: mid - 1, width: Math.max(x2 - x1, 2), height: 2 },
          style: { fill: colour } },
        { type: "rect", shape: { x: x1, y: mid - cap, width: 1.5, height: cap * 2 },
          style: { fill: colour } },
        { type: "rect", shape: { x: x2 - 1.5, y: mid - cap, width: 1.5, height: cap * 2 },
          style: { fill: colour } },
      ],
    };
  };

  return {
    animation: false,
    backgroundColor: "transparent",
    grid: { left: 96, right: 128, top: 54, bottom: 62, containLabel: false },
    tooltip: {
      trigger: "item",
      confine: true,
      backgroundColor: css("--ground"),
      borderColor: css("--line"),
      textStyle: { color: css("--ink-2"), fontSize: 12 },
      extraCssText: "box-shadow: 0 8px 24px -16px rgba(22,33,28,.4);",
      formatter: (p) => {
        const it = items[p.value[p.seriesIndex === 0 ? 3 : 4]];
        if (p.seriesIndex === 0) {
          const w = it.coverage_window;
          const rows = [
            ["downloaded", fmtStamp(it.downloaded_at)],
            ["covers", `${fmtDay(w.start)} \u2192 ${fmtDay(w.end)}`],
            ["length", `${fmtSpan(w.days)} (${w.days}d)`],
            ["source", it.coverage_window_source],
            ["2-year limit", it.within_max_coverage_window ? "within" : "exceeded"],
          ];
          if (it.feed_info_matches !== null) rows.push(["feed_info", it.feed_info_matches ? "matches" : "disagrees"]);
          return tipHtml(it.dataset_id + (it.is_latest ? " (latest)" : ""), rows);
        }
        const older = items[p.value[4] + 1];
        const isGap = it.gap_days != null;
        return tipHtml(
          isGap ? `${it.gap_days} service days uncovered` : `${it.overlap_days} service days shared`,
          isGap
            ? [["older covers to", fmtDay(older.coverage_window.end)],
               ["newer covers from", fmtDay(it.coverage_window.start)],
               ["older dataset", older.dataset_id], ["newer dataset", it.dataset_id]]
            : [["shared from", fmtDay(it.coverage_window.start)],
               ["shared to", fmtDay(older.coverage_window.end)],
               ["older dataset", older.dataset_id], ["newer dataset", it.dataset_id]]
        );
      },
    },
    xAxis: {
      type: "time",
      position: "top",
      name: "service dates the dataset covers",
      nameLocation: "middle",
      nameGap: 30,
      nameTextStyle: { color: css("--muted"), fontSize: 11, fontWeight: 500 },
      axisLine: { lineStyle: { color: css("--line") } },
      axisTick: { lineStyle: { color: css("--line") } },
      axisLabel: { color: css("--muted"), fontSize: 10, fontFamily: "IBM Plex Mono, monospace", hideOverlap: true },
      splitLine: { show: true, lineStyle: { color: css("--line-soft") } },
    },
    yAxis: {
      type: "time",
      // Time runs upward, the way a cartesian axis normally reads: the oldest dataset sits at the
      // bottom and the newest at the top, with today above it.
      min: yMin,
      max: yMax,
      name: "when we downloaded it",
      nameLocation: "middle",
      nameGap: 74,
      nameRotate: 90,
      nameTextStyle: { color: css("--muted"), fontSize: 11, fontWeight: 500 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: css("--muted"), fontSize: 10, fontFamily: "IBM Plex Mono, monospace", hideOverlap: true },
      splitLine: { show: true, lineStyle: { color: css("--line-soft"), type: "dashed" } },
    },
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "slider", xAxisIndex: 0, filterMode: "none", height: 20, bottom: 16,
        borderColor: css("--line"), fillerColor: "rgba(65,78,192,.10)",
        handleStyle: { color: css("--ground"), borderColor: css("--cal") },
        dataBackground: { lineStyle: { color: css("--line") }, areaStyle: { color: css("--surface-2") } },
        textStyle: { color: css("--muted"), fontSize: 10 } },
    ],
    series: [
      {
        name: "coverage",
        type: "custom",
        renderItem: renderBar,
        encode: { x: [1, 2], y: 0 },
        dimensions: ["downloadedAt", "start", "end", "idx"],
        data: bars,
        z: 3,
      },
      {
        name: "joins",
        type: "custom",
        renderItem: renderJoin,
        encode: { x: [2, 3], y: [0, 1] },
        dimensions: ["yNewer", "yOlder", "from", "to", "idx", "isGap"],
        data: joins,
        z: 5,
        markArea: markAreas.length ? { silent: true, data: markAreas, z: 0 } : undefined,
        markLine: { silent: true, symbol: "none", label: { show: true }, data: markLines, z: 6 },
      },
    ],
  };
}

function tipHtml(title, rows) {
  const body = rows
    .map(
      ([k, v]) =>
        `<div style="display:flex;gap:10px;justify-content:space-between">
           <span style="color:${css("--muted")}">${k}</span>
           <span style="font-family:'IBM Plex Mono',monospace">${v}</span>
         </div>`
    )
    .join("");
  return `<div style="font-weight:600;color:${css("--ink")};margin-bottom:4px">${title}</div>${body}`;
}

function renderChart() {
  const host = $("chart");
  const items = state.response.items;
  const todayTs = parseDay(state.today).getTime();

  // Height comes from the wall-clock span so the vertical scale stays honest: two datasets a month
  // apart sit a month apart, and a four-month silence looks like four months.
  const stamps = items.map((i) => i.downloadedAt).filter((t) => t != null).concat([todayTs]);
  for (const r of probationRuns(items)) stamps.push(r.start, r.brokenBy ? r.brokenBy.at : r.end);
  const months = stamps.length > 1 ? (Math.max(...stamps) - Math.min(...stamps)) / (DAY * 30.44) : 1;
  host.style.height = Math.round(Math.min(Math.max(months * PX_PER_MONTH + 116, 260), 1400)) + "px";

  if (!state.chart) {
    state.chart = echarts.init(host, null, { renderer: "svg" });
  }
  state.chart.setOption(chartOption(items, state.criterion, todayTs), { notMerge: true });
  state.chart.resize();
}

function renderProbationNote() {
  const note = $("probation-note");
  const items = state.response.items;
  const runs = probationRuns(items);
  const current = runs.find((r) => r.brokenBy == null);
  note.replaceChildren();

  if (!runs.length) {
    note.append(
      el("strong", null, "No probation. "),
      document.createTextNode(
        "No gap in this chain is followed by a clean upload, so nothing has started a probation " +
        "period. fresh_continuous has no grace period either, which is why there is no grace band."
      )
    );
    return;
  }

  note.append(el("strong", null, "How these bands were worked out. "));
  note.append(document.createTextNode(
    "A gap withdraws the seal that day. Probation starts only if the very next upload has no gap, " +
    `and then runs ${PROBATION_DAYS} days from that upload's download date. A further gap inside ` +
    "that window restarts the clock. Applied to the " + items.length + " datasets below:"
  ));

  const ol = document.createElement("ol");
  ol.className = "runs";
  runs.forEach((r, n) => {
    const li = document.createElement("li");
    li.append(el("span", "mono", fmtTs(r.start) + " → " + fmtTs(r.end)));
    li.append(document.createTextNode(" started by " + r.startedBy + ", the first clean upload after a gap. "));
    if (r.brokenBy) {
      li.append(el("strong", null, "Broken"));
      li.append(document.createTextNode(
        ` on ${fmtTs(r.brokenBy.at)} by a ${r.brokenBy.days}-day gap, so the clock restarted.`
      ));
    } else {
      const open = r.start <= parseDay(state.today).getTime() && parseDay(state.today).getTime() < r.end;
      li.append(document.createTextNode(open ? "Still open today." : "Completed."));
    }
    ol.append(li);
  });
  note.append(ol);

  // The criterion is served by a different endpoint, so the two can be checked against each other.
  const c = state.criterion;
  if (current && c && c.probation_ends_at) {
    const served = new Date(c.probation_ends_at).getTime();
    const agrees = Math.abs(served - current.end) < DAY;
    note.append(el("p", "cross",
      agrees
        ? `This matches probation_ends_at of ${fmtTs(served)} from the reliability endpoint, so the ` +
          "rule applied to the coverage data and the stored criterion agree."
        : `The reliability endpoint reports probation_ends_at of ${fmtTs(served)}, which does not ` +
          `match the ${fmtTs(current.end)} derived here — worth investigating.`
    ));
  }
}

/* ---- chain rows ---------------------------------------------------------- */

function renderRows() {
  const rows = $("rows");
  rows.replaceChildren();
  const items = state.response.items;

  items.forEach((it, i) => {
    const older = items[i + 1];
    const row = el("div", "row");

    const head = el("div", "rhead");
    head.append(el("span", "dl", "Downloaded " + fmtStamp(it.downloaded_at)));
    head.append(el("span", "id", it.dataset_id));
    if (it.is_latest) head.append(el("span", "pill pass", "latest"));

    // An unchanged window reports a full-window overlap, which is true but says nothing about
    // continuity. Naming it is more use to a reader than the number.
    if (older && sameWindow(it.coverage_window, older.coverage_window)) {
      head.append(el("span", "pill none", "window unchanged"));
    } else if (it.gap_days != null) {
      head.append(el("span", "pill fail", it.gap_days + "d uncovered"));
    } else if (it.overlap_days != null) {
      head.append(el("span", "pill pass", it.overlap_days === 0 ? "meets exactly" : it.overlap_days + "d overlap"));
    }
    row.append(head);

    const meta = el("div", "rmeta");
    const w = it.coverage_window;
    meta.append(el("span", "dates",
      w ? `${fmtDay(w.start)} → ${fmtDay(w.end)} · ${fmtSpan(w.days)}` : "no window reported"));
    const right = el("div", "right");
    if (w && it.coverage_window_source === "feed_info") right.append(el("span", "pill warn", "window from feed_info"));
    if (it.feed_info_matches === true) right.append(el("span", "pill pass", "✓ feed_info matches"));
    if (it.feed_info_matches === false) right.append(el("span", "pill fail", "feed_info disagrees"));
    if (it.feed_info_matches === null && w) right.append(el("span", "pill none", "no feed_info"));
    meta.append(right);
    row.append(meta);

    const disc = el("details", "disc");
    disc.append(el("summary", null, "this item's fields"));
    const pre = el("pre", "json");
    pre.textContent = JSON.stringify(it, null, 2);
    disc.append(pre);
    row.append(disc);

    rows.append(row);
  });
}

/* ---- loading ------------------------------------------------------------- */

function paint() {
  withTimes(state.response.items);
  renderSummary(state.response.items);
  renderChart();
  renderProbationNote();
  renderRows();
  const r = state.response;
  $("count").textContent = `${r.items.length} of ${r.total} datasets · ${r.feed_id}`;
  $("footer").textContent = state.live
    ? "Loaded live from the API. The probation band still comes from the bundled criterion fixture."
    : "Showing a captured response. Point the form at a running API to load a live feed.";
}

function showFixture() {
  state.response = COVERAGE;
  state.live = false;
  $("status").textContent = "";
  $("status").className = "status";
  paint();
}

async function loadLive() {
  const base = $("api").value.trim().replace(/\/+$/, "");
  const feed = $("feed").value.trim();
  const limit = $("limit").value.trim() || "100";
  const status = $("status");

  if (!base || !feed) {
    status.textContent = "Enter an API base URL and a feed ID.";
    status.className = "status err";
    return;
  }

  const url = `${base}/v1/gtfs_feeds/${encodeURIComponent(feed)}/continuous_coverage?limit=${encodeURIComponent(limit)}`;
  status.textContent = "Loading " + url;
  status.className = "status";

  try {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch (e) { /* not JSON */ }
      status.textContent = `${res.status} ${res.statusText}${detail ? " — " + detail : ""}`;
      status.className = "status err";
      return;
    }
    const body = await res.json();
    state.response = body;
    state.live = true;
    status.textContent = `Loaded ${body.items.length} of ${body.total} datasets for ${body.feed_id}.`;
    status.className = "status ok";
    paint();
  } catch (err) {
    status.textContent =
      "Could not reach the API. Start it, and check the base URL. (" + err.message + ")";
    status.className = "status err";
  }
}

/* ---- wiring -------------------------------------------------------------- */

$("load").addEventListener("click", loadLive);
$("reset").addEventListener("click", showFixture);
$("feed").addEventListener("keydown", (e) => { if (e.key === "Enter") loadLive(); });

let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (state.chart) state.chart.resize(); }, 120);
});

showFixture();
