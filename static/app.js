// ---- state ----
// largest preview edge in screen px — sized to the viewport (bigger on big screens),
// computed once at load; clamped so it never gets tiny or unwieldy
const MAX_PREVIEW = Math.max(640, Math.min(1400,
  Math.min(window.innerHeight - 110, window.innerWidth - 360)));
const DPI = 300;                  // mirrors cover_sizer.DPI (export resolution)
let dims = null;                  // from /api/dimensions (full-res px)
let previewScale = 1;             // full-res px * previewScale = screen px
let imageFiles = [null, null];    // original uploaded File per slot (sent to backend)
let imgNodes = [null, null];      // Konva.Image per slot
let selected = -1;                // index of the selected node (-1 = none)
let transformer = null;
let stackOrder = [];              // slot indices in bottom->top paint order

// the image the Transform controls currently act on
function activeNode() { return selected < 0 ? null : imgNodes[selected]; }

const $ = (id) => document.getElementById(id);
const stage = new Konva.Stage({ container: "stage", width: 100, height: 100 });
// bottom: white bg | image | blank-outside-safe mask | guide lines | KDP template overlay
// (all non-image layers non-interactive)
const bgLayer = new Konva.Layer({ listening: false });
const imageLayer = new Konva.Layer();
const blankLayer = new Konva.Layer({ listening: false, visible: false });
const guideLayer = new Konva.Layer({ listening: false });
const templateLayer = new Konva.Layer({ listening: false, visible: false });
stage.add(bgLayer);
stage.add(imageLayer);
stage.add(blankLayer);
stage.add(guideLayer);
stage.add(templateLayer);

// ---- settings helpers ----
function settings() {
  return {
    pages: $("pages").value || "120",
    paper: $("paper").value,
    trim: $("trim").value,
    guides: $("guides").checked,
    blank: $("blankOutside").checked,
  };
}

async function fetchDims() {
  const s = settings();
  const r = await fetch(`/api/dimensions?pages=${s.pages}&paper=${s.paper}&trim=${s.trim}`);
  if (!r.ok) { $("status").textContent = "Invalid book settings."; return; }
  dims = await r.json();
  previewScale = Math.min(MAX_PREVIEW / dims.total_w, MAX_PREVIEW / dims.total_h);
  stage.size({ width: dims.total_w * previewScale, height: dims.total_h * previewScale });
  drawGuides();
  if (templateLayer.visible()) drawReference();
  if (blankLayer.visible()) drawBlank();
}

// ---- blank-outside-safe-area mask (white bands covering the 'out of live area' zone) ----
function drawBlank() {
  blankLayer.destroyChildren();
  if (!dims) return;
  const d = dims;
  const sxr = sx(d.safe_x), syr = sx(d.safe_y);
  const sx2 = sx(d.safe_x + d.safe_w), sy2 = sx(d.safe_y + d.safe_h);
  const W = sx(d.total_w), H = sx(d.total_h);
  const band = (x, y, w, h) => new Konva.Rect({ x, y, width: w, height: h, fill: "#ffffff" });
  blankLayer.add(band(0, 0, W, syr));            // top
  blankLayer.add(band(0, sy2, W, H - sy2));      // bottom
  blankLayer.add(band(0, syr, sxr, sy2 - syr));  // left
  blankLayer.add(band(sx2, syr, W - sx2, sy2 - syr)); // right
  blankLayer.batchDraw();
}

