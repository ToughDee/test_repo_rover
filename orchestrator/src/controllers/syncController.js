const { performIncrementalSync, updateHashes, removeDeletedHashes } = require('../services/syncService');
const path = require('path');
const fs = require('fs');
const axios = require('axios');

exports.syncRepo = async (req, res) => {
  try {
    const { repoId, sourceUrl, branch } = req.body;

    if (!repoId || !sourceUrl) {
      return res.status(400).json({ error: 'repoId and sourceUrl are required' });
    }

    // TODO: In Phase 4, we'll actually clone/pull from sourceUrl here.
    // For now, assume it's a local folder path just like the Python MVP did.
    const repoRoot = path.resolve(sourceUrl);

    if (!fs.existsSync(repoRoot)) {
      return res.status(404).json({ error: 'Repository path not found', path: repoRoot });
    }

    console.log(`[SYNC] Starting incremental sync for repo: ${repoId} at ${repoRoot}`);

    const diff = await performIncrementalSync(repoId, repoRoot);

    console.log(`[SYNC] Diff results - Added: ${diff.added.length}, Modified: ${diff.modified.length}, Deleted: ${diff.deleted.length}, Unchanged: ${diff.unchanged.length}`);

    const toProcess = [...diff.added, ...diff.modified];

    if (toProcess.length > 0 || diff.deleted.length > 0) {
      console.log(`[SYNC] Sending incremental update to Python worker...`);
      // Tell Python worker which files changed
      // Wait for it to extract ASTs, embed them, and update the Neo4j graph
      const payload = {
        repoId: repoId,
        sourceUrl: sourceUrl,
        branch: branch,
        addedOrModifiedFiles: toProcess.map(f => f.relPath),
        deletedFiles: diff.deleted
      };

      const workerUrl = process.env.PYTHON_WORKER_URL || 'http://localhost:8000';
      
      try {
        await axios.post(`${workerUrl}/ingest`, payload, {
          timeout: 0 // Ingestion might take a long time
        });
        console.log(`[SYNC] Python worker successfully processed files.`);
      } catch (err) {
        console.error(`[SYNC] Python worker failed: ${err.message}`);
        return res.status(500).json({ error: 'Worker ingestion failed', details: err.message });
      }
    }

    // Assuming the worker successfully processes everything:
    if (toProcess.length > 0) {
      await updateHashes(repoId, toProcess);
      console.log(`[SYNC] Updated hashes for ${toProcess.length} files`);
    }

    if (diff.deleted.length > 0) {
      await removeDeletedHashes(repoId, diff.deleted);
      // TODO: Tell python worker to delete these files from Vector DB / Neo4j
      console.log(`[SYNC] Removed hashes for ${diff.deleted.length} deleted files`);
    }

    res.json({
      message: 'Sync complete',
      stats: {
        added: diff.added.length,
        modified: diff.modified.length,
        deleted: diff.deleted.length,
        unchanged: diff.unchanged.length
      }
    });

  } catch (error) {
    console.error('[SYNC ERROR]', error);
    res.status(500).json({ error: 'Internal server error', details: error.message });
  }
};
