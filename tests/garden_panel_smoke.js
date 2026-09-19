// Source-only panel check: the Morph stays visible while Gardens offers games.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let Panel;
globalThis.HTMLElement = class {
  setAttribute(name, value) { this[name] = value; }
  attachShadow() {
    this.shadowRoot = { innerHTML: "", querySelectorAll: () => [], querySelector: () => null, addEventListener: () => {} };
    return this.shadowRoot;
  }
};
globalThis.customElements = { define: (_, cls) => { Panel = cls; } };
globalThis.location = { search: "" };
const source = fs.readFileSync(path.join(__dirname, "../custom_components/morph_domain/frontend/morph-domain-panel.js"), "utf8");
vm.runInThisContext(source);

const panel = new Panel();
assert.throws(() => panel.setConfig({ place: "MORPHBANK" }), /canonical Morph Domain place/);
panel.setConfig({ place: "SEREIN_GARDENS" });
assert.equal(panel.place, "SEREIN_GARDENS");
assert.equal(panel["data-card-mode"], "");
const morph = {
  morph_id: "pulse", founder_id: "PULSE", generation: 1,
  authority: "HAOS", place: "SEREIN_GARDENS", habitat_engine_state: "ACTIVE",
  presentation: { display_name: "Pulse", revision: 0 },
  environment: { expression_q8: { WATER: 20 } },
  life: { fatigue_q8: 20, food_q8: 180, water_q8: 180, play_q8: 180, rest_q8: 180 },
};
panel.place = "SEREIN_GARDENS";
panel.rows = [morph];
panel.selected = "pulse";
panel.loading = false;
panel.render();
assert.ok(panel.shadowRoot.innerHTML.includes('aria-label="Pulse"'));
assert.match(panel.shadowRoot.innerHTML, /data-care="FEED"/);
assert.match(panel.shadowRoot.innerHTML, /data-move="HORIZON"/);
assert.match(panel.shadowRoot.innerHTML, /data-morph-id="pulse"/);
assert.ok(panel.shadowRoot.innerHTML.indexOf('data-move="HORIZON"') < panel.shadowRoot.innerHTML.indexOf('class="detail"'));
assert.ok(panel.shadowRoot.innerHTML.indexOf('class="garden-game"') < panel.shadowRoot.innerHTML.indexOf('class="detail"'));
assert.match(panel.shadowRoot.innerHTML, /<article class="morph-slot"[\s\S]*class="garden-game"[\s\S]*class="detail"[\s\S]*<\/article>/);
assert.doesNotMatch(panel.detail(morph), /data-care=|data-move=|data-game-start=|data-hatch=/);
assert.equal((panel.shadowRoot.innerHTML.match(/class="garden-game"/g) || []).length, 1);
assert.equal(panel.element(morph), "WATER");
assert.match(panel.morph(morph), /water lineage/);
assert.doesNotMatch(panel.morph(morph), /earth lineage/);
assert.match(panel.silhouette("WATER", 1), /M90 17/);
assert.match(panel.silhouette("AIR", 1), /M38 139/);
assert.match(panel.silhouette("FIRE", 1), /M91 18/);
assert.match(panel.silhouette("EARTH", 1), /M51 40/);
assert.deepEqual(panel.palette({founder_id:"SPARK",life:{morph_core:{root:{identity:{primitive_element:"AIR"}},ui:{expression:"air-stage-4"}}}}),["#2bdacb","#d9e1e8"]);
assert.deepEqual(panel.palette({founder_id:"SENTINEL",life:{morph_core:{root:{identity:{primitive_element:"EARTH"}},ui:{expression:"earth-stage-3"}}}}),["#805aa5","#66d0d5"]);
assert.deepEqual(panel.palette({founder_id:"PULSE",life:{morph_core:{root:{identity:{primitive_element:"WATER"}},ui:{expression:"legacy"}}}}),["#123e79","#378fc1"]);
assert.match(panel.shadowRoot.innerHTML, /Matching · 4×4/);
assert.match(panel.shadowRoot.innerHTML, /Which hand\?/);
assert.match(panel.shadowRoot.innerHTML, /Follow the pattern/);
assert.match(panel.shadowRoot.innerHTML, /Core alignment pending/);
const coreNames = ["platform", "root", "memory", "knowledge", "ui", "audio", "personality", "modular", "cloud"];
morph.life.morph_core = Object.fromEntries(coreNames.map(name => [name, {}]));
morph.life.morph_core.schema = "serein.morph-nine-core.v1";
morph.life.morph_core.root.historic_role = "founder";
panel.render();
assert.match(panel.shadowRoot.innerHTML, /Nine cores aligned/);
assert.match(panel.shadowRoot.innerHTML, /founder · HAOS snapshot/);
delete morph.life.morph_core.cloud;
panel.render();
assert.match(panel.shadowRoot.innerHTML, /Core alignment pending/);
morph.life.morph_core.cloud = {};

panel.game = { game_id: "game-1", morph_id: "pulse", game: "MATCHING",
  board: Array(16).fill(null), turn: 0, score: 0, finished: false, rewarded: false };