// ---- generated KDP reference overlay (spine-safe + barcode), never exported ----
function drawReference() {
  templateLayer.destroyChildren();
  if (!dims) return;
  const d = dims;
  // spine safe area (magenta dashed)
  if (d.spine_safe_w > 0) {
    templateLayer.add(new Konva.Rect({
      x: sx(d.spine_safe_x), y: sx(d.y0 + d.live_px),
      width: sx(d.spine_safe_w), height: sx(d.panel_h - 2 * d.live_px),
      stroke: "#a020f0", strokeWidth: 1, dash: [5, 5] }));
  }
  // barcode reserved area (orange, bottom-left of back cover)
  templateLayer.add(new Konva.Rect({
    x: sx(d.bc_x), y: sx(d.bc_y), width: sx(d.bc_w), height: sx(d.bc_h),
    stroke: "#e67e00", strokeWidth: 1, dash: [5, 5], fill: "rgba(255,180,0,0.15)" }));
  templateLayer.add(new Konva.Text({
    x: sx(d.bc_x) + 4, y: sx(d.bc_y) + 4, text: "Barcode", fontSize: 12, fill: "#b45309" }));
  templateLayer.batchDraw();
}

// ---- guides (screen px = full-res px * previewScale) ----
function sx(v) { return v * previewScale; }
function drawGuides() {
  bgLayer.destroyChildren();
  guideLayer.destroyChildren();
  const d = dims, P = previewScale;
  // white background of full canvas (incl. bleed) — stays at the very back
  bgLayer.add(new Konva.Rect({ x: 0, y: 0, width: sx(d.total_w), height: sx(d.total_h), fill: "#ffffff" }));
  bgLayer.draw();
  // bleed area edge (red rectangle = full canvas outline)
  guideLayer.add(new Konva.Rect({ x: 0, y: 0, width: sx(d.total_w), height: sx(d.total_h), stroke: "#e11", strokeWidth: 2 }));
  // trim boxes (black)
  const trim = (x) => new Konva.Rect({ x: sx(x), y: sx(d.y0), width: sx(d.panel_w), height: sx(d.panel_h), stroke: "#000", strokeWidth: 1 });
  guideLayer.add(trim(d.back_x));
  guideLayer.add(trim(d.front_x));
  // spine fold lines (blue dashed)
  const vline = (x) => new Konva.Line({ points: [sx(x), sx(d.y0), sx(x), sx(d.y0 + d.panel_h)], stroke: "#1e50dc", strokeWidth: 1, dash: [6, 6] });
  guideLayer.add(vline(d.spine_x));
  guideLayer.add(vline(d.spine_x + d.spine_px));
  // safe areas (green dashed): inset 'live' from each TRIM edge; spine-fold edge flush (KDP)
  const liveRect = (x, w) => new Konva.Rect({ x: sx(x), y: sx(d.y0 + d.live_px), width: sx(w), height: sx(d.panel_h - 2 * d.live_px), stroke: "#0b4", strokeWidth: 1, dash: [6, 6] });
  // back: inset left, flush right to spine
  guideLayer.add(liveRect(d.back_x + d.live_px, d.panel_w - d.live_px));
  // front: flush left to spine, inset right
  guideLayer.add(liveRect(d.front_x, d.panel_w - d.live_px));
  guideLayer.draw();
  // guides always render on top so they stay visible over the image
  guideLayer.moveToTop();
}

// ---- image load & presets ----
function loadImage(file, slot) {
  imageFiles[slot] = file;
  const url = URL.createObjectURL(file);
  const htmlImg = new Image();
  htmlImg.onload = () => {
    if (imgNodes[slot]) imgNodes[slot].destroy();
    const node = new Konva.Image({
      image: htmlImg,
      width: htmlImg.naturalWidth,
      height: htmlImg.naturalHeight,
      offsetX: htmlImg.naturalWidth / 2,
      offsetY: htmlImg.naturalHeight / 2,
      draggable: true,
    });
    // clicking an image makes it the active one for the Transform controls
    node.on("mousedown touchstart", () => selectNode(slot));
    // recompute the resolution warning after a manual resize
    node.on("transformend", updateDpiWarning);
    // hold Ctrl while dragging to lock movement to one axis (the one you start
    // moving along), like Shift-constrain in design tools
    let dragStart = null, dragAxis = null;
    node.on("dragstart", () => { dragStart = { x: node.x(), y: node.y() }; dragAxis = null; });
    node.on("dragmove", (e) => {
      if (!dragStart || !e.evt || !e.evt.ctrlKey) { dragAxis = null; return; }
      const dx = node.x() - dragStart.x, dy = node.y() - dragStart.y;
      if (!dragAxis) {
        if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return;   // wait for a clear direction
        dragAxis = Math.abs(dx) >= Math.abs(dy) ? "x" : "y";
      }
      if (dragAxis === "x") node.y(dragStart.y); else node.x(dragStart.x);
    });
    imgNodes[slot] = node;
    imageLayer.add(node);
    stackOrder = stackOrder.filter((s) => s !== slot);
    stackOrder.push(slot);          // newly loaded image goes on top
    selectNode(slot);
    applyPreset("overall");
    updateExportButtons();
    URL.revokeObjectURL(url);
  };
  htmlImg.src = url;
}

