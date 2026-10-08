// server/routes/b2b.js
// B2B endpoint used by Shopify brands.
// NOTE: the main backend is FastAPI (/app/backend/server.py) and already
// exposes GET /api/b2b/fitting-accuracy/:userId with real logic.
// This Express handler mirrors the dummy contract requested in FASE 2.

const express = require("express");
const router = express.Router();

router.get("/api/b2b/fitting-accuracy/:userId", (req, res) => {
  res.json({
    userId: req.params.userId,
    accuracy: 85,
    last_weight_update: "2026-10-08",
    is_reliable: true,
  });
});

module.exports = router;
