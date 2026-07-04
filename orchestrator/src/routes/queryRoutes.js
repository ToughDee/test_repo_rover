const express = require('express');
const router = express.Router();
const queryController = require('../controllers/queryController');

router.get('/repos', queryController.getRepos);
router.get('/graph/:repoId', queryController.getGraph);
router.post('/query', queryController.queryAgent);

module.exports = router;