function selectNode(slot) {
  if (!imgNodes[slot]) return;
  selected = slot;
  attachTransformer();
  $("optimize").disabled = false;
}

// apply the user-controlled stack order (bottom->top) so the preview
// matches the export, which pastes images bottom-first
function restack() {
  // bottom->top: each moveToTop lands above the previously raised node
  stackOrder.forEach((slot) => { if (imgNodes[slot]) imgNodes[slot].moveToTop(); });
  if (transformer) transformer.moveToTop();
}

function attachTransformer() {
  if (transformer) transformer.destroy();
  const node = activeNode();
  if (!node) return;
  transformer = new Konva.Transformer({ keepRatio: true, rotateEnabled: false,
    enabledAnchors: ["top-left", "top-right", "bottom-left", "bottom-right"] });
  imageLayer.add(transformer);
  transformer.nodes([node]);
  restack();
  // reflect the selected image's rotation in the slider
  const r = Math.round(node.rotation());
  $("rotate").value = r;
  $("rotateVal").textContent = `${r}°`;
  imageLayer.draw();
}

function updateExportButtons() {
  const any = imgNodes.some((n) => n);
  $("export").disabled = !any;
  $("exportPdf").disabled = !any;
  $("optimize").disabled = !any;   // clickable whenever an image is loaded
}

// effective print resolution of a placed image: native px mapped onto the
// 300-DPI output. scaleX/previewScale = output px per native px; <300 = upscaled.
function effectiveDpi(imgNode) {
  return DPI / (Math.abs(imgNode.scaleX()) / previewScale);
}
function updateDpiWarning() {
  const low = [0, 1]
    .filter((i) => imgNodes[i])
    .map((i) => ({ i, dpi: Math.round(effectiveDpi(imgNodes[i])) }))
    .filter((x) => x.dpi < DPI);
  $("dpiWarn").textContent = low.length
    ? low.map((x) => `Image ${x.i + 1}: ~${x.dpi} DPI (below 300 — may print blurry)`).join("  ·  ")
    : "";
}

// remove the selected image and free its slot for re-upload
function deleteSelected() {
  if (selected < 0) return;
  const slot = selected;
  if (imgNodes[slot]) { imgNodes[slot].destroy(); imgNodes[slot] = null; }
  imageFiles[slot] = null;
  stackOrder = stackOrder.filter((s) => s !== slot);
  if (transformer) { transformer.destroy(); transformer = null; }
  selected = -1;
  $(slot === 0 ? "file" : "file2").value = "";  // allow re-selecting the same file
  updateExportButtons();                        // also toggles the optimize button
  updateDpiWarning();
  imageLayer.draw();
}

function setProgress(p) {
  $("optimizeBar").style.width = p + "%";
  $("optimizePct").textContent = p + "%";
}

