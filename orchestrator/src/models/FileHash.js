const mongoose = require('mongoose');

const fileHashSchema = new mongoose.Schema({
  repoId: {
    type: String,
    required: true,
    index: true
  },
  filePath: {
    type: String,
    required: true
  },
  fileHash: {
    type: String,
    required: true
  },
  lastSyncedAt: {
    type: Date,
    default: Date.now
  }
});

// Compound index to quickly find a specific file in a repo
fileHashSchema.index({ repoId: 1, filePath: 1 }, { unique: true });

module.exports = mongoose.model('FileHash', fileHashSchema);
