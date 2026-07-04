const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const FileHash = require('../models/FileHash');

const EXT_TO_LANG = new Set([
  '.py', '.js', '.jsx', '.ts', '.tsx', '.cpp', '.c', '.go', '.java', '.php', '.rb', '.rs'
]);

const SKIP_DIRS = new Set([
  '.work', '.chroma', 'node_modules', '.git', '.venv', 'dist', 'build'
]);

/**
 * Computes SHA256 hash of a file
 */
function computeFileHash(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

/**
 * Recursively scans directory for supported code files
 */
function getCodeFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      if (!SKIP_DIRS.has(file.toLowerCase())) {
        getCodeFiles(filePath, fileList);
      }
    } else {
      const ext = path.extname(file).toLowerCase();
      if (EXT_TO_LANG.has(ext)) {
        fileList.push(filePath);
      }
    }
  }
  return fileList;
}

/**
 * Performs incremental diffing against MongoDB
 * Returns arrays of file paths that need processing
 */
async function performIncrementalSync(repoId, repoRoot) {
  if (!fs.existsSync(repoRoot)) {
    throw new Error(`Repository root not found: ${repoRoot}`);
  }

  const allFiles = getCodeFiles(repoRoot);
  
  // Fetch existing hashes from MongoDB for this repo
  const existingRecords = await FileHash.find({ repoId });
  const hashDb = new Map();
  for (const record of existingRecords) {
    hashDb.set(record.filePath, record);
  }

  const added = [];
  const modified = [];
  const unchanged = [];
  const currentPaths = new Set();

  for (const absPath of allFiles) {
    const relPath = path.relative(repoRoot, absPath).replace(/\\/g, '/');
    currentPaths.add(relPath);
    
    const currentHash = computeFileHash(absPath);
    const existing = hashDb.get(relPath);

    if (!existing) {
      added.push({ relPath, absPath, hash: currentHash });
    } else if (existing.fileHash !== currentHash) {
      modified.push({ relPath, absPath, hash: currentHash });
    } else {
      unchanged.push(relPath);
    }
  }

  // Find deleted files (exist in DB but not on disk)
  const deleted = [];
  for (const [relPath, record] of hashDb.entries()) {
    if (!currentPaths.has(relPath)) {
      deleted.push(relPath);
    }
  }

  return { added, modified, unchanged, deleted };
}

/**
 * Saves new hashes to DB after a successful sync
 */
async function updateHashes(repoId, successfulFiles) {
  const ops = successfulFiles.map(file => ({
    updateOne: {
      filter: { repoId, filePath: file.relPath },
      update: { $set: { fileHash: file.hash, lastSyncedAt: new Date() } },
      upsert: true
    }
  }));

  if (ops.length > 0) {
    await FileHash.bulkWrite(ops);
  }
}

/**
 * Removes deleted files from DB
 */
async function removeDeletedHashes(repoId, deletedRelPaths) {
  if (deletedRelPaths.length > 0) {
    await FileHash.deleteMany({ repoId, filePath: { $in: deletedRelPaths } });
  }
}

module.exports = {
  performIncrementalSync,
  updateHashes,
  removeDeletedHashes
};