// upscale the selected image: start a backend job, poll its percentage, then
// swap the higher-res result in without changing its on-canvas size (DPI ~4x)
async function optimizeSelected() {
  let slot = selected;
  if (slot < 0) {                       // nothing selected: fall back to a loaded image
    slot = [0, 1].find((i) => imageFiles[i] && imgNodes[i]);
    if (slot === undefined) return;
    selectNode(slot);
  }
  if (!imageFiles[slot]) return;
  const btn = $("optimize");
  btn.disabled = true;
  $("status").textContent = "";
  setProgress(0);
  $("optimizeProgress").hidden = false;
  try {
    const fd = new FormData();
    fd.append("image", imageFiles[slot]);
    const start = await fetch("/api/upscale", { method: "POST", body: fd });
    if (!start.ok) throw new Error(await start.text());
    const { job } = await start.json();

    while (true) {
      await new Promise((r) => setTimeout(r, 400));
      const s = await (await fetch(`/api/upscale/status?job=${job}`)).json();
      if (s.error) throw new Error(s.error);
      setProgress(s.progress);
      if (s.done) break;
    }
    const blob = await (await fetch(`/api/upscale/result?job=${job}`)).blob();
    await replaceSlotImage(slot, blob);
    $("status").textContent = "Optimized to higher resolution.";
  } catch (e) {
    $("status").textContent = "Optimize failed: " + (e.message || e);
  } finally {
    $("optimizeProgress").hidden = true;
    btn.disabled = (selected < 0);
  }
}

// replace a slot's bitmap with a new (higher-res) one, preserving how big it
// looks on screen by dividing the node scale by the resolution gain factor
function replaceSlotImage(slot, blob) {
  return new Promise((resolve) => {
    const node = imgNodes[slot];
    if (!node) { resolve(); return; }
    const url = URL.createObjectURL(blob);
    const htmlImg = new Image();
    htmlImg.onload = () => {
      const factor = htmlImg.naturalWidth / node.width();   // ~4
      node.image(htmlImg);
      node.width(htmlImg.naturalWidth);
      node.height(htmlImg.naturalHeight);
      node.offsetX(htmlImg.naturalWidth / 2);
      node.offsetY(htmlImg.naturalHeight / 2);
      node.scaleX(node.scaleX() / factor);
      node.scaleY(node.scaleY() / factor);
      imageFiles[slot] = new File([blob], "optimized.png", { type: "image/png" });
      if (selected === slot) attachTransformer();           // resize handles to new bounds
      imageLayer.draw();
      updateDpiWarning();
      URL.revokeObjectURL(url);
      resolve();
    };
    htmlImg.src = url;
  });
}

// move the selected image one step in the stack (dir +1 = forward/up, -1 = backward/down)
function moveInStack(dir) {
  if (selected < 0) return;
  const i = stackOrder.indexOf(selected);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= stackOrder.length) return;
  [stackOrder[i], stackOrder[j]] = [stackOrder[j], stackOrder[i]];
  restack();
  imageLayer.draw();
}

// preset: "fit" | "fill" | "reset" | "overall" (acts on the selected image)
function applyPreset(kind) {
  const imgNode = activeNode();
  if (!imgNode || !dims) return;
  const nw = imgNode.width(), nh = imgNode.height();
  let fullScale;
  if (kind === "overall") {
    // snap to the OVERALL canvas (full bleed-to-bleed spread) — whole image visible, no cropping
    fullScale = Math.min(dims.total_w / nw, dims.total_h / nh);
  } else {
    // safe area (inside the green live lines), spanning both panels + spine
    const safeW = (2 * dims.panel_w + dims.spine_px) - 2 * dims.live_px;
    const safeH = dims.panel_h - 2 * dims.live_px;
    // fit = whole image inside safe area; fill/reset = cover the safe area
    const fitSafe = Math.min(safeW / nw, safeH / nh);
    const fillSafe = Math.max(safeW / nw, safeH / nh);
    fullScale = (kind === "fit") ? fitSafe : fillSafe;
  }
  const k = fullScale * previewScale; // screen-space scale
  imgNode.scaleX(k); imgNode.scaleY(k);
  imgNode.rotation(0);
  $("rotate").value = 0; $("rotateVal").textContent = "0°";
  imgNode.position({ x: sx(dims.total_w / 2), y: sx(dims.total_h / 2) });
  imageLayer.draw();
  updateDpiWarning();
}

