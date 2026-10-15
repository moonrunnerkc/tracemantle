// Deterministic export fixture producer; no agent or model is contacted.
module.exports = class {
  id() { return 'deterministic-error'; }
  async callApi() { return { error: 'Deterministic provider failure for import contract verification' }; }
};