panel.render();
assert.equal((panel.shadowRoot.innerHTML.match(/data-game-tile=/g) || []).length, 16);
assert.ok(panel.shadowRoot.innerHTML.includes('aria-label="Pulse"'));
panel.game = { game_id: "game-2", morph_id: "pulse", game: "WHICH_HAND",
  round: 1, turn: 0, score: 0, finished: false, rewarded: false };
panel.render();
assert.ok(panel.shadowRoot.innerHTML.includes('data-game-hand="0"'));
assert.ok(panel.shadowRoot.innerHTML.includes('data-game-hand="1"'));
panel.game = { game_id: "game-3", morph_id: "pulse", game: "FOLLOW_PATTERN",
  pattern: [0, 1], turn: 0, score: 0, finished: false, rewarded: false };
panel.render();
assert.equal((panel.shadowRoot.innerHTML.match(/data-game-pattern=/g) || []).length, 4);
panel.place = "HORIZON";
panel.rows[0].place = "HORIZON";
panel.rows[0].frame_return = { dedicated: true, target_frame: "android-frame:v1:pulse", call_available: true, recall_available: false };
panel.rows[0].social = { last_activity: { kind: "REST", expression: "SWIM" } };
panel.render();
assert.doesNotMatch(panel.shadowRoot.innerHTML, /data-game-tile=/);
assert.match(panel.shadowRoot.innerHTML, /data-call-frame/);
assert.match(panel.shadowRoot.innerHTML, /Send to frame/);
assert.match(panel.shadowRoot.innerHTML, /swimming/);
panel.rows[0].social.last_activity.expression = "AIR_CURRENTS";
assert.equal(panel.status(panel.rows[0]), "riding air currents");
assert.match(panel.morph(panel.rows[0]), /riding air currents/);
panel.render();
assert.match(panel.shadowRoot.innerHTML, /riding air currents/);
assert.match(panel.shadowRoot.innerHTML, /data-care="FEED"/);
assert.match(panel.shadowRoot.innerHTML, /data-move="SEREIN_GARDENS"/);
const egg = { ...morph, morph_id: "egg", founder_id: "L1-04", life: { morph_core: { ui: { expression: "egg" } } } };
assert.equal(panel.isEgg(egg), true);
assert.match(panel.morph(egg), /Unknown egg/);
assert.match(panel.morph(egg), /--a:#09101b;--b:#e7f0ff/);
assert.doesNotMatch(panel.inlineActions(egg), /data-care="FEED"/);
assert.match(panel.inlineActions({...egg,place:"NURSERY"}), /data-hatch="egg"/);
panel.place = "SEREIN_GARDENS";
panel.rows[0].place = "SEREIN_GARDENS";
panel.game = null;
panel.rows[0].games = [{ game_id: "resume-1", morph_id: "pulse", game: "MATCHING",
  board: Array(16).fill(null), turn: 1, score: 0, finished: false, rewarded: false }];
panel._hass = { callApi: async (method, route) => route.endsWith("starter-status")
  ? { result: {} } : { result: { morphs: panel.rows } } };
panel.refresh().then(async () => {
  assert.equal(panel.game.game_id, "resume-1");
  assert.equal((panel.shadowRoot.innerHTML.match(/data-game-tile=/g) || []).length, 16);
  const calls = [];
  panel._hass = { callApi: async (method, route, body) => {
    calls.push({ method, route, body });
    return route.endsWith("starter-status") ? { result: {} } : { result: { morphs: panel.rows } };
  } };
  await panel.actOnMorph("care", "FEED");
  assert.equal(calls[0].route, "morph-domain/v1/habitat/care");
  assert.equal(calls[0].body.action, "FEED");
  calls.length = 0;
  panel.rows[0].place = "HORIZON";
  panel.rows[0].frame_return = { dedicated: true, target_frame: "android-frame:v1:pulse", call_available: true, recall_available: false };
  await panel.callFrame("pulse");
  assert.equal(calls[0].route, "morph-domain/v1/habitat/return-frame");
  assert.equal(calls[0].body.target_frame, "android-frame:v1:pulse");
  assert.equal(calls[0].body.morph_id, "pulse");
  calls.length = 0;
  panel.rows[0].authority = "android-frame:v1:pulse";
  panel.rows[0].frame_return = { dedicated: true, target_frame: "android-frame:v1:pulse", call_available: false, recall_available: true };
  assert.match(panel.inlineActions(panel.rows[0]), /Recall to Horizon/);
  await panel.recallFrame("pulse");
  assert.equal(calls[0].route, "morph-domain/v1/habitat/recall-frame");
  assert.equal(calls[0].body.source_frame, "android-frame:v1:pulse");
  panel.rows[0].authority = "HAOS";
  calls.length = 0;
  await panel.actOnMorph("move", "NURSERY");
  assert.equal(calls[0].route, "morph-domain/v1/habitat/place");
  assert.equal(calls[0].body.place, "NURSERY");
  calls.length = 0;
  await panel.actOnMorph("move", "VOID");
  assert.equal(calls.length, 0, "Void requires a second tap");
  console.log("Gardens panel smoke PASS");
}).catch(error => { console.error(error.message); process.exitCode = 1; });