// ---- transform readout (screen -> full-res, center-anchored) ----
function currentTransform(imgNode) {
  const k = Math.abs(imgNode.scaleX());           // screen-space magnitude
  return {
    cx: imgNode.x() / previewScale,
    cy: imgNode.y() / previewScale,
    scale: k / previewScale,                        // full-res multiplier
    rotation: imgNode.rotation(),                   // clockwise deg
    flipH: imgNode.scaleX() < 0,
    flipV: imgNode.scaleY() < 0,
  };
}

// ---- export ----
async function exportFile(fmt) {
  // slots with both a file and a node, in stack order (first = bottom layer)
  const loaded = stackOrder.filter((i) => imageFiles[i] && imgNodes[i]);
  if (loaded.length === 0) return;
  $("status").textContent = "Rendering…";
  const s = settings();
  const fd = new FormData();
  loaded.forEach((i) => fd.append("image", imageFiles[i]));
  fd.append("transform", JSON.stringify(loaded.map((i) => currentTransform(imgNodes[i]))));
  fd.append("pages", s.pages);
  fd.append("paper", s.paper);
  fd.append("trim", s.trim);
  fd.append("guides", s.guides ? "true" : "false");
  fd.append("blank", s.blank ? "true" : "false");
  fd.append("format", fmt);
  const r = await fetch("/api/render", { method: "POST", body: fd });
  if (!r.ok) { $("status").textContent = "Render failed."; return; }
  const blob = await r.blob();
  const name = "cover_spread." + fmt;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
  $("status").textContent = "Exported " + name;
}

// ---- wire up controls ----
$("sidebarToggle").addEventListener("click", () => document.body.classList.toggle("panel-collapsed"));
$("file").addEventListener("change", (e) => { if (e.target.files[0]) loadImage(e.target.files[0], 0); });
$("file2").addEventListener("change", (e) => { if (e.target.files[0]) loadImage(e.target.files[0], 1); });
["pages", "paper", "trim"].forEach((id) =>
  $(id).addEventListener("change", async () => { await fetchDims(); applyPreset("overall"); }));
$("guides").addEventListener("change", () => {});  // affects export only
$("template").addEventListener("change", (e) => {
  templateLayer.visible(e.target.checked);
  if (e.target.checked) drawReference();
  templateLayer.batchDraw();
});
$("blankOutside").addEventListener("change", (e) => {
  blankLayer.visible(e.target.checked);
  if (e.target.checked) drawBlank();
  blankLayer.batchDraw();
});
$("rotate").addEventListener("input", (e) => {
  const imgNode = activeNode();
  if (!imgNode) return;
  imgNode.rotation(Number(e.target.value));
  $("rotateVal").textContent = `${e.target.value}°`;
  imageLayer.draw();
});
$("flipH").addEventListener("click", () => { const n = activeNode(); if (n) { n.scaleX(-n.scaleX()); imageLayer.draw(); } });
$("flipV").addEventListener("click", () => { const n = activeNode(); if (n) { n.scaleY(-n.scaleY()); imageLayer.draw(); } });
$("bringForward").addEventListener("click", () => moveInStack(+1));
$("sendBackward").addEventListener("click", () => moveInStack(-1));
$("optimize").addEventListener("click", optimizeSelected);
// Delete = remove selected; Ctrl/Cmd+] / [ = forward / backward (ignored while typing in a field)
window.addEventListener("keydown", (e) => {
  const t = e.target;
  if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
  if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); deleteSelected(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "]") { e.preventDefault(); moveInStack(+1); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "[") { e.preventDefault(); moveInStack(-1); }
});
$("fit").addEventListener("click", () => applyPreset("fit"));
$("fill").addEventListener("click", () => applyPreset("fill"));
$("reset").addEventListener("click", () => applyPreset("reset"));
$("overallFit").addEventListener("click", () => applyPreset("overall"));
$("export").addEventListener("click", () => exportFile("png"));
$("exportPdf").addEventListener("click", () => exportFile("pdf"));

// ---- init ----
fetchDims();
