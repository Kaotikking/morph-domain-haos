// Source-only panel check: the Morph stays visible while Gardens offers games.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

let Panel;
globalThis.HTMLElement = class {
  setAttribute(name, value) { this[name] = value; }
  attachShadow() {
    this.shadowRoot = { innerHTML: "", querySelectorAll: () => [], querySelector: () => null };
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
assert.ok(panel.shadowRoot.innerHTML.includes('aria-label="P&#117;lse"'));
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
assert.match(panel.shadowRoot.innerHTML, /fo&#117;nder · HAOS snapshot/);
delete morph.life.morph_core.cloud;
panel.render();
assert.match(panel.shadowRoot.innerHTML, /Core alignment pending/);
morph.life.morph_core.cloud = {};

panel.game = { game_id: "game-1", morph_id: "pulse", game: "MATCHING",
  board: Array(16).fill(null), turn: 0, score: 0, finished: false, rewarded: false };
panel.render();
assert.equal((panel.shadowRoot.innerHTML.match(/data-game-tile=/g) || []).length, 16);
assert.ok(panel.shadowRoot.innerHTML.includes('aria-label="P&#117;lse"'));
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
panel.rows[0].social = { last_activity: { kind: "REST", expression: "SWIM" } };
panel.render();
assert.doesNotMatch(panel.shadowRoot.innerHTML, /data-game-tile=/);
assert.match(panel.shadowRoot.innerHTML, /swimming/);
panel.rows[0].social.last_activity.expression = "AIR_CURRENTS";
assert.equal(panel.status(panel.rows[0]), "riding air currents");
assert.match(panel.morph(panel.rows[0]), /riding air c&#117;rrents/);
panel.render();
assert.match(panel.shadowRoot.innerHTML, /riding air c&#117;rrents/);
panel.place = "SEREIN_GARDENS";
panel.rows[0].place = "SEREIN_GARDENS";
panel.game = null;
panel.rows[0].games = [{ game_id: "resume-1", morph_id: "pulse", game: "MATCHING",
  board: Array(16).fill(null), turn: 1, score: 0, finished: false, rewarded: false }];
panel._hass = { callApi: async (method, route) => route.endsWith("starter-status")
  ? { result: {} } : { result: { morphs: panel.rows } } };
panel.refresh().then(() => {
  assert.equal(panel.game.game_id, "resume-1");
  assert.equal((panel.shadowRoot.innerHTML.match(/data-game-tile=/g) || []).length, 16);
  console.log("Gardens panel smoke PASS");
}).catch(error => { console.error(error.message); process.exitCode = 1; });